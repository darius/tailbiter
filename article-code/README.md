Here are source files extracted from my article on compiling
Python. There are three versions of the compiler, each handling a
larger subset of Python. To run one, you need Python 3.4. You
also need `check_subset.py` from the parent directory; copy it down
here. Then this should work:

    $ python3 tailbiter0.py greet.py
    Hi, Chrysophylax

and likewise for the article's other example runs.

The final version of the compiler from the article, `tailbiter2.py`,
is almost the same as `../compiler.py` but missing a few features
needed to compile `byterun`. These smaller versions are provided just
so you can easily run the exact code from the article.

`handaxeweb.py` extracted the tailbiter source from the article's
Markdown source; since the article is distributed as HTML this is
useless to you, but perhaps someone might adapt it for their own
literate programming, so here you are. It's derived from an earlier
version in Python of Kragen Sitaker's
[handaxeweb](https://github.com/kragen/peg-bootstrap/blob/master/handaxeweb.md).
