"""Stable bounded graph display layout; coordinates carry no quantitative meaning."""

import math
import networkx as nx
import numpy as np


def readable_positions(graph):
    ids = list(graph.nodes)
    if len(ids) > 24:
        raise ValueError("Görsel yerleşim en fazla24 düğüm.")
    if not ids:
        return {}
    # Raw co-purchase weights can be thousands: do not let them collapse the
    # connected component against its isolates. Weight remains an edge measure.
    initial = nx.spring_layout(graph, seed=47, weight=None, iterations=150)
    xs = [float(initial[n][0] * 260) for n in ids]
    ys = [float(initial[n][1] * 155) for n in ids]
    # Project a minimum screen-space separation, with deterministic pair order. Plain floats do exactly the
    # arithmetic numpy did per pair (same IEEE operations, same order) without its per-call overhead (AW-25:
    # 220 ms -> a few ms); a pass in which no pair moves ends the projection, since later passes change nothing.
    n = len(ids)
    for _ in range(220):
        moved = False
        for i in range(n):
            for j in range(i + 1, n):
                dx, dy = xs[j] - xs[i], ys[j] - ys[i]
                distance = math.sqrt(dx * dx + dy * dy)
                if distance >= 72:
                    continue
                moved = True
                if distance < 1e-9:
                    angle = (i + 1) * (j + 1) * 2.3999632297
                    ux, uy = math.cos(angle), math.sin(angle)
                else:
                    ux, uy = dx / distance, dy / distance
                sx, sy = ux * (72 - distance) * 0.51, uy * (72 - distance) * 0.51
                xs[i] -= sx
                ys[i] -= sy
                xs[j] += sx
                ys[j] += sy
        xs = [min(max(x, -270.0), 270.0) for x in xs]
        ys = [min(max(y, -165.0), 165.0) for y in ys]
        if not moved:
            break
    return {node: np.array([xs[i] / 270, ys[i] / 165]) for i, node in enumerate(ids)}


def positive_communities(graph):
    """Negative similarity is not cohesion; community membership uses positive ties."""
    positive = nx.Graph()
    positive.add_nodes_from(graph.nodes)
    positive.add_edges_from(
        (a, b, {"weight": data.get("weight", 1)})
        for a, b, data in graph.edges(data=True)
        if data.get("signed_weight", data.get("weight", 1)) > 0
    )
    return (
        list(nx.community.greedy_modularity_communities(positive, weight="weight"))
        if positive.number_of_edges()
        else [{n} for n in positive]
    )
