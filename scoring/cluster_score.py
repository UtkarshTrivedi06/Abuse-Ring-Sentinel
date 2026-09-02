"""
Phase 3 — Weighting, clustering, and false-positive dampening.

This is the deterministic core of the system: every scoring decision here
is reproducible math, not a model's opinion. That matters for the panel
question "how is this auditable" — the answer is that this file, not the
LLM, is what actually decides what gets flagged. The LLM (Phase 4) only
ever explains a decision this file already made.

Three things happen here:
  1. Different shared attributes get different WEIGHTS (device is a much
     stronger signal than promo code, promo alone is weak).
  2. Weights get DAMPENED for signals that are more likely to be innocent
     coincidence (old, KYC-verified accounts; corporate/shared IP ranges).
  3. The graph is broken into CLUSTERS (connected components — for a
     dataset this size that is more transparent and just as effective as
     full Louvain community detection, and much easier to explain to a
     panel), and each cluster is scored by summing its dampened edge
     weights. Only clusters above a threshold get flagged.
"""

import json
import networkx as nx
from datetime import datetime

from graph.build_graph import load_orders, build_graph

# Base weight per shared-attribute type — how strong a fraud signal it is
# in isolation. Calibrated from how Razorpay's own Thirdwatch documentation
# describes device fingerprinting as the strongest single-order signal.
BASE_WEIGHTS = {
    "device_id": 3.0,
    "shipping_address": 2.0,
    "payment_fingerprint": 2.5,
    "promo_code": 1.5,
}

# A cluster's total dampened weight must reach this to be flagged for review.
FLAG_THRESHOLD = 4.0


def _account_age_days(order):
    created = datetime.fromisoformat(order["account_created_at"])
    return (datetime.now() - created).days


def dampen_edge_weight(order_a, order_b, base_weight):
    """
    Reduce an edge's weight when BOTH orders look like plausibly-innocent
    coincidence rather than coordinated fraud: old accounts, KYC-verified,
    or a corporate/shared IP range (e.g. an office or hostel WiFi). This is
    the direct fix for the "dorms and roommates get flagged" objection —
    it is applied here, structurally, not bolted on as an exception later.
    """
    dampen_factor = 1.0
    both_old = _account_age_days(order_a) > 180 and _account_age_days(order_b) > 180
    both_verified = order_a["kyc_verified"] and order_b["kyc_verified"]
    either_corporate = order_a.get("corporate_ip") or order_b.get("corporate_ip")

    if both_old and both_verified:
        dampen_factor *= 0.15  # near-elimination — this is the strongest innocence signal
    elif both_verified:
        dampen_factor *= 0.5
    if either_corporate:
        dampen_factor *= 0.4

    return base_weight * dampen_factor


def score_graph(G):
    """Returns a list of scored clusters, each with its member orders and total weight."""
    # weight every edge, with dampening applied
    for a, b, data in G.edges(data=True):
        order_a, order_b = G.nodes[a], G.nodes[b]
        total = 0.0
        contributions = {}
        for attr in data["shared_attrs"]:
            base = BASE_WEIGHTS[attr]
            dampened = dampen_edge_weight(order_a, order_b, base)
            total += dampened
            contributions[attr] = round(dampened, 2)
        data["weight"] = total
        data["weight_breakdown"] = contributions

    # connected components = clusters. Simple, transparent, defensible.
    clusters = []
    for component in nx.connected_components(G):
        if len(component) < 2:
            continue  # isolated order, not a cluster
        subG = G.subgraph(component)
        total_weight = sum(d["weight"] for _, _, d in subG.edges(data=True))
        clusters.append({
            "order_ids": sorted(component),
            "size": len(component),
            "total_weight": round(total_weight, 2),
            "flagged": total_weight >= FLAG_THRESHOLD,
            "edges": [
                {"a": a, "b": b, "shared_attrs": d["shared_attrs"], "weight": round(d["weight"], 2)}
                for a, b, d in subG.edges(data=True)
            ],
        })

    clusters.sort(key=lambda c: c["total_weight"], reverse=True)
    return clusters


if __name__ == "__main__":
    orders = load_orders()
    G = build_graph(orders)
    clusters = score_graph(G)

    flagged = [c for c in clusters if c["flagged"]]
    not_flagged = [c for c in clusters if not c["flagged"]]

    print(f"Total clusters found: {len(clusters)}")
    print(f"Flagged for review: {len(flagged)}")
    print(f"Below threshold (not flagged): {len(not_flagged)}\n")

    print("=== FLAGGED CLUSTERS ===")
    for c in flagged:
        print(f"  {c['order_ids']} — weight {c['total_weight']}")

    print("\n=== NOT FLAGGED (includes the legit-lookalike near-miss) ===")
    for c in not_flagged:
        print(f"  {c['order_ids']} — weight {c['total_weight']}")

    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(base_dir, "scoring", "clusters.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(clusters, f, indent=2)
    print(f"\nSaved full cluster output to {out_path}")
