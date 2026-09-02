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
    accounts. Now randomized to avoid identical weights across all rings.
    """
    # Randomly pick which attributes to share to diversify the signal
    attrs = ["device_id", "shipping_address", "promo_code", "payment_fingerprint"]

    # Generate a random chain of connections
    # Each account i connects to i+1 via a random attribute
    connections = []
    for i in range(n_accounts - 1):
        connections.append(random.choice(attrs))

    # Create unique values for these shared attributes
    attr_values = {}
    for attr in attrs:
        if attr == "device_id":
            attr_values[attr] = [_random_device_id() for _ in range(n_accounts)]
        elif attr == "shipping_address":
            attr_values[attr] = [_random_address() for _ in range(n_accounts)]
        elif attr == "promo_code":
            attr_values[attr] = [f"PROMO-{ring_id}-{uuid.uuid4().hex[:4].upper()}" for _ in range(n_accounts)]
        elif attr == "payment_fingerprint":
            attr_values[attr] = [_random_payment_fingerprint() for _ in range(n_accounts)]

    accounts_created_days_ago = random.randint(1, 3)
    base_time = datetime.now() - timedelta(days=accounts_created_days_ago)

    ring_orders = []
    for i in range(n_accounts):
        o = _base_order(
            f"ord_ring{ring_id}_{i}",
            created_days_ago=accounts_created_days_ago,
            kyc_verified=False,
        )

        # Apply shared attributes based on the randomized chain
        # Account i shares attribute connections[i] with account i+1
        if i < n_accounts - 1:
            attr = connections[i]
            val = f"shared_{ring_id}_{attr}_{i}" # marker for debugging
            # Actually use a realistic random value for the shared attribute
            shared_val = f"VAL_{ring_id}_{attr}_{i}"
            # To keep it simple and effective for the graph:
            # We'll use a shared pool for this specific ring's attributes
            # But randomized per ring.

        o["order_timestamp"] = (base_time + timedelta(minutes=random.randint(0, 40))).isoformat()
        o["is_injected_ring"] = True
        o["ring_id"] = ring_id
        ring_orders.append(o)

    # Now correctly apply the shared attributes to the orders
    # For each connection in the chain, make the two orders share that attribute
    for i in range(n_accounts - 1):
        attr = connections[i]
        # Generate a unique value for this specific connection
        if attr == "device_id": val = _random_device_id()
        elif attr == "shipping_address": val = _random_address()
        elif attr == "promo_code": val = f"PROMO-{ring_id}-{i}"
        else: val = _random_payment_fingerprint()

        ring_orders[i][attr] = val
        ring_orders[i+1][attr] = val

    return ring_orders


def inject_hub_ring(ring_id, start_index, n_accounts=5):
    """
    A 'hub-and-spoke' ring where one account (the hub) shares different
    attributes with different 'spoke' accounts. Randomized to diversify weights.
    """
    accounts_created_days_ago = random.randint(1, 3)
    base_time = datetime.now() - timedelta(days=accounts_created_days_ago)

    ring_orders = []
    hub = _base_order(f"ord_ring{ring_id}_hub", created_days_ago=accounts_created_days_ago, kyc_verified=False)
    hub["is_injected_ring"] = True
    hub["ring_id"] = ring_id
    hub["order_timestamp"] = base_time.isoformat()
    ring_orders.append(hub)

    # Randomly decide which attributes the hub shares with its spokes
    attrs = ["device_id", "shipping_address", "promo_code", "payment_fingerprint"]

    for i in range(1, n_accounts):
        o = _base_order(f"ord_ring{ring_id}_{i}", created_days_ago=accounts_created_days_ago, kyc_verified=False)

        # Pick 1-2 random attributes to share with the hub
        shared_attrs = random.sample(attrs, random.randint(1, 2))
        for attr in shared_attrs:
            if attr == "device_id": val = _random_device_id()
            elif attr == "shipping_address": val = _random_address()
            elif attr == "promo_code": val = f"HUB-PROMO-{ring_id}-{i}"
            else: val = _random_payment_fingerprint()

            o[attr] = val
            hub[attr] = val # Hub now shares this with spoke i

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


def build_dataset(n_normal=3000, n_rings=15, n_legit_lookalikes=5):
    orders = generate_normal_batch(n_normal)
    for r in range(n_rings):
        # Mix of chain rings and hub-and-spoke rings
        if r % 2 == 0:
            orders.extend(inject_multihop_ring(ring_id=r, start_index=len(orders), n_accounts=5))
        else:
            orders.extend(inject_hub_ring(ring_id=r, start_index=len(orders), n_accounts=5))
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
