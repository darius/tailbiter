Here are source files extracted from my [Code Words](https://codewords.recurse.com/issues/seven)
article on compiling
Python. There are three versions of the compiler, each handling a
larger subset of Python. To run them, you need Python 3.4. You
also need `check_subset.py` from the parent directory; copy it down
here. Then this should work:

    $ python3 tailbiter0.py greet.py
    Hi, Chrysophylax

and likewise for the article's other example runs.

If you have Python 3.5 instead, then use `tailbiter1_py35.py` and
`tailbiter2_py35.py` in place of `tailbiter1.py` and `tailbiter2.py`.
You can see what changes were needed with

    $ diff -u tailbiter1.py tailbiter1_py35.py

and similarly for `tailbiter2`: the main change was to how dict
literals get compiled. (The `BUILD_MAP` operation changes to expect
all of the keys and values on the stack before it creates the dict.)

For Python 3.6 there's `tailbiter2_py36.py`. Currently it can't
compile itself, because it needs to generate a jump with a
more-than-one-byte offset.

After `tailbiter2` I added a few more features to be able to compile
`byterun`; the result is `../compiler.py`. (It's for Python 3.4 only,
for now, because those particular features changed in Python 3.5.)

`handaxeweb.py` exists to extract the tailbiter source code from the article's
Markdown source. Since the article is distributed as HTML, this is
useless to you, but perhaps someone might adapt it for their own
literate programming, so here you are. This is derived from an earlier
version in Python of Kragen Sitaker's
[handaxeweb](https://github.com/kragen/peg-bootstrap/blob/master/handaxeweb.md).
