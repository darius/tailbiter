"""
Load a module using metacircular versions of both compiler and
byterun.interpreter.
"""

import ast, sys, types
import compiler, byterun.interpreter

def read_file(filename):
    f = open(filename)
    text = f.read()
    f.close()
    return text

class Loader:
    def __init__(self, piler, terp):
        self.compiler = piler
        self.interpreter = terp

    def load_file(self, filename, module_name):
        source = read_file(filename)
        return self.module_from_ast(module_name, filename, ast.parse(source))

    def module_from_ast(self, module_name, filename, t):
        code = self.compiler.code_for_module(module_name, filename, t)
        module = types.ModuleType(module_name, ast.get_docstring(t))
        self.interpreter.run(code, module.__dict__, None)
        return module

base_loader = Loader(compiler, byterun.interpreter)

meta_compiler    = base_loader.load_file('compiler.py', 'compiler')
meta_interpreter = base_loader.load_file('byterun/interpreter.py', 'interpreter')

meta_loader = Loader(meta_compiler, meta_interpreter)

if __name__ == '__main__':
    sys.argv.pop(0)
    meta_loader.load_file(sys.argv[0], '__main__')
