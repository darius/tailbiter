"""Basic tests for tailbiter."""

from . import vmtest

class TestIt(vmtest.VmTestCase):
    def test_constant(self):
        self.assert_ok("17")

    def test_for_loop(self):
        self.assert_ok("""\
            out = ""
            for i in range(5):
                out = out + str(i)
            print(out)
            """)

    def test_building_stuff(self):
        self.assert_ok("""\
            print((1+1, 2+2, 3+3))
            """)
        self.assert_ok("""\
            print([1+1, 2+2, 3+3])
            """)
        self.assert_ok("""\
            print({1:1+1, 2:2+2, 3:3+3})
            """)

    def test_subscripting(self):
        self.assert_ok("""\
            l = list(range(10))
            print("%s %s %s" % (l[0], l[3], l[9]))
            """)
        self.assert_ok("""\
            l = list(range(10))
            l[5] = 17
            print(l)
            """)

    def test_list_comprehension(self):
        self.assert_ok("""\
            x = [z*z for z in range(5)]
            assert x == [0, 1, 4, 9, 16]
            """)

    def test_unary_operators(self):
        self.assert_ok("""\
            x = 8
            print(-x, ~x, not x)
            """)

    def test_attributes(self):
        self.assert_ok("""\
            l = lambda: 1   # Just to have an object...
            l.foo = 17
            print(hasattr(l, "foo"), l.foo)
            """)

    def test_import(self):
        self.assert_ok("""\
            import math
            print(math.pi, math.e)
            from math import sqrt
            print(sqrt(2))
            """)

    def test_classes(self):
        self.assert_ok("""\
            class Thing(object):
                def __init__(self, x):
                    self.x = x
                def meth(self, y):
                    return self.x * y
            thing1 = Thing(2)
            thing2 = Thing(3)
            print(thing1.x, thing2.x)
            print(thing1.meth(4), thing2.meth(5))
            """)

    def test_calling_methods_wrong(self):
        self.assert_ok("""\
            class Thing(object):
                def __init__(self, x):
                    self.x = x
                def meth(self, y):
                    return self.x * y
            thing1 = Thing(2)
            print(Thing.meth(14))
            """, raises=TypeError)

    def test_calling_subclass_methods(self):
        self.assert_ok("""\
            class Thing(object):
                def foo(self):
                    return 17

            class SubThing(Thing):
                pass

            st = SubThing()
            print(st.foo())
            """)

    def test_subclass_attribute(self):
        self.assert_ok("""\
            class Thing(object):
                def __init__(self):
                    self.foo = 17
            class SubThing(Thing):
                pass
            st = SubThing()
            print(st.foo)
            """)

    def test_subclass_attributes_not_shared(self):
        self.assert_ok("""\
            class Thing(object):
                foo = 17
            class SubThing(Thing):
                foo = 25
            st = SubThing()
            t = Thing()
            assert st.foo == 25
            assert t.foo == 17
            """)

    def test_object_attrs_not_shared_with_class(self):
        self.assert_ok("""\
            class Thing(object):
                pass
            t = Thing()
            t.foo = 1
            Thing.foo""", raises=AttributeError)

    def test_data_descriptors_precede_instance_attributes(self):
        self.assert_ok("""\
            class Foo(object):
                pass
            f = Foo()
            f.des = 3
            class Descr(object):
                def __get__(self, obj, cls):
                    return 2
                def __set__(self, obj, val):
                    raise NotImplementedError
            Foo.des = Descr()
            assert f.des == 2
            """)

    def test_instance_attrs_precede_non_data_descriptors(self):
        self.assert_ok("""\
            class Foo(object):
                pass
            f = Foo()
            f.des = 3
            class Descr(object):
                def __get__(self, obj, cls):
                    return 2
            Foo.des = Descr()
            assert f.des == 3
            """)

    def test_subclass_attributes_dynamic(self):
        self.assert_ok("""\
            class Foo(object):
                pass
            class Bar(Foo):
                pass
            b = Bar()
            Foo.baz = 3
            assert b.baz == 3
            """)

    def test_attribute_access(self):
        self.assert_ok("""\
            class Thing(object):
                z = 17
                def __init__(self):
                    self.x = 23
            t = Thing()
            print(Thing.z)
            print(t.z)
            print(t.x)
            """)

        self.assert_ok("""\
            class Thing(object):
                z = 17
                def __init__(self):
                    self.x = 23
            t = Thing()
            print(t.xyzzy)
            """, raises=AttributeError)

    def test_staticmethods(self):
        self.assert_ok("""\
            class Thing(object):
                @staticmethod
                def smeth(x):
                    print(x)
                @classmethod
                def cmeth(cls, x):
                    print(x)

            Thing.smeth(1492)
            Thing.cmeth(1776)
            """)

    def test_unbound_methods(self):
        self.assert_ok("""\
            class Thing(object):
                def meth(self, x):
                    print(x)
            m = Thing.meth
            m(Thing(), 1815)
            """)

    def test_bound_methods(self):
        self.assert_ok("""\
            class Thing(object):
                def meth(self, x):
                    print(x)
            t = Thing()
            m = t.meth
            m(1815)
            """)

    def test_callback(self):
        self.assert_ok("""\
            def lcase(s):
                return s.lower()
            l = ["xyz", "ABC"]
            l.sort(key=lcase)
            print(l)
            assert l == ["ABC", "xyz"]
            """)

    def test_unpacking(self):
        self.assert_ok("""\
            a, b, c = (1, 2, 3)
            assert a == 1
            assert b == 2
            assert c == 3
            """)

    def test_exec_statement(self):
        self.assert_ok("""\
            g = {}
            exec("a = 11", g, g)
            assert g['a'] == 11
            """)

    def test_jump_if_true_or_pop(self):
        self.assert_ok("""\
            def f(a, b):
                return a or b
            assert f(17, 0) == 17
            assert f(0, 23) == 23
            assert f(0, "") == ""
            """)

    def test_jump_if_false_or_pop(self):
        self.assert_ok("""\
            def f(a, b):
                return not(a and b)
            assert f(17, 0) is True
            assert f(0, 23) is True
            assert f(0, "") is True
            assert f(17, 23) is False
            """)

    def test_pop_jump_if_true(self):
        self.assert_ok("""\
            def f(a):
                if not a:
                    return 'foo'
                else:
                    return 'bar'
            assert f(0) == 'foo'
            assert f(1) == 'bar'
            """)

    def test_decorator(self):
        self.assert_ok("""\
            def verbose(func):
                def _wrapper(a, b):
                    return func(a, b)
                return _wrapper

            @verbose
            def add(x, y):
                return x+y

            add(7, 3)
            """)

    def test_multiple_classes(self):
        # Making classes used to mix together all the class-scoped values
        # across classes.  This test would fail because A.__init__ would be
        # over-written with B.__init__, and A(1, 2, 3) would complain about
        # too many arguments.
        self.assert_ok("""\
            class A(object):
                def __init__(self, a, b, c):
                    self.sum = a + b + c

            class B(object):
                def __init__(self, x):
                    self.x = x

            a = A(1, 2, 3)
            b = B(7)
            print(a.sum)
            print(b.x)
            """)


class TestLoops(vmtest.VmTestCase):
    def test_for(self):
        self.assert_ok("""\
            for i in range(10):
                print(i)
            print("done")
            """)


class TestComparisons(vmtest.VmTestCase):
    def test_in(self):
        self.assert_ok("""\
            assert "x" in "xyz"
            assert "x" not in "abc"
            assert "x" in ("x", "y", "z")
            assert "x" not in ("a", "b", "c")
            """)

    def test_less(self):
        self.assert_ok("""\
            assert 1 < 3
            assert 1 <= 2 and 1 <= 1
            assert "a" < "b"
            assert "a" <= "b" and "a" <= "a"
            """)

    def test_greater(self):
        self.assert_ok("""\
            assert 3 > 1
            assert 3 >= 1 and 3 >= 3
            assert "z" > "a"
            assert "z" >= "a" and "z" >= "z"
            """)
