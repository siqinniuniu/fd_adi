#!/usr/bin/env python

import sys
import time

import numpy as np
import pylab
import scipy.sparse
import scipy.optimize
import inspect
from bisect import bisect_left

def attr_dict(a):
    return dict(inspect.getmembers(a))


def tic(label=None):
    """
    Matlab-style timing function.

        In []: tic('foo:'); sleep(10); toc();
            foo: 10.0004s
        Out[]: 10.0004
    """
    global TIC_START
    if label is not None:
        print label,
    sys.stdout.flush()
    TIC_START = time.time()


def toc(label=None):
    """
    Matlab-style timing function.

        In []: tic('foo:'); sleep(10); toc();
            foo: 10.0004s
        Out[]: 10.0004
    """
    t = time.time() - TIC_START
    if label is not None:
        print label,
    print "%fs" % t
    sys.stdout.flush()
    return t


def D(dim):
    """
    Discrete first derivative operator with no boundary.
    Returns a DIAmatrix object looking like:

         0  0  0  0  0
        -1  0  1  0  0
         0 -1  0  1  0
         0  0 -1  0  1
         0  0  0  0  0
    """
    operator = np.zeros((3, dim))
    operator[0,2:]  =  0.5
    operator[2,:-2] = -0.5
    return scipy.sparse.dia_matrix((operator, (1,0,-1)), shape=(dim,dim))


def D2(dim):
    """
    Discrete second derivative operator with no boundary.
    Returns a DIAmatrix object looking like:

         0  0  0  0  0
         1 -2  1  0  0
         0  1 -2  1  0
         0  0  1 -2  1
         0  0  0  0  0
    """
    operator = np.zeros((3, dim))
    operator[0,2:]  =  1
    operator[1,1:-1]  = -2
    operator[2,:-2] =  1
    return scipy.sparse.dia_matrix((operator, (1,0,-1)), shape=(dim,dim))


def center_diff(domain, n=1, axis=-1):
    """Like numpy.diff, but centered instead of forward."""
    xs = domain.copy()
    dx = np.zeros_like(xs,dtype=float)
    if axis == 0:
        for i in xrange(n):
            dx[:-1]  += np.diff(xs, axis=axis)
            dx[1:]   += np.diff(xs[::-1], axis=axis)[::-1]*-1
            dx[1:-1] *= 0.5
            t = xs; xs = dx; dx = t
    if axis == 1:
        for i in xrange(n):
            dx[:,:-1]  += np.diff(xs, axis=axis)
            dx[:,1:]   += np.diff(xs[::-1], axis=axis)[::-1]*-1
            dx[:,1:-1] *= 0.5
            t = xs; xs = dx; dx = t
    return xs


def sinh_space(exact, high, density, size, force_exact=True):
    """
    Sigmoidal space with high density around 'exact'.

    Play with the density value because it's really dependent on exact and high.

    This function will shift 'high' around a little to make sure that @exact@
    is matched closely. If @force@ is True, it then shifts that value up to
    match @exact@ exactly.
    """
    # def g(x, K, c, p): return K + c/p * np.sinh(p*x + np.arcsinh(-p*K/c))
    # c = float(density)
    density = float(density)
    high_orig = high
    if size == 1:
        return np.asarray(exact)

    def newspace(high):
        Smax = high
        K = exact
        deps = 1./size * (np.arcsinh((Smax - K)*(1/density)) - np.arcsinh(-K/density))
        eps = np.arcsinh(-K/density) + np.arange(size)*deps
        space = K + density * np.sinh(eps)
        space -= min(space)
        return space

    def energy(high):
        space = newspace(high)
        try:
            best = space[bisect_left(space, exact)]
        except IndexError:
            best = space[-2]
        return abs(exact - best)

    newmax, best, failed, _ = scipy.optimize.fminbound(energy, high*0.95, high*1.05, full_output=True)
    if failed:
        print newspace(newmax)
        raise ValueError("Unable to create a suitable space. %s\n%s" % ((exact, high, density, size), newmax))
    space = newspace(newmax)
    if force_exact:
        idx = bisect_left(space, exact)
        try:
            space[idx] = exact
        except IndexError:
            print "Boy, this is terrible."
    return space

