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

## How It Works

1. **Multi-Attribute Graph Modeling**: Links incoming transactions across shared device IDs, delivery addresses, payment card fingerprints, and promo codes.
2. **Component Discovery**: Discovers connected clusters to surface multi-hop syndicates that evade single-attribute SQL queries.
3. **Smart False-Positive Dampening**: Applies an 85% score reduction for mature, KYC-verified accounts to prevent flagging legitimate households, dorms, and shared office networks.
4. **Autonomous AI Sentinel Agent**: Runs multi-provider LLM forensic analysis (Gemini / Groq / Offline) to evaluate graph topology and creation velocity, generating plain-English `[OBSERVATION]`, `[ANALYSIS]`, `[VERDICT]`, and `[RECOMMENDED ACTION]` reports.
5. **Analyst Review Console**: Interactive local dashboard with live graph visualization, metric tracking, and single-click cluster escalations.

For the presentation and video demo walkthrough script, see [docs/PITCH_SCRIPT.md](docs/PITCH_SCRIPT.md).
