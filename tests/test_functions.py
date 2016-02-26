"""Test functions etc, for Byterun."""

from __future__ import print_function
from . import vmtest

class TestFunctions(vmtest.VmTestCase):
    def XXX_test_functions(self):
        self.assert_ok("""\
            def fn(a, b=17, c="Hello", d=[]):
                d.append(99)
                print(a, b, c, d)
            fn(1)
            fn(2, 3)
            fn(3, c="Bye")
            fn(4, d=["What?"])
            fn(5, "b", "c")
            """)

    def test_recursion(self):
        self.assert_ok("""\
            def fact(n):
                if n <= 1:
                    return 1
                else:
                    return n * fact(n-1)
            f6 = fact(6)
            print(f6)
            assert f6 == 720
            """)

    def test_nested_names(self):
        self.assert_ok("""\
            def one():
                x = 1
                def two():
                    x = 2
                    print(x)
                two()
                print(x)
            one()
            """)

    def test_calling_functions_with_args_kwargs(self):
        self.assert_ok("""\
            def fn(a, b, c, d):
                d.append(99)
                print(a, b, c, d)
            fn(6, *[77, 88, [99]])
            fn(**{'c': 23, 'a': 7, 'b': 42, 'd': [111]})
            fn(6, *[77], **{'c': 23, 'd': [123]})
            """)

    def test_defining_functions_with_args_kwargs(self):
        self.assert_ok("""\
            def fn(*args):
                print("args is %r" % (args,))
            fn(1, 2)
            """)
        self.assert_ok("""\
            def fn(**kwargs):
                print("kwargs is %r" % (kwargs,))
            fn(red=True, blue=False)
            """)
        self.assert_ok("""\
            def fn(*args, **kwargs):
                print("args is %r" % (args,))
                print("kwargs is %r" % (kwargs,))
            fn(1, 2, red=True, blue=False)
            """)
        self.assert_ok("""\
            def fn(x, y, *args, **kwargs):
                print("x is %r, y is %r" % (x, y))
                print("args is %r" % (args,))
                print("kwargs is %r" % (kwargs,))
            fn('a', 'b', 1, 2, red=True, blue=False)
            """)

    def test_defining_functions_with_empty_args_kwargs(self):
        self.assert_ok("""\
            def fn(*args):
                print("args is %r" % (args,))
            fn()
            """)
        self.assert_ok("""\
            def fn(**kwargs):
                print("kwargs is %r" % (kwargs,))
            fn()
            """)
        self.assert_ok("""\
            def fn(*args, **kwargs):
                print("args is %r, kwargs is %r" % (args, kwargs))
            fn()
            """)

    def test_partial(self):
        self.assert_ok("""\
            from _functools import partial

            def f(a,b):
                return a-b

            f7 = partial(f, 7)
            four = f7(3)
            assert four == 4
            """)

    def XXX_test_partial_with_kwargs(self):
        self.assert_ok("""\
            from _functools import partial

            def f(a,b,c=0,d=0):
                return (a,b,c,d)

            f7 = partial(f, b=7, c=1)
            them = f7(10)
            assert them == (10,7,1,0)
            """)

    def test_wraps(self):
        self.assert_ok("""\
            from functools import wraps
            def my_decorator(f):
                dec = wraps(f)
                def wrapper(*args, **kwds):
                    print('Calling decorated function')
                    return f(*args, **kwds)
                wrapper = dec(wrapper)
                return wrapper

            @my_decorator
            def example():
                '''Docstring'''
                return 17

            assert example() == 17
            """)


class TestClosures(vmtest.VmTestCase):
    def test_closures(self):
        self.assert_ok("""\
            def make_adder(x):
                def add(y):
                    return x+y
                return add
            a = make_adder(10)
            print(a(7))
            assert a(7) == 17
            """)

    def test_closures_store_deref(self):
        self.assert_ok("""\
            def make_adder(x):
                z = x+1
                def add(y):
                    return x+y+z
                return add
            a = make_adder(10)
            print(a(7))
            assert a(7) == 28
            """)

    def test_closures_in_loop(self):
        self.assert_ok("""\
            def make_fns(x):
                fns = []
                for i in range(x):
                    fns.append((lambda i: lambda: i)(i))
                return fns
            fns = make_fns(3)
            for f in fns:
                print(f())
            assert (fns[0](), fns[1](), fns[2]()) == (0, 1, 2)
            """)

    def XXX_test_closures_with_defaults(self):
        self.assert_ok("""\
            def make_adder(x, y=13, z=43):
                def add(q, r=11):
                    return x+y+z+q+r
                return add
            a = make_adder(10, 17)
            print(a(7))
            assert a(7) == 88
            """)

    def test_deep_closures(self):
        self.assert_ok("""\
            def f1(a):
                b = 2*a
                def f2(c):
                    d = 2*c
                    def f3(e):
                        f = 2*e
                        def f4(g):
                            h = 2*g
                            return a+b+c+d+e+f+g+h
                        return f4
                    return f3
                return f2
            answer = f1(3)(4)(5)(6)
            print(answer)
            assert answer == 54
            """)

    def test_closure_vars_from_static_parent(self):
        self.assert_ok("""\
            def f(xs):
                return lambda: xs[0]

            def g(h):
                xs = 5
                lambda: xs
                return h()

            assert g(f([42])) == 42
            """)

    def test_scope_analysis_of_varargs(self):
        self.assert_ok("""\
            def f(*xs):
                return lambda: xs[0]
            print(f(137)())
            """)

    def test_scope_analysis_of_varkw(self):
        self.assert_ok("""\
            def f(**kws):
                return lambda: kws['y']
            print(f(y=183)())
            """)

