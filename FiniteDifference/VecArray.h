#ifndef VECARRAY_H
#define VECARRAY_H

#include <thrust/host_vector.h>
#include <thrust/device_vector.h>
#include <thrust/device_free.h>
#include <thrust/device_malloc.h>

#include <iostream>
#include <sstream>
#include <algorithm>
#include <cassert>

#include "common.h"
#include "_kernels.h"

using thrust::device_malloc;
using thrust::device_free;

template <typename T>
struct GPUVec : thrust::device_vector<T> {

    GPUVec() : thrust::device_vector<T>() {}

    template<typename X>
    GPUVec(const X &x)
        : thrust::device_vector<T>(x) {}

    template<typename X, typename Y>
    GPUVec(const X &x, const Y &y)
        : thrust::device_vector<T>(x, y) {}

    template<typename X, typename Y, typename Z>
    GPUVec(const X &x, const Y &y, const Z &z)
        : thrust::device_vector<T>(x, y, z) {}

    GPUVec<T> &operator+=(T x) {
        thrust::transform(
                this->begin(),
                this->end(),
                make_constant_iterator(x),
                this->begin(),
                thrust::plus<T>());
        return *this;
    }

    GPUVec<T> &operator*=(T x) {
        thrust::transform(
                this->begin(),
                this->end(),
                make_constant_iterator(x),
                this->begin(),
                thrust::multiplies<T>());
        return *this;
    }

    inline thrust::device_reference<T> ref() {
        return thrust::device_reference<T>(ptr());
    }

    inline thrust::device_ptr<T> ptr() {
        return thrust::device_ptr<T>(raw());
    }

    inline T *raw() {
        return thrust::raw_pointer_cast(this->data());
    }
};

template <typename T>
struct HostVec : thrust::host_vector<T> {

    HostVec() : thrust::host_vector<T>() {}

    template<typename X>
    HostVec(const X &x)
        : thrust::host_vector<T>(x) {}

    template<typename X, typename Y>
    HostVec(const X &x, const Y &y)
        : thrust::host_vector<T>(x, y) {}

    template<typename X, typename Y, typename Z>
    HostVec(const X &x, const Y &y, const Z &z)
        : thrust::host_vector<T>(x, y, z) {}

    T *raw() {
        return thrust::raw_pointer_cast(this->data());
    }
};


template <typename T>
void print_array(T *a, Py_ssize_t len) {
    std::ostream_iterator<T> out = std::ostream_iterator<T>(std::cout, " ");
    std::copy(a, a+len, out);
}

template <typename T>
std::ostream & operator<<(std::ostream &os, thrust::host_vector<T> const &v) {
    os << "HOST addr(" << &v << ") size(" << v.size() << ")  [ ";
    std::ostream_iterator<T> out = std::ostream_iterator<T>(os, " ");
    std::copy(v.begin(), v.end(), out);
    return os << "]";
}

template <typename T>
std::ostream & operator<<(std::ostream &os, thrust::device_vector<T> const &v) {
    os << "DEVICE addr(" << &v << ") size(" << v.size() << ")  [ ";
    std::ostream_iterator<T> out = std::ostream_iterator<T>(os, " ");
    std::copy(v.begin(), v.end(), out);
    return os << "]";
}

template<typename T>
struct SizedArray {
    bool owner;
    thrust::device_ptr<T> data;
    Py_ssize_t ndim;
    Py_ssize_t size;
    Py_ssize_t shape[8];
    std::string name;


    SizedArray(Py_ssize_t size, std::string name)
        : owner(true), data(device_malloc<T>(size)), ndim(1), size(size), name(name) {
        shape[0] = size;
        sanity_check();
    }

    SizedArray(SizedArray<T> const &S, bool deep)
        : owner(deep),
          data(owner ? device_malloc<T>(S.size) : S.data),
          ndim(S.ndim), size(S.size), name(S.name) {
        // LOG("Owner("<<owner<<")");
        if (owner) {
            thrust::copy(S.data, S.data + S.size, data);
        }
        for (Py_ssize_t i = 0; i < ndim; ++i) {
            shape[i] = S.shape[i];
        }
        sanity_check();
        FULLTRACE;
    }

    SizedArray(T *rawptr, Py_ssize_t size, std::string name, bool from_host)
        : owner(from_host),
          data(),
          ndim(1),
          size(size),
          name(name) {
        // LOG("Owner("<<owner<<")");
        if (owner) {
            data = device_malloc<T>(size);
            thrust::copy(rawptr, rawptr + size, data);
        } else {
            data = thrust::device_pointer_cast(rawptr);
        }
        shape[0] = size;
        sanity_check();
        FULLTRACE;
    }

