"""
Builds the frontend/dashboard_data.json payload from pipeline artifacts.

This is the SINGLE source of truth for how orders/clusters/explanations get
formatted for the dashboard. Two ways to use it:

  1. Standalone: `python build_dashboard_data.py` reads everything from disk
     (useful if you only re-ran part of the pipeline manually).
  2. From agent.py: `format_dashboard_payload()` is called directly with data
     already in memory, so the agent doesn't re-read files it just wrote.

Both paths go through the same `format_dashboard_payload()` function, so the
dashboard's data shape can never drift between the two entry points.
"""

import json
import os


def format_dashboard_payload(orders, clusters, report, explained_lookup=None):
    """
    Core formatting logic, independent of where the data came from.

    orders: list of order dicts
    clusters: list of cluster dicts (from scoring/cluster_score.py)
    report: audit report dict (from metrics/evaluate.py)
    explained_lookup: dict mapping tuple(order_ids) -> explanation string.
        If None, clusters are assumed to already carry "llm_explanation".
    """
    orders_by_id = {o["order_id"]: o for o in orders}

    formatted_clusters = []
    for c in clusters:
        c_orders = {}
        for oid in c["order_ids"]:
            if oid in orders_by_id:
                o = orders_by_id[oid]
                c_orders[oid] = {
                    "kyc_verified": o.get("kyc_verified"),
                    "order_value": o.get("order_value"),
                    "account_created_at": o.get("account_created_at", "")[:10],
                    "shipping_address": o.get("shipping_address"),
                }

        if explained_lookup is not None:
            explanation = explained_lookup.get(tuple(c["order_ids"]))
        else:
            explanation = c.get("llm_explanation")

        formatted_clusters.append({
            "order_ids": c["order_ids"],
            "size": c["size"],
            "total_weight": c["total_weight"],
            "flagged": c["flagged"],
            "edges": c["edges"],
            "explanation": explanation,
            "orders": c_orders,
        })

    return {"clusters": formatted_clusters, "audit": report}


def generate_dashboard_data():
    """Standalone entry point — reads all pipeline artifacts from disk."""
    base_dir = os.path.dirname(os.path.abspath(__file__))

    orders_path = os.path.join(base_dir, "data", "orders.json")
    clusters_path = os.path.join(base_dir, "scoring", "clusters.json")
    explained_path = os.path.join(base_dir, "llm", "explained_clusters.json")
    audit_path = os.path.join(base_dir, "metrics", "audit_report.json")

    if not os.path.exists(orders_path) or not os.path.exists(clusters_path):
        print("Pipeline artifacts missing. Run the pipeline first "
              "(e.g. `python agent.py`).")
        return

    with open(orders_path) as f:
        orders = json.load(f)
    with open(clusters_path) as f:
        clusters = json.load(f)
    with open(audit_path) as f:
        report = json.load(f)

    explained_lookup = {}
    if os.path.exists(explained_path):
        with open(explained_path) as f:
            for c in json.load(f):
                explained_lookup[tuple(c["order_ids"])] = c.get("llm_explanation")

    payload = format_dashboard_payload(orders, clusters, report, explained_lookup)

    out_path = os.path.join(base_dir, "frontend", "dashboard_data.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Updated {out_path}")


if __name__ == "__main__":
    generate_dashboard_data()
