# Architecture — Abuse-Ring Sentinel

## One-line pitch
Thirdwatch (Razorpay's real fraud engine) catches a bad order. This catches
a bad *network* of orders that each individually pass — by tracing shared
signals across a batch instead of scoring one order at a time, and handing
an analyst a plain-English explanation of why five accounts that look
unrelated actually aren't.

## Why this exists next to Thirdwatch, not instead of it
Per-order, real-time scoring has a structural blind spot: a ring that
deliberately spreads its shared attributes across different fields (one
shared device here, a different shared address there) never trips a
single-order or single-attribute check, because no individual order looks
suspicious in isolation, and no single column has two matching values for
the *same pair* every time. This system is explicitly **retrospective**,
not real-time — it runs as a periodic second pass over orders Thirdwatch
already approved, which is also how real fraud ops teams actually combine
real-time and network-level review in practice.

## Pipeline

```
generate_orders.py          build_graph.py             cluster_score.py
  (synthetic orders    →      (multi-attribute      →     (weighted edges,
   + injected rings)           graph construction)          connected components,
                                                              dampening,
                                                              threshold)
                                                                   │
                                                                   ▼
                                                          explain_cluster.py
                                                          (LLM explains the
                                                           decision already made
                                                           — never makes one)
                                                                   │
                                                                   ▼
                                                            evaluate.py
                                                          (precision/recall,
                                                           queue reduction,
                                                           audit log)
                                                                   │
                                                                   ▼
                                                          frontend/index.html
                                                          (analyst review UI)
```

## The core design decision: determinism is the audit trail, not the LLM

`scoring/cluster_score.py` makes every flag/no-flag decision using
reproducible graph math — fixed attribute weights, explicit dampening
rules, a fixed threshold. That file, and its logged output, is the answer
to "how is this auditable and regulator-friendly." The LLM in
`llm/explain_cluster.py` is strictly read-only over that output: it is
given a decision that has already been made and turns it into a sentence a
human can read in five seconds. It cannot flip a flag. This separation is
enforced structurally (a clean function boundary, the LLM never receives
raw unscored data) — not just claimed in the pitch.

## Key design choices, and why

- **Multi-hop graph over pairwise matching.** A ring in this dataset never
  has one pair of orders sharing every attribute — the shared footprint is
  deliberately spread across a chain (order 0↔1 shares a device, 1↔2
  shares an address, 2↔3 shares a promo code). A single-column
  `GROUP BY` only catches direct pairs; graph traversal catches the chain.
- **Differentiated, dampened edge weights, not a flat rule.** Device
  sharing is weighted higher than promo-code sharing, because it's a
  stronger real-world fraud signal. Weights are further dampened when both
  orders involved are old, KYC-verified accounts, or on a
  corporate/shared IP — this is the direct, structural answer to "won't
  this just flag every dorm and every family sharing a home address."
- **Connected components over full community detection.** For a batch this
  size, connected components are exactly as effective as heavier
  algorithms like Louvain, and far easier to explain and defend line by
  line to a reviewer — an intentional simplicity choice, not a limitation.
- **Human review only, never auto-block.** The system's only output is a
  ranked, explained review queue. This is what keeps it inside the
  "strictly defense-only" requirement by construction.

## Honest limitations (stated up front, not waiting to be asked)

- **Precision/recall are measured against known, injected ring patterns in
  synthetic data.** This proves the detection *mechanism* correctly
  identifies a known pattern — the same logic as a security researcher
  validating a detector against a known exploit before real-world testing.
  It does not, by itself, prove generalization to real, unseen fraud
  patterns, which would require real (anonymized) order data this project
  has no access to.
- **A maximally sophisticated ring — fully distinct devices, IPs, and
  addresses per fake account — would not be caught by this mechanism.**
  Most real fraud rings don't go to that expense, which is also why
  device-fingerprinting-based systems like Thirdwatch already catch as
  much as they do in production. This is one additional layer in
  defense-in-depth, not a complete solution.
- **This does not scale to full production volume as a batch recompute.**
  The realistic production path is incremental graph updates on a graph
  database (e.g. Neo4j), recomputing only the subgraph touched by new
  orders — not rebuilding the whole graph on every run. This build
  demonstrates the mechanism at a scale a panel can inspect directly, and
  names the scaling path rather than pretending it's already solved.

## How to run it

```bash
pip install networkx  # matplotlib optional, only used for ad-hoc plotting

python3 data/generate_orders.py       # Phase 1 — generates data/orders.json
python3 -m scoring.cluster_score      # Phase 3 — generates scoring/clusters.json
python3 -m llm.explain_cluster        # Phase 4 — generates llm/explained_clusters.json
python3 -m metrics.evaluate           # Phase 5 — generates metrics/audit_report.json
python3 -m tests.near_miss_case       # Phase 7 — proves the graceful-failure case

# then open frontend/index.html directly in a browser — no server needed,
# the review data is inlined into the page.
```

To use a real Claude API call instead of the offline explanation fallback,
set `ANTHROPIC_API_KEY` in your environment before running
`llm/explain_cluster.py` — no code changes needed, the script detects the
key automatically.
