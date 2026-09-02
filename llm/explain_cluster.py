"""
Phase 4 — LLM explanation layer.

CRITICAL DESIGN RULE: the LLM does NOT decide whether a cluster is fraud. Phase 3's
deterministic weighted-graph math already made that call. This file only takes
a cluster that scoring already flagged (or explicitly did NOT flag) and turns
the structured data into a plain-English explanation an analyst can read in
five seconds instead of five minutes.

MULTI-PROVIDER SUPPORT: auto-detects API key in environment.
1. GROQ_API_KEY
2. GEMINI_API_KEY
3. ANTHROPIC_API_KEY
If none, falls back to a clearly-labeled OFFLINE explanation.
"""

import json
import os
import requests

GROQ_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")

if GROQ_KEY:
    ACTIVE_PROVIDER = "groq"
elif GEMINI_KEY:
    ACTIVE_PROVIDER = "gemini"
elif ANTHROPIC_KEY:
    ACTIVE_PROVIDER = "anthropic"
else:
    ACTIVE_PROVIDER = "offline"

SYSTEM_PROMPT = """You are a Senior Fraud Intelligence Analyst. Your task is to transform structured cluster data into a professional Forensic Intelligence Report.

The scoring system has already decided the verdict; your job is to frame the evidence.

STRUCTURE YOUR RESPONSE EXACTLY AS FOLLOWS:
[OBSERVATION]
(A concise summary of the cluster size and the primary connection attributes found.)

[ANALYSIS]
(A detailed forensic breakdown. Explain the 'Chain' pattern if multiple attributes are used. Mention the lack of KYC verification or the suspicious timing of account creation.)

[VERDICT]
(A definitive statement on the risk level: HIGH, MEDIUM, or LOW based on the provided flag.)

[RECOMMENDED ACTION]
(A specific, actionable next step for a human analyst.)

RULES:
1. Be concise and professional.
2. Do NOT invent facts not present in the data. Use only provided data.
3. Do NOT change the verdict decided by the scoring system.
4. Use a forensic, objective tone. Avoid conversational filler."""

def _build_user_prompt(cluster, orders_by_id):
    lines = [f"Cluster verdict (already decided by scoring system): "
             f"{'FLAGGED for review' if cluster['flagged'] else 'NOT flagged'}",
             f"Total weighted connection score: {cluster['total_weight']}",
             f"Number of orders in cluster: {cluster['size']}", "", "Orders:"]
    for oid in cluster["order_ids"]:
        o = orders_by_id[oid]
        lines.append(
            f"  - {oid}: kyc_verified={o['kyc_verified']}, "
            f"order_value=₹{o['order_value']}, created={o['account_created_at'][:10]}"
        )
    lines.append("\nConnections between orders:")
    for e in cluster["edges"]:
        lines.append(f"  - {e['a']} <-> {e['b']} share {e['shared_attrs']} (weight {e['weight']})")
    return "\n".join(lines)

def explain_cluster_groq(cluster, orders_by_id):
    """
    Free tier — Groq. No card required to sign up.
    Tries a short list of current model IDs in order, so a single deprecated
    model name (which has already happened once with this project) doesn't
    silently break the whole AI layer again. Check
    https://console.groq.com/docs/models if all of these ever stop working.
    """
    candidate_models = ["openai/gpt-oss-20b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    last_error = None
    for model in candidate_models:
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "max_tokens": 300,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": _build_user_prompt(cluster, orders_by_id)},
                    ],
                },
                timeout=30,
                # verify=False was removed here on purpose — disabling SSL
                # verification is a real security risk (man-in-the-middle),
                # never re-add it even to "fix" a connection error.
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip(), model
        except Exception as e:
            last_error = e
            continue
    raise last_error


