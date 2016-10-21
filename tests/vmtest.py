"""Testing tools for byterun."""

import ast, dis, io, sys, textwrap, types, unittest

from byterun.interpreter import run, VirtualMachineError
import compiler

# Make this false if you need to run the debugger inside a test.
CAPTURE_STDOUT = ('-s' not in sys.argv)
# Make this false to see the traceback from a failure inside interpreter.
CAPTURE_EXCEPTION = 1


def dis_code(code):
    """Disassemble `code` and all the code it refers to."""
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            dis_code(const)

    print("")
    print(code)
    dis.dis(code)


class VmTestCase(unittest.TestCase):

    def assert_ok(self, source_code, raises=None):
        """Run `code` in our VM and in real Python: they behave the same."""

        source_code = textwrap.dedent(source_code)
        filename = "<%s>" % self.id()

        ref_code = compile(source_code, filename, "exec", 0, 1)

        # Print the disassembly so we'll see it if the test fails.
        if 0: dis_code(ref_code)

        # Run the code through our VM and the real Python interpreter, for comparison.
        vm_value, vm_exc, vm_stdout = self.run_in_vm(ref_code)
        py_value, py_exc, py_stdout = self.run_in_real_python(ref_code)

        self.assert_same_exception(vm_exc, py_exc)
        self.assertEqual(vm_stdout.getvalue(), py_stdout.getvalue())
        self.assertEqual(vm_value, py_value)
        if raises:
            self.assertIsInstance(vm_exc, raises)
        else:
            self.assertIsNone(vm_exc)

        # Same thing for tailbiter-compiled code run in byterun.
        tb_code = compiler.code_for_module(filename, filename, ast.parse(source_code))

        if ref_code.co_stacksize != tb_code.co_stacksize:
            print("Different stacksize: ref %d, tb %d" % (ref_code.co_stacksize,
                                                          tb_code.co_stacksize))
            print(source_code)
            self.assertTrue(False)

        if 0: dis_code(tb_code)

        tb_value, tb_exc, tb_stdout = self.run_in_vm(tb_code)

        self.assert_same_exception(tb_exc, py_exc)
        self.assertEqual(tb_stdout.getvalue(), py_stdout.getvalue())
        self.assertEqual(tb_value, py_value)
        if raises:
            self.assertIsInstance(tb_exc, raises)
        else:
            self.assertIsNone(tb_exc)

        # And the same again but with the compiler also running in the vm.
        both_code = self.run_compiler_in_vm(source_code)
        
        both_value, both_exc, both_stdout = self.run_in_vm(ref_code)

        self.assert_same_exception(both_exc, py_exc)
        self.assertEqual(both_stdout.getvalue(), py_stdout.getvalue())
        self.assertEqual(both_value, py_value)
        if raises:
            self.assertIsInstance(both_exc, raises)
        else:
            self.assertIsNone(both_exc)

    def run_compiler_in_vm(self, source_code):
        "Run tailbiter on vm, compiling source_code."
        source_code = textwrap.dedent(source_code)
        source_ast = ast.parse(source_code)
        module_name = filename = "<%s>" % self.id()

        # 1. Make a compiler2 module, which is compiler compiled by itself
        #    with the resulting code run in vm.
        compiler2 = self.get_meta_compiler()

        # 2. Compile source_code by running compiler2 in the vm.
        return compiler2.code_for_module(module_name, filename, source_ast)

    def get_meta_compiler(self):
        if not hasattr(VmTestCase, 'meta_compiler'):
            with open('compiler.py') as f: # XXX needs the right pwd
                compiler_source = f.read()
            compiler_ast = ast.parse(compiler_source)
            compiler_code = compiler.code_for_module('compiler',
                                                     'compiler.py',
                                                     compiler_ast)
            VmTestCase.meta_compiler = types.ModuleType('compiler2')
            run(compiler_code, VmTestCase.meta_compiler.__dict__, None)
        return VmTestCase.meta_compiler

    def run_in_vm(self, code):
        real_stdout = sys.stdout

        # Run the code through our VM.

        vm_stdout = io.StringIO()
        if CAPTURE_STDOUT:              # pragma: no branch
            sys.stdout = vm_stdout

        vm_value = vm_exc = None
        try:
            vm_value = run(code, None, None)
        except VirtualMachineError:         # pragma: no cover
            # If the VM code raises an error, show it.
            raise
        except AssertionError:              # pragma: no cover
            # If test code fails an assert, show it.
            raise
        except Exception as e:
            # Otherwise, keep the exception for comparison later.
            if not CAPTURE_EXCEPTION:       # pragma: no cover
                raise
            vm_exc = e
        finally:
            sys.stdout = real_stdout
            real_stdout.write("-- stdout ----------\n")
            real_stdout.write(vm_stdout.getvalue())

        return vm_value, vm_exc, vm_stdout

    def run_in_real_python(self, code):
        real_stdout = sys.stdout

        py_stdout = io.StringIO()
        sys.stdout = py_stdout

        py_value = py_exc = None
        globs = {
            '__builtins__': __builtins__,
            '__name__': '__main__',
            '__doc__': None,
            '__package__': None,
        }

        try:
            py_value = eval(code, globs, globs)
        except AssertionError:              # pragma: no cover
            raise
        except Exception as e:
            py_exc = e
        finally:
            sys.stdout = real_stdout

        return py_value, py_exc, py_stdout

    def assert_same_exception(self, e1, e2):
        """Exceptions don't implement __eq__, check it ourselves."""
        self.assertEqual(str(e1), str(e2))
        self.assertIs(type(e1), type(e2))
