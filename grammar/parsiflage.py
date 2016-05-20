"""
Let's work out some basic parsing of some productions from the Python grammar.
Start from a py3 port of parts of Parson, adapted to work on tokens
from `tokenize`.
"""

import sys
import ast
import token as T
from tokenize import tokenize

import parson3 as P

def main(argv):
    filename = argv[1]
    with open(filename, 'rb') as f:
        tokens = list(tokenize(f.readline))
    print_tokens(tokens)
    parse(tokens)

class Tok(P._Pex):
    "Matches a single lexical token of a given kind."
    def __init__(self, kind, literal_string=None, keep=True):
        self.kind = kind
        self.expected = literal_string
        self.keep = keep
    def run(self, s, far, state):
        i, vals = state
        token = s[i]
        if token.type != self.kind: return []
        if self.expected is not None and token.string != self.expected: return []
        if self.keep:
            vals += (token,)
        return [(_step(far, i+1), vals)]

def _step(far, i):
    "Update far with a new position."
    far[0] = max(far[0], i)
    return i

"""
test: arith_expr
arith_expr: term (('+'|'-') term)*
term: factor (('*'|'/'|'%'|'//') factor)*
factor: ('+'|'-'|'~') factor | atom
atom: '(' test ')' | NAME | NUMBER | STRING+ | 'None' | 'True' | 'False'
"""

NUMBER = Tok(T.NUMBER)
STRING = Tok(T.STRING)
NAME   = Tok(T.NAME)
OP     = lambda s: Tok(T.OP, s)
Punct  = lambda s: Tok(T.OP, s, keep=False)

def Subst(string, maker):
    def wtf(t):
        assert hasattr(t, 'start')
        print('wtf', maker.__name__, t.start[0], t.start[1])
        import astpp
        print('  ', astpp.dump(maker(lineno=t.start[0], col_offset=t.start[1]),
                               include_attributes=True))
        return maker(lineno=t.start[0], col_offset=t.start[1])
    return OP(string) >> wtf
    return OP(string) >> (lambda t: maker(lineno=t.start[0], col_offset=t.start[1]))

def propagating(maker):
    def wtf(node, *nodes):
        if maker is not ast.UnaryOp:
            return ast.copy_location(maker(node, *nodes), node) # XXX what's wrong with this in UnaryOp?
        else:
            return maker(node, *nodes, lineno=node.lineno, col_offset=node.col_offset)
    return wtf

atom =   P.delay(lambda:
            Punct('(') + test + Punct(')')
          | NUMBER >> (lambda t: ast.Num(number_value(t.string),
                                         lineno=t.start[0],
                                         col_offset=t.start[1]))
          | STRING.plus() >> (lambda *tokens: ast.Str(''.join(t.string for t in tokens), # XXX decode the .string values
                                                      lineno=tokens[0].start[0],
                                                      col_offset=tokens[0].start[1]))
          | Tok(T.NAME, 'None') # XXX how is this different from a bare NAME?
          | Tok(T.NAME, 'True')
          | Tok(T.NAME, 'False')
          | NAME >> (lambda t: ast.Name(t.string, ast.Load(), # XXX we don't know the context yet
                                        lineno=t.start[0],
                                        col_offset=t.start[1]))
          )
factor = P.delay(lambda:
          ( (( Subst('+', ast.UAdd)
             | Subst('-', ast.USub)
             | Subst('~', ast.Invert)) + factor) >> propagating(ast.UnaryOp))  # XXX propagate location info
          | atom)
term =   P.seclude(
            factor + ((  Subst('*', ast.Mult)
                       | Subst('/', ast.Div)
                       | Subst('%', ast.Mod)
                       | Subst('//', ast.FloorDiv)) + factor + P.feed(propagating(ast.BinOp))).star())
arith_expr = P.seclude(
            term + ((  Subst('+', ast.Add)
                     | Subst('-', ast.Sub)) + term + P.feed(propagating(ast.BinOp))).star())
test =   arith_expr

def number_value(s):
    return int(s)               # XXX for now

def parse(tokens):
    far = [0]
    for i, vals in arith_expr.run(tokens[1:], far, (0, ())):
        print(i, tokens[i+1:])
        try:
            import astpp
        except ImportError:
            continue
        for tree in vals:
            print(astpp.dump(tree, include_attributes=True))

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
