"""
Process Python's LL(1) grammar.
For the moment we just recognize it (`pip install parson`).
"""

from parson import Grammar

g = r"""
grammar: _ defn* !/./.

defn: id ':'_ e.

e: e1.

e1: term ('|'_ term)*.

term: factor*.

factor: primary ('?'_ | '*'_ | '+'_)?.

primary: '('_ e ')'_
       | '['_ e ']'_
       | qstring
       | tokenid
       | id !':'.

qstring: /'([^']*)'/_.
tokenid: /([A-Z_]+)/_.
id: /([a-z_]+)/_.
_ = /\s*/.
"""

grammar = Grammar(g)()

subset = open('subset').read()
pygrammar = grammar.grammar(subset)

## grammar.grammar("dotted_name: NAME ('.' NAME)*")
#. ('dotted_name', 'NAME', '.', 'NAME')

## grammar.grammar('yo: hey boo: yah')
#. ('yo', 'hey', 'boo', 'yah')