def todia(A):
    """
    Just like normal sparse.dia_matrix, but swap the offsets and row data from
    ascending to descending. In the data matrix, top row should be top diagonal.
    """
    d = scipy.sparse.dia_matrix(A)
    idx = np.argsort(d.offsets)[::-1]
    d.data = d.data[idx]
    d.offsets = d.offsets[idx]
    return d


def exponential_space(low, exact, high, ex, size, force_exact=True):
    """
    Exponential space like y = x**ex. The exact value will be satisfied by
    adjust the high value upwards as necessary.
    """
    if size == 1:
        return np.array([exact])
    v = np.zeros(size)
    l = pow(low,1./ex)
    h = pow(high,1./ex)
    x = pow(exact,1./ex)
    dv = (h - l) / (size-1)

    if force_exact:
        j = 0
        d = 1e100
        for i in range(size):
            if (l + i*dv > x):
            # if abs(i*dv - x) < d:
                # d = abs(i*dv - x)
                j = i-1
                break
        if (j == 0):
            assert(j != 0), "Did not find suitable value."
        dx = x - (l + j*dv)
        h += (size-1) * dx/j
    dv = (h - l) / (size-1)
    for i in range(size):
        v[i] = l + pow(i*dv, ex)
    return v


def cubic_sigmoid_space(exact, high, density, size):
    """Cheap and bad sigmoid curve. Use sinh instead."""
    if size == 1:
        return array([exact])
    if density == 0:
        return linspace(exact - (high - exact), high, size)

    y = np.zeros(size)
    dx = 1.0/(size-1)
    scale = (float(high)-exact)/(density**3 + density)
    for i in range(size):
        x = (2*(i*dx)-1)*density
        y[i] = exact + (x**3+x)*scale

    return y


def nonuniform_backward_coefficients(deltas):
    """
    The coefficients for tridiagonal matrices operating on a non-uniform grid.

    L = spl.dia_matrix((fst, (0,-1,-2)), shape=(fst.shape[1], fst.shape[1]))
    """
    d = deltas.copy()
    m = 1
    fst = np.zeros((4,len(d)))
    snd = fst.copy()
    for i in range(2,len(d)-1):
        fst[m  , i]   = (d[i-1]+2*d[i])  / (d[i]*(d[i-1]+d[i]))
        fst[m+1, i-1] = (-d[i-1] - d[i]) / (d[i-1]*d[i])
        fst[m+2, i-2] = d[i]             / (d[i-1]*(d[i-1]+d[i]))

        denom = (0.5*(d[i]+d[i-1])*d[i]*d[i-1])
        snd[m  , i]   = d[i-1]         / denom
        snd[m+1, i-1] = -(d[i]+d[i-1]) / denom
        snd[m+2, i-2] = d[i]           / denom

    # Use first order approximation for the first (inner) row
    # fst[m,   1] =  1 / d[1]
    # fst[m+1, 0] = -1 / d[1]
    # fst[m+2, 0] = 0
    fst[m-1,2] =          d[1]  / (d[2]*(d[1]+d[2]))
    fst[m,  1] = (-d[1] + d[2]) /       (d[1]*d[2])
    fst[m+1,0] =         -d[2]  / (d[1]*(d[1]+d[2]))

    # Use centered approximation for the first (inner) row
    snd[m-1, 2] =  2 / (d[2]*(d[1]+d[2]))
    snd[m,   1] = -2 /       (d[1]*d[2])
    snd[m+1, 0] =  2 / (d[1]*(d[1]+d[2]))

    L1 = scipy.sparse.dia_matrix((fst.copy(), (1, 0, -1, -2)), shape=(len(d),len(d)))
    L2 = scipy.sparse.dia_matrix((snd.copy(), (1, 0, -1, -2)), shape=(len(d),len(d)))
    return L1,L2


