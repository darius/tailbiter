"""Test exceptions for tailbiter."""

from . import vmtest

class TestExceptions(vmtest.VmTestCase):
    def test_raise_exception(self):
        self.assert_ok("raise Exception('oops')", raises=Exception)

    def test_raise_exception_class(self):
        self.assert_ok("raise ValueError", raises=ValueError)

    def test_local_name_error(self):
        self.assert_ok("""\
            def fn():
                fooey
            fn()
            """, raises=NameError)
