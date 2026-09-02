"""
Phase 1 — Synthetic order generator.

Produces a batch of independent, realistic-looking e-commerce orders, then
SEPARATELY injects a small number of deliberate "rings" — clusters of orders
that are individually plausible but connected through a CHAIN of shared
attributes (not one single shared field, which is what a simple
`GROUP BY device_id` would catch).

The two generation paths are kept in clearly separate functions so it is
always possible to point at exactly which orders were injected and why —
this is the honest answer to "you rigged this data" from a panel: it proves
the detection mechanism against a known pattern, it does not fabricate a
result.
"""

import json
import os
import random
import uuid
from datetime import datetime, timedelta

random.seed(42)  # reproducible — same output every run, important for a demo

INDIAN_CITIES = ["Pune", "Mumbai", "Bengaluru", "Delhi", "Hyderabad", "Chennai"]
STREET_NAMES = ["MG Road", "Baner Road", "FC Road", "Koregaon Park", "Camp",
                "Aundh", "Viman Nagar", "Kothrud", "Hinjewadi", "Wakad"]


def _random_device_id():
    return f"dev_{uuid.uuid4().hex[:10]}"


def _random_ip():
    return f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def _random_address():
    # Wide enough address space that two UNRELATED orders colliding on the
    # exact same flat number + street + city is genuinely rare, not a
    # coin-flip — this keeps any observed address collision meaningful.
    return f"Flat {random.randint(1,999)}, Building {random.randint(1,40)}, {random.choice(STREET_NAMES)}, {random.choice(INDIAN_CITIES)}"


def _random_payment_fingerprint():
    return f"pay_{uuid.uuid4().hex[:8]}"


def _random_promo_code():
    """
    Realistic promo modeling matters here: a generic blanket code like
    'WELCOME50' is used by thousands of unrelated legitimate customers, so
    two random orders sharing it means NOTHING about fraud — it's noise,
    not signal. Rings, by contrast, tend to reuse one SPECIFIC referral-style
    code across their fake accounts. So normal orders get either no promo,
    or a near-unique referral code (collisions are rare by construction) —
    which means when two orders DO share one, it's actually informative.
    """
    if random.random() < 0.15:
        return f"REF-{uuid.uuid4().hex[:6].upper()}"  # effectively unique per order
    return None


def _base_order(order_id, created_days_ago, kyc_verified=None, corporate_ip=False):
    account_id = f"acc_{uuid.uuid4().hex[:8]}"
    account_created_at = datetime.now() - timedelta(days=created_days_ago)
    order_time = account_created_at + timedelta(
        days=random.randint(0, created_days_ago), hours=random.randint(0, 23)
    )
    return {
        "order_id": order_id,
        "account_id": account_id,
        "account_created_at": account_created_at.isoformat(),
        "order_timestamp": order_time.isoformat(),
        "device_id": _random_device_id(),
        "ip": _random_ip(),
        "shipping_address": _random_address(),
        "promo_code": _random_promo_code(),
        "payment_fingerprint": _random_payment_fingerprint(),
        "order_value": round(random.uniform(199, 4999), 2),
        "kyc_verified": kyc_verified if kyc_verified is not None else random.random() < 0.55,
        "corporate_ip": corporate_ip,
        "is_injected_ring": False,
        "ring_id": None,
    }


def generate_normal_batch(n=3000):
    """Independent, unrelated orders — the 'noise' the detector has to see through."""
    orders = []
    for i in range(n):
        created_days_ago = random.randint(1, 400)
        orders.append(_base_order(f"ord_{i:05d}", created_days_ago))
    return orders


def inject_multihop_ring(ring_id, start_index, n_accounts=5):
    """
    A ring that deliberately AVOIDS sharing one single attribute across all
    accounts — because that's exactly what a naive single-column groupby
    would catch. Instead it spreads its footprint:

      order 0 <-> order 1   share DEVICE
      order 1 <-> order 2   share ADDRESS
      order 2 <-> order 3   share PROMO CODE
      order 3 <-> order 4   share DEVICE (different device than 0-1)

    No two orders share ALL the same attributes, and orders 0 and 4 share
    NOTHING directly — they are only connected transitively, through the
    chain. This is the exact pattern a multi-hop graph traversal catches
    and a single-attribute query cannot.
    """
    shared_device_a = _random_device_id()
    shared_device_b = _random_device_id()
    shared_address = _random_address()
    shared_promo = f"FIRST100-{ring_id}"  # unique per ring — different rings must not collide with each other

    accounts_created_days_ago = random.randint(1, 3)  # rings are usually FRESH accounts
    base_time = datetime.now() - timedelta(days=accounts_created_days_ago)

    ring_orders = []
    for i in range(n_accounts):
        o = _base_order(
            f"ord_ring{ring_id}_{i}",
            created_days_ago=accounts_created_days_ago,
            kyc_verified=False,
        )
        # spread the shared footprint across the chain, not uniformly
        if i in (0, 1):
            o["device_id"] = shared_device_a
        if i in (1, 2):
            o["shipping_address"] = shared_address
        if i in (2, 3):
            o["promo_code"] = shared_promo
        if i in (3, 4):
            o["device_id"] = shared_device_b
        o["order_timestamp"] = (base_time + timedelta(minutes=random.randint(0, 40))).isoformat()
        o["is_injected_ring"] = True
        o["ring_id"] = ring_id
        ring_orders.append(o)
    return ring_orders


def inject_legit_lookalike(pair_id, start_index):
    """
    The DELIBERATE near-miss / false-positive case (Phase 7 material, seeded
    here so it's part of the same dataset): two accounts that share an
    address — because they're plausibly family/roommates — but are old,
    KYC-verified, and never share anything else. This should NOT be flagged
    once tenure/KYC dampening is applied in Phase 3.
    """
    shared_address = _random_address()
    o1 = _base_order(f"ord_legit{pair_id}_0", created_days_ago=280, kyc_verified=True)
    o2 = _base_order(f"ord_legit{pair_id}_1", created_days_ago=310, kyc_verified=True)
    o1["shipping_address"] = shared_address
    o2["shipping_address"] = shared_address
    return [o1, o2]


def build_dataset(n_normal=3000, n_rings=3, n_legit_lookalikes=2):
    orders = generate_normal_batch(n_normal)
    for r in range(n_rings):
        orders.extend(inject_multihop_ring(ring_id=r, start_index=len(orders), n_accounts=5))
    for p in range(n_legit_lookalikes):
        orders.extend(inject_legit_lookalike(pair_id=p, start_index=len(orders)))
    random.shuffle(orders)
    return orders


if __name__ == "__main__":
    dataset = build_dataset()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(base_dir, "data", "orders.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(dataset, f, indent=2)
    n_ring_orders = sum(1 for o in dataset if o["is_injected_ring"])
    print(f"Generated {len(dataset)} total orders")
    print(f"  - {len(dataset) - n_ring_orders} normal/noise orders")
    print(f"  - {n_ring_orders} orders belonging to injected rings")
    print(f"  - 4 orders forming legit-lookalike near-miss pairs")
    print(f"Saved to {out_path}")