def nonuniform_forward_coefficients(deltas):
    """
    The coefficients for tridiagonal matrices operating on a non-uniform grid.

    L = spl.dia_matrix((fst, (2,1,0)), shape=(fst.shape[1], fst.shape[1]))
    """
    d = deltas.copy()
    m = 2
    fst = np.zeros((4,len(d)))
    snd = fst.copy()
    for i in range(1,len(d)-2):
        fst[m-2, i+2] = -d[i+1]            / (d[i+2]*(d[i+1]+d[i+2]))
        fst[m-1, i+1] = (d[i+1] + d[i+2])  /         (d[i+1]*d[i+2])
        fst[m  , i  ] = (-2*d[i+1]-d[i+2]) / (d[i+1]*(d[i+1]+d[i+2]))

        denom = (0.5*(d[i+2]+d[i+1])*d[i+2]*d[i+1]);
        snd[m-2,  i+2] = d[i+1]           / denom
        snd[m-1  ,i+1] = -(d[i+2]+d[i+1]) / denom
        snd[m,i]       = d[i+2]           / denom

    # Use first order approximation for the last (inner) row
    # fst[m-2,  0] = 0
    # fst[m-1,   -1] =  1 / d[-1]
    # fst[m, -2] = -1 / d[-1]
    fst[m-1,-1] =           d[-2]  / (d[-1]*(d[-2]+d[-1]))
    fst[m,  -2] = (-d[-2] + d[-1]) /        (d[-2]*d[-1])
    fst[m+1,-3] =          -d[-1]  / (d[-2]*(d[-2]+d[-1]))

    # Use centered approximation for the last (inner) row
    snd[m-1, -1] = 2 / (d[-1]*(d[-2]+d[-1]))
    snd[m  ,-2] = -2 /       (d[-2]*d[-1])
    snd[m+1,-3] = 2  / (d[-2]*(d[-2]+d[-1]))

    L1 = scipy.sparse.dia_matrix((fst.copy(), (2, 1, 0, -1)), shape=(len(d),len(d)))
    L2 = scipy.sparse.dia_matrix((snd.copy(), (2, 1, 0, -1)), shape=(len(d),len(d)))
    return L1,L2


def nonuniform_center_coefficients(deltas):
    """
    The coefficients for tridiagonal matrices operating on a non-uniform grid.

    L = spl.dia_matrix((fst, (1,0,-1)), shape=(fst.shape[1], fst.shape[1]))
    """
    d = deltas.copy()
    fst = np.zeros((3,len(d)))
    snd = fst.copy()
    for i in range(1,len(d)-1):
        fst[0,i+1] =            d[i]  / (d[i+1]*(d[i]+d[i+1]))
        fst[1,i]   = (-d[i] + d[i+1]) /         (d[i]*d[i+1])
        fst[2,i-1] =         -d[i+1]  / (d[i  ]*(d[i]+d[i+1]))

        snd[0,i+1] = 2  / (d[i+1]*(d[i]+d[i+1]))
        snd[1,i]   = -2 /       (d[i]*d[i+1])
        snd[2,i-1] = 2  / (d[i  ]*(d[i]+d[i+1]))
    L1 = scipy.sparse.dia_matrix((fst.copy(), (1, 0, -1)), shape=(len(d),len(d)))
    L2 = scipy.sparse.dia_matrix((snd.copy(), (1, 0, -1)), shape=(len(d),len(d)))
    return L1, L2


