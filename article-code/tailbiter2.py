import ast, collections, dis, types, sys
from functools import reduce
from itertools import chain
from check_subset import check_conformity

def assemble(assembly):
    return bytes(iter(assembly.encode(0, dict(assembly.resolve(0)))))
def plumb_depths(assembly):
    depths = [0]
    assembly.plumb(depths)
    return max(depths)
def make_lnotab(assembly):
    firstlineno, lnotab = None, []
    byte, line = 0, None
    for next_byte, next_line in assembly.line_nos(0):
        if firstlineno is None:
            firstlineno = line = next_line
        elif line < next_line:
            while byte+255 < next_byte:
                lnotab.extend([255, 0])
                byte = byte+255
            while line+255 < next_line:
                lnotab.extend([next_byte-byte, 255])
                byte, line = next_byte, line+255
            if (byte, line) != (next_byte, next_line):
                lnotab.extend([next_byte-byte, next_line-line])
                byte, line = next_byte, next_line
    return firstlineno or 1, bytes(lnotab)
def concat(assemblies):
    return sum(assemblies, no_op)
class Assembly:
    def __add__(self, other):
        return Chain(self, other)
    length = 0
    def resolve(self, start):
        return ()
    def encode(self, start, addresses):
        return b''
    def line_nos(self, start):
        return ()
    def plumb(self, depths):
        pass

no_op = Assembly()
class Label(Assembly):
    def resolve(self, start):
        return ((self, start),)
class SetLineNo(Assembly):
    def __init__(self, line):
        self.line = line
    def line_nos(self, start):
        return ((start, self.line),)
