import ast, collections, dis, types, sys
from functools import reduce
from itertools import chain
from check_subset import check_conformity

def Instruction(opcode, arg):
    return bytes([opcode] if arg is None else [opcode, arg % 256, arg // 256])

def concat(assemblies):     return b''.join(assemblies)
def SetLineNo(lineno):      return b''
def make_lnotab(assembly):  return 1, b''
def plumb_depths(assembly): return 10
def assemble(assembly):     return assembly

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
    return CodeGen(filename, StubScope()).compile_module(t, module_name)

class StubScope: freevars, cellvars, derefvars = (), (), ()

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

    def load(self, name):  return op.LOAD_NAME(self.names[name])
    def store(self, name): return op.STORE_NAME(self.names[name])
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

if __name__ == '__main__':
    sys.argv.pop(0)
    run(sys.argv[0], '__main__')
