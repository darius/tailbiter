"""A pure-Python Python bytecode interpreter."""
# Derived from Byterun by Ned Batchelder, based on pyvm2 by Paul
# Swartz (z3p), from http://www.twistedmatrix.com/users/z3p/

import builtins, dis, operator, types

class Function:
    __slots__ = [
        '__name__', '__code__', '__globals__', '__defaults__', '__closure__',
        '__dict__', '__doc__',
    ]

    def __init__(self, name, code, globs, defaults, closure):
        self.__name__ = name or code.co_name
        self.__code__ = code
        self.__globals__ = globs
        self.__defaults__ = tuple(defaults)
        self.__closure__ = closure
        self.__dict__ = {}
        self.__doc__ = code.co_consts[0] if code.co_consts else None

    def __repr__(self):         # pragma: no cover
        return '<Function %s at 0x%08x>' % (self.__name__, id(self))

    def __get__(self, instance, owner):
        return self if instance is None else Method(instance, owner, self)

    def __call__(self, *args, **kwargs):
        code      = self.__code__
        argc      = code.co_argcount
        varargs   = 0 != (code.co_flags & 0x04)
        varkws    = 0 != (code.co_flags & 0x08)
        params    = code.co_varnames[slice(0, argc+varargs+varkws)]

        defaults  = self.__defaults__
        nrequired = -len(defaults) if defaults else argc

        f_locals = dict(zip(params[slice(nrequired, None)], defaults))
        f_locals.update(dict(zip(params, args)))
        if varargs:
            f_locals[params[argc]] = args[slice(argc, None)]
        elif argc < len(args):
            raise TypeError("%s() takes up to %d positional argument(s) but got %d"
                            % (self.__name__, argc, len(args)))
        if varkws:
            f_locals[params[-1]] = varkw_dict = {}
        for kw, value in kwargs.items():
            if kw in params:
                f_locals[kw] = value
            elif varkws:
                varkw_dict[kw] = value
            else:
                raise TypeError("%s() got an unexpected keyword argument %r"
                                % (self.__name__, kw))
        missing = [v for v in params[slice(0, nrequired)] if v not in f_locals]
        if missing:
            raise TypeError("%s() missing %d required positional argument%s: %s"
                            % (code.co_name,
                               len(missing), 's' if 1 < len(missing) else '',
                               ', '.join(map(repr, missing))))

        return run_frame(code, self.__closure__, self.__globals__, f_locals)

class Method:
    def __init__(self, obj, _class, func):
        self.__self__ = obj
        self._class = _class
        self.__func__ = func

    def __repr__(self):         # pragma: no cover
        name = "%s.%s" % (self._class.__name__, self.__func__.__name__)
        return '<bound method %s of %s>' % (name, self.__self__)

    def __call__(self, *args, **kwargs):
        return self.__func__(self.__self__, *args, **kwargs)

class Cell:
    def __init__(self, value):
        self.contents = value

class VirtualMachineError(Exception):
    "For raising errors in the operation of the VM."

def run(code, f_globals, f_locals):
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
            byte_name, arguments = self.parse_byte_and_args()
            outcome = self.dispatch(byte_name, arguments)
            if outcome:
                assert outcome == 'return'
                return self.pop()

    def parse_byte_and_args(self):
        code = self.f_code
        opcode = code.co_code[self.f_lasti]
        self.f_lasti = self.f_lasti + 1
        if opcode >= dis.HAVE_ARGUMENT:
            int_arg = (   code.co_code[self.f_lasti]
                       + (code.co_code[self.f_lasti+1] << 8))
            self.f_lasti = self.f_lasti + 2
            if opcode in dis.hasconst:
                arg = code.co_consts[int_arg]
            elif opcode in dis.hasfree:
                if int_arg < len(code.co_cellvars):
                    arg = code.co_cellvars[int_arg]
                else:
                    arg = code.co_freevars[int_arg - len(code.co_cellvars)]
            elif opcode in dis.hasname:
                arg = code.co_names[int_arg]
            elif opcode in dis.haslocal:
                arg = code.co_varnames[int_arg]
            elif opcode in dis.hasjrel:
                arg = self.f_lasti + int_arg
            else:
                arg = int_arg
            return dis.opname[opcode], (arg,)
        return dis.opname[opcode], ()

    def dispatch(self, byte_name, arguments):
        if byte_name.startswith('UNARY_'):
            self.unary_operator(byte_name.replace('UNARY_', '', 1))
        elif byte_name.startswith('BINARY_'):
            self.binary_operator(byte_name.replace('BINARY_', '', 1))
        else:
            return getattr(self, 'byte_%s' % byte_name)(*arguments)

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

    def unary_operator(self, op):
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

    def binary_operator(self, op):
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
        self.push(Function(name, code, self.f_globals, defaults, None))

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
        len_kw, len_pos = divmod(oparg, 256)
        namedargs = dict([self.popn(2) for i in range(len_kw)])
        namedargs.update(kwargs)
        posargs = self.popn(len_pos)
        posargs.extend(varargs)
        func = self.pop()
        self.push(func(*posargs, **namedargs))

    def byte_RETURN_VALUE(self):
        return 'return'

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

    cell = run_frame(func.__code__, func.__closure__,
                     func.__globals__, namespace)

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
