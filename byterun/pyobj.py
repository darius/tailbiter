"""Implementations of Python fundamental objects for Byterun."""

import collections, inspect, re, types
import six

def make_cell(value):
    fn = (lambda x: lambda: x)(value)
    return fn.__closure__[0]

class Function(object):
    __slots__ = [
        'func_code', 'func_name', 'func_defaults', 'func_globals',
        'func_dict', 'func_closure',
        '__name__', '__dict__', '__doc__',
        '_vm', '_func',
    ]

    def __init__(self, name, code, globs, defaults, closure, vm):
        self._vm = vm
        self.func_code = code
        self.func_name = self.__name__ = name or code.co_name
        self.func_defaults = tuple(defaults)
        self.func_globals = globs
        self.__dict__ = {}
        self.func_closure = closure
        self.__doc__ = code.co_consts[0] if code.co_consts else None

        kw = {
            'argdefs': self.func_defaults,
        }
        if closure:
            kw['closure'] = tuple(make_cell(0) for _ in closure)
        self._func = types.FunctionType(code, globs, **kw)

    def __repr__(self):         # pragma: no cover
        return '<Function %s at 0x%08x>' % (
            self.func_name, id(self)
        )

    def __get__(self, instance, owner):
        return self if instance is None else Method(instance, owner, self)

    def __call__(self, *args, **kwargs):
        if re.search(r'<(?:listcomp|setcomp|dictcomp|genexpr)>$', self.func_name):
            assert len(args) == 1 and not kwargs, "Surprising comprehension!"
            callargs = {".0": args[0]}
        else:
            callargs = inspect.getcallargs(self._func, *args, **kwargs)
        return self._vm.run_frame(self._vm.make_frame(
            self.func_code, callargs, self.func_globals, {}, self.func_closure
        ))

class Method(object):
    def __init__(self, obj, _class, func):
        self.im_self = obj
        self.im_class = _class
        self.im_func = func

    def __repr__(self):         # pragma: no cover
        name = "%s.%s" % (self.im_class.__name__, self.im_func.func_name)
        if self.im_self is not None:
            return '<Bound Method %s of %s>' % (name, self.im_self)
        else:
            return '<Unbound Method %s>' % (name,)

    def __call__(self, *args, **kwargs):
        if self.im_self is not None:
            if not isinstance(self.im_self, self.im_class):
                raise TypeError(
                    'unbound method %s() must be called with %s instance '
                    'as first argument (got %s instance instead)' % (
                        self.im_func.func_name,
                        self.im_class.__name__,
                        type(self.im_self).__name__,
                    )
                )
            return self.im_func(self.im_self, *args, **kwargs)
        else:
            return self.im_func(*args, **kwargs)

class Cell(object):
    def __init__(self, value):
        self.contents = value

Block = collections.namedtuple("Block", "type, handler, level")
