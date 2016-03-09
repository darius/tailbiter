"""
Process Python's LL(1) grammar.
For the moment we just recognize it (`pip install parson`).
"""

import tokenize
from parson import Grammar, chain, delay, either, empty, label, one_that, plus, star

g = r"""
grammar: _ defn* !/./.

defn: id ':'_ e        :hug.

e: e1.

e1: term ('|'_ e1 :either)?.

term: factor*          :Chain.

factor: primary ( '*'_ :star
                | '+'_ :plus)?.

primary: '('_ e ')'_
       | '['_ e ']'_   :Optional
       | qstring       :Literal
       | tokenid       :Token
       | id !':'       :RuleRef.

qstring: /'([^']*)'/_.
tokenid: /([A-Z_]+)/_.
id:      /([a-z_]+)/_.
_ =      /\s*/.
"""

def foldr1(f, xs):
    return xs[0] if len(xs) == 1 else f(xs[0], foldr1(f, xs[1:]))

def Chain(*pes):   return empty if not pes else foldr1(chain, pes)
def Optional(pe):  return pe.maybe()
def Literal(s):    return label(one_that(lambda t: t[1] == s), repr(s)) # XXX
def Token(name):   return label(one_that(lambda t: t[1] == name), name) # XXX
def RuleRef(name): return delay((lambda: rules[name]), name)

grammar = Grammar(g)(**globals())

subset = open('subset').read()
metagrammar = grammar.grammar(subset)
rules = dict(metagrammar)
pygrammar = rules['file_input']
## pygrammar([('', 'ENDMARKER',)])
#. ()

## grammar.grammar("dotted_name: NAME ('.' NAME)*")
#. (('dotted_name', (NAME (('.' NAME))*)),)

## for pair in grammar.grammar('yo: hey boo: yah'): print pair
#. ('yo', hey)
#. ('boo', yah)

## for k, v in sorted(rules.items()): print k, v
#. and_expr (shift_expr (('&' shift_expr))*)
#. and_test (not_test (('and' not_test))*)
#. arglist (((argument ','))* ((argument (',')?)|(('*' (test (((',' argument))* ((',' ('**' test)))?)))|('**' test))))
#. argslist ((NAME (((',' NAME))* ((',' ((('*' (NAME ((',' ('**' NAME)))?))|('**' NAME)))?))?))|(('*' (NAME ((',' ('**' NAME)))?))|('**' NAME)))
#. argument ((test (comp_for)?)|(test ('=' test)))
#. arith_expr (term ((('+'|'-') term))*)
#. assert_stmt ('assert' (test ((',' test))?))
#. atom (('[' ((testlist_comp)? ']'))|(NAME|(NUMBER|((STRING)+|('None'|('True'|'False'))))))
#. classdef ('class' (NAME ((('(' ((arglist)? ')')))? (':' suite))))
#. comp_for ('for' (exprlist ('in' (or_test (comp_iter)?))))
#. comp_if ('if' (test_nocond (comp_iter)?))
#. comp_iter (comp_for|comp_if)
#. comp_op ('<'|('>'|('=='|('>='|('<='|('!='|('in'|(('not' 'in')|('is'|('is' 'not'))))))))))
#. comparison (expr ((comp_op expr))*)
#. compound_stmt (if_stmt|(while_stmt|(for_stmt|(funcdef|(classdef|decorated)))))
#. decorated ((decorator)+ funcdef)
#. decorator ('@' (dotted_name ((('(' ((arglist)? ')')))? NEWLINE)))
#. dotted_as_name (dotted_name (('as' NAME))?)
#. dotted_as_names (dotted_as_name ((',' dotted_as_name))*)
#. dotted_name (NAME (('.' NAME))*)
#. expr (xor_expr (('|' xor_expr))*)
#. expr_stmt (testlist_expr (('=' testlist_expr))*)
#. exprlist (expr (((',' expr))* (',')?))
#. factor ((('+'|('-'|'~')) factor)|power)
#. file_input (((NEWLINE|stmt))* ENDMARKER)
#. flow_stmt (return_stmt|raise_stmt)
#. for_stmt ('for' (exprlist ('in' (testlist (':' suite)))))
#. funcdef ('def' (NAME (parameters (':' suite))))
#. if_stmt ('if' (test (':' (suite ((('elif' (test (':' suite))))* (('else' (':' suite)))?)))))
#. import_as_name (NAME (('as' NAME))?)
#. import_as_names (import_as_name (((',' import_as_name))* (',')?))
#. import_from ('from' (((('.')* dotted_name)|('.')+) ('import' (('(' (import_as_names ')'))|import_as_names))))
#. import_name ('import' dotted_as_names)
#. import_stmt (import_name|import_from)
#. lambdef ('lambda' ((argslist)? (':' test)))
#. lambdef_nocond ('lambda' ((argslist)? (':' test_nocond)))
#. not_test (('not' not_test)|comparison)
#. or_test (and_test (('or' and_test))*)
#. parameters ('(' ((argslist)? ')'))
#. power (atom ((trailer)* (('**' factor))?))
#. raise_stmt ('raise' (test)?)
#. return_stmt ('return' (testlist)?)
#. shift_expr (arith_expr ((('<<'|'>>') arith_expr))*)
#. simple_stmt (small_stmt (((';' small_stmt))* ((';')? NEWLINE)))
#. small_stmt (expr_stmt|(flow_stmt|(import_stmt|assert_stmt)))
#. stmt (simple_stmt|compound_stmt)
#. subscript test
#. subscriptlist (subscript (((',' subscript))* (',')?))
#. suite (simple_stmt|(NEWLINE (INDENT ((stmt)+ DEDENT))))
#. term (factor ((('*'|('/'|('%'|'//'))) factor))*)
#. test ((or_test (('if' (or_test ('else' test))))?)|lambdef)
#. test_nocond (or_test|lambdef_nocond)
#. testlist (test (((',' test))* (',')?))
#. testlist_comp (test (comp_for|(((',' test))* (',')?)))
#. testlist_expr (test (((',' test))* (',')?))
#. trailer (('(' ((arglist)? ')'))|(('[' (subscriptlist ']'))|('.' NAME)))
#. while_stmt ('while' (test (':' suite)))
#. xor_expr (and_expr (('^' and_expr))*)
