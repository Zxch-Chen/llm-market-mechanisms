import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from mechanisms import (run_double_auction, run_planner, efficiency, payoffs,
                        optimal_welfare, realized_welfare, Buyer, Seller)
from mechanisms.bots import truthful_bid, truthful_ask, make_shaded


def _planner(buyers, sellers, bid, ask):
    return run_planner(buyers, sellers,
                       {b.id: bid(b) for b in buyers},
                       {s.id: ask(s) for s in sellers})


def test_draw_market_is_deterministic():
    b1, s1 = config.draw_market(3)
    b2, s2 = config.draw_market(3)
    assert b1 == b2 and s1 == s2
    assert len(b1) == config.N_BUYERS and len(s1) == config.N_SELLERS
    assert all(0 <= b.value <= 100 for b in b1)


def test_truthful_planner_is_fully_efficient():
    for seed in config.SEEDS:
        buyers, sellers = config.draw_market(seed)
        out = _planner(buyers, sellers, truthful_bid, truthful_ask)
        assert abs(efficiency(out.trades, buyers, sellers) - 1.0) < 1e-9
        # uniform price, individually rational for every trader
        for t in out.trades:
            assert t.price == out.price
        p = payoffs(out.trades, buyers, sellers)
        assert all(x >= -1e-9 for x in p.values())


def test_truthful_double_auction_is_near_efficient():
    es = []
    for seed in config.SEEDS:
        buyers, sellers = config.draw_market(seed)
        da = run_double_auction(buyers, sellers, truthful_bid, truthful_ask, config.N_ROUNDS)
        es.append(efficiency(da.trades, buyers, sellers))
        assert all(x >= -1e-9 for x in payoffs(da.trades, buyers, sellers).values())
    assert min(es) >= 0.95, es


def test_shaded_planner_loses_efficiency():
    bid, ask = make_shaded(config.SHADE_FRACTION)
    es = []
    for seed in config.SEEDS:
        buyers, sellers = config.draw_market(seed)
        out = _planner(buyers, sellers, bid, ask)
        es.append(efficiency(out.trades, buyers, sellers))
    assert all(e <= 1.0 + 1e-9 for e in es)
    assert sum(es) / len(es) < 1.0, es
    assert min(es) < 1.0, es


def test_shaded_double_auction_loses_efficiency():
    bid, ask = make_shaded(config.SHADE_FRACTION)
    es = []
    for seed in config.SEEDS:
        buyers, sellers = config.draw_market(seed)
        da = run_double_auction(buyers, sellers, bid, ask, config.N_ROUNDS)
        es.append(efficiency(da.trades, buyers, sellers))
    assert min(es) < 1.0, es


def test_hand_example():
    buyers = [Buyer("B0", 90), Buyer("B1", 60), Buyer("B2", 30)]
    sellers = [Seller("S0", 20), Seller("S1", 50), Seller("S2", 80)]
    # efficient: (90,20),(60,50) -> W* = 70+10 = 80
    assert optimal_welfare(buyers, sellers) == 80
    out = _planner(buyers, sellers, truthful_bid, truthful_ask)
    assert len(out.trades) == 2 and out.price == 55.0  # midpoint of marginal pair (60,50)
    assert realized_welfare(out.trades, buyers, sellers) == 80
    da = run_double_auction(buyers, sellers, truthful_bid, truthful_ask, 5)
    assert [(t.buyer_id, t.seller_id, t.price) for t in da.trades] == \
        [("B0", "S0", 55.0), ("B1", "S1", 55.0)]
    assert da.round == 2 or da.done  # nothing left to match after round 1 pairs; B2/S2 can't trade


def test_double_auction_state_machine_rejects_missing_bids():
    import pytest
    buyers, sellers = config.draw_market(0)
    from mechanisms import DoubleAuction
    da = DoubleAuction(buyers, sellers)
    with pytest.raises(ValueError):
        da.step({}, {s.id: s.cost for s in sellers})
