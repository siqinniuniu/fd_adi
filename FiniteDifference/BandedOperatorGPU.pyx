# coding: utf8
# cython: annotate = True
# cython: infer_types = True
# cython: profile = True
# cython: embedsignature = True
# distutils: language = c++
# distutils: sources = FiniteDifference/_GPU_Code.cu FiniteDifference/backtrace.c FiniteDifference/filter.c


from bisect import bisect_left

import numpy as np
cimport numpy as np
import scipy.sparse

cimport cython
from cython.operator import dereference as deref

from FiniteDifference.BandedOperator import BandedOperator as BO
from FiniteDifference.BandedOperator cimport BandedOperator as BO
from FiniteDifference.VecArray cimport SizedArray, GPUVec

FOLDED = "FOLDED"
CAN_FOLD = "CAN_FOLD"
CANNOT_FOLD = "CANNOT_FOLD"


cdef class BandedOperator(object):

    def __init__(self, other=None, tag="Constructor"):
        """
        A linear operator for discrete derivatives.
        Consist of a banded matrix (B.D) and a residual vector (B.R) for things
        like

            U2 = L*U1 + Rj  -->   U2 = B.apply(U1)
            U2 = L.I * (U1 - R) --> U2 = B.solve(U1)
        """
        self.attrs = ('deltas', 'derivative', 'is_mixed_derivative', 'order', 'axis',
                      'blocks', 'top_fold_status', 'bottom_fold_status')

        if other:
            self.emigrate(other, tag)


    property operator_rows:
        def __get__(self):
            if self.is_mixed_derivative:
                return self.thisptr_csr.operator_rows
            else:
                return self.thisptr_tri.operator_rows


    property shape:
        def __get__(self):
            return (self.operator_rows, self.operator_rows)


    def __dealloc__(self):
        if self.thisptr_csr:
            del self.thisptr_csr
        elif self.thisptr_tri:
            del self.thisptr_tri


    def copy_meta_data(self, other, **kwargs):
        for attr in self.attrs:
            if attr in kwargs:
                setattr(self, attr, kwargs[attr])
            elif attr in ('deltas', 'top_factors', 'bottom_factors'):
                setattr(self, attr, getattr(other, attr).copy())
            else:
                setattr(self, attr, getattr(other, attr))


    def __richcmp__(self, other, op):
        raise NotImplementedError
        true = op == 2
        false = op == 3

        def no_nan(x):
            return np.array(0) if x is None else np.nan_to_num(x)

        for attr in self.attrs:
            if attr in ('deltas', 'top_factors', 'bottom_factors'):
                continue
            if getattr(self, attr) != getattr(other, attr):
                print "%s:" % attr,  getattr(self, attr), getattr(other, attr)
                return false

        if self.is_mixed_derivative:
            top_factors = bottom_factors = True
            R = True
        else:
            top_factors    = np.array_equal(no_nan(self.top_factors), no_nan(other.top_factors))
            bottom_factors = np.array_equal(no_nan(self.bottom_factors), no_nan(other.bottom_factors))
            R              = np.array_equal(self.R, other.R)

        mat_type = self.is_mixed_derivative == other.is_mixed_derivative
        deltas         = np.array_equal(no_nan(self.deltas), no_nan(other.deltas))
        Ddata          = np.array_equal(self.D.data, other.D.data)
        shape          = np.array_equal(self.shape, other.shape)

        if (mat_type
            and shape
            and top_factors
            and bottom_factors
            and deltas
            and R
            and Ddata):
            return true
        else:
            print "mat_type", mat_type
            print "shape", shape
            print "top_fact", top_factors
            print "bot_fact", bottom_factors
            print "deltas", deltas
            print "R", R
            print "Data", Ddata
            return false


    cpdef copy(self):
        cdef BandedOperator B = BandedOperator()
        if self.is_mixed_derivative:
            B.thisptr_csr = new _CSRBandedOperator(
                  self.thisptr_csr.data
                , self.thisptr_csr.row_ptr
                , self.thisptr_csr.row_ind
                , self.thisptr_csr.col_ind
                , self.thisptr_csr.operator_rows
                , self.blocks
                , self.thisptr_csr.name
            )
        else:
            B.thisptr_tri = new _TriBandedOperator(
                      self.thisptr_tri.diags
                    , self.thisptr_tri.R
                    , self.thisptr_tri.high_dirichlet
                    , self.thisptr_tri.low_dirichlet
                    , self.thisptr_tri.top_factors
                    , self.thisptr_tri.bottom_factors
                    , self.axis
                    , self.thisptr_tri.operator_rows
                    , self.thisptr_tri.blocks
                    , self.thisptr_tri.has_high_dirichlet
                    , self.thisptr_tri.has_low_dirichlet
                    , self.thisptr_tri.top_is_folded
                    , self.thisptr_tri.bottom_is_folded
                    , self.thisptr_tri.has_residual
                    )
        B.copy_meta_data(self)
        return B


    cpdef emigrate(self, other, tag=""):
        self.copy_meta_data(other)
        if self.is_mixed_derivative:
            return self.emigrate_csr(other, tag)
        else:
            return self.emigrate_tri(other, tag)


    cpdef immigrate(self, tag=""):
        if self.is_mixed_derivative:
            return self.immigrate_csr(tag)
        else:
            return self.immigrate_tri(tag)


    cdef emigrate_csr(self, other, tag=""):
        if tag:
            print "Emigrate CSR:", tag, to_string(self.thisptr_csr)
        assert not (self.thisptr_csr)
        csr = other.D.tocsr()
        coo = csr.tocoo()
        cdef:
            SizedArray[double] *data = to_SizedArray(csr.data, "data")
            SizedArray[int] *row_ptr = to_SizedArray_i(csr.indptr, "row_ptr")
            SizedArray[int] *row_ind = to_SizedArray_i(coo.row, "row_ind")
            SizedArray[int] *col_ind = to_SizedArray_i(csr.indices, "col_ind")

        self.thisptr_csr = new _CSRBandedOperator(
                  data.data
                , row_ptr.data
                , row_ind.data
                , col_ind.data
                , other.D.shape[0]
                , other.blocks
                , tag
                )
        del data, row_ptr, row_ind, col_ind


    cdef immigrate_csr(self, tag=""):
        if tag:
            print "Immigrate CSR:", tag, to_string(self.thisptr_csr)
        assert (self.thisptr_csr)

        data = from_GPUVec(self.thisptr_csr.data)
        indices = from_GPUVec_i(self.thisptr_csr.col_ind)
        indptr = from_GPUVec_i(self.thisptr_csr.row_ptr)

        shp = (self.thisptr_csr.operator_rows,self.thisptr_csr.operator_rows)
        mat = scipy.sparse.csr_matrix((data, indices, indptr), shape=shp).todia()

        cdef BO B = BO((mat.data,mat.offsets), residual=None, inplace=False,
            deltas=self.deltas,
            derivative=self.derivative,
            order=self.order,
            axis=self.axis)
        B.is_mixed_derivative = True
        B.blocks = self.blocks
        return B


    cdef emigrate_tri(self, other, tag=""):
        if tag:
            print "Emigrate Tri:", tag, "<- offsets", other.D.offsets
        assert not self.thisptr_tri

        other = other.copy()

        scipy_to_cublas(other)

        diad = False

        if other.top_fold_status == CAN_FOLD or other.bottom_fold_status == CAN_FOLD:
            diad = True
            other.diagonalize()

        cdef:
            SizedArray[double] *diags = to_SizedArray(other.D.data, "data")
            SizedArray[double] *R = to_SizedArray(other.R, "R")
            SizedArray[double] *low_dirichlet = to_SizedArray(np.atleast_1d(other.dirichlet[0] or [0.0]), "low_dirichlet")
            SizedArray[double] *high_dirichlet = to_SizedArray(np.atleast_1d(other.dirichlet[1] or [0.0]), "high_dirichlet")
            SizedArray[double] *top_factors = to_SizedArray(np.atleast_1d(other.top_factors if other.top_factors is not None else [0.0]), "top_factors")
            SizedArray[double] *bottom_factors = to_SizedArray(np.atleast_1d(other.bottom_factors if other.bottom_factors is not None else [0.0]), "bottom_factors")

        self.thisptr_tri = new _TriBandedOperator(
                  deref(diags)
                , deref(R)
                , deref(high_dirichlet)
                , deref(low_dirichlet)
                , deref(top_factors)
                , deref(bottom_factors)
                , other.axis
                , other.shape[0]
                , other.blocks
                , other.dirichlet[1] is not None
                , other.dirichlet[0] is not None
                , other.top_factors is not None
                , other.bottom_factors is not None
                , other.R is not None
                )

        del diags, R, high_dirichlet, low_dirichlet, top_factors, bottom_factors

        if diad:
            self.undiagonalize()


    cdef immigrate_tri(self, tag=""):
        cdef BO B

        if tag:
            print "Immigrate Tri:", tag, to_string(self.thisptr_tri)
        assert self.thisptr_tri != <void *>0


        bots = from_SizedArray(self.thisptr_tri.bottom_factors)
        tops = from_SizedArray(self.thisptr_tri.top_factors)

        center = 1
        bottom = 2
        if self.top_fold_status == CAN_FOLD:
            center += 1
            bottom += 1
        if self.bottom_fold_status == CAN_FOLD:
            bottom += 1

        block_len = self.thisptr_tri.block_len

        data = np.zeros((bottom+1, self.operator_rows), dtype=float)
        offsets = -np.arange(bottom+1) + center
        data[center-1:center+2, :] = from_SizedArray_2(self.thisptr_tri.diags)

        if self.top_fold_status == CAN_FOLD:
            data[0,::block_len] = tops
        if self.bottom_fold_status == CAN_FOLD:
            data[-1,block_len-1::block_len] = bots

        R = from_SizedArray(self.thisptr_tri.R) if self.thisptr_tri.has_residual else None

        B = BO((data, offsets), residual=R, inplace=False,
            deltas=self.deltas,
            derivative=self.derivative,
            order=self.order,
            axis=self.axis)

        h = tuple(from_SizedArray(self.thisptr_tri.high_dirichlet)) if self.thisptr_tri.has_high_dirichlet else None
        l = tuple(from_SizedArray(self.thisptr_tri.low_dirichlet)) if self.thisptr_tri.has_low_dirichlet else None
        B.dirichlet = [l,h]
        B.blocks = self.thisptr_tri.blocks
        B.top_fold_status = self.top_fold_status
        B.bottom_fold_status = self.bottom_fold_status

        cublas_to_scipy(B)

        B.bottom_factors = bots if B.bottom_fold_status == FOLDED else None
        B.top_factors = tops if B.top_fold_status == FOLDED else None

        B.solve_banded_offsets = (abs(min(B.D.offsets)), abs(max(B.D.offsets)))
        return B


    cpdef diagonalize(self):
        self.thisptr_tri.diagonalize()


    cpdef undiagonalize(self):
        self.thisptr_tri.undiagonalize()


    cpdef cbool is_folded(self):
        return (self.top_fold_status == FOLDED
                or self.bottom_fold_status == FOLDED)


    cpdef apply(self, np.ndarray V, overwrite=False):

        cdef SizedArrayPtr sa_V = SizedArrayPtr(V, "sa_V apply")
        cdef SizedArrayPtr sa_U = SizedArrayPtr()
        sa_U.tag = "sa_U apply"

        if self.thisptr_tri:
            sa_U.store(self.thisptr_tri.apply(deref(sa_V.p)))
        else:
            sa_U.store(self.thisptr_csr.apply(deref(sa_V.p)))

        V = sa_U.to_numpy()

        return V


    cpdef solve(self, np.ndarray V, overwrite=False):
        assert not self.is_mixed_derivative
        cdef SizedArrayPtr sa_V = SizedArrayPtr(V, "sa_V solve")
        cdef SizedArrayPtr sa_U = SizedArrayPtr()
        sa_U.tag = "sa_U solve"
        sa_U.store(self.thisptr_tri.solve(deref(sa_V.p)))
        V = sa_U.to_numpy()
        return V


    cdef inline no_mixed(self):
        if self.is_mixed_derivative:
            raise ValueError("Operation not supported with mixed operator.")


    cpdef fold_top(self, unfold=False):
        self.no_mixed()
        self.thisptr_tri.fold_top(unfold)


    cpdef fold_bottom(self, unfold=False):
        self.no_mixed()
        self.thisptr_tri.fold_bottom(unfold)


    cpdef mul(self, val, inplace=False):
        if inplace:
            self *= val
            return self
        else:
            return self * val
    def __mul__(self, val):
        B = self.copy()
        B.__imul__(val)
        return B
    def __imul__(self, val):
        self.vectorized_scale(np.ones(self.shape[0]) * val)
        return self

    cpdef add(self, val, inplace=False):
        if inplace:
            self += val
            return self
        else:
            return self + val
    def __add__(self, val):
        B = self.copy()
        if isinstance(val, BandedOperator):
            B.add_operator(val)
        else:
            B.add_scalar(val)
        return B
    def __iadd__(self, val):
        if isinstance(val, BandedOperator):
            self.add_operator(val)
        else:
            self.add_scalar(val)
        return self


    cpdef add_operator(BandedOperator self, BandedOperator other):
        """
        Add a second BandedOperator to this one.
        Does not alter self.R, the residual vector.
        """
        # TODO: Move these errors into C++
        if self.is_mixed_derivative:
            raise NotImplementedError("No add to mixed operator")
        elif other.is_mixed_derivative:
            raise NotImplementedError("No add mixed operator to this one")

        if self.axis != other.axis:
            raise ValueError("Both operators must operate on the same axis."
                    " (%s != %s)" % (self.axis, other.axis))

        # Verify that they are compatible
        if self.thisptr_tri.operator_rows != other.thisptr_tri.operator_rows:
            raise ValueError("Both operators must have the same length")
        if self.is_folded():
            raise NotImplementedError("No add to diagonalized operator.")
        elif other.is_folded():
            raise NotImplementedError("No add diagonalized operator to this one.")

        # Copy the data from the other operator over
        # Don't double the dirichlet boundaries!
        self.thisptr_tri.add_operator(deref(other.thisptr_tri))
        return


    cpdef add_scalar(self, float other):
        """
        Add a scalar to the main diagonal
        Does not alter self.R, the residual vector.
        """
        self.thisptr_tri.add_scalar(other)
        return


    cpdef vectorized_scale(self, np.ndarray vector):
        """
        @vector@ is the correpsonding mesh vector of the current dimension.

        Also applies to the residual vector self.R.

        See FiniteDifferenceEngine.coefficients.
        """
        cdef SizedArray[double] *v = to_SizedArray(vector, "Vectorized scale v")
        if self.thisptr_tri:
            self.thisptr_tri.vectorized_scale(deref(v))
        elif self.thisptr_csr:
            self.thisptr_csr.vectorized_scale(deref(v))
        del v

        return