    SizedArray(T *rawptr, int ndim, intptr_t *s, std::string name, bool from_host)
        : owner(from_host),
          ndim(ndim),
          size(1),
          name(name) {
        // LOG("Owner("<<owner<<")");
        for (Py_ssize_t i = 0; i < ndim; ++i) {
            shape[i] = s[i];
            size *= shape[i];
        }
        if (owner) {
            data = device_malloc<T>(size);
            thrust::copy(rawptr, rawptr + size, data);
        } else {
            data = thrust::device_pointer_cast(rawptr);
        }
        sanity_check();
        FULLTRACE;
    }

    ~SizedArray() {
        // LOG("Owner("<<owner<<") ptr("<<data.get()<<")");
        if (owner) {
            device_free(data);
        }
        FULLTRACE;
    }

    void sanity_check() {
        if (!owner) {
            DIE("Just take ownership for now...");
        }
        if (data.get() == NULL) {
            if (owner) {
                DIE(name << ": Failed to alloc memory of size("<<size<<")");
            } else {
                DIE(name << ": data doesn't point ot anything");
            }
        }
        if (ndim > 8) {
            DIE(name << ": ndim("<<ndim<<") is out of range. Failed to initialize?");
        }
        for (int i = 0; i < ndim; ++i) {
            if (shape[i] == 0) {
                DIE(name << ": shape["<<i<<"] is "<<i<<"... ndim("<<ndim<<")");
            }
        }
    }

    void reshape(Py_ssize_t h, Py_ssize_t w) {
        if (h*w != size) {
            DIE("Height("<<h<<") x Width("<<w<<") != Size("<<size<<")");
        }
        shape[0] = h;
        shape[1] = w;
        ndim = 2;
    }

    void flatten() {
        shape[0] = size;
        shape[1] = 0;
        ndim = 1;
    }

    void transpose(int strategy) {
        if (ndim != 2) {
            /* Skip transposing for 1D case */
            return;
            // DIE("Can only transpose 2D matrix");
        }
        //XXX
        thrust::device_ptr<T> out = device_malloc<T>(size);
        switch (strategy) {
            case 1:
                transposeNoBankConflicts(out.get(), data.get(), shape[0], shape[1]);
                break;
            default:
                DIE("\nUnknown Transpose Strategy")
        }
        reshape(shape[1], shape[0]);
        if (owner) {
            std::swap(out, data);
        } else {
            thrust::copy(out, out+size, data);
        }
        device_free(out);
    }

    std::string show() {
        std::string s0 = to_string(*this);
        std::string s1 = to_string(data);
        return s0 + " (" + s1 + ")";
    }


    int idx(int idx) {
        if (idx < 0 || size <= idx) {
            DIE(name  << " idx("<<idx<<") not in range [0, Size("<<size<<"))");
        }
        return idx;
    }

    int idx(int i, int j) {
        if (ndim != 2) {
            DIE("Can't use 2D index on a 1D array");
        }
        int idx = i * shape[1] + j;
        if (i >= shape[0]) {
            DIE(name  << " i("<<i<<")"
                << "not in range [0, shape[0]("<<shape[0]<<"))");
        };
        if (j >= shape[1]) {
            DIE(name  << " j("<<j<<") "
                "not in range [0, shape[1]("<<shape[1]<<"))");
        };
        if (idx < 0 || size <= idx) {
            DIE("\nNot only are we out of range, but you wrote the"
                << " single-dimension tests wrong, obviously.\n\t"
                << name  << " i("<<i<<") j("<<j<<") Shape("
                <<shape[0]<<','<<shape[1]<<") idx("<<idx
                <<") not in range [0, Size("<<size<<"))\n");
        }
        return idx;
    }

    SizedArray<T> & plus(T x) {
        thrust::transform(
                data, data+size,
                make_constant_iterator(x),
                data,
                thrust::plus<T>());
        return *this;
    }

    SizedArray<T> & times(T x) {
        thrust::transform(
                data, data+size,
                make_constant_iterator(x),
                data,
                thrust::multiplies<T>());
        return *this;
    }


    inline void set(int i, T x) {
        data[idx(i)] = x;
    }
    inline T get(int i) {
        return data[idx(i)];
    }

    inline void set(int i, int j, T x) {
        data[idx(i, j)] = x;
    }
    inline T get(int i, int j) {
        return data[idx(i, j)];
    }
};

template <typename T>
std::ostream & operator<<(std::ostream & os, SizedArray<T> const &sa) {
    std::ostringstream s;
    std::copy(sa.data, sa.data+sa.size, std::ostream_iterator<T>(s, " "));
    return os << sa.name << ": addr("<<&sa<<") size("
        <<sa.size<<") ndim("<<sa.ndim<< ") ["
        << s.str() << " ]";
}


#endif /* end of include guard */