def nonuniform_complete_coefficients(deltas, boundary=None, up_or_down=None,
                                     flip_idx=None):
    """
    The coefficients for tridiagonal matrices. Boundary can be one of 'low',
    'high', or 'both'. downwind_from is the index of the first element for which
    backwards differencing will be applied.


    L = spl.dia_matrix((fst, (1,0,-1)), shape=(fst.shape[1], fst.shape[1]))
    """
    d = deltas.copy()

    U1 = np.zeros((5, len(d)))
    U2 = np.zeros((5, len(d)))

    upwind_from = None
    downwind_from = None
    if up_or_down is not None and flip_idx is not None:
        up_or_down = up_or_down.lower()
        if up_or_down.startswith('down'):
            downwind_from = flip_idx
            # print "Using downwinding:",
        elif up_or_down.startswith('up'):
            upwind_from = flip_idx
            # print "Using upwinding:",


    # Indexing is getting complicated so we'll do it like this
    # U[m,:] is the center diag
    # U[m-x,:] is the x'th diag above center
    # Note diag m starts at 0, m-1 starts at +1, m-2 starts at +2...
    #                          m+1 ENDS   at -1, m+2 ENDS at -2...
    m = 2
    b = 1
    c = 1
    f = 2

    C1, C2 = nonuniform_center_coefficients(d)
    F1, F2 = nonuniform_forward_coefficients(d)
    B1, B2 = nonuniform_backward_coefficients(d)

    if downwind_from is not None and upwind_from is not None:
        raise NotImplementedError("One or both of downwind_from and upwind_from"
                                  "must be None.")
    elif downwind_from is not None:
        if downwind_from < 1:
            raise ValueError("Can't use backward differencing at top boundary."
                             " (downwind_from == %i < 2)" % downwind_from)
        elif downwind_from == 1:
            U1[m-B1.offsets] = B1.data
            U2[m-B2.offsets] = B2.data

        else:
            u = downwind_from
            assert u-2 >= 0

            U1[m-2, :u+2] = 0
            U1[m-2, u+2:] = 0
            U2[m-2, :u+2] = 0
            U2[m-2, u+2:] = 0

            U1[m-1, :u+1] = C1.data[c-1,:u+1]
            U2[m-1, :u+1] = C2.data[c-1,:u+1]
            U1[m-1, u+1:] = B1.data[b-1,u+1:]
            U2[m-1, u+1:] = B2.data[b-1,u+1:]

            U1[m  , :u] = C1.data[c,:u]
            U2[m  , :u] = C2.data[c,:u]
            U1[m  , u:] = B1.data[b,u:]
            U2[m  , u:] = B2.data[b,u:]

            U1[m+1, :u-1] = C1.data[c+1,:u-1]
            U2[m+1, :u-1] = C2.data[c+1,:u-1]
            U1[m+1, u-1:] = B1.data[b+1,u-1:]
            U2[m+1, u-1:] = B2.data[b+1,u-1:]

            U1[m+2, :u-2] = 0
            U1[m+2, u-2:] = B1.data[b+2,u-2:]
            U2[m+2, :u-2] = 0
            U2[m+2, u-2:] = B2.data[b+2,u-2:]



    elif upwind_from is not None:
        if upwind_from > len(d)-1:
            raise ValueError("Can't use foward differencing at bottom boundary."
                             " (upwind_from == %i > len(d)-1 (%i))" % (upwind_from, len(d)-1))

        u = upwind_from
        assert u+2 < U1.shape[1]

        U1[m-2, :u+2]  = 0
        U1[m-2,  u+2:] = F1.data[f-2,u+2:]
        U2[m-2, :u+2]  = 0
        U2[m-2,  u+2:] = F2.data[f-2,u+2:]

        U1[m-1, :u+1]  = C1.data[c-1,:u+1]
        U1[m-1,  u+1:] = F1.data[f-1, u+1:]
        U2[m-1, :u+1]  = C2.data[c-1,:u+1]
        U2[m-1,  u+1:] = F2.data[f-1, u+1:]

        U1[m+0, :u]  = C1.data[c,:u]
        U1[m+0,  u:] = F1.data[f,u:]
        U2[m+0, :u]  = C2.data[c,:u]
        U2[m+0,  u:] = F2.data[f,u:]

        U1[m+1, :u-1]  = C1.data[c+1,:u-1]
        U1[m+1,  u-1:] = F1.data[f+1,u-1:]
        U2[m+1, :u-1]  = C2.data[c+1,:u-1]
        U2[m+1,  u-1:] = F2.data[f+1,u-1:]

        U1[m+2, :u-2]  = 0
        U1[m+2,  u-2:] = 0
        U2[m+2, :u-2]  = 0
        U2[m+2,  u-2:] = 0



    # If we don't use anything special, then just copy the center coefficients
    elif downwind_from is None and upwind_from is None:
        U1[m-1,:] = C1.data[c-1,:]
        U1[m,:]   = C1.data[c  ,:]
        U1[m+1,:] = C1.data[c+1,:]

        U2[m-1,:] = C2.data[c-1,:]
        U2[m,:]   = C2.data[c  ,:]
        U2[m+1,:] = C2.data[c+1,:]

    else:
        raise NotImplementedError("The universe has terminated.")

    U1 = scipy.sparse.dia_matrix((U1, (2, 1, 0, -1,-2)), shape=(len(d),len(d)))
    U2 = scipy.sparse.dia_matrix((U2, (2, 1, 0, -1,-2)), shape=(len(d),len(d)))
    return U1, U2


