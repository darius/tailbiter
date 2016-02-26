"""A pure-Python Python bytecode interpreter."""
# Derived from Byterun by Ned Batchelder, based on pyvm2 by Paul
# Swartz (z3p), from http://www.twistedmatrix.com/users/z3p/

import builtins, dis, inspect, operator, re, types

def make_cell(value):
    fn = (lambda x: lambda: x)(value)
    return fn.__closure__[0]

class Function:
    __slots__ = [
        'func_code', 'func_name', 'func_defaults', 'func_globals',
        'func_dict', 'func_closure',
        '__name__', '__dict__', '__doc__',
        '_func',
    ]

    def __init__(self, name, code, globs, defaults, closure):
        self.func_code = code
        self.func_name = self.__name__ = name or code.co_name
        self.func_defaults = tuple(defaults)
        self.func_globals = globs
        self.__dict__ = {}
        self.func_closure = closure
        self.__doc__ = code.co_consts[0] if code.co_consts else None

        kw = {'argdefs': self.func_defaults}
        if closure:
            kw['closure'] = tuple([make_cell(0) for _ in closure])
        self._func = types.FunctionType(code, globs, **kw)

    def __repr__(self):         # pragma: no cover
        return '<Function %s at 0x%08x>' % (self.func_name, id(self))

    def __get__(self, instance, owner):
        return self if instance is None else Method(instance, owner, self)

    def __call__(self, *args, **kwargs):
        if re.search(r'<(?:listcomp|setcomp|dictcomp|genexpr)>$', self.func_name):
            assert len(args) == 1 and not kwargs, "Surprising comprehension!"
            callargs = {".0": args[0]}
        else:
            callargs = inspect.getcallargs(self._func, *args, **kwargs)
        return run_frame(self.func_code, self.func_closure,
                         self.func_globals, callargs)

class Method:
    def __init__(self, obj, _class, func):
        self.im_self = obj
        self.im_class = _class
        self.im_func = func

    def __repr__(self):         # pragma: no cover
        name = "%s.%s" % (self.im_class.__name__, self.im_func.func_name)
        return '<Bound Method %s of %s>' % (name, self.im_self)

    def __call__(self, *args, **kwargs):
        if not isinstance(self.im_self, self.im_class):
            raise TypeError(
                'unbound method %s() must be called with %s instance '
                'as first argument (got %s instance instead)'
                % (self.im_func.func_name,
                   self.im_class.__name__,
                   type(self.im_self).__name__))
        return self.im_func(self.im_self, *args, **kwargs)

class Cell:
    def __init__(self, value):
        self.contents = value

class VirtualMachineError(Exception):
    "For raising errors in the operation of the VM."

def vm_exec(code, f_globals, f_locals):
    if f_globals is None: f_globals = builtins.globals()
    if f_locals is None:  f_locals = f_globals
    if '__builtins__' not in f_globals:
        f_globals['__builtins__'] = builtins.__dict__
    return run_frame(code, None, f_globals, f_locals)

def run_frame(code, f_closure, f_globals, f_locals):
    return Frame(code, f_closure, f_globals, f_locals).run()

