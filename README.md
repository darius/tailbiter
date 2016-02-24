A compiler from a subset of Python 3.4 (starting with abstract syntax
trees in Python's `ast` form) to CPython 3.4 bytecode. The compiler is
coded in that same Python subset; it can compile itself.

It can optionally run on top of a port of
[byterun](https://github.com/nedbat/byterun) to Python 3.4. (The
original Byterun runs in 2.7 or 3.3.)

I've greatly stripped down the version of byterun in this repo, and
extended the compiler a bit, towards compiling the interpreter.

To do: make the whole package metacircular. That is, get
compiler-compiled interpreter to run on the interpreter.

This is a continuation of
https://github.com/darius/500lines/tree/master/bytecode-compiler
