"""
Let's work out some basic parsing of some productions from the Python grammar.
Start from a py3 port of parts of Parson, adapted to work on tokens
from `tokenize`.
"""

import sys
import ast
import token as T
from tokenize import tokenize

# First an annoying necessary hack. Certain of the AST types (the
# 'simple' ones) do not carry source-position attributes: the
# constructors silently drop them. (If this is documented, I missed
# it. I suppose the reason is efficiency; but this position info needs
# to live *somewhere*, and the AST node is its natural home.) For all
# of these types let's define subclasses that do retain these
# attributes.

position_attributes = dict(_attributes = ('lineno', 'col_offset'))

def position_extend(class_):
    return type(class_.__name__, (class_,), position_attributes)
def map_extend(names):
    return [position_extend(getattr(ast, name)) for name in names.split()]

And, Or = map_extend('And Or')
Add, Sub, Mult, Div, Mod, Pow, LShift, RShift, BitOr, BitXor, BitAnd, FloorDiv = \
    map_extend('Add Sub Mult Div Mod Pow LShift RShift BitOr BitXor BitAnd FloorDiv')
Invert, Not, UAdd, USub = \
    map_extend('Invert Not UAdd USub')
Eq, NotEq, Lt, LtE, Gt, GtE, Is, IsNot, In, NotIn = \
    map_extend('Eq NotEq Lt LtE Gt GtE Is IsNot In NotIn')


# OK, back to parsing.

if __name__ == '__main__':
    # XXX temporary hack during development
    import parson3 as P
else:
    from . import parson3 as P

def main(argv):
    filename = argv[1]
    if 0:
        with open(filename, 'rb') as f:
            tokens = list(tokenize(f.readline))
        print_tokens(tokens)
        demo_parse(tokens)
    else:
        with open(filename, 'rb') as f:
            t = parse(f)
        import astpp
        print(astpp.dump(t, include_attributes=True))

class Name(P._Pex):
    def __init__(self):
        self.face = 'XXX'
    def run(self, s, far, state):
        i, vals = state
        token = s[i]
        if token.type != T.NAME or token.string in keywords:
            return []
        vals += (token,)
        return [(_step(far, i+1), vals)]

class Tok(P._Pex):
    "Matches a single lexical token of a given kind."
    def __init__(self, kind, literal_string=None, keep=True):
        self.kind = kind
        self.expected = literal_string
        self.keep = keep
        self.face = 'XXX'
    def run(self, s, far, state):
        i, vals = state
        token = s[i]
        if token.type != self.kind:
            return []
        if self.expected is not None and token.string != self.expected:
            return []
        if self.keep:
            vals += (token,)
        return [(_step(far, i+1), vals)]

def _step(far, i):
    "Update far with a new position."
    far[0] = max(far[0], i)
    return i

"""
file_input: (NEWLINE | stmt)* ENDMARKER
stmt: simple_stmt | compound_stmt
simple_stmt: small_stmt (';' small_stmt)* [';'] NEWLINE
small_stmt: expr_stmt | flow_stmt | import_stmt | assert_stmt

compound_stmt: if_stmt | while_stmt | for_stmt | funcdef | classdef | decorated
if_stmt: 'if' test ':' suite ('elif' test ':' suite)* ['else' ':' suite]
suite: simple_stmt | NEWLINE INDENT stmt+ DEDENT

expr_stmt: testlist_expr ('=' testlist_expr)*
testlist_expr: test
test: arith_expr
arith_expr: term (('+'|'-') term)*
term: factor (('*'|'/'|'%'|'//') factor)*
factor: ('+'|'-'|'~') factor | power
power: atom trailer* ('**' factor)?
atom: '(' test ')' | NAME | NUMBER | STRING+ | 'None' | 'True' | 'False'
trailer: '(' [arglist] ')'
arglist: (argument ',')* argument [',']
argument: test ['=' test]
"""

NUMBER = Tok(T.NUMBER)
STRING = Tok(T.STRING)
NAME   = Name()
OP     = lambda s: Tok(T.OP, s)
Punct  = lambda s: Tok(T.OP, s, keep=False)

keywords = set()

def Kwd(s, keep=False):
    keywords.add(s)
    return Tok(T.NAME, s, keep=keep)

def Subst(string, maker):
    return OP(string) >> (lambda t: lambda ctx: maker(lineno=t.start[0], col_offset=t.start[1]))

def wrapping(maker, wrapper):
    return lambda t: lambda ctx: maker(wrapper(t.string),
                                       lineno=t.start[0],
                                       col_offset=t.start[1])

def propagating(maker):
    result = lambda node_fn, *node_fns: lambda ctx: next(ast.copy_location(maker(node, *[n(ctx) for n in node_fns]), node)
                                                         for node in [node_fn(ctx)])
    result.__name__ = maker.__name__
    return result

def hug(*args):
    return lambda ctx: [arg(ctx) for arg in args]

def make_module(*stmts):
    m = ast.Module(list(stmts))
    return ast.copy_location(m, stmts[0]) if stmts else m

