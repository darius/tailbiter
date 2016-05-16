"""
A port of the core of Parson to py3
"""

def maybe(p):
    "Return a pex matching 0 or 1 of what p matches."
    return label(either(p, empty),
                 '(%r)?', p)

def plus(p):
    "Return a pex matching 1 or more of what p matches."
    return label(chain(p, star(p)),
                 '(%r)+', p)

def star(p):
    "Return a pex matching 0 or more of what p matches."
    return label(recur(lambda p_star: maybe(chain(p, p_star))),
                 '(%r)*', p)

def invert(p):
    "Return a pex that succeeds just when p fails."
    return _Pex(('~(%r)', p),
                lambda s, far, st: [] if p.run(s, [0], st) else [st])

def Pex(x):
    if isinstance(x, _Pex): return x
    if callable(x):         return feed(x)
    assert False

class _Pex:
    "A parsing expression."
    def __init__(self, face, run):
        self.face = face
        self.run = run
    def __repr__(self):
        if isinstance(self.face, str):   return self.face
        if isinstance(self.face, tuple): return self.face[0] % self.face[1:]
        assert False, "Bad face"
    def __call__(self, sequence):
        """Parse a prefix of sequence and return a tuple of values, or
        raise Unparsable."""
        far = [0]
        for _, vals in self.run(sequence, far, (0, ())):
            return vals
        raise Unparsable(self, sequence[:far[0]], sequence[far[0]:])
    def __add__(self, other):  return chain(self, Pex(other))
    def __radd__(self, other): return chain(Pex(other), self)
    def __or__(self, other):   return either(self, Pex(other))
    def __ror__(self, other):  return either(Pex(other), self)
    def __rshift__(self, fn):  return label(seclude(chain(self, Pex(fn))),
                                            '(%r>>%s)', self, _fn_name(fn))
    __invert__ = invert
    maybe = maybe
    plus = plus
    star = star

class Unparsable(Exception):
    "A parsing failure."
    @property
    def position(self):
        "The rightmost position positively reached in the parse attempt."
        return len(self.args[1])
    @property
    def failure(self):  # XXX rename?
        "Return slices of the input before and after the parse failure."
        return self.args[1], self.args[2]

def label(p, string, *args):
    """Return an equivalent pex whose repr is (string % args), or just
    string if no args."""
    return _Pex(((string,) + args if args else string),
                p.run)

def recur(fn):
    "Return a pex p such that p = fn(p). This is like the Y combinator."
    p = delay(lambda: fn(p), 'recur(%s)', _fn_name(fn))
    return p

def _fn_name(fn):
    return fn.__name__ if hasattr(fn, '__name__') else repr(fn)

def delay(thunk, *face):        # XXX document face
    """Precondition: thunk() will return a pex p. We immediately
    return a pex q equivalent to that future p, but we'll call thunk()
    only once, and not until the first use of q. Use this for
    recursive grammars."""
    def run(s, far, st):
        q.run = Pex(thunk()).run
        return q.run(s, far, st)
    q = _Pex(face or ('delay(%s)', _fn_name(thunk)),
             run)
    return q

# TODO: need doc comments or something
fail  = _Pex('fail', lambda s, far, st: [])
empty = label(~fail, 'empty')
             
def seclude(p):
    """Return a pex like p, but where p doesn't get to see or alter
    the incoming values tuple."""
    def run(s, far, state):
        i, vals = state
        return [(i2, vals + vals2)
                for i2, vals2 in p.run(s, far, (i, ()))]
    return _Pex(('[%r]', p), run)

def either(p, q):
    """Return a pex that succeeds just when one of p or q does, trying
    them in that order."""
    return _Pex(('(%r|%r)', p, q),
                lambda s, far, st:
                    p.run(s, far, st) or q.run(s, far, st))

def chain(p, q):
    """Return a pex that succeeds when p and q both do, with q
    starting where p left off."""
    return _Pex(('(%r %r)', p, q),
                lambda s, far, st:
                    [st3 
                     for st2 in p.run(s, far, st)
                     for st3 in q.run(s, far, st2)])

def alter(fn):                  # XXX better name
    """Return a pex that always succeeds, changing the values tuple
    from xs to fn(*xs)."""
    def run(s, far, state):
        i, vals = state
        return [(i, fn(*vals))]  # XXX check that result is tuple?
    return _Pex(('alter(%s)', _fn_name(fn)), run)

def feed(fn):
    """Return a pex that always succeeds, changing the values tuple
    from xs to (fn(*xs),). (We're feeding fn with the values.)"""
    return label(alter(lambda *vals: (fn(*vals),)),
                 ':%s', _fn_name(fn))