class Frame:
    def __init__(self, f_code, f_closure, f_globals, f_locals):
        self.f_code = f_code
        self.f_globals = f_globals
        self.f_locals = f_locals

        self.f_builtins = f_globals.get('__builtins__')
        if isinstance(self.f_builtins, types.ModuleType):
            self.f_builtins = self.f_builtins.__dict__
        if self.f_builtins is None:
            self.f_builtins = {'None': None}

        self.stack = []

        self.f_lineno = f_code.co_firstlineno # XXX doesn't get updated
        self.f_lasti = 0

        self.cells = {} if f_code.co_cellvars or f_code.co_freevars else None
        for var in f_code.co_cellvars:
            self.cells[var] = Cell(self.f_locals.get(var))
        if f_code.co_freevars:
            assert len(f_code.co_freevars) == len(f_closure)
            self.cells.update(zip(f_code.co_freevars, f_closure))

    def __repr__(self):         # pragma: no cover
        return ('<Frame at 0x%08x: %r @ %d>'
                % (id(self), self.f_code.co_filename, self.f_lineno))

    def run(self):
        while True:
            byteName, arguments = self.parse_byte_and_args()
            outcome = self.dispatch(byteName, arguments)
            if outcome:
                assert outcome[0] == 'return'
                return outcome[1]

    def parse_byte_and_args(self):
        code = self.f_code
        opcode = code.co_code[self.f_lasti]
        self.f_lasti = self.f_lasti + 1
        if opcode >= dis.HAVE_ARGUMENT:
            intArg = (code.co_code[self.f_lasti]
                      + (code.co_code[self.f_lasti+1] << 8))
            self.f_lasti = self.f_lasti + 2
            if opcode in dis.hasconst:
                arg = code.co_consts[intArg]
            elif opcode in dis.hasfree:
                if intArg < len(code.co_cellvars):
                    arg = code.co_cellvars[intArg]
                else:
                    arg = code.co_freevars[intArg - len(code.co_cellvars)]
            elif opcode in dis.hasname:
                arg = code.co_names[intArg]
            elif opcode in dis.haslocal:
                arg = code.co_varnames[intArg]
            elif opcode in dis.hasjrel:
                arg = self.f_lasti + intArg
            else:
                arg = intArg
            return dis.opname[opcode], (arg,)
        return dis.opname[opcode], ()

    def dispatch(self, byteName, arguments):
        if byteName.startswith('UNARY_'):
            self.unaryOperator(byteName.replace('UNARY_', '', 1))
        elif byteName.startswith('BINARY_'):
            self.binaryOperator(byteName.replace('BINARY_', '', 1))
        else:
            return getattr(self, 'byte_%s' % byteName)(*arguments)

    def top(self):
        return self.stack[-1]

    def push(self, val):
        self.stack.append(val)

    def pop(self):
        return self.stack.pop()

    def popn(self, n):
        vals = [self.stack.pop() for _ in range(n)]
        vals.reverse()
        return vals

    def jump(self, jump):
        self.f_lasti = jump

    def byte_POP_TOP(self):
        self.pop()

    def byte_DUP_TOP(self):
        self.push(self.top())

    def byte_LOAD_CONST(self, const):
        self.push(const)

    def byte_LOAD_GLOBAL(self, name): # XXX not used by the compiler; just for comparison runs
        if   name in self.f_globals:  val = self.f_globals[name]
        elif name in self.f_builtins: val = self.f_builtins[name]
        else: raise NameError("name '%s' is not defined" % name)
        self.push(val)

    def byte_LOAD_NAME(self, name):
        if   name in self.f_locals:   val = self.f_locals[name]
        elif name in self.f_globals:  val = self.f_globals[name]
        elif name in self.f_builtins: val = self.f_builtins[name]
        else: raise NameError("name '%s' is not defined" % name)
        self.push(val)

    def byte_STORE_NAME(self, name):
        self.f_locals[name] = self.pop()

    def byte_LOAD_FAST(self, name):
        if name not in self.f_locals:
            raise UnboundLocalError(
                "local variable '%s' referenced before assignment" % name)
        self.push(self.f_locals[name])

    def byte_STORE_FAST(self, name):
        self.f_locals[name] = self.pop()

    def byte_LOAD_DEREF(self, name):
        self.push(self.cells[name].contents)

    def byte_STORE_DEREF(self, name):
        self.cells[name].contents = self.pop()

    UNARY_OPERATORS = {
        'POSITIVE': operator.pos,   'NOT':    operator.not_,
        'NEGATIVE': operator.neg,   'INVERT': operator.invert,
    }

    def unaryOperator(self, op):
        x = self.pop()
        self.push(self.UNARY_OPERATORS[op](x))

    BINARY_OPERATORS = {
        'POWER':    pow,             'ADD':      operator.add,
        'LSHIFT':   operator.lshift, 'SUBTRACT': operator.sub,
        'RSHIFT':   operator.rshift, 'MULTIPLY': operator.mul,
        'OR':       operator.or_,    'MODULO':   operator.mod,
        'AND':      operator.and_,   'TRUE_DIVIDE': operator.truediv,
        'XOR':      operator.xor,    'FLOOR_DIVIDE': operator.floordiv,
        'SUBSCR':   operator.getitem,
    }

    def binaryOperator(self, op):
        x, y = self.popn(2)
        self.push(self.BINARY_OPERATORS[op](x, y))

    COMPARE_OPERATORS = [
        operator.lt,
        operator.le,
        operator.eq,
        operator.ne,
        operator.gt,
        operator.ge,
        lambda x, y: x in y,
        lambda x, y: x not in y,
        lambda x, y: x is y,
        lambda x, y: x is not y,
        lambda x, y: issubclass(x, Exception) and issubclass(x, y),
    ]

    def byte_COMPARE_OP(self, opnum):
        x, y = self.popn(2)
        self.push(self.COMPARE_OPERATORS[opnum](x, y))

    def byte_LOAD_ATTR(self, attr):
        obj = self.pop()
        val = getattr(obj, attr)
        self.push(val)

    def byte_STORE_ATTR(self, name):
        val, obj = self.popn(2)
        setattr(obj, name, val)

    def byte_STORE_SUBSCR(self):
        val, obj, subscr = self.popn(3)
        obj[subscr] = val

    def byte_BUILD_TUPLE(self, count):
        self.push(tuple(self.popn(count)))

    def byte_BUILD_LIST(self, count):
        self.push(self.popn(count))

    def byte_BUILD_MAP(self, size):
        self.push({})

    def byte_STORE_MAP(self):
        the_map, val, key = self.popn(3)
        the_map[key] = val
        self.push(the_map)

    def byte_UNPACK_SEQUENCE(self, count):
        seq = self.pop()
        for x in reversed(seq):
            self.push(x)

    def byte_LIST_APPEND(self, count):
        val = self.pop()
        self.stack[-count].append(val)

    def byte_JUMP_FORWARD(self, jump):
        self.jump(jump)

    def byte_JUMP_ABSOLUTE(self, jump):
        self.jump(jump)

    def byte_POP_JUMP_IF_TRUE(self, jump): # XXX not emitted by the compiler
        val = self.pop()
        if val:
            self.jump(jump)

    def byte_POP_JUMP_IF_FALSE(self, jump):
        val = self.pop()
        if not val:
            self.jump(jump)

    def byte_JUMP_IF_TRUE_OR_POP(self, jump):
        if self.top():
            self.jump(jump)
        else:
            self.pop()

    def byte_JUMP_IF_FALSE_OR_POP(self, jump):
        if not self.top():
            self.jump(jump)
        else:
            self.pop()

    def byte_SETUP_LOOP(self, dest):
        pass

    def byte_GET_ITER(self):
        self.push(iter(self.pop()))

    def byte_FOR_ITER(self, jump):
        void = object()
        element = next(self.top(), void)
        if element is void:
            self.pop()
            self.jump(jump)
        else:
            self.push(element)

    def byte_POP_BLOCK(self):
        pass

    def byte_RAISE_VARARGS(self, argc):
        assert argc == 1
        raise self.pop()

    def byte_MAKE_FUNCTION(self, argc):
        name = self.pop()
        code = self.pop()
        defaults = self.popn(argc)
        globs = self.f_globals
        self.push(Function(name, code, globs, defaults, None))

    def byte_LOAD_CLOSURE(self, name):
        self.push(self.cells[name])

    def byte_MAKE_CLOSURE(self, argc):
        name = self.pop()
        closure, code = self.popn(2)
        defaults = self.popn(argc)
        globs = self.f_globals
        self.push(Function(name, code, globs, defaults, closure))

    def byte_CALL_FUNCTION(self, arg):
        return self.call_function(arg, [], {})

    def byte_CALL_FUNCTION_VAR(self, arg):
        varargs = self.pop()
        return self.call_function(arg, varargs, {})

    def byte_CALL_FUNCTION_KW(self, arg):
        kwargs = self.pop()
        return self.call_function(arg, [], kwargs)

    def byte_CALL_FUNCTION_VAR_KW(self, arg):
        varargs, kwargs = self.popn(2)
        return self.call_function(arg, varargs, kwargs)

    def call_function(self, oparg, varargs, kwargs):
        lenKw, lenPos = divmod(oparg, 256)
        namedargs = dict([self.popn(2) for i in range(lenKw)])
        namedargs.update(kwargs)
        posargs = self.popn(lenPos)
        posargs.extend(varargs)
        func = self.pop()
        self.push(func(*posargs, **namedargs))

    def byte_RETURN_VALUE(self):
        return 'return', self.pop()

    def byte_IMPORT_NAME(self, name):
        level, fromlist = self.popn(2)
        val = __import__(name, self.f_globals, self.f_locals, fromlist, level)
        self.push(val)

    def byte_IMPORT_FROM(self, name):
        self.push(getattr(self.top(), name))

    def byte_LOAD_BUILD_CLASS(self):
        self.push(build_class)

def build_class(func, name, *bases, **kwds):
    if not isinstance(func, Function):
        raise TypeError("func must be a function")
    if not isinstance(name, str):
        raise TypeError("name is not a string")
    metaclass = kwds.pop('metaclass', None)
    if metaclass is None:
        metaclass = type(bases[0]) if bases else type
    if isinstance(metaclass, type):
        metaclass = calculate_metaclass(metaclass, bases)

    void = object()
    prepare = getattr(metaclass, '__prepare__', void)
    namespace = {} if prepare is void else prepare(name, bases, **kwds)

    cell = run_frame(func.func_code, func.func_closure,
                     func.func_globals, namespace)

    cls = metaclass(name, bases, namespace)
    if isinstance(cell, Cell):
        cell.contents = cls
    return cls

def calculate_metaclass(metaclass, bases):
    winner = metaclass
    for base in bases:
        t = type(base)
        if issubclass(t, winner):
            winner = t
        elif not issubclass(winner, t):
            raise TypeError("metaclass conflict", winner, t)
    return winner
