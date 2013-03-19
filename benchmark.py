#!/usr/bin/env python
# coding: utf8
"""Benchmarking the FiniteDifferenceEngine."""

import sys

from FiniteDifference import utils

from FiniteDifference.Grid import Grid
from FiniteDifference.FiniteDifferenceEngineGPU import FiniteDifferenceEngineADI as FDE_ADI_GPU
from FiniteDifference.heston import HestonOption, HestonBarrierOption, hs_call_vector, HestonFiniteDifferenceEngine
from FiniteDifference.blackscholes import BlackScholesOption

from FiniteDifference.visualize import fp

Opt = HestonOption
Opt = HestonBarrierOption

DefaultHeston = Opt( spot=100
                 , strike=100
                 , interest_rate=0.03
                 , volatility = 0.2
                 , tenor=1.0
                 , mean_reversion = 1
                 , mean_variance = 0.12
                 , vol_of_variance = 0.3
                 , correlation = 0.4
                 )

DefaultHeston = Opt( spot=100
                 , strike=100
                 , interest_rate=0.03
                 , volatility = 0.3
                 , tenor=2.0
                 , mean_reversion = 2
                 , mean_variance = 0.1
                 , vol_of_variance = 0.6
                 , correlation = 0.2
                 )


DefaultHeston = Opt( spot=100
                 , strike=130
                 , interest_rate=-0.1
                 , volatility = 0.43
                 , tenor=2.75
                 , mean_reversion = 4.2
                 , mean_variance = 0.21
                 , vol_of_variance = 0.5
                 , correlation = -0.3
                 )

# DefaultHeston = HestonOption(spot=100 , strike=100 , interest_rate=0.03 , volatility = 0.2
                # , tenor=1.0
                # , mean_reversion = 1
                # , mean_variance = 0.12
                # , vol_of_variance = 0.3
                # , correlation = 0.4
                # )

H = DefaultHeston
H.top = (False, 170)
print H
# H.bottom = (False, 85)

# trims = (H.strike * .2 < spots) & (spots < H.strike * 2.0)
# trimv = (0.0 < vars) & (vars < 1)  # v0*2.0)
# trims = slice(None)
# trimv = slice(None)


def create(nspots=30, nvols=30):
    F = HestonFiniteDifferenceEngine(H, nspots=nspots,
                                        nvols=nvols, spotdensity=10, varexp=4,
                                        var_max=12, verbose=False)
    F.init()
    F.operators[1].diagonalize()
    return F


def run(dt, F=None, func=None, initial=None):
    if F is None:
        F = create()

    if func is None:
        func = 'hv'

    if initial is None:
        initial = F.grid.domain[0].copy()

    funcs = {
        'hv': lambda dt: F.solve_hundsdorferverwer(H.tenor/dt, dt, initial, 0.65),
        'i' : lambda dt: F.solve_implicit(H.tenor/dt, dt, initial),
        'd' : lambda dt: F.solve_douglas(H.tenor/dt, dt, initial, 0.65),
        # 'smooth': lambda dt: F.smooth(H.tenor/dt, dt, smoothing_steps=1, scheme=F.solve_hundsdorferverwer)
        'smooth': lambda dt: F.solve_smooth(H.tenor/dt, dt, initial, smoothing_steps=1)
    }
    labels = {
        'hv': "Hundsdorfer-Verwer",
        'i' : "Fully Implicit",
        'd' : "Douglas",
        'smooth': "Smoothed HV"
    }

    Vs = funcs[func](dt)
    return Vs


def main():
    if len(sys.argv) > 1:
        func = sys.argv[1]
    else:
        func=None

    if len(sys.argv) > 2:
        nspots = int(sys.argv[2])
    else:
        nspots = 200

    if len(sys.argv) > 3:
        nvols = int(sys.argv[3])
    else:
        nvols = 200

    if len(sys.argv) > 4:
        dt = float(sys.argv[4])
    else:
        dt = 1.0 / 252

    print func, nspots, nvols, dt

    F = create(nspots=nspots, nvols=nvols)
    idx = F.idx
    FG = FDE_ADI_GPU(F)
    # mc = F.option.monte_carlo()
    print
    print run(dt, F, func)[idx]
    F.grid.reset()
    print run(dt, FG,func,F.grid.domain[0])[idx], "Estimate:", mc['expected'], "+-", mc['error']
    # print run(dt, FG,func,F.grid.domain[0])[idx], F.option.analytical

if __name__ == '__main__':
    main()
