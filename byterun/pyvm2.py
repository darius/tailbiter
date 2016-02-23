"""A pure-Python Python bytecode interpreter."""
# Derived from Byterun by Ned Batchelder, based on pyvm2 by Paul
# Swartz (z3p), from http://www.twistedmatrix.com/users/z3p/

import dis, linecache, logging, operator

import six
from six.moves import reprlib

from .pyobj import Block, Function, Cell

log = logging.getLogger(__name__)

# Create a repr that won't overflow.
repr_obj = reprlib.Repr()
repr_obj.maxother = 120
repper = repr_obj.repr

class VirtualMachineError(Exception):
    """For raising errors in the operation of the VM."""

class VirtualMachine(object):
    def __init__(self):
        self.frames = []
        self.frame = None

    def make_frame(self, code, callargs={},
                   f_globals=None, f_locals=None, f_closure=None):
        log.info("make_frame: code=%r, callargs=%s" % (code, repper(callargs)))
        if f_globals is not None:
            if f_locals is None:
                f_locals = f_globals
        elif self.frames:
            f_globals = self.frame.f_globals
            f_locals = {}
        else:
            f_globals = f_locals = {
                '__builtins__': __builtins__,
                '__name__': '__main__',
                '__doc__': None,
                '__package__': None,
            }
        f_locals.update(callargs)
        return Frame(code, f_globals, f_locals, f_closure, self)

    def push_frame(self, frame):
        self.frames.append(frame)
        self.frame = frame

    def pop_frame(self):
        self.frames.pop()
        self.frame = self.frames[-1] if self.frames else None

    def print_frames(self):
        """Print the call stack, for debugging."""
        for f in self.frames:
            filename = f.f_code.co_filename
            lineno = f.line_number()
            print('  File "%s", line %d, in %s' % (
                filename, lineno, f.f_code.co_name
            ))
            linecache.checkcache(filename)
            line = linecache.getline(filename, lineno, f.f_globals)
            if line:
                print('    ' + line.strip())

    def run_code(self, code, f_globals=None, f_locals=None):
        frame = self.make_frame(code, f_globals=f_globals, f_locals=f_locals)
        val = self.run_frame(frame)
        if self.frames:            # pragma: no cover
            raise VirtualMachineError("Frames left over!")
        if self.frame and self.frame.stack:             # pragma: no cover
            raise VirtualMachineError("Data left on stack! %r" % self.frame.stack)
        return val

    def run_frame(self, frame):
        self.push_frame(frame)
        outcome = frame.run()
        self.pop_frame()
        assert outcome[0] == 'return'
        return outcome[1]

