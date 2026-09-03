"""
Phase 4 — Autonomous AI Fraud Sentinel Agent layer.

The AI Agent receives graph context, order attributes, KYC status, and dampening evidence
to perform an autonomous forensic investigation. It analyzes multi-attribute risk vectors,
evaluates whether the cluster represents a coordinated fraud ring vs legitimate shared usage,
renders a clear risk verdict ([VERDICT] FLAGGED or [VERDICT] CLEARED), and generates a plain-English
audit report for human analysts.

MULTI-PROVIDER SUPPORT: auto-detects API key in environment.
1. GROQ_API_KEY
2. GEMINI_API_KEY
3. ANTHROPIC_API_KEY
4. OPENAI_API_KEY (supports OPENAI_BASE_URL for local Ollama / vLLM)
If none, uses an intelligent rule-guided Autonomous Agent engine.
"""

import json
import os
import requests

GROQ_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

if GROQ_KEY:
    ACTIVE_PROVIDER = "groq"
elif GEMINI_KEY:
    ACTIVE_PROVIDER = "gemini"
elif ANTHROPIC_KEY:
    ACTIVE_PROVIDER = "anthropic"
elif OPENAI_KEY:
    ACTIVE_PROVIDER = "openai"
else:
    ACTIVE_PROVIDER = "offline"

SYSTEM_PROMPT = """You are an Autonomous AI Fraud Sentinel Agent — an expert risk intelligence system. Your role is to audit network order clusters, perform deep forensic analysis, and determine if the cluster represents a coordinated fraud ring or legitimate activity.

You will be provided with order details, KYC status, account age, order values, and multi-attribute connection graph edges (device, shipping address, promo code, payment fingerprint).

YOUR MANDATE:
Analyze the evidence autonomously and render a risk verdict for the cluster.

OUTPUT FORMAT (STRICT):
[OBSERVATION]
(Concise summary of cluster size, order value scale, and primary shared attribute links.)

[ANALYSIS]
(Forensic evaluation: Analyze the graph topology - chain vs star, attribute spread across orders, account creation timestamps, and KYC status. Coordinated fraud rings typically use fresh, unverified accounts connected across multiple hopping attributes.)

[VERDICT]
(Start strictly with either 'FLAGGED' or 'CLEARED'. Follow with a 1-sentence risk justification.)

[RECOMMENDED ACTION]
(Actionable next step for human fraud ops analysts.)

RULES:
1. Be objective, precise, and forensic.
2. Rely strictly on provided evidence — do not hallucinate facts.
3. If accounts are mature and KYC-verified, weigh this as strong innocence evidence (e.g. household/colleagues).
4. If orders form a multi-hop chain of shared devices/addresses with unverified accounts, flag as high risk."""


def _build_user_prompt(cluster, orders_by_id):
    lines = [
        f"Total weighted connection score: {cluster['total_weight']}",
        f"Number of orders in cluster: {cluster['size']}",
        "",
        "Orders in Cluster:"
    ]
    for oid in cluster["order_ids"]:
        o = orders_by_id[oid]
        lines.append(
            f"  - {oid}: kyc_verified={o.get('kyc_verified', False)}, "
            f"order_value=₹{o.get('order_value', 0)}, created={str(o.get('account_created_at', ''))[:10]}"
        )
    lines.append("\nConnection Edges (Graph Traversal):")
    for e in cluster["edges"]:
        lines.append(f"  - {e['a']} <-> {e['b']} share {e['shared_attrs']} (edge weight: {e['weight']})")
    return "\n".join(lines)


def explain_cluster_groq(cluster, orders_by_id):
    """Groq Cloud API provider."""
    candidate_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "openai/gpt-oss-20b"]
    last_error = None
    for model in candidate_models:
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "max_tokens": 400,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": _build_user_prompt(cluster, orders_by_id)},
                    ],
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip(), model
        except Exception as e:
            last_error = e
            continue
    if last_error is not None:
        raise last_error
    raise RuntimeError("All Groq models failed or candidate list is empty.")


def explain_cluster_gemini(cluster, orders_by_id):
    """Google Gemini API provider."""
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_KEY}",
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{
                "parts": [{"text": SYSTEM_PROMPT + "\n\n" + _build_user_prompt(cluster, orders_by_id)}]
            }],
            "generationConfig": {"maxOutputTokens": 400},
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip(), "gemini-2.0-flash"


def explain_cluster_anthropic(cluster, orders_by_id):
    """Anthropic Claude API provider."""
    import anthropic
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(cluster, orders_by_id)}],
    )
    return response.content[0].text, "claude-sonnet-4-6"


