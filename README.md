A compiler from a subset of Python 3.4 (starting with abstract syntax
trees in Python's `ast` form) to CPython 3.4 bytecode. The compiler is
coded in that same Python subset; it can compile itself.

It can optionally run on top of a port of
[byterun](https://github.com/nedbat/byterun) to Python 3.4. (The
original Byterun runs in 2.7 or 3.3.)

I've greatly stripped down and modified the version of byterun in this
repo, and extended the compiler a bit, to run both together, i.e. the
compiler-compiled compiler and interpreter on the interpreter.

This is a continuation of
https://github.com/darius/500lines/tree/master/bytecode-compiler

See
[article-code](https://github.com/darius/tailbiter/tree/master/article-code)
for the version [published in Code Words](https://codewords.recurse.com/issues/seven/dragon-taming-with-tailbiter-a-bytecode-compiler).
Also, for tweaks to run in Python 3.5 and 3.6.

If you run a later CPython version, **don't expect this to work there**. I haven't tried it.
