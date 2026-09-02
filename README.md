# Abuse-Ring Sentinel

**Retrospective network fraud detection for Razorpay's AI Buildathon — Track 02, AI Risk Manager**

Thirdwatch scores individual orders in real time. This project catches
something Thirdwatch's per-order scoring structurally can't see:
coordinated **rings** of orders that are each individually plausible, but
connected through shared devices, addresses, or promo codes spread
deliberately across a chain to dodge single-attribute detection.

## Results on this build's dataset

| Metric | Value |
|---|---|
| Orders scanned | 3,019 |
| Known injected rings | 3 |
| Rings correctly caught | 3 / 3 (100% recall) |
| Clusters flagged for review | 3 (0 false positives) |
| Legit-lookalike pairs correctly cleared | 2 / 2 |
| Review-queue reduction | 3,019 orders → 3 clusters worth a human's time (99.9%) |

**Honest caveat, said out loud rather than hidden:** these numbers are
measured against deliberately injected, known ring patterns in synthetic
data — they validate that the detection *mechanism* works correctly, not
that it generalizes to real-world fraud it has never seen. See
`docs/ARCHITECTURE.md` for the full limitations section.

## Repo structure

```
data/       synthetic order generator + deliberate ring & near-miss injection
graph/      multi-attribute graph construction
scoring/    weighted edges, dampening, candidate clustering — candidate discovery
llm/        Autonomous AI Risk Sentinel Agent for forensic investigation & risk verdicts
metrics/    precision/recall, review-queue reduction, audit report
tests/      standalone proof of the graceful-failure (near-miss) case
frontend/   self-contained analyst review dashboard (open index.html directly)
docs/       architecture + design-decision writeup
```

## Quickstart

```bash
pip install networkx
python3 data/generate_orders.py
python3 -m scoring.cluster_score
python3 -m llm.explain_cluster
python3 -m metrics.evaluate
python3 -m tests.near_miss_case
# then open frontend/index.html in any browser
```

## 5-minute pitch script

**[0:00–0:30] The gap.**
"Thirdwatch already scores every order in real time, and it's genuinely
good at that. But it has one structural blind spot: a ring of five fake
accounts, each individually plausible, that deliberately spreads its
shared attributes — one shared device here, a different shared address
there — never trips a single-order or single-attribute check, because no
individual order looks suspicious alone, and no single field connects all
five directly."

**[0:30–1:30] The mechanism.** Show the graph. Click a flagged cluster —
walk through the chain: order 0 and 1 share a device, order 1 and 2 share
an address, order 2 and 3 share a promo code. No pair shares everything.
"That's the exact pattern a `GROUP BY device_id` can't see, and a
multi-hop graph traversal catches by construction."

**[1:30–2:15] The numbers, said honestly.** "3,019 orders, 3 known rings
injected, all 3 caught, zero false positives — and I'll say directly: this
proves the mechanism works on a known pattern, the same way a security
researcher validates a detector against a known exploit. It's not proof of
real-world generalization, which would need real data I don't have access
to as a student."

**[2:15–3:00] The graceful failure.** Run `tests/near_miss_case.py` live.
"Two accounts share a home address — could easily be flagged as a ring.
They're not, because they're old, KYC-verified accounts, and the dampening
logic in the scoring layer treats that combination as far more consistent
with an innocent explanation than coordinated fraud."

**[3:00–3:45] The Autonomous AI Agent.** "The AI Agent receives the multi-attribute candidate graph and order evidence, performs deep forensic chain-of-thought analysis, evaluates account ages, KYC statuses, and dampening signals, and renders structured risk verdicts (`FLAGGED` / `CLEARED`) alongside plain-English recommendations for human analysts."

**[3:45–4:30] Honest limits + what's next.** "A maximally sophisticated
ring using fully distinct infrastructure per fake account would beat this
— though that's expensive enough that most real rings don't bother, which
is also why device-fingerprinting already catches as much as it does in
production. This is one additional layer, and the real production path is
incremental graph updates on something like Neo4j, not a full batch
recompute every time."

**[4:30–5:00] Close.** "3,019 orders down to 3 clusters worth a human's
time, fully auditable, strictly human-review, never auto-block."