class Instruction(Assembly):
    def __init__(self, opcode, arg):
        self.opcode = opcode
        self.arg    = arg
        self.length = 1 if arg is None else 3
    def encode(self, start, addresses):
        if   self.opcode in dis.hasjabs: arg = addresses[self.arg]
        elif self.opcode in dis.hasjrel: arg = addresses[self.arg] - (start+3)
        else:                            arg = self.arg
        if arg is None: return bytes([self.opcode])
        else:           return bytes([self.opcode, arg % 256, arg // 256])
    def plumb(self, depths):
        depths.append(depths[-1] + stack_effect(self.opcode, self.arg))
or_pop_ops = (dis.opmap['JUMP_IF_TRUE_OR_POP'],
              dis.opmap['JUMP_IF_FALSE_OR_POP'])

def stack_effect(opcode, oparg):
    if opcode in or_pop_ops:
        return -1
    else:
        if isinstance(oparg, Label): oparg = 0
        return dis.stack_effect(opcode, oparg)
class Chain(Assembly):
    def __init__(self, assembly1, assembly2):
        self.part1 = assembly1
        self.part2 = assembly2
        self.length = assembly1.length + assembly2.length
    def resolve(self, start):
        return chain(self.part1.resolve(start),
                     self.part2.resolve(start + self.part1.length))
    def encode(self, start, addresses):
        return chain(self.part1.encode(start, addresses),
                     self.part2.encode(start + self.part1.length, addresses))
    def line_nos(self, start):
        return chain(self.part1.line_nos(start),
                     self.part2.line_nos(start + self.part1.length))
    def plumb(self, depths):
        self.part1.plumb(depths)
        self.part2.plumb(depths)

def denotation(opcode):
    if opcode < dis.HAVE_ARGUMENT:
        return Instruction(opcode, None)
    else:
        return lambda arg: Instruction(opcode, arg)

op = type('op', (), dict([(name, denotation(opcode))
                          for name, opcode in dis.opmap.items()]))
def make_table():
    table = collections.defaultdict(lambda: len(table))
    return table

def collect(table):
    return tuple(sorted(table, key=table.get))
def run(filename, module_name):
    f = open(filename)
    source = f.read()
    f.close()
    return module_from_ast(module_name, filename, ast.parse(source))

def module_from_ast(module_name, filename, t):
    code = code_for_module(module_name, filename, t)
    module = types.ModuleType(module_name, ast.get_docstring(t))
    exec(code, module.__dict__)
    return module

def code_for_module(module_name, filename, t):
    t = desugar(t)
    check_conformity(t)
    return CodeGen(filename, top_scope(t)).compile_module(t, module_name)

class CodeGen(ast.NodeVisitor):

    def __init__(self, filename, scope):
        self.filename  = filename
        self.scope     = scope
        self.constants = make_table()
        self.names     = make_table()
        self.varnames  = make_table()
    def compile_module(self, t, name):
        assembly = self(t.body) + self.load_const(None) + op.RETURN_VALUE
        return self.make_code(assembly, name, 0)

    def make_code(self, assembly, name, argcount):
        kwonlyargcount = 0
        nlocals = len(self.varnames)
        stacksize = plumb_depths(assembly)
        flags = (  (0x02 if nlocals                  else 0)
                 | (0x10 if self.scope.freevars      else 0)
                 | (0x40 if not self.scope.derefvars else 0))
        firstlineno, lnotab = make_lnotab(assembly)
        return types.CodeType(argcount, kwonlyargcount,
                              nlocals, stacksize, flags, assemble(assembly),
                              self.collect_constants(),
                              collect(self.names), collect(self.varnames),
                              self.filename, name, firstlineno, lnotab,
                              self.scope.freevars, self.scope.cellvars)
    def __call__(self, t):
        if isinstance(t, list): return concat(map(self, t)) 
        assembly = self.visit(t)
        return SetLineNo(t.lineno) + assembly if hasattr(t, 'lineno') else assembly
    def generic_visit(self, t):
        raise NotImplementedError()
    def load_const(self, constant):
        return op.LOAD_CONST(self.constants[constant, type(constant)])

    def collect_constants(self):
        return tuple([constant for constant,_ in collect(self.constants)])
    def visit_NameConstant(self, t): return self.load_const(t.value)
    def visit_Num(self, t):          return self.load_const(t.n)
    def visit_Str(self, t):          return self.load_const(t.s)
    visit_Bytes = visit_Str
    def visit_Name(self, t):
        if   isinstance(t.ctx, ast.Load):  return self.load(t.id)
        elif isinstance(t.ctx, ast.Store): return self.store(t.id)
        else: assert False

    def load(self, name):
        access = self.scope.access(name)
        if   access == 'fast':  return op.LOAD_FAST(self.varnames[name])
        elif access == 'deref': return op.LOAD_DEREF(self.cell_index(name))
        elif access == 'name':  return op.LOAD_NAME(self.names[name])
        else: assert False

    def store(self, name):
        access = self.scope.access(name)
        if   access == 'fast':  return op.STORE_FAST(self.varnames[name])
        elif access == 'deref': return op.STORE_DEREF(self.cell_index(name))
        elif access == 'name':  return op.STORE_NAME(self.names[name])
        else: assert False

    def cell_index(self, name):
        return self.scope.derefvars.index(name)
    def visit_Call(self, t):
        assert len(t.args) < 256 and len(t.keywords) < 256
        return (self(t.func) + self(t.args) + self(t.keywords)
                + op.CALL_FUNCTION((len(t.keywords) << 8) | len(t.args)))

    def visit_keyword(self, t):
        return self.load_const(t.arg) + self(t.value)
    def visit_Expr(self, t):
        return self(t.value) + op.POP_TOP
    def visit_Assign(self, t):
        def compose(left, right): return op.DUP_TOP + left + right
        return self(t.value) + reduce(compose, map(self, t.targets))
    def visit_If(self, t):
        orelse, after = Label(), Label()
        return (           self(t.test) + op.POP_JUMP_IF_FALSE(orelse)
                         + self(t.body) + op.JUMP_FORWARD(after)
                + orelse + self(t.orelse)
                + after)

    visit_IfExp = visit_If
    def visit_Dict(self, t):
        return (op.BUILD_MAP(min(0xFFFF, len(t.keys)))
                + concat([self(v) + self(k) + op.STORE_MAP
                          for k, v in zip(t.keys, t.values)]))
    def visit_Subscript(self, t):
        return self(t.value) + self(t.slice.value) + self.subscr_ops[type(t.ctx)]
    subscr_ops = {ast.Load: op.BINARY_SUBSCR, ast.Store: op.STORE_SUBSCR}

    def visit_Attribute(self, t):
        sub_op = self.attr_ops[type(t.ctx)]
        return self(t.value) + sub_op(self.names[t.attr])
    attr_ops = {ast.Load: op.LOAD_ATTR, ast.Store: op.STORE_ATTR}
    def visit_List(self, t):  return self.visit_sequence(t, op.BUILD_LIST)
    def visit_Tuple(self, t): return self.visit_sequence(t, op.BUILD_TUPLE)

    def visit_sequence(self, t, build_op):
        if   isinstance(t.ctx, ast.Load):
            return self(t.elts) + build_op(len(t.elts))
        elif isinstance(t.ctx, ast.Store):
            return op.UNPACK_SEQUENCE(len(t.elts)) + self(t.elts)
        else:
            assert False
    def visit_UnaryOp(self, t):
        return self(t.operand) + self.ops1[type(t.op)]
    ops1 = {ast.UAdd: op.UNARY_POSITIVE,  ast.Invert: op.UNARY_INVERT,
            ast.USub: op.UNARY_NEGATIVE,  ast.Not:    op.UNARY_NOT}
    def visit_BinOp(self, t):
        return self(t.left) + self(t.right) + self.ops2[type(t.op)]
    ops2 = {ast.Pow:    op.BINARY_POWER,  ast.Add:  op.BINARY_ADD,
            ast.LShift: op.BINARY_LSHIFT, ast.Sub:  op.BINARY_SUBTRACT,
            ast.RShift: op.BINARY_RSHIFT, ast.Mult: op.BINARY_MULTIPLY,
            ast.BitOr:  op.BINARY_OR,     ast.Mod:  op.BINARY_MODULO,
            ast.BitAnd: op.BINARY_AND,    ast.Div:  op.BINARY_TRUE_DIVIDE,
            ast.BitXor: op.BINARY_XOR,    ast.FloorDiv: op.BINARY_FLOOR_DIVIDE}
    def visit_Compare(self, t):
        [operator], [right] = t.ops, t.comparators
        cmp_index = dis.cmp_op.index(self.ops_cmp[type(operator)])
        return self(t.left) + self(right) + op.COMPARE_OP(cmp_index)
    ops_cmp = {ast.Eq: '==', ast.NotEq: '!=', ast.Is: 'is', ast.IsNot: 'is not',
               ast.Lt: '<',  ast.LtE:   '<=', ast.In: 'in', ast.NotIn: 'not in',
               ast.Gt: '>',  ast.GtE:   '>='}
    def visit_BoolOp(self, t):
        op_jump = self.ops_bool[type(t.op)]
        def compose(left, right):
            after = Label()
            return left + op_jump(after) + right + after
        return reduce(compose, map(self, t.values))
    ops_bool = {ast.And: op.JUMP_IF_FALSE_OR_POP,
                ast.Or:  op.JUMP_IF_TRUE_OR_POP}
    def visit_Pass(self, t):
        return no_op

    def visit_Raise(self, t):
        return self(t.exc) + op.RAISE_VARARGS(1)
    def visit_Import(self, t):
        return concat([self.import_name(0, None, alias.name)
                       + self.store(alias.asname or alias.name.split('.')[0])
                       for alias in t.names])

    def visit_ImportFrom(self, t):
        fromlist = tuple([alias.name for alias in t.names])
        return (self.import_name(t.level, fromlist, t.module)
                + concat([op.IMPORT_FROM(self.names[alias.name])
                          + self.store(alias.asname or alias.name)
                         for alias in t.names])
                + op.POP_TOP)

    def import_name(self, level, fromlist, name):
        return (self.load_const(level)
                + self.load_const(fromlist)
                + op.IMPORT_NAME(self.names[name]))
    def visit_While(self, t):
        loop, end, after = Label(), Label(), Label()
        return (         op.SETUP_LOOP(after)
                + loop + self(t.test) + op.POP_JUMP_IF_FALSE(end)
                       + self(t.body) + op.JUMP_ABSOLUTE(loop)
                + end  + op.POP_BLOCK
                + after)

    def visit_For(self, t):
        loop, end, after = Label(), Label(), Label()
        return (         op.SETUP_LOOP(after) + self(t.iter) + op.GET_ITER
                + loop + op.FOR_ITER(end) + self(t.target)
                       + self(t.body) + op.JUMP_ABSOLUTE(loop)
                + end  + op.POP_BLOCK
                + after)
    def visit_Return(self, t):
        return ((self(t.value) if t.value else self.load_const(None))
                + op.RETURN_VALUE)
    def visit_Function(self, t):
        code = self.sprout(t).compile_function(t)
        return self.make_closure(code, t.name)
    def sprout(self, t):
        return CodeGen(self.filename, self.scope.children[t])
    def make_closure(self, code, name):
        if code.co_freevars:
            return (concat([op.LOAD_CLOSURE(self.cell_index(freevar))
                            for freevar in code.co_freevars])
                    + op.BUILD_TUPLE(len(code.co_freevars))
                    + self.load_const(code) + self.load_const(name)
                    + op.MAKE_CLOSURE(0))
        else:
            return (self.load_const(code) + self.load_const(name)
                    + op.MAKE_FUNCTION(0))
    def compile_function(self, t):
        self.load_const(ast.get_docstring(t))
        for arg in t.args.args:
            self.varnames[arg.arg]
        assembly = self(t.body) + self.load_const(None) + op.RETURN_VALUE
        return self.make_code(assembly, t.name, len(t.args.args))
    def visit_ClassDef(self, t):
        code = self.sprout(t).compile_class(t)
        return (op.LOAD_BUILD_CLASS + self.make_closure(code, t.name)
                                    + self.load_const(t.name)
                                    + self(t.bases)
                + op.CALL_FUNCTION(2 + len(t.bases))
                + self.store(t.name))
    def compile_class(self, t):
        docstring = ast.get_docstring(t)
        assembly = (  self.load('__name__')      + self.store('__module__')
                    + self.load_const(t.name)    + self.store('__qualname__')
                    + (no_op if docstring is None else
                       self.load_const(docstring) + self.store('__doc__'))
                    + self(t.body) + self.load_const(None) + op.RETURN_VALUE)
        return self.make_code(assembly, t.name, 0)
def desugar(t):
    return ast.fix_missing_locations(Desugarer().visit(t))

class Desugarer(ast.NodeTransformer):
    def visit_Assert(self, t):
        t = self.generic_visit(t)
        result = ast.If(t.test,
                        [],
                        [ast.Raise(Call(ast.Name('AssertionError', load),
                                        [] if t.msg is None else [t.msg]),
                                   None)])
        return ast.copy_location(result, t)
    def visit_Lambda(self, t):
        t = self.generic_visit(t)
        result = Function('<lambda>', t.args, [ast.Return(t.body)])
        return ast.copy_location(result, t)

    def visit_FunctionDef(self, t):
        t = self.generic_visit(t)
        fn = Function(t.name, t.args, t.body)
        result = ast.Assign([ast.Name(t.name, store)], fn)
        for d in reversed(t.decorator_list):
            result = Call(d, [result])
        return ast.copy_location(result, t)
    def visit_ListComp(self, t):
        t = self.generic_visit(t)
        add_element = ast.Attribute(ast.Name('.elements', load), 'append', load)
        body = ast.Expr(Call(add_element, [t.elt]))
        for loop in reversed(t.generators):
            for test in reversed(loop.ifs):
                body = ast.If(test, [body], [])
            body = ast.For(loop.target, loop.iter, [body], [])
        fn = [body,
              ast.Return(ast.Name('.elements', load))]
        args = ast.arguments([ast.arg('.elements', None)], None, [], None, [], [])
        result = Call(Function('<listcomp>', args, fn),
                      [ast.List([], load)])
        return ast.copy_location(result, t)
class Function(ast.FunctionDef):
    _fields = ('name', 'args', 'body')

load, store = ast.Load(), ast.Store()

def Call(fn, args):
    return ast.Call(fn, args, [], None, None)
def top_scope(t):
    top = Scope(t, ())
    top.visit(t)
    top.analyze(set())
    return top
class Scope(ast.NodeVisitor):
    def __init__(self, t, defs):
        self.t = t
        self.children = {}       # Enclosed sub-scopes
        self.defs = set(defs)    # Variables defined
        self.uses = set()        # Variables referenced

    def visit_ClassDef(self, t):
        self.defs.add(t.name)
        for expr in t.bases: self.visit(expr)
        subscope = Scope(t, ())
        self.children[t] = subscope
        for stmt in t.body: subscope.visit(stmt)

    def visit_Function(self, t):
        subscope = Scope(t, [arg.arg for arg in t.args.args])
        self.children[t] = subscope
        for stmt in t.body: subscope.visit(stmt)

    def visit_Import(self, t):
        for alias in t.names:
            self.defs.add(alias.asname or alias.name.split('.')[0])

    def visit_ImportFrom(self, t):
        for alias in t.names:
            self.defs.add(alias.asname or alias.name)

    def visit_Name(self, t):
        if   isinstance(t.ctx, ast.Load):  self.uses.add(t.id)
        elif isinstance(t.ctx, ast.Store): self.defs.add(t.id)
        else: assert False
    def analyze(self, parent_defs):
        self.local_defs = self.defs if isinstance(self.t, Function) else set()
        for child in self.children.values():
            child.analyze(parent_defs | self.local_defs)
        child_uses = set([var for child in self.children.values()
                              for var in child.freevars])
        uses = self.uses | child_uses
        self.cellvars = tuple(child_uses & self.local_defs)
        self.freevars = tuple(uses & (parent_defs - self.local_defs))
        self.derefvars = self.cellvars + self.freevars
    def access(self, name):
        return ('deref' if name in self.derefvars else
                'fast'  if name in self.local_defs else
                'name')

if __name__ == '__main__':
    sys.argv.pop(0)
    run(sys.argv[0], '__main__')
