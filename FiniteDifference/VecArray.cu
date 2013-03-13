#include <thrust/host_vector.h>
#include <thrust/device_vector.h>
#include <thrust/device_free.h>
#include <thrust/device_malloc.h>
#include <thrust/iterator/constant_iterator.h>
#include <thrust/functional.h>
#include <thrust/transform.h>

#include <iostream>
#include <sstream>
#include <algorithm>
#include <cassert>

#include "common.h"
#include "_kernels.h"
#include "VecArray.h"

using thrust::device_malloc;
using thrust::device_free;
using thrust::make_constant_iterator;

namespace impl {
    /* Vector Vector double */
    void pluseq(
        thrust::device_ptr<double> &out,
        thrust::device_ptr<double> &in,
        Py_ssize_t size) {
        thrust::transform(
                in, in+size,
                out,
                out,
                thrust::plus<double>());
    }
    void minuseq(
        thrust::device_ptr<double> &out,
        thrust::device_ptr<double> &in,
        Py_ssize_t size) {
        thrust::transform(
                in, in+size,
                out,
                out,
                thrust::minus<double>());
    }
    void timeseq(
        thrust::device_ptr<double> &out,
        thrust::device_ptr<double> &in,
        Py_ssize_t size) {
        thrust::transform(
                in, in+size,
                out,
                out,
                thrust::multiplies<double>());
    }


    /* Vector Vector int */
    void pluseq(
        thrust::device_ptr<int> &out,
        thrust::device_ptr<int> &in,
        Py_ssize_t size) {
        thrust::transform(
                in, in+size,
                out,
                out,
                thrust::plus<int>());
    }
    void minuseq(
        thrust::device_ptr<int> &out,
        thrust::device_ptr<int> &in,
        Py_ssize_t size) {
        thrust::transform(
                in, in+size,
                out,
                out,
                thrust::minus<int>());
    }
    void timeseq(
        thrust::device_ptr<int> &out,
        thrust::device_ptr<int> &in,
        Py_ssize_t size) {
        thrust::transform(
                in, in+size,
                out,
                out,
                thrust::multiplies<int>());
    }


    /* Vector Scalar double */
    void minuseq(
        thrust::device_ptr<double> &data,
        Py_ssize_t size,
        double x) {
        thrust::transform(
                data, data+size,
                thrust::make_constant_iterator(x),
                data,
                thrust::minus<double>());
    }
    void timeseq(
        thrust::device_ptr<double> &data,
        Py_ssize_t size,
        double x) {
        thrust::transform(
                data, data+size,
                thrust::make_constant_iterator(x),
                data,
                thrust::multiplies<int>());
    }
    void pluseq(
        thrust::device_ptr<double> &data,
        Py_ssize_t size,
        double x) {
        thrust::transform(
                data, data+size,
                thrust::make_constant_iterator(x),
                data,
                thrust::plus<double>());
    }


    /* Vector Scalar int */
    void minuseq(
        thrust::device_ptr<int> &data,
        Py_ssize_t size,
        int x) {
        thrust::transform(
                data, data+size,
                thrust::make_constant_iterator(x),
                data,
                thrust::minus<int>());
    }
    void timeseq(
        thrust::device_ptr<int> &data,
        Py_ssize_t size,
        int x) {
        thrust::transform(
                data, data+size,
                thrust::make_constant_iterator(x),
                data,
                thrust::multiplies<int>());
    }
    void pluseq(
        thrust::device_ptr<int> &data,
        Py_ssize_t size,
        int x) {
        thrust::transform(
                data, data+size,
                thrust::make_constant_iterator(x),
                data,
                thrust::plus<int>());
    }
} // namespace impl