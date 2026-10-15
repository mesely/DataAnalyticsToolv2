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
    points = np.array(
        [[initial[n][0] * 260, initial[n][1] * 155] for n in ids], dtype=float
    )
    # Project a minimum screen-space separation, with deterministic pair order.
    # The bound keeps this inexpensive (<=276 pairs), even with dense graphs.
    for _ in range(220):
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                delta = points[j] - points[i]
                distance = float(np.linalg.norm(delta))
                if distance >= 72:
                    continue
                if distance < 1e-9:
                    angle = (i + 1) * (j + 1) * 2.3999632297
                    direction = np.array([math.cos(angle), math.sin(angle)])
                else:
                    direction = delta / distance
                shift = direction * (72 - distance) * 0.51
                points[i] -= shift
                points[j] += shift
        points[:, 0] = np.clip(points[:, 0], -270, 270)
        points[:, 1] = np.clip(points[:, 1], -165, 165)
    return {
        n: np.array([points[i, 0] / 270, points[i, 1] / 165]) for i, n in enumerate(ids)
    }


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
