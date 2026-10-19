"""Sanity and invariant tests for ZEMIZDAT-SIM-1.0 (fast; small N)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import simulator as S  # noqa: E402


def mk(**kw):
    base = dict(N=60, T=300, sample_s=60, seed=3)
    base.update(kw)
    return S.Sim(S.Params(**base))


@pytest.mark.parametrize("strategy", ["BCAST", "BCAST_RC", "PAIRWISE", "AE_INV", "HYBRID", "ORACLE"])
def test_bookkeeping_invariants(strategy):
    sim = mk(strategy=strategy)
    sim.run()
    # I1 analogue: library counters equal the boolean library
    assert (sim.libn == sim.have.sum(1)).all()
    # complete fragment masks <=> held
    assert ((sim.prog == sim.full) | ~sim.have).all()
    # bucket signatures are exactly the sums over held items
    sig = np.zeros_like(sim.sig)
    r, c = np.nonzero(sim.have)
    np.add.at(sig, (r, sim.bucket[c]), sim.rkey[c])
    assert (sig == sim.sig).all()
    # originators still hold their own pamphlet
    assert sim.have[sim.origin, np.arange(sim.M)].all()


def test_determinism():
    a = S.run(N=50, T=200, seed=9, strategy="HYBRID")
    b = S.run(N=50, T=200, seed=9, strategy="HYBRID")
    for k in ("completeness_mean", "tx_events", "new_fragment_receptions"):
        assert a[k] == b[k]


def test_listeners_get_nothing_from_pairwise():
    out = S.run(N=80, T=600, seed=2, strategy="AE_INV")
    assert out["listen_mean"] is not None
    # a LISTEN device holds no pamphlet of its own and never connects
    assert out["listen_mean"] == 0.0


def test_listen_mode_never_transmits():
    sim = mk(strategy="HYBRID", T=600)
    sim.run()
    assert (sim.tx_time[sim.mode == S.LISTEN] == 0).all()


def test_exchange_mode_never_forwards_third_party():
    sim = mk(strategy="BCAST_RC", T=600, mode_mix=(0.0, 1.0, 0.0))
    sim.run()
    # with only EXCHANGE devices, every holder of item p other than its author got it from
    # the author; check no device ever transmitted: tx only of own (structural) -> each
    # item's coverage only grows via its author, so completeness is still possible but the
    # candidate sets were singletons. Verify structurally:
    assert not sim.can_fwd.any()


def test_unregulated_broadcast_collapses_with_density():
    small = S.run(N=40, T=300, seed=1, strategy="BCAST")
    big = S.run(N=800, T=300, seed=1, strategy="BCAST")
    assert small["G_mean"] < 0.5 < big["G_mean"]
    assert big["completeness_mean"] < small["completeness_mean"]


def test_rate_control_holds_target_load():
    out = S.run(N=800, T=300, seed=1, strategy="BCAST_RC")
    assert out["G_mean"] < 0.5


def test_partition_blocks_dissemination():
    cut = S.run(N=120, T=1800, seed=4, env="barbell", bridges=4, cut_bridges=True, strategy="HYBRID")
    ok = S.run(N=120, T=1800, seed=4, env="barbell", bridges=4, cut_bridges=False, strategy="HYBRID")
    assert cut["completeness_mean"] <= 0.6          # roughly one side's share
    assert ok["completeness_mean"] > cut["completeness_mean"] + 0.2


def test_capacity_respected():
    sim = mk(strategy="HYBRID", capacity=10, T=600)
    sim.run()
    assert (sim.libn + sim.junk <= 10).all()
