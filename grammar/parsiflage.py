"""
Let's work out some basic parsing of some productions from the Python grammar.
Start from a py3 port of parts of Parson, adapted to work on tokens
from `tokenize`.
"""

import sys
import token as T
from token import tok_name
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
        if 0:
            print('a', token.type, self.kind)
            skim_token(token)
        if token.type != self.kind: return []
        if self.expected is None:
            vals += (token.string,)
        else:
            if token.string != self.expected: return []
        return [(_step(far, i+1), vals)]

def _step(far, i):
    "Update far with a new position."
    far[0] = max(far[0], i)
    return i

"""
arith_expr: term (('+'|'-') term)*
term: factor (('*'|'/'|'%'|'//') factor)*
factor: ('+'|'-'|'~') factor | atom
atom: NAME | NUMBER | STRING+ | 'None' | 'True' | 'False'
"""

NUMBER = Tok(T.NUMBER)
STRING = Tok(T.STRING)
NAME   = Tok(T.NAME)
OP     = lambda s: Tok(T.OP, s)

atom =   P.delay(lambda:
            OP('(') + test + OP(')')
          | NUMBER
          | (STRING.plus() >> (lambda *strings: ''.join(strings))) # XXX wrong semantics
          | Tok(T.NAME, 'None')
          | Tok(T.NAME, 'True')
          | Tok(T.NAME, 'False')
          | NAME)
factor = P.delay(lambda:
            (OP('+') | OP('-') | OP('~')) + factor
          | atom)
term =   factor + ((OP('*') | OP('/') | OP('%') | OP('//')) + factor).star()
arith_expr = (
         term + ((OP('+') | OP('-')) + term).star())
test =   arith_expr

def parse(tokens):
    far = [0]
    for i, vals in arith_expr.run(tokens[1:], far, (0, ())):
        print(i, vals)

def print_tokens(tokens):
    for t in tokens:
#        print_token(t)
        skim_token(t)

def skim_token(t):
    if tok_name[t.type] == tok_name[t.exact_type]:
        print(tok_name[t.type], t.string)
    else:
        print(tok_name[t.type], tok_name[t.exact_type], t.string)

def print_token(t):
#    print(t.count)
#    print(t.index)
#    print()
    print('line', t.line)
    print('start', t.start)
    print('end', t.end)
    print('string', t.string)
    print('type', t.type, tok_name[t.type])
    print('exact_type', t.exact_type, tok_name[t.exact_type])
    print()

if __name__ == '__main__':
    main(sys.argv)