def make_if(test, then, *rest):
    # (This'd be simpler with a different form of the grammar.)
    test = test(ast.Load())
    if not rest:         else_ = []
    elif len(rest) == 1: else_ = rest[0]
    else:                else_ = make_if(*rest)
    # XXX location should come from 'if' token
    return ast.copy_location(ast.If(test, then, else_), test)

def maybe_assignment(*expr_fns):
    if len(expr_fns) == 1:
        node0 = expr_fns[0](ast.Load())
        stmt = ast.Expr(node0)
    else:
        lhses = [fn(ast.Store()) for fn in expr_fns[:-1]]
        node0 = lhses[0]
        stmt = ast.Assign(lhses, expr_fns[-1](ast.Load()))
    return ast.copy_location(stmt, node0)

def fill_context(ctx):
    return lambda f: f(ctx)

atom =   P.delay(lambda:
            Punct('(') + test + Punct(')')
          | NUMBER >> wrapping(ast.Num, ast.literal_eval)
          | STRING.plus() >> (lambda *tokens: lambda ctx: ast.Str(ast.literal_eval(' '.join(t.string for t in tokens)),
                                                                  lineno=tokens[0].start[0],
                                                                  col_offset=tokens[0].start[1]))
          | Tok(T.NAME, 'None')  >> wrapping(ast.NameConstant, lambda s: None)
          | Tok(T.NAME, 'True')  >> wrapping(ast.NameConstant, lambda s: True)
          | Tok(T.NAME, 'False') >> wrapping(ast.NameConstant, lambda s: False)
          | NAME >> (lambda t: lambda ctx: ast.Name(t.string, ctx,
                                                    lineno=t.start[0],
                                                    col_offset=t.start[1]))
          )
arglist = P.delay(lambda:
            (test + Punct(',')).star() + test + Punct(',').maybe())
trailer = (Punct('(') + (arglist.maybe() >> hug) + Punct(')')
           + propagating(lambda f, args: ast.Call(f, args, [], None, None)))
power  = P.delay(lambda:
         P.seclude(
            atom + trailer.star() + (Subst('**', Pow) + factor + propagating(ast.BinOp)).maybe()))
factor = P.delay(lambda:
          ( (( Subst('+', UAdd)
             | Subst('-', USub)
             | Subst('~', Invert)) + factor) >> propagating(ast.UnaryOp))
          | power)
term =   P.seclude(
            factor + ((  Subst('*', Mult)
                       | Subst('/', Div)
                       | Subst('%', Mod)
                       | Subst('//', FloorDiv)) + factor + propagating(ast.BinOp)).star())
arith_expr = P.seclude(
            term + ((  Subst('+', Add)
                     | Subst('-', Sub)) + term + propagating(ast.BinOp)).star())
test =   arith_expr

expr_stmt = P.seclude(
              test + (Punct('=') + test).star()
            + maybe_assignment)

simple_stmt = expr_stmt + Tok(T.NEWLINE, keep=False)

stmt = P.delay(lambda: simple_stmt | compound_stmt)

suite = (
      simple_stmt
    | (Tok(T.NEWLINE, keep=False) + Tok(T.INDENT, keep=False) + stmt.plus() + Tok(T.DEDENT, keep=False))
) >> (lambda *stmts: list(stmts))

if_stmt = P.seclude(
      Kwd('if') + test + Punct(':') + suite
    + (Kwd('elif') + test + Punct(':') + suite).star()
    + (Kwd('else') + Punct(':') + suite).maybe()
    + make_if
)

compound_stmt = if_stmt

file_input = (Tok(56, keep=False)  # 'ENCODING' token -- yeah, no name for it
              + (Tok(T.NEWLINE, keep=False) | stmt).star()
              + Tok(T.ENDMARKER, keep=False)) >> make_module

top = file_input

def parse(f):
    tokens = list(tokenize(f.readline))
#    print_tokens(tokens)
    far = [0]
    for i, vals in top.run(tokens, far, (0, ())):
        if 1:
            assert i == len(tokens), "not full parse: %d of %r" % (i, tokens)
        assert len(vals) == 1
        return vals[0]

def demo_parse(tokens):
    far = [0]
    for i, vals in top.run(tokens, far, (0, ())):
        print(i, tokens[i:])
        print('vals', vals)
        try:
            import astpp
        except ImportError:
            continue
        for tree in vals:
            print(tree)
            print(astpp.dump(tree, include_attributes=True))
    print('far', far[0])

def print_tokens(tokens):
    for t in tokens:
#        print_token(t)
        skim_token(t)

def skim_token(t):
    print(T.tok_name[t.type], T.tok_name[t.exact_type], t.string)
    return
    if T.tok_name[t.type] == T.tok_name[t.exact_type]:
        print(T.tok_name[t.type], t.string)
    else:
        print(T.tok_name[t.type], T.tok_name[t.exact_type], t.string)

def print_token(t):
#    print(t.count)
#    print(t.index)
#    print()
    print('line', t.line)
    print('start', t.start)
    print('end', t.end)
    print('string', t.string)
    print('type', t.type, T.tok_name[t.type])
    print('exact_type', t.exact_type, T.tok_name[t.exact_type])
    print()

if __name__ == '__main__':
    main(sys.argv)
