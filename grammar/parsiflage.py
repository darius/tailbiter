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
    def __init__(self, kind, literal_string=None):
        self.kind = kind
        self.expected = literal_string
    def run(self, s, far, state):
        i, vals = state
        token = s[i]
        if token.type != self.kind: return []
        if self.expected is None:
            vals += (token,)
        else:
            if token.string != self.expected: return []
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

atom =   P.delay(lambda:
            OP('(') + test + OP(')')
          | NUMBER >> (lambda t: ast.Num(number_value(t.string),
                                         lineno=t.line,
                                         col_offset=t.start))
          | STRING.plus() >> (lambda *tokens: ast.Str(''.join(t.string for t in tokens),
                                                      lineno=t.line,
                                                      col_offset=t.start))
          | Tok(T.NAME, 'None') # XXX how is this different from a bare NAME?
          | Tok(T.NAME, 'True')
          | Tok(T.NAME, 'False')
          | NAME >> (lambda t: ast.Name(t.string, ast.Load(), # XXX we don't know the context yet
                                        lineno=t.line,
                                        col_offset=t.start))
          )
factor = P.delay(lambda:
          ( (( (OP('+') >> (lambda: ast.UAdd())) # XXX location info here?
             | (OP('-') >> (lambda: ast.USub()))
             | (OP('~') >> (lambda: ast.Invert())))
            + factor) >> ast.UnaryOp)  # XXX propagate location info
          | atom)
term =   P.seclude(
            factor
          + ((  (OP('*') >> (lambda: ast.Mult()))
              | (OP('/') >> (lambda: ast.Div()))
              | (OP('%') >> (lambda: ast.Mod()))
              | (OP('//') >> (lambda: ast.FloorDiv())))
             + factor + P.feed(lambda lhs, operator, rhs: ast.BinOp(operator, lhs, rhs))).star())
arith_expr = P.seclude(
            term
          + ((  (OP('+') >> (lambda: ast.Add()))
              | (OP('-') >> (lambda: ast.Sub())))
             + term + P.feed(lambda lhs, operator, rhs: ast.BinOp(operator, lhs, rhs))).star())
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
            print(astpp.dump(tree))

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
