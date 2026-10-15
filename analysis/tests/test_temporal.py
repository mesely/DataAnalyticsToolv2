import csv, json, itertools, math
from collections import defaultdict, Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import pytest
from analysis.worker import handle
from analysis.temporal import aov_interval, edge_comparison
from analysis.adapted.temporal import stage_months


def temporal(**kwargs):
    return handle(
        {
            "action": "temporal",
            "dataset": "demo",
            "month": "2025-02",
            "window": 1,
            "min_shared": 2,
            **kwargs,
        }
    )


def independent_months():
    months = defaultdict(list)
    for row in csv.DictReader(
        (Path(__file__).parents[1] / "data/demo_retail.csv").open()
    ):
        price = Decimal(row["unit_price"])
        quantity = int(row["quantity"])
        if row["invoice"].startswith("C") or price <= 0 or quantity <= 0:
            continue
        pence = int(
            (price * quantity * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        months[row["order_date"][:7]].append((row, pence))
    return months


def test_windows_oracle_and_year_boundary():
    assert stage_months("2025-01", 1, 1) == {
        "pre": ["2024-12"],
        "shock": ["2025-01"],
        "post": ["2025-02"],
    }
    assert len(stage_months("2025-01", 3, 3)["pre"]) == 3
    result = temporal()
    oracle = independent_months()
    for stage in result["stages"]:
        data = [x for month in stage["months"] for x in oracle[month]]
        total = sum(p for _, p in data)
        invoices = {r["invoice"] for r, _ in data}
        products = defaultdict(int)
        for r, p in data:
            products[r["product_id"]] += p
        assert stage["summary"]["gross_pence"] == total
        assert stage["summary"]["orders"] == len(invoices) == 60
        assert stage["summary"]["rows"] == len(data) == 180
        assert stage["summary"]["product_hhi"] == pytest.approx(
            sum((p / total) ** 2 for p in products.values()), abs=1e-6
        )
        assert 1 / len(products) <= stage["summary"]["product_hhi"] <= 1
        interval = stage["aov_bootstrap"]
        assert interval["repetitions"] == 200 and interval["seed"] == 47
        assert (
            interval["interval"][0] < stage["summary"]["aov"] < interval["interval"][1]
        )
    assert sum(s["summary"]["gross_pence"] for s in result["stages"]) == 2140500


def test_edges_same_universe_and_independent_basket_oracle():
    result = temporal()
    universe = {r["product_id"] for r in result["selected_products"]}
    oracle = independent_months()
    for stage in result["stages"]:
        baskets = defaultdict(set)
        for month in stage["months"]:
            for r, _ in oracle[month]:
                if r["product_id"] in universe:
                    baskets[r["invoice"]].add(r["product_id"])
        counts = Counter(
            pair
            for products in baskets.values()
            for pair in itertools.combinations(sorted(products), 2)
        )
        expected = {pair: count for pair, count in counts.items() if count >= 2}
        assert {
            (e["source"], e["target"]): e["weight"] for e in stage["edges"]
        } == expected
        assert stage["edge_count"] <= len(universe) * (len(universe) - 1) / 2
    pre = {(e["source"], e["target"]) for e in result["stages"][0]["edges"]}
    post = {(e["source"], e["target"]) for e in result["stages"][2]["edges"]}
    change = result["graph_comparison"]
    assert change["new_edges"] == len(post - pre) and change["lost_edges"] == len(
        pre - post
    )
    assert change["jaccard"] == pytest.approx(
        len(pre & post) / len(pre | post), abs=1e-6
    )


def test_partial_month_empty_scope_and_null_similarity():
    result = temporal(filters={"country": "France"})
    assert result["stages"][2]["coverage"]["partial"]
    assert result["stages"][2]["coverage"]["covered_days"] == 27
    assert all(s["negative_affinity_share"] is None for s in result["stages"])
    empty = temporal(filters={"start": "2030-01-01"})
    assert all(
        s["summary"]["orders"] == 0
        and s["summary"]["aov"] is None
        and s["summary"]["product_hhi"] is None
        for s in empty["stages"]
    )
    assert empty["graph_comparison"]["jaccard"] is None
    assert all(s["coverage"]["covered_days"] == 0 for s in empty["stages"])
    json.dumps(empty, allow_nan=False)


def test_bootstrap_seed_limits_and_no_silent_sampling():
    values = [1000, 2000, 3000] * 20
    assert aov_interval(values) == aov_interval(values)
    assert aov_interval(values)["n"] == 60
    assert aov_interval([100] * 19)["reason"] == "insufficient_orders"
    assert aov_interval([100] * 50001)["reason"] == "sample_limit"
    assert aov_interval([100] * 20)["interval"] == [1.0, 1.0]
    assert edge_comparison([], [])["jaccard"] is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"month": "../../etc"},
        {"month": "2025-13"},
        {"month": "2030-01"},
        {"window": 0},
        {"window": 4},
        {"window": True},
        {"min_shared": 0},
        {"min_shared": 101},
        {"filters": {"country": "France' OR 1=1"}},
    ],
)
def test_temporal_invalid_inputs(kwargs):
    with pytest.raises(ValueError):
        temporal(**kwargs)


def test_temporal_output_digest_seed_scope_and_threshold():
    a = temporal()
    b = temporal()
    c = temporal(min_shared=3)
    assert (
        a["evidence"]["output_sha256"]
        == b["evidence"]["output_sha256"]
        != c["evidence"]["output_sha256"]
    )
    assert all(
        s["edge_count"] <= a["stages"][i]["edge_count"]
        for i, s in enumerate(c["stages"])
    )
    assert a["evidence"]["dataset_sha256"]


def test_uci_temporal_is_real_and_bounded():
    r = temporal(dataset="uci", month="2011-06", window=1)
    assert len(r["selected_products"]) == 24
    assert all(s["summary"]["orders"] > 1000 for s in r["stages"])
    assert all(s["edge_count"] <= 276 for s in r["stages"])
    assert all(
        s["negative_affinity_share"] is None or 0 <= s["negative_affinity_share"] <= 1
        for s in r["stages"]
    )


def test_dense_weighted_graph_display_keeps_nodes_separate():
    from analysis.worker import graph

    result = graph({"dataset": "uci"})
    nodes = result["nodes"]
    for i, a in enumerate(nodes):
        assert -1.001 <= a["x"] <= 1.001 and -1.001 <= a["y"] <= 1.001
        for b in nodes[i + 1 :]:
            distance = math.hypot((a["x"] - b["x"]) * 270, (a["y"] - b["y"]) * 165)
            assert distance >= 65, (a["id"], b["id"], distance)


def test_signed_communities_do_not_treat_negative_similarity_as_cohesion():
    import networkx as nx
    from analysis.layout import positive_communities

    g = nx.Graph()
    g.add_edge("A", "B", weight=0.8, signed_weight=0.8)
    g.add_edge("B", "C", weight=0.9, signed_weight=-0.9)
    groups = positive_communities(g)
    assert {"A", "B"} in groups and {"C"} in groups


def test_single_country_profile_has_no_spurious_similarity_edges():
    from analysis.worker import graph

    r = graph(
        {
            "dataset": "demo",
            "filters": {"country": "France"},
            "graph_mode": "similarity",
        }
    )
    assert r["edges"] == []
    assert "en az iki ülke" in r["note"]
