"Load a module using grammar.parsiflage, compiler, and byterun.interpreter."

import ast, sys, types
import compiler, byterun.interpreter, grammar.parsiflage

def load_file(filename, module_name):
    f = open(filename, 'rb')
    t = grammar.parsiflage.parse(f)
    f.close()
    return module_from_ast(module_name, filename, t)

def module_from_ast(module_name, filename, t):
    code = compiler.code_for_module(module_name, filename, t)
    module = types.ModuleType(module_name, ast.get_docstring(t))
    byterun.interpreter.run(code, module.__dict__, None)
    return module

if __name__ == '__main__':
    sys.argv.pop(0)
    load_file(sys.argv[0], '__main__')
