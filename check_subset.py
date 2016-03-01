"""
Check if a program conforms to our Python subset.
XXX check that names are legal Python identifiers, since our
    bytecompile assumes it can add illegal ones without clashing
"""

import ast

def check_conformity(t):
    Checker().visit(t)

class Checker(ast.NodeVisitor):

    def __init__(self, scope_type='module', in_loop=False):
        self.scope_type = scope_type
        self.in_loop = in_loop

    def generic_visit(self, t):
        "Any node type we don't know about is an error."
        assert False, "Unsupported syntax: %r" % (t,)

    def __call__(self, t):
        if isinstance(t, list):
            for child in t:
                self.visit(child)
        elif isinstance(t, ast.AST):
            self.visit(t)
        else:
            assert False, "Unexpected type: %r" % (t,)

    def visit_Module(self, t):
        assert self.scope_type == 'module', "Module inside %s" % self.scope_type
        self(t.body)

    def visit_Function(self, t):
        self.check_arguments(t.args)
        Checker('function', in_loop=False)(t.body)

    def visit_ClassDef(self, t):
        assert self.scope_type == 'module', ("Nested classes are not supported %r"
                                             % (t,))
        self.check_identifier(t.name)
        self(t.bases)
        assert not t.keywords
        assert not t.starargs
        assert not t.kwargs
        assert not t.decorator_list
        Checker('class', in_loop=False)(t.body)

    def visit_Return(self, t):
        if t.value is not None:
            self(t.value)

    def visit_Assign(self, t):
        assert t.targets, "At least one target required: %r" % (t,)
        self(t.targets)
        self(t.value)

    def visit_For(self, t):
        self(t.target)
        self(t.iter)
        Checker(self.scope_type, in_loop=True)(t.body)
        assert not t.orelse

    def visit_While(self, t):
        self(t.test)
        Checker(self.scope_type, in_loop=True)(t.body)
        assert not t.orelse

    def visit_If(self, t):
        self(t.test)
        self(t.body)
        self(t.orelse)

    def visit_Raise(self, t):
        self(t.exc)
        assert not t.cause, "Cause argument not supported: %r" % (t,)

    def visit_Import(self, t):
        self(t.names)

    def visit_ImportFrom(self, t):
        self.check_identifier(t.module)
        self(t.names)

    def visit_alias(self, t):
        assert t.name != '*', "Star import not supported: %r" % (t,)
        self.check_identifier(t.name)
        if t.asname is not None: 
            self.check_identifier(t.asname)

    def visit_Expr(self, t):
        self(t.value)

    def visit_Pass(self, t):
        pass

    def visit_Break(self, t):
        assert False, "break not supported"

    def visit_BoolOp(self, t):
        assert type(t.op) in self.ops_bool, "Unsupported boolean op: %r" % (t,)
        self(t.values)
    ops_bool = {ast.And, ast.Or}

    def visit_BinOp(self, t):
        assert type(t.op) in self.ops2, "Unsupported binary op: %r" % (t,)
        self(t.left)
        self(t.right)
    ops2 = {ast.Pow,       ast.Add,
            ast.LShift,    ast.Sub,
            ast.RShift,    ast.Mult,
            ast.BitOr,     ast.Mod,
            ast.BitAnd,    ast.Div,
            ast.BitXor,    ast.FloorDiv}

    def visit_UnaryOp(self, t):
        assert type(t.op) in self.ops1, "Unsupported unary op: %r" % (t,)
        self(t.operand)
    ops1 = {ast.UAdd,  ast.Invert,
            ast.USub,  ast.Not}

    visit_IfExp = visit_If

    def visit_Dict(self, t):
        for k, v in zip(t.keys, t.values):
            self(v)
            self(k)

    def visit_Set(self, t):
        assert False, "Set constructor not supported: %r" % (t,)

    def visit_Compare(self, t):
        self(t.left)
        assert 1 == len(t.ops), "Complex comparisons not supported: %r" % (t,)
        assert type(t.ops[0]) in self.ops_cmp, "Unsupported compare op: %r" % (t,)
        assert len(t.ops) == len(t.comparators), "Wrong number of arguments: %r" % (t,)
        self(t.comparators[0])
    ops_cmp = {ast.Eq,  ast.NotEq,  ast.Is,  ast.IsNot,
               ast.Lt,  ast.LtE,    ast.In,  ast.NotIn,
               ast.Gt,  ast.GtE}

    def visit_Call(self, t):
        self(t.func)
        self(t.args)
        self(t.keywords)
        if t.starargs: self(t.starargs)
        if t.kwargs:   self(t.kwargs)

    def visit_keyword(self, t):
        self.check_identifier(t.arg)
        self(t.value)

    def visit_Num(self, t):
        # -0.0 is distinct from +0.0, but my compiler would mistakenly
        # coalesce the two, if both appear among the constants. Likewise
        # for -0.0 as a component of a complex number. As a hack, instead
        # of handling this case correctly in the compiler, we just forbid
        # it. It's especially unlikely to crop up because the parser even
        # parses -0.0 as UnaryOp(op=USub(), operand=Num(0.0)) -- you'd
        # have to build the AST some other way, to get Num(-0.0).
        assert not has_negzero(t.n), "Negative-zero literals not supported: %r" % (t,)

    def visit_Str(self, t):
        pass

    visit_Bytes = visit_Str

    def visit_Attribute(self, t):
        self(t.value)
        self.check_identifier(t.attr)
        if   isinstance(t.ctx, ast.Load):  pass
        elif isinstance(t.ctx, ast.Store): pass
        else: assert False, "Only loads and stores are supported: %r" % (t,)

    def visit_Subscript(self, t):
        self(t.value)
        if isinstance(t.slice, ast.Index):
            if   isinstance(t.ctx, ast.Load):  pass
            elif isinstance(t.ctx, ast.Store): pass
            else: assert False, "Only loads and stores are supported: %r" % (t,)
            self(t.slice.value)
        else:
            assert False, "Only simple subscripts are supported: %r" % (t,)

    def visit_NameConstant(self, t):
        pass

    def visit_Name(self, t):
        self.check_identifier(t.id)
        if   isinstance(t.ctx, ast.Load):  pass
        elif isinstance(t.ctx, ast.Store): pass
        else: assert False, "Only loads and stores are supported: %r" % (t,)

    def visit_sequence(self, t):
        self(t.elts)
        # XXX make sure there are no stars in elts
        if   isinstance(t.ctx, ast.Load):  pass
        elif isinstance(t.ctx, ast.Store): pass
        else: assert False, "Only loads and stores are supported: %r" % (t,)

    visit_List = visit_sequence
    visit_Tuple = visit_sequence

    def check_arguments(self, args):
        for arg in args.args: self.check_arg(arg)
        if args.vararg: self.check_arg(args.vararg)
        assert not args.kwonlyargs, "Keyword-only args are not supported: %r" % (args,)
        if args.kwarg: self.check_arg(args.kwarg)
        assert not args.defaults, "Default values are not supported: %r" % (args,)
        assert not args.kw_defaults, "Keyword default values are not supported: %r" % (args,)

    def check_arg(self, arg):
        self.check_identifier(arg.arg)

    def check_identifier(self, name):
        assert isinstance(name, str), "An identifier must be a string: %r" % (name,)
        # Not a private, mangled name:
        # XXX also make sure there's no '.' inside (the compiler will add some sometimes)
        assert len(name) <= 2 or not name.startswith('__') or name.endswith('__'), \
            "Mangled private names are not supported: %r" % (name,)

def has_negzero(num):
    return (is_negzero(num)
            or (isinstance(num, complex)
                and (is_negzero(num.real) or is_negzero(num.imag))))

def is_negzero(num):
    return str(num) == '-0.0'
