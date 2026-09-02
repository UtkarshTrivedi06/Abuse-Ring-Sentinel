"""
Phase 7 — The deliberate "handled gracefully" failure case.

This is not a bug being caught after the fact — it's a scenario built
INTO the dataset from Phase 1 (see `inject_legit_lookalike` in
data/generate_orders.py) specifically to prove the system doesn't just
flag every coincidence. Two accounts share a shipping address (plausibly
family, roommates, or a hostel) but are old and KYC-verified, with no
other shared attributes.

This script is meant to be run on its own, live, as the answer to
"show us a failure your system handles gracefully" — instead of hoping
the right example comes up naturally in the full dataset.
"""

import json
import sys

from graph.build_graph import load_orders, build_graph
from scoring.cluster_score import score_graph
from llm.explain_cluster import explain_cluster


def run_near_miss_test():
    orders = load_orders()
    orders_by_id = {o["order_id"]: o for o in orders}
    G = build_graph(orders)
    clusters = score_graph(G)

    legit_clusters = [
        c for c in clusters
        if any("legit" in oid for oid in c["order_ids"])
    ]

    print("=" * 70)
    print("DELIBERATE FAILURE CASE — legit-lookalike pairs")
    print("=" * 70)

    all_passed = True
    for c in legit_clusters:
        status = "CORRECTLY NOT FLAGGED" if not c["flagged"] else "INCORRECTLY FLAGGED (BUG)"
        if c["flagged"]:
            all_passed = False

        print(f"\nCluster: {c['order_ids']}")
        print(f"  Weighted score: {c['total_weight']} (threshold is 4.0)")
        print(f"  Status: {status}")

        for oid in c["order_ids"]:
            o = orders_by_id[oid]
            print(f"    {oid}: kyc_verified={o['kyc_verified']}, "
                  f"account_age_days~{(_days_since(o['account_created_at']))}")

        explanation, provider, model = explain_cluster(c, orders_by_id)
        print(f"  Explanation: {explanation}")

    print("\n" + "=" * 70)
    if all_passed:
        print("PASS — both legit-lookalike pairs correctly stayed below the "
              "review threshold, despite sharing a real attribute (address).")
    else:
        print("FAIL — a legit-lookalike pair was incorrectly flagged. "
              "Dampening logic in scoring/cluster_score.py needs adjustment.")
    print("=" * 70)
    return all_passed


def _days_since(iso_str):
    from datetime import datetime
    return (datetime.now() - datetime.fromisoformat(iso_str)).days


if __name__ == "__main__":
    passed = run_near_miss_test()
    sys.exit(0 if passed else 1)