cdef class SizedArrayPtr(object):

    def __init__(self, a=None, tag="Unknown"):
        if a is not None:
            self.from_numpy(a, tag)
            print "imported from numpy in constructor"

    cdef store(self, SizedArray[double] *p, cpp_string tag="Unknown"):
        if self.p:
            raise RuntimeError("SizedArrayPtr is single assignment")
        self.p = new SizedArray[double](deref(p))
        print "SAPtr -> Storing %s:" % tag, to_string(p)

    cpdef from_numpy(self, np.ndarray a, cpp_string tag="Unknown"):
        if self.p:
            print "SizedArrayPtr is single assignment"
            raise RuntimeError("SizedArrayPtr is single assignment")
        self.p = to_SizedArray(a, tag)
        print "Numpy -> Storing %s: %s" % (tag, to_string(self.p))

    cpdef to_numpy(self):
        print "Converting", to_string(deref(self.p))
        print "ndim", self.p.ndim, self.p.shape[0], self.p.shape[1]
        if self.p.ndim == 2:
            a = from_SizedArray_2(deref(self.p))
        else:
            a = from_SizedArray(deref(self.p))
        assert a.ndim == self.p.ndim
        return a

    def __dealloc__(self):
        if self.p:
            print "Freeing %s:" % (self.tag,), to_string(self.p)
            del self.p

    def __str__(self):
        return "SizedArrayPtr (%s)@%s" % (self.tag, to_string(self.p))


