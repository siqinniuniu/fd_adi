# coding: utf8

import numpy as np
cimport numpy as np

from FiniteDifference.VecArray cimport SizedArray

from libcpp.string cimport string as cpp_string
from libcpp cimport bool as cbool

cdef class SizedArrayPtr(object):
    cdef SizedArray[double] *p
    cdef cpp_string tag
    cdef store(self, SizedArray[double] *p, cpp_string tag=*)
    cpdef from_numpy(self, np.ndarray a, cpp_string tag=*)
    cpdef to_numpy(self)
    cpdef SizedArrayPtr copy(self, cbool deep)
    cpdef pluseq(self, SizedArrayPtr other)
    cpdef minuseq(self, SizedArrayPtr other)
    cpdef timeseq(self, SizedArrayPtr other)
    cpdef pluseq_scalar(self, double other)
    cpdef minuseq_scalar(self, double other)
    cpdef timeseq_scalar(self, double other)


cdef class SizedArrayPtr_i(object):
    cdef SizedArray[int] *p
    cdef cpp_string tag
    cdef store(self, SizedArray[int] *p, cpp_string tag=*)
    cpdef from_numpy(self, np.ndarray a, cpp_string tag=*)
    cpdef to_numpy(self)
    cpdef SizedArrayPtr_i copy(self, cbool deep)
    cpdef pluseq(self, SizedArrayPtr_i other)
    cpdef minuseq(self, SizedArrayPtr_i other)
    cpdef timeseq(self, SizedArrayPtr_i other)
    cpdef pluseq_scalar(self, int other)
    cpdef minuseq_scalar(self, int other)
    cpdef timeseq_scalar(self, int other)


cdef from_SizedArray(SizedArray[double] &v)
cdef from_SizedArray_i(SizedArray[int] &v)
cdef SizedArray[double]* to_SizedArray(np.ndarray v, cpp_string name) except +
cdef SizedArray[int]* to_SizedArray_i(np.ndarray v, cpp_string name) except +
