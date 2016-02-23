A compiler from a subset of Python 3.4 (starting with abstract syntax
trees in Python's `ast` form) to CPython 3.4 bytecode. The compiler is
coded in that same Python subset; it can compile itself.

It can optionally run on top of a port of
[byterun](https://github.com/nedbat/byterun) to Python 3.4. (The
original Byterun runs in 2.7 or 3.3.)

I've greatly stripped down the version of byterun in this repo.

To do: make the whole package metacircular. That is, get the compiler
and byterun to use and implement the same subset of Python.

This is a continuation of
https://github.com/darius/500lines/tree/master/bytecode-compiler