cdef inline int sign(int i):
    if i < 0:
        return -1
    else:
        return 1


# @cython.boundscheck(False)
cdef inline unsigned int get_real_index(double[:] haystack, double needle):
    cdef unsigned int length = haystack.shape[0]
    for i in range(length):
        if needle == haystack[i]:
            return i
    raise ValueError("Value not in array: %s" % needle)


# @cython.boundscheck(False)
cdef inline unsigned int get_int_index(int[:] haystack, int needle):
    cdef unsigned int length = haystack.shape[0]
    for i in range(length):
        if needle == haystack[i]:
            return i
    raise ValueError("Value not in array: %s" % needle)


def test_SizedArray_transpose(np.ndarray[ndim=2, dtype=double] v):
    cdef SizedArray[double]* s = to_SizedArray(v, "transpose s")
    v[:] = 0
    s.transpose(1)
    v = from_SizedArray_2(deref(s))
    return v


def test_SizedArray1_roundtrip(np.ndarray[ndim=1, dtype=double] v):
    cdef SizedArray[double]* s = to_SizedArray(v, "Round Trip")
    v[:] = 0
    return from_SizedArray(deref(s))


def test_SizedArray2_roundtrip(np.ndarray[ndim=2, dtype=double] v):
    cdef SizedArray[double]* s = to_SizedArray(v, "Round trip 2")
    v[:,:] = 0
    return from_SizedArray_2(deref(s))