class Frame(object):
    def __init__(self, f_code, f_globals, f_locals, f_closure, vm):
        self.f_code = f_code
        self.f_globals = f_globals
        self.f_locals = f_locals
        self.stack = []
        self.vm = vm
        f_back = vm.frame
        if f_back:
            self.f_builtins = f_back.f_builtins
        else:
            self.f_builtins = f_globals['__builtins__'] # XXX was f_locals. what's right?
            if hasattr(self.f_builtins, '__dict__'):
                self.f_builtins = self.f_builtins.__dict__

        self.f_lineno = f_code.co_firstlineno
        self.f_lasti = 0

        self.cells = {} if f_code.co_cellvars or f_code.co_freevars else None
        for var in f_code.co_cellvars:
            self.cells[var] = Cell(self.f_locals.get(var))
        if f_code.co_freevars:
            assert len(f_code.co_freevars) == len(f_closure)
            self.cells.update(zip(f_code.co_freevars, f_closure))

        self.block_stack = []

    def __repr__(self):         # pragma: no cover
        return '<Frame at 0x%08x: %r @ %d>' % (
            id(self), self.f_code.co_filename, self.f_lineno
        )

    def line_number(self):
        """Get the current line number the frame is executing."""
        lnotab = self.f_code.co_lnotab
        byte_increments = six.iterbytes(lnotab[0::2])
        line_increments = six.iterbytes(lnotab[1::2])

        byte_num = 0
        line_num = self.f_code.co_firstlineno

        for byte_incr, line_incr in zip(byte_increments, line_increments):
            byte_num += byte_incr
            if byte_num > self.f_lasti:
                break
            line_num += line_incr

        return line_num

    def run(self):
        while True:
            byteName, arguments, opoffset = self.parse_byte_and_args()
            if log.isEnabledFor(logging.INFO):
                self.log(byteName, arguments, opoffset)
            outcome = self.dispatch(byteName, arguments)
            if outcome:
                return outcome

    def parse_byte_and_args(self):
        f = self
        opoffset = f.f_lasti
        byteCode = f.f_code.co_code[opoffset]
        f.f_lasti += 1
        byteName = dis.opname[byteCode]
        arg = None
        arguments = []
        if byteCode >= dis.HAVE_ARGUMENT:
            arg = f.f_code.co_code[f.f_lasti:f.f_lasti+2]
            f.f_lasti += 2
            intArg = arg[0] + (arg[1] << 8)
            if byteCode in dis.hasconst:
                arg = f.f_code.co_consts[intArg]
            elif byteCode in dis.hasfree:
                if intArg < len(f.f_code.co_cellvars):
                    arg = f.f_code.co_cellvars[intArg]
                else:
                    var_idx = intArg - len(f.f_code.co_cellvars)
                    arg = f.f_code.co_freevars[var_idx]
            elif byteCode in dis.hasname:
                arg = f.f_code.co_names[intArg]
            elif byteCode in dis.hasjrel:
                arg = f.f_lasti + intArg
            elif byteCode in dis.hasjabs:
                arg = intArg
            elif byteCode in dis.haslocal:
                arg = f.f_code.co_varnames[intArg]
            else:
                arg = intArg
            arguments = [arg]

        return byteName, arguments, opoffset

    def log(self, byteName, arguments, opoffset):
        op = "%d: %s" % (opoffset, byteName)
        if arguments:
            op += " %r" % (arguments[0],)
        indent = ""  # XXX "    "*(len(self.frames)-1)
        stack_rep = repper(self.stack)
        block_stack_rep = repper(self.block_stack)

        log.info("  %sdata: %s" % (indent, stack_rep))
        log.info("  %sblks: %s" % (indent, block_stack_rep))
        log.info("%s%s" % (indent, op))

    def dispatch(self, byteName, arguments):
        if byteName.startswith('UNARY_'):
            self.unaryOperator(byteName[6:])
        elif byteName.startswith('BINARY_'):
            self.binaryOperator(byteName[7:])
        elif byteName.startswith('INPLACE_'):
            self.inplaceOperator(byteName[8:])
        elif 'SLICE+' in byteName:
            self.sliceOperator(byteName)
        else:
            bytecode_fn = getattr(self, 'byte_%s' % byteName, None)
            return bytecode_fn(*arguments)

    def top(self):
        return self.stack[-1]

    def pop(self, i=0):
        return self.stack.pop(-1-i)

    def push(self, *vals):
        self.stack.extend(vals)

    def popn(self, n):
        if n:
            ret = self.stack[-n:]
            self.stack[-n:] = []
            return ret
        else:
            return []

    def peek(self, n):
        return self.stack[-n]

    def jump(self, jump):
        self.f_lasti = jump

    def push_block(self, type, handler=None, level=None):
        if level is None:
            level = len(self.stack)
        self.block_stack.append(Block(type, handler, level))

    def pop_block(self):
        return self.block_stack.pop()

    def byte_LOAD_CONST(self, const):
        self.push(const)

    def byte_POP_TOP(self):
        self.pop()

    def byte_DUP_TOP(self):
        self.push(self.top())

    def byte_LOAD_NAME(self, name):
        frame = self
        if name in frame.f_locals:
            val = frame.f_locals[name]
        elif name in frame.f_globals:
            val = frame.f_globals[name]
        elif name in frame.f_builtins:
            val = frame.f_builtins[name]
        else:
            raise NameError("name '%s' is not defined" % name)
        self.push(val)

    def byte_STORE_NAME(self, name):
        self.f_locals[name] = self.pop()

    def byte_LOAD_FAST(self, name):
        if name not in self.f_locals:
            raise UnboundLocalError(
                "local variable '%s' referenced before assignment" % name
            )
        self.push(self.f_locals[name])

    def byte_STORE_FAST(self, name):
        self.f_locals[name] = self.pop()

    def byte_LOAD_GLOBAL(self, name): # XXX not used by the compiler; just for comparison runs
        f = self
        if name in f.f_globals:
            val = f.f_globals[name]
        elif name in f.f_builtins:
            val = f.f_builtins[name]
        else:
            raise NameError("name '%s' is not defined" % name)
        self.push(val)

    def byte_LOAD_DEREF(self, name):
        self.push(self.cells[name].contents)

    def byte_STORE_DEREF(self, name):
        self.cells[name].contents = self.pop()

    def byte_LOAD_LOCALS(self):
        self.push(self.f_locals)

    UNARY_OPERATORS = {
        'POSITIVE': operator.pos,
        'NEGATIVE': operator.neg,
        'NOT':      operator.not_,
        'CONVERT':  repr,
        'INVERT':   operator.invert,
    }

    def unaryOperator(self, op):
        x = self.pop()
        self.push(self.UNARY_OPERATORS[op](x))

    BINARY_OPERATORS = {
        'POWER':    pow,
        'MULTIPLY': operator.mul,
        'FLOOR_DIVIDE': operator.floordiv,
        'TRUE_DIVIDE':  operator.truediv,
        'MODULO':   operator.mod,
        'ADD':      operator.add,
        'SUBTRACT': operator.sub,
        'SUBSCR':   operator.getitem,
        'LSHIFT':   operator.lshift,
        'RSHIFT':   operator.rshift,
        'AND':      operator.and_,
        'XOR':      operator.xor,
        'OR':       operator.or_,
    }

    def binaryOperator(self, op):
        x, y = self.popn(2)
        self.push(self.BINARY_OPERATORS[op](x, y))

    def sliceOperator(self, op):
        start = 0
        end = None          # we will take this to mean end
        op, count = op[:-2], int(op[-1])
        if count == 1:
            start = self.pop()
        elif count == 2:
            end = self.pop()
        elif count == 3:
            end = self.pop()
            start = self.pop()
        l = self.pop()
        if end is None:
            end = len(l)
        if op.startswith('STORE_'):
            l[start:end] = self.pop()
        else:
            self.push(l[start:end])

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
        elts = self.popn(count)
        self.push(tuple(elts))

    def byte_BUILD_LIST(self, count):
        elts = self.popn(count)
        self.push(elts)

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

    def byte_BUILD_SLICE(self, count):
        if count == 2:
            x, y = self.popn(2)
            self.push(slice(x, y))
        elif count == 3:
            x, y, z = self.popn(3)
            self.push(slice(x, y, z))
        else:           # pragma: no cover
            raise VirtualMachineError("Strange BUILD_SLICE count: %r" % count)

    def byte_LIST_APPEND(self, count):
        val = self.pop()
        the_list = self.peek(count)
        the_list.append(val)

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
        self.push_block('loop', dest)

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
        self.pop_block()

    def byte_RAISE_VARARGS(self, argc):
        assert argc == 1
        raise self.pop()

    def byte_MAKE_FUNCTION(self, argc):
        name = self.pop()
        code = self.pop()
        defaults = self.popn(argc)
        globs = self.f_globals
        self.push(Function(name, code, globs, defaults, None, self.vm))

    def byte_LOAD_CLOSURE(self, name):
        self.push(self.cells[name])

    def byte_MAKE_CLOSURE(self, argc):
        name = self.pop()
        closure, code = self.popn(2)
        defaults = self.popn(argc)
        globs = self.f_globals
        self.push(Function(name, code, globs, defaults, closure, self.vm))

    def byte_CALL_FUNCTION(self, arg):
        return self.call_function(arg, [], {})

    def byte_CALL_FUNCTION_VAR(self, arg):
        args = self.pop()
        return self.call_function(arg, args, {})

    def byte_CALL_FUNCTION_KW(self, arg):
        kwargs = self.pop()
        return self.call_function(arg, [], kwargs)

    def byte_CALL_FUNCTION_VAR_KW(self, arg):
        args, kwargs = self.popn(2)
        return self.call_function(arg, args, kwargs)

    def call_function(self, arg, args, kwargs):
        lenKw, lenPos = divmod(arg, 256)
        namedargs = dict(self.popn(2) for i in range(lenKw))
        namedargs.update(kwargs)
        posargs = self.popn(lenPos)
        posargs.extend(args)
        func = self.pop()
        self.push(func(*posargs, **namedargs))

    def byte_RETURN_VALUE(self):
        return 'return', self.pop()

    def byte_IMPORT_NAME(self, name):
        level, fromlist = self.popn(2)
        frame = self
        self.push(
            __import__(name, frame.f_globals, frame.f_locals, fromlist, level)
        )

    def byte_IMPORT_FROM(self, name):
        self.push(getattr(self.top(), name))

    def byte_LOAD_BUILD_CLASS(self):
        self.push(build_class)

def build_class(func, name, *bases, metaclass=None, **kwds):
    if not isinstance(func, Function):
        raise TypeError("func must be a function")
    if not isinstance(name, str):
        raise TypeError("name is not a string")
    if metaclass is None:
        metaclass = type(bases[0]) if bases else type
    if isinstance(metaclass, type):
        metaclass = calculate_metaclass(metaclass, bases)

    try:
        prepare = metaclass.__prepare__
    except AttributeError:
        namespace = {}
    else:
        namespace = prepare(name, bases, **kwds)

    frame = func._vm.make_frame(func.func_code,
                                f_globals=func.func_globals,
                                f_locals=namespace,
                                f_closure=func.func_closure)
    cell = func._vm.run_frame(frame)

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
