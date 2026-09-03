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

## 5-Minute Presentation Script

**[0:00–0:45] The Problem**
> *"Tools like Thirdwatch are really good at scoring individual transactions in real time. But real fraud rings don't operate as single orders — they work in groups. A fraud ring will spin up 4 or 5 fresh accounts, place completely normal-looking orders, and intentionally mix their details: Order 1 shares a phone with Order 2, Order 2 shares an address with Order 3, and Order 3 shares a card with Order 4. Individually, every order looks safe. And a simple database query like `GROUP BY device_id` completely misses it because no single field connects all of them."*

**[0:45–1:45] How the Graph Works**
> *(Show the network graph on the dashboard at `http://localhost:8000`)*
> *"To fix this, Abuse-Ring Sentinel links incoming orders into a connection graph. Every time two orders share a device, an address, a card, or a promo code, we draw a weighted connection between them. Even if Order 1 and Order 4 have completely different cards and addresses, the graph traverses the intermediate hops and surfaces the entire ring as one single cluster in milliseconds."*

**[1:45–2:45] The AI Agent Breakdown**
> *(Click a flagged cluster in the dashboard to show the AI report)*
> *"Once we have a connected cluster, our AI Agent looks at the full picture — not just the graph score, but account creation dates, KYC status, and order amounts. Instead of giving the fraud team a random black-box score, the agent writes a clear, plain-English summary: what it observed, why it looks suspicious, a clear verdict, and a concrete action to take before dispatch."*

**[2:45–3:30] Avoiding False Positives (The Roommate Problem)**
> *(Click a cleared cluster or point to dampening)*
> *"A big challenge in fraud detection is not annoying real users. Two roommates or family members living in the same apartment will naturally share a shipping address or Wi-Fi. We handle this with dampening: if accounts are older and KYC-verified, the system drops the connection weight by 85%. The AI agent reviews it, recognizes it's just a normal household, and clears the orders without adding friction."*

**[3:30–4:15] The Results**
> *(Point to the metrics at the top of the dashboard)*
> *"In our test run with 3,000+ orders, Sentinel caught 100% of the injected fraud rings and reduced the manual review queue by over 99%. Instead of a human analyst having to sift through thousands of individual orders, they only have to look at a handful of high-signal clusters. To be completely honest, these numbers are tested against synthetic ring patterns to prove the graph and AI logic work, and the next step would be validating on real anonymized merchant logs."*

**[4:15–5:00] Wrap-up**
> *"Sentinel acts as an intelligent assistant for fraud analysts — it explains every decision clearly, cuts manual review time drastically, and stops coordinated rings before fulfillment. Thank you, and I'd love to take any questions!"*