def explain_cluster_gemini(cluster, orders_by_id):
    """Free tier — Google Gemini. No card required in most regions."""
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_KEY}",
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{
                "parts": [{"text": SYSTEM_PROMPT + "\n\n" + _build_user_prompt(cluster, orders_by_id)}]
            }],
            "generationConfig": {"maxOutputTokens": 300},
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip(), "gemini-2.0-flash"


def explain_cluster_anthropic(cluster, orders_by_id):
    """Paid — Claude. Highest quality, used if ANTHROPIC_API_KEY is set and no free key is."""
    import anthropic
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(cluster, orders_by_id)}],
    )
    return response.content[0].text, "claude-sonnet-4-6"

def explain_cluster_offline(cluster, orders_by_id):
    """
    Offline structured fallback — used when NO API key is set, or every live
    provider call failed. This is NOT an LLM call; it's deterministic
    template logic so the pipeline still runs end-to-end with zero setup.
    Never present this as AI-generated output in a demo — the "[OFFLINE]"
    prefix and the llm_provider="offline" field are both there specifically
    so this can't be confused with real model output downstream.
    """
    attrs_involved = set()
    for e in cluster["edges"]:
        attrs_involved.update(e["shared_attrs"])

    all_new = all(
        orders_by_id[oid]["kyc_verified"] is False for oid in cluster["order_ids"]
    )

    if cluster["flagged"]:
        chain_note = ""
        if len(attrs_involved) > 1:
            chain_note = (
                f" Notably, no single pair shares every attribute — the orders are connected "
                f"through a CHAIN across {', '.join(sorted(attrs_involved))}, which is exactly "
                f"the pattern a single-attribute check would miss."
            )
        verified_note = " None of the accounts are KYC-verified." if all_new else ""
        return (
            f"[OFFLINE — not LLM-generated] {cluster['size']} orders form a tightly connected "
            f"cluster (weighted score {cluster['total_weight']}) linked via "
            f"{', '.join(sorted(attrs_involved))}.{chain_note}{verified_note} Recommended action: "
            f"route to a fraud analyst for manual review before dispatch; do not auto-block."
        )
    else:
        return (
            f"[OFFLINE — not LLM-generated] {cluster['size']} orders share "
            f"{', '.join(sorted(attrs_involved))}, but the weighted score "
            f"({cluster['total_weight']}) stays below the review threshold — the accounts "
            f"involved are older and/or KYC-verified, which is far more consistent with an "
            f"innocent explanation (e.g. shared household address) than a coordinated ring. "
            f"Recommended action: no action needed, do not add to review queue."
        )


_PROVIDER_FUNCS = {
    "groq": explain_cluster_groq,
    "gemini": explain_cluster_gemini,
    "anthropic": explain_cluster_anthropic,
}


def explain_cluster(cluster, orders_by_id):
    """
    Returns (explanation_text, provider, model). provider/model let the
    frontend honestly show which system actually produced this text — never
    just "AI" with no attribution.
    """
    if ACTIVE_PROVIDER == "offline":
        return explain_cluster_offline(cluster, orders_by_id), "offline", None
    try:
        text, model = _PROVIDER_FUNCS[ACTIVE_PROVIDER](cluster, orders_by_id)
        return text, ACTIVE_PROVIDER, model
    except Exception as e:
        fallback = (f"[{ACTIVE_PROVIDER} call failed: {e}] Falling back to offline explanation:\n"
                    + explain_cluster_offline(cluster, orders_by_id))
        return fallback, "offline", None


if __name__ == "__main__":
    from graph.build_graph import load_orders
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    orders = load_orders()
    orders_by_id = {o["order_id"]: o for o in orders}
    clusters_path = os.path.join(base_dir, "scoring", "clusters.json")
    with open(clusters_path) as f:
        clusters = json.load(f)
    print(f"Active provider: {ACTIVE_PROVIDER.upper()}\n")
    results = []
    to_explain = [c for c in clusters if c["flagged"]]
    to_explain += [c for c in clusters if not c["flagged"] and "legit" in c["order_ids"][0]][:1]
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
    print(f"Saved to {out_path}")