cdef inline SizedArray[double]* to_SizedArray(np.ndarray v, name):
    assert v.dtype.type == np.float64, ("Types don't match! Got (%s) expected (%s)."
                                      % (v.dtype.type, np.float64))
    cdef double *ptr
    if not v.flags.c_contiguous:
        v = v.copy("C")
    return new SizedArray[double](<double *>np.PyArray_DATA(v), v.ndim, v.shape, name)


cdef inline SizedArray[int]* to_SizedArray_i(np.ndarray v, cpp_string name):
    assert v.dtype.type == np.int32, ("Types don't match! Got (%s) expected (%s)."
                                      % (v.dtype.type, np.int32))
    if not v.flags.c_contiguous:
        v = v.copy("C")
    return new SizedArray[int](<int *>np.PyArray_DATA(v), v.ndim, v.shape, name)


cdef inline from_SizedArray_i(SizedArray[int] &v):
    cdef int sz = v.size
    cdef np.ndarray[int, ndim=1] s = np.empty(sz, dtype=int)
    cdef int i
    for i in range(sz):
        s[i] = v.get(i)
    return s


cdef inline from_SizedArray(SizedArray[double] &v):
    sz = v.size
    cdef np.ndarray[double, ndim=1] s = np.empty(sz, dtype=float)
    cdef int i
    for i in range(sz):
        s[i] = v.get(i)
    return s


