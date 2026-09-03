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
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Set your LLM API Key (Gemini, Groq, OpenAI, or Anthropic)
# If not provided, Sentinel automatically runs its built-in Autonomous Offline Engine.
$env:GEMINI_API_KEY="your-gemini-key"   # PowerShell
# or export GEMINI_API_KEY="your-gemini-key" # Bash

# 3. Run the unified end-to-end Sentinel Agent
python agent.py

# 4. Open http://localhost:8000/ to view the live investigation dashboard
```

## 5-Minute Pitch & Presentation Script

**[0:00–0:45] The Gap: What Single-Order Scoring Can't See**
> *"Thirdwatch and traditional fraud systems score transactions in real-time at checkout. They are effective at catching obvious bad actors on a single transaction, but they have a structural blind spot: coordinated fraud rings. A syndicate creates 5 fresh accounts, each placing an individually plausible order, but deliberately hops attributes — Account 1 shares a device with Account 2, Account 2 shares an address with Account 3, and Account 3 shares a payment card with Account 4. No single order trips a risk rule, and no single SQL `GROUP BY` sees the whole ring."*

**[0:45–1:45] The Mechanism: Multi-Attribute Graph Traversal**
> *(Show the interactive Network Graph on the dashboard at `http://localhost:8000`)*
> *"Abuse-Ring Sentinel models incoming transactions as a multi-attribute connected graph. Nodes are orders, and weighted edges represent shared hardware devices, delivery drop points, payment fingerprints, and promo codes. By executing graph component discovery, Sentinel traverses the hops and unmasks the entire syndicate as a unified cluster in milliseconds."*

**[1:45–2:45] The Autonomous AI Sentinel Agent**
> *(Click a flagged cluster and showcase the AI Agent forensic report)*
> *"Once candidate clusters are discovered, our Autonomous AI Agent (powered by Gemini / Groq / Sentinel Engine) conducts an automated forensic audit. It analyzes graph topology, account creation velocity, order values, and KYC verification to generate a structured intelligence report: `[OBSERVATION]`, `[ANALYSIS]`, `[VERDICT]`, and `[RECOMMENDED ACTION]`. It flags coordinated attacks while explaining its exact rationale in plain English."*

**[2:45–3:30] False-Positive Resistance: Smart Dampening**
> *(Click a cleared cluster or run `python -m tests.near_miss_case`)*
> *"The biggest fear in fraud prevention is blocking legitimate customers, like roommates or families sharing an apartment address and Wi-Fi. Sentinel solves this through structural dampening: if accounts are mature (>180 days) and KYC-verified, the connection weight is dampened by 85% (0.15x multiplier). The AI Agent recognizes legitimate domestic patterns and issues a `[VERDICT] CLEARED`, preventing costly false declines."*

**[3:30–4:15] The Numbers (Delivered Honestly)**
> *(Point to the Dashboard Metrics bar)*
> *"In our benchmark scan of 3,019 orders, Sentinel discovered the injected fraud rings with 100% recall while delivering a 99.8% Review-Queue Reduction — compressing thousands of raw orders into just a handful of high-signal clusters for human analysts. We state our honest caveat clearly: these metrics validate the detection mechanism on known patterns, and real-world deployment would scale with anonymized production logs."*

**[4:15–5:00] Architecture, Limits & Next Steps**
> *"Sentinel operates as an auditable human-in-the-loop copilot — it flags and recommends, never silently auto-blocking legitimate revenue. For enterprise scale, the batch pipeline transitions cleanly into incremental streaming graph updates via Neo4j or Memgraph with our Supabase cloud sync integration. Sentinel turns disconnected transactions into connected fraud intelligence."*
