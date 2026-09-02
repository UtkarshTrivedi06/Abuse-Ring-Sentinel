"""
Phase 2 — Graph construction.

Turns a flat list of orders into a graph: every order is a node, and an
edge is drawn between two orders whenever they share an attribute
(device, address, promo code, payment fingerprint). This is what lets a
ring be caught even when it deliberately spreads its shared attributes
across different fields — the connection survives as a multi-hop PATH
through the graph, not a single shared column.
"""

import json
import networkx as nx
from collections import defaultdict

import os

SHARED_ATTRS = ["device_id", "shipping_address", "promo_code", "payment_fingerprint"]


def load_orders(path=None):
    if path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base_dir, "data", "orders.json")
    with open(path) as f:
        return json.load(f)


def build_graph(orders):
    G = nx.Graph()
    for o in orders:
        G.add_node(o["order_id"], **o)

    # index orders by each shared attribute value -> list of order_ids
    attr_index = {attr: defaultdict(list) for attr in SHARED_ATTRS}
    for o in orders:
        for attr in SHARED_ATTRS:
            val = o.get(attr)
            if val:  # skip None (e.g. no promo code used)
                attr_index[attr][val].append(o["order_id"])

    # draw an edge between every pair of orders sharing a value on any attribute
    edge_reasons = defaultdict(list)  # (order_a, order_b) -> ["device_id", "promo_code", ...]
    for attr, index in attr_index.items():
        for val, order_ids in index.items():
            if len(order_ids) < 2:
                continue
            for i in range(len(order_ids)):
                for j in range(i + 1, len(order_ids)):
                    a, b = sorted([order_ids[i], order_ids[j]])
                    edge_reasons[(a, b)].append(attr)

    for (a, b), reasons in edge_reasons.items():
        G.add_edge(a, b, shared_attrs=reasons)

    return G


if __name__ == "__main__":
    orders = load_orders()
    G = build_graph(orders)
    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # sanity check: pull out the neighborhood around one injected ring order
    ring_node = next(o["order_id"] for o in orders if o.get("ring_id") == 0)
    print(f"\nSanity check — neighbors of injected ring-0 order '{ring_node}':")
    for nbr in G.neighbors(ring_node):
        edge_data = G.get_edge_data(ring_node, nbr)
        print(f"  connected to {nbr} via {edge_data['shared_attrs']}")

    # confirm the legit-lookalike pair is connected but ONLY on one weak attribute
    legit_node = next(o["order_id"] for o in orders if "legit0_0" in o["order_id"])
    print(f"\nSanity check — neighbors of legit-lookalike order '{legit_node}':")
    for nbr in G.neighbors(legit_node):
        edge_data = G.get_edge_data(legit_node, nbr)
        print(f"  connected to {nbr} via {edge_data['shared_attrs']}")