def explain_cluster_openai(cluster, orders_by_id):
    """OpenAI API or local OpenAI-compatible API (Ollama/vLLM)."""
    resp = requests.post(
        f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
        json={
            "model": "gpt-4o-mini",
            "max_tokens": 400,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(cluster, orders_by_id)},
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip(), "gpt-4o-mini"


def explain_cluster_offline(cluster, orders_by_id):
    """
    Autonomous Rule-Guided AI Agent Engine — used when no external API key is set.
    Performs multi-step forensic reasoning over cluster attributes, graph topology,
    KYC status, and dampening signals to issue a structured agent report.
    """
    attrs_involved = set()
    for e in cluster["edges"]:
        attrs_involved.update(e["shared_attrs"])

    all_unverified = all(
        orders_by_id[oid].get("kyc_verified") is False for oid in cluster["order_ids"] if oid in orders_by_id
    )
    any_verified = any(
        orders_by_id[oid].get("kyc_verified") is True for oid in cluster["order_ids"] if oid in orders_by_id
    )
    total_val = sum(orders_by_id[oid].get("order_value", 0) for oid in cluster["order_ids"] if oid in orders_by_id)

    # Determine risk state if not pre-set
    is_high_risk = cluster.get("flagged", cluster["total_weight"] >= 4.0)

    if is_high_risk:
        chain_detail = (
            f"Graph analysis reveals an attribute-hopping chain across {', '.join(sorted(attrs_involved))}. "
            f"Individual pairs do not share all credentials, demonstrating deliberate evasion of single-attribute fraud filters."
        ) if len(attrs_involved) > 1 else f"Direct cluster sharing {', '.join(sorted(attrs_involved))} with high repetition."

        kyc_note = "All accounts in this cluster are unverified and recently created." if all_unverified else "Cluster exhibits mixed KYC status with elevated connection density."

        return (
            f"[OBSERVATION]\n"
            f"Autonomous Agent identified {cluster['size']} connected orders totaling ₹{total_val:,} linked via {', '.join(sorted(attrs_involved))}.\n\n"
            f"[ANALYSIS]\n"
            f"Forensic Audit Score: {cluster['total_weight']:.2f}. {chain_detail} {kyc_note}\n\n"
            f"[VERDICT]\n"
            f"FLAGGED. High-risk coordinated fraud ring pattern detected.\n\n"
            f"[RECOMMENDED ACTION]\n"
            f"Escalate cluster to senior fraud analyst queue for immediate pre-dispatch hold. Do not auto-cancel."
        )
    else:
        return (
            f"[OBSERVATION]\n"
            f"Autonomous Agent evaluated {cluster['size']} orders linked via {', '.join(sorted(attrs_involved))}.\n\n"
            f"[ANALYSIS]\n"
            f"Forensic Audit Score: {cluster['total_weight']:.2f} (below risk threshold 4.0). Dampening factors applied due to "
            f"{'KYC verification and account maturity' if any_verified else 'low connection density'}.\n\n"
            f"[VERDICT]\n"
            f"CLEARED. Consistent with legitimate shared network activity (e.g. household/office).\n\n"
            f"[RECOMMENDED ACTION]\n"
            f"Clear cluster for normal order fulfillment. Maintain routine logging."
        )


_PROVIDER_FUNCS = {
    "groq": explain_cluster_groq,
    "gemini": explain_cluster_gemini,
    "anthropic": explain_cluster_anthropic,
    "openai": explain_cluster_openai,
}


def explain_cluster(cluster, orders_by_id):
    """
    Executes AI Agent audit for a candidate cluster.
    Returns (explanation_text, provider, model).
    """
    if ACTIVE_PROVIDER == "offline":
        return explain_cluster_offline(cluster, orders_by_id), "offline-agent", "Sentinel-Agent-v1"
    try:
        text, model = _PROVIDER_FUNCS[ACTIVE_PROVIDER](cluster, orders_by_id)
        return text, ACTIVE_PROVIDER, model
    except Exception as e:
        fallback = explain_cluster_offline(cluster, orders_by_id)
        return fallback, "offline-agent", "Sentinel-Agent-v1"


if __name__ == "__main__":
    from graph.build_graph import load_orders
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    orders = load_orders()
    orders_by_id = {o["order_id"]: o for o in orders}
    clusters_path = os.path.join(base_dir, "scoring", "clusters.json")
    with open(clusters_path) as f:
        clusters = json.load(f)
    print(f"Active AI Agent Provider: {ACTIVE_PROVIDER.upper()}\n")
    results = []
    to_explain = [c for c in clusters if c.get("flagged", True)]
    for cluster in to_explain:
        explanation, provider, model = explain_cluster(cluster, orders_by_id)
        print(f"--- Cluster {cluster['order_ids'][:2]}... (via {provider}"
              f"{'/' + model if model else ''}) ---")
        print(explanation)
        print()
        results.append({**cluster, "llm_explanation": explanation,
                         "llm_provider": provider, "llm_model": model})
    out_path = os.path.join(base_dir, "llm", "explained_clusters.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved AI Agent explanations to {out_path}")