def nonuniform_center_forward_coefficients(deltas, upwind_from=None):
    d = deltas.copy()
    if upwind_from is None:
        return nonuniform_center_coefficients(d)
    u = upwind_from

    C1, C2 = nonuniform_center_coefficients(d)
    F1, F2 = nonuniform_forward_coefficients(d)

    U1 = np.zeros((4, len(d)))
    U1[0,:u+2] = 0
    U1[0,u+2:] = F1.data[0,u+2:]
    U1[1,:u+1] = C1.data[0,:u+1]
    U1[1,u+1:] = F1.data[1,u+1:]
    U1[2,:u] = C1.data[1,:u]
    U1[2,u:] = F1.data[2,u:]
    U1[3,:u-1] = C1.data[2,:u-1]
    U1[3,u-1:] = 0.0
    U1[2,-2] = -1 / d[-1] # Use first order approximation for the last row
    U1[1,-1] =  1 / d[-1]

    U2 = np.zeros((4, len(d)))
    U2[0,:u+2] = 0
    U2[0,u+2:] = F2.data[0,u+2:]
    U2[1,:u+1] = C2.data[0,:u+1]
    U2[1,u+1:] = F2.data[1,u+1:]
    U2[2,:u] = C2.data[1,:u]
    U2[2,u:] = F2.data[2,u:]
    U2[3,:u-1] = C2.data[2,:u-1]
    U2[3,u-1:] = 0.0


    U1 = scipy.sparse.dia_matrix((U1, (2, 1, 0, -1)), shape=(len(d),len(d)))
    U2 = scipy.sparse.dia_matrix((U2, (2, 1, 0, -1)), shape=(len(d),len(d)))
    return U1, U2


def cs(deltas, upwind_from=None):
    B1,B2 = nonuniform_backward_coefficients(deltas)
    C1,C2 = nonuniform_center_coefficients(deltas)
    F1,F2 = nonuniform_forward_coefficients(deltas)
    U1,U2 = nonuniform_center_forward_coefficients(delta, upwind_from=upwind_from)
    return F1,F2,C1,C2,B1,B2,U1,U2

def clear_boundary(domain, inplace=False):
    if not inplace:
        domain = domain.copy()
    domain[0,:] = 0
    domain[:,0] = 0
    domain[:,-1] = 0
    domain[-1,:] = 0
    return domain

def rolllist(l, fromindex, toindex):
    """
    Move an element in the list, preserving the relative positions of the
    other elements."""
    n = l.pop(fromindex)
    l.insert(toindex, n)


def foldMatFor(A, blocks):
    """
    A matrix that, when applied to @A@, will perform a step of gaussian
    elimination. Used in testing only.
    """
    l = A.shape[0] // blocks
    data = np.zeros((3, A.shape[0]))
    data[1, :] = 1
    offsets = (1, 0, -1)
    m = len(A.offsets) // 2
    for b in range(blocks):
        data[0, b*l+1] = -A.data[m-2,b*l+2] / A.data[m-1,b*l+2] if A.data[m-1,b*l+2] else 0
        data[2, (b+1)*l-2] = -A.data[m+2,(b+1)*l-3] / A.data[m+1,(b+1)*l-3] if A.data[m+2,(b+1)*l-3] else 0
        d = scipy.sparse.dia_matrix((data, offsets), shape=A.shape)
    return d


def block_repeat(B, blocks):
    B = B.copy()
    B.D = scipy.sparse.dia_matrix((np.tile(B.D.data, blocks), B.D.offsets), [x*blocks for x in B.shape])
    B.R = np.tile(B.R, blocks)
    B.blocks = blocks
    B.shape = tuple(x*blocks for x in B.shape)
    return B


def enum(name, *sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    reverse = dict((value, key) for key, value in enums.iteritems())
    enums['reverse_mapping'] = reverse
    return type('Enum: '+name, (), enums)