cdef inline from_SizedArray_2(SizedArray[double] &v):
    assert v.ndim == 2, ("Using from_SizedArray_2 on an array of dim %s" % v.ndim)
    cdef np.ndarray[double, ndim=2] s = np.empty((v.shape[0], v.shape[1]), dtype=float)
    cdef int i, j
    for i in range(v.shape[0]):
        for j in range(v.shape[1]):
            s[i, j] = v.get(i, j)
    return s


cdef inline from_GPUVec(GPUVec[double] &v):
    cdef int sz = v.size(), i
    cdef np.ndarray[double, ndim=1] s = np.empty(sz, dtype=np.float64)
    for i in range(sz):
        s[i] = v[i]
    return s


cdef inline from_GPUVec_i(GPUVec[int] &v):
    cdef int sz = v.size(), i
    cdef np.ndarray[int, ndim=1] s = np.empty(sz, dtype=np.int32)
    for i in range(sz):
        s[i] = v[i]
    return s


cdef cublas_to_scipy(B):
    # Shift because of scipy/cublas row configuration
    for row, o in enumerate(B.D.offsets):
        if o > 0:
            B.D.data[row,o:] = B.D.data[row,:-o]
            B.D.data[row,:o] = 0
        if o < 0:
            B.D.data[row,:o] = B.D.data[row,-o:]
            B.D.data[row,o:] = 0


cdef scipy_to_cublas(B):
    # We have to shift the offsets between scipy and cublas
    for row, o in enumerate(B.D.offsets):
        if o > 0:
            B.D.data[row,:-o] = B.D.data[row,o:]
            B.D.data[row,-o:] = 0
        if o < 0:
            B.D.data[row,-o:] = B.D.data[row,:o]
            B.D.data[row,:-o] = 0
