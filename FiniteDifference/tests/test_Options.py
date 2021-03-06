#!/usr/bin/env python
# coding: utf8

import itertools
import unittest

import numpy as np
import numpy.testing as npt
import scipy.sparse
import scipy.linalg as spl

import FiniteDifference.utils as utils
from FiniteDifference.utils import todia
from FiniteDifference.visualize import fp
import FiniteDifference.Grid as Grid

import FiniteDifference.FiniteDifferenceEngine as FD
import FiniteDifference.FiniteDifferenceEngineGPU as FDG
import FiniteDifference.BandedOperatorGPU as BOG

from FiniteDifference.blackscholes import BlackScholesFiniteDifferenceEngine, BlackScholesOption
from FiniteDifference.heston import HestonOption, HestonBarrierOption, HestonFiniteDifferenceEngine


class BarrierOption_test(unittest.TestCase):

    def setUp(self):
        self.option = HestonBarrierOption()
        self.s = np.array((4.5, 0.2, 5.5, 0, 3, 5.3, 0.001, 24, 1.3, 2.5))
        self.state = np.array((1, 1, 1, 1, 1, 1, 1, 1, 1, 1), dtype=bool)


    def test_knockout_impossible(self):
        s = self.s.copy()
        state = self.state.copy()
        self.option.top = (False, np.infty)
        self.option.monte_carlo_callback(s, state)
        npt.assert_array_equal(np.ones(state.shape), state)


    def test_knockout_inevitable(self):
        self.option.top = (False, 0)
        self.option.monte_carlo_callback(self.s, self.state)
        npt.assert_array_equal(self.state, np.zeros(self.state.shape))


    def test_knockout_partial(self):
        self.option.top = (False, 3.0)
        self.option.monte_carlo_callback(self.s, self.state)
        res = np.array((0,1,0,1,0,0,1,0,1,1), dtype=bool)
        npt.assert_array_equal(self.state, res)


    def test_knockout_permanent(self):
        self.option.top = (False, 3.0)
        self.option.monte_carlo_callback(self.s, self.state)
        res = np.array((0,1,0,1,0,0,1,0,1,1), dtype=bool)
        self.s *= 0
        self.option.monte_carlo_callback(self.s, self.state)
        npt.assert_array_equal(self.state, res)


    def test_knockout_double(self):
        self.option.top = (False, 3.0)
        self.option.bottom = (False, 1.0)
        res = np.array((0,0,0,0,0,0,0,0,1,1), dtype=bool)
        self.option.monte_carlo_callback(self.s, self.state)
        npt.assert_array_equal(self.state, res)


class BlackScholesOption_test(unittest.TestCase):

    def setUp(self):
        v = 0.04
        r = 0.06
        k = 99.0
        spot = 100.0
        t = 1.0
        self.dt = 1.0/150.0
        BS = BlackScholesOption(spot=spot, strike=k, interest_rate=r, variance=v, tenor=t)

        self.F = BlackScholesFiniteDifferenceEngine( BS
                                                   , spot_max=5000.0
                                                   , nspots=150
                                                   , spotdensity=1.0
                                                   , force_exact=True
                                                   , flip_idx_spot=False
                                                     )
        self.F.init()


    def test_implicit(self):
        t, dt = self.F.option.tenor, self.dt
        for o in self.F.operators.values():
            assert o.is_tridiagonal()
        V = self.F.solve_implicit(t/dt, dt)[self.F.idx]
        ans = self.F.option.analytical
        # print "Spot:", self.F.option.spot
        # print "Price:", V, ans, V - ans
        npt.assert_allclose(V, ans, rtol=0.001)


    def test_douglas(self):
        t, dt = self.F.option.tenor, self.dt
        V = self.F.solve_douglas(t/dt, dt)[self.F.idx]
        ans = self.F.option.analytical
        # print "Spot:", self.F.option.spot
        # print "Price:", V, ans, V - ans
        npt.assert_allclose(V, ans, rtol=0.001)


    def test_smooth(self):
        t, dt = self.F.option.tenor, self.dt
        for o in self.F.operators.values():
            assert o.is_tridiagonal()
        V = self.F.solve_smooth(t/dt, dt)[self.F.idx]
        ans = self.F.option.analytical
        # print "Spot:", self.F.option.spot
        # print "Price:", V, ans, V - ans
        npt.assert_allclose(V, ans, rtol=0.001)


class HestonOption_test(unittest.TestCase):

    def setUp(self):
        DefaultHeston = HestonOption(spot=100
                        , strike=100
                        , interest_rate=0.03
                        , volatility = 0.2
                        , tenor=1.0
                        , mean_reversion = 1
                        , mean_variance = 0.12
                        , vol_of_variance = 0.3
                        , correlation = 0.4
                        )
        option = DefaultHeston
        # option = HestonOption(tenor=1, strike=99.0, volatility=0.2,
                                        # mean_reversion=3, mean_variance=0.04,
                                        # vol_of_variance=0.6, correlation=-0.7)


        self.dt = 1.0/150.0
        self.F = HestonFiniteDifferenceEngine(option, nspots=150,
                                                   nvols=80,
                                                   force_bandwidth=None,
                                                   flip_idx_var=False)


        # self.F = HestonFiniteDifferenceEngine(H, nspots=100,
                                         # nvols=100, spotdensity=10, varexp=4,
                                         # var_max=12, flip_idx_spot=False,
                                         # flip_idx_var=False, verbose=False,
                                         # force_bandwidth=None,
                                         # force_exact=False)
        self.F.init()
        self.F.operators[1].diagonalize()


    def test_implicit(self):
        t, dt = self.F.option.tenor, self.dt
        dt = 1.0/600.0
        for d, o in self.F.operators.items():
            if type(d) != tuple:
                assert o.is_tridiagonal(), "%s, %s" % (d, o.D.offsets)
        V = self.F.solve_implicit(t/dt, dt)[self.F.idx]
        ans = self.F.option.analytical
        # print "Spot:", self.F.option.spot
        # print "Price:", V, ans, V - ans
        npt.assert_allclose(V, ans, rtol=0.001)


    def test_douglas(self):
        t, dt = self.F.option.tenor, self.dt
        for d, o in self.F.operators.items():
            if type(d) != tuple:
                assert o.is_tridiagonal(), "%s, %s" % (d, o.D.offsets)
        V = self.F.solve_douglas(t/dt, dt)[self.F.idx]
        ans = self.F.option.analytical
        # print "Spot:", self.F.option.spot
        # print "Price:", V, ans, V - ans
        npt.assert_allclose(V, ans, rtol=0.001)


    def test_smooth(self):
        t, dt = self.F.option.tenor, self.dt
        for d, o in self.F.operators.items():
            if type(d) != tuple:
                assert o.is_tridiagonal(), "%s, %s" % (d, o.D.offsets)
        V = self.F.solve_smooth(t/dt, dt)[self.F.idx]
        ans = self.F.option.analytical
        # print "Spot:", self.F.option.spot
        # print "Price:", V, ans, V - ans
        npt.assert_allclose(V, ans, rtol=0.001)



def main():
    """Run main."""
    import nose
    nose.main()
    return 0

if __name__ == '__main__':
    main()
