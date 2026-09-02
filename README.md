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
scoring/    weighted edges, dampening, clustering, threshold — the auditable core
llm/        plain-English explanation layer, read-only over scoring output
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


