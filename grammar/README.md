# Sketching towards a Python parser

* subset: Python 3's official grammar, edited down to just the parts
  that go into the Tailbiter subset of Python (untested, probably a
  bit wrong).

* metagrammar.py: Parses a grammar like `subset`, and turns it into a
  recognizer. (Mostly; I haven't yet stapled it together with the
  Python lexer.) We don't yet do anything with this, and most likely
  won't ever; but maybe the way to go for the full Python parser will
  be to auto-generate it from the grammar, starting with this. To make
  that happen I'd have to figure out how to bring in knowledge of the
  AST types and how they're related to the concrete syntax. In Py2 for
  now.

* parson3.py: Port of the core of the Parson parsing library to Py3.

* parsiflage.py: Uses `parson3` to parse a tiny fragment of Py3 (some
  arithmetic expressions). Uses the built-in `tokenize` module for the
  lexer, for now. For now, this is just a recognizer, and doesn't
  produce useful error messages.

Vague plan: 

* Make `parsiflage` actually produce Python ASTs.

* Produce reasonable error messages.

* Extend the tiny grammar a bit to if-statements so we'll have to
  contend with indentation.

* Sketch a lexer to go with the
  parser. (https://github.com/hausdorff/pow likely to help a lot.)

* Sketch ways to scale this up to the full grammar, and pick one.
  (This'll include deciding on a parsing algorithm! LL(1), PEG,
  derivatives?)

* Make sure all the final code stays within the Tailbiter subset of
  Python, for self-hosting.
