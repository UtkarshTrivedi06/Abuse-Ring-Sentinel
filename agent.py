# -*- coding: utf-8 -*-
"""
Abuse-Ring Sentinel - Unified AI Agent
=======================================
A single autonomous agent that runs the full fraud detection pipeline
end-to-end, then serves the analyst dashboard locally.

  python agent.py [--serve] [--port 8000] [--no-regen]

Phases:
  1  Data generation        synthetic orders + injected rings
  2  Graph construction     multi-attribute edge graph
  3  Cluster scoring        weighted dampened edge scoring
  4  LLM explanation        plain-English analyst summaries
  5  Metrics evaluation     precision / recall / queue-reduction
  6  Dashboard build        compile frontend/dashboard_data.json
  7  Serve  (optional)      local HTTP server on --port

Each phase is tracked with wall-clock timing and a clear pass/fail status.
The agent is fully autonomous: all paths are resolved relative to this
file so it works on any OS without manual path editing.
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler

try:
    from supabase import create_client, Client
except ImportError:
    Client = None

# ── resolve repo root ─────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)          # make package imports work

# Force UTF-8 on Windows to prevent cp1252 UnicodeEncodeErrors
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── terminal colours (no external deps) ───────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
VIOLET = "\033[95m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"

def _supports_color():
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

USE_COLOR = _supports_color()

def c(text, *codes):
    if not USE_COLOR:
        return text
    return "".join(codes) + str(text) + RESET


# ── pretty printer ─────────────────────────────────────────────────────────────
AGENT_TAG  = c(" AGENT ", BOLD, "\033[45m")   # violet bg
PHASE_TAG  = lambda n: c(f"  P{n}  ", BOLD, "\033[44m")  # blue bg
OK_TAG     = c("  OK  ", BOLD, "\033[42m")    # green bg
FAIL_TAG   = c(" FAIL ", BOLD, "\033[41m")    # red bg
INFO_TAG   = c(" INFO ", DIM)

WIDTH = 72

def ruler(ch="="):
    return c(ch * WIDTH, DIM)

def header():
    print()
    print(ruler("="))
    print(c("  [*]  Abuse-Ring Sentinel  -  Unified AI Agent", BOLD, WHITE))
    print(c(f"      {datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}  -  Razorpay AI Buildathon", DIM))
    print(ruler("="))
    print()

PIPELINE_LOG = []  # real record of what actually ran, exposed to the dashboard as an honest "Agent Run Log"

def phase_start(n, name, description):
    print(f"  {PHASE_TAG(n)}  {c(name, BOLD, WHITE)}")
    print(f"         {c(description, DIM)}")
    PIPELINE_LOG.append({"phase": n, "name": name, "description": description,
                          "status": "running", "elapsed_s": None, "detail": None})

def phase_done(name, elapsed, detail=""):
    tail = f"  {c(detail, DIM)}" if detail else ""
    print(f"  {OK_TAG}  {c(name, GREEN)}  {c(f'{elapsed:.2f}s', DIM)}{tail}")
    print()
    for entry in reversed(PIPELINE_LOG):
        if entry["status"] == "running":
            entry["status"] = "ok"
            entry["elapsed_s"] = round(elapsed, 3)
            entry["detail"] = detail
            break

def phase_fail(name, err):
    print(f"  {FAIL_TAG}  {c(name, RED)}")
    print(f"         {c(str(err), RED)}")
    print()
    for entry in reversed(PIPELINE_LOG):
        if entry["status"] == "running":
            entry["status"] = "failed"
            entry["detail"] = str(err)
            break

def info(msg):
    print(f"  {INFO_TAG}  {c(msg, DIM)}")

def result_row(label, value, color=WHITE):
    pad = max(1, 32 - len(label))
    print(f"         {c(label, DIM)}{' ' * pad}{c(str(value), BOLD, color)}")


def verify_dependencies(auto_fix=False):
    """
    Ensure HARD requirements are installed. Soft/optional packages
    (matplotlib, anthropic, supabase) are reported as informational notes,
    never as a blocking failure — the whole point of the multi-provider and
    Supabase-optional design is that the pipeline runs with zero setup
    beyond networkx + requests.
    """
    HARD_REQUIRED = {"networkx", "requests"}
    SOFT_OPTIONAL = {
        "matplotlib": "only needed if you manually plot the raw graph",
        "anthropic": "only needed if ANTHROPIC_API_KEY is set",
        "supabase": "only needed if SUPABASE_URL/SUPABASE_KEY are set",
    }

    req_path = os.path.join(ROOT, "requirements.txt")
    if not os.path.exists(req_path):
        return True

    with open(req_path, "r") as f:
        reqs = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    import importlib.util
    missing_hard, missing_soft = [], []
    for req in reqs:
        pkg_name = req.split(">=")[0].split("==")[0].split("<=")[0].strip()
        found = importlib.util.find_spec(pkg_name) is not None
        if not found:
            if pkg_name in HARD_REQUIRED:
                missing_hard.append(pkg_name)
            elif pkg_name in SOFT_OPTIONAL:
                missing_soft.append(pkg_name)

    for pkg in missing_soft:
        info(f"Optional package '{pkg}' not installed ({SOFT_OPTIONAL[pkg]}) — continuing without it.")

    if not missing_hard:
        return True

    print(f"\n{FAIL_TAG}  {c('Dependency Error', RED)}")
    print(f"         {c('The following REQUIRED packages are missing from your current Python environment:', RED)}")
    for m in missing_hard:
        print(f"         - {m}")
    missing = missing_hard

    if auto_fix:
        print(f"\n{INFO_TAG}  {c('Attempting to auto-fix dependencies...', DIM)}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_path])
            print(f"  {OK_TAG}  {c('Dependencies installed successfully!', GREEN)}")
            return True
        except Exception as e:
            print(f"  {FAIL_TAG}  {c('Auto-fix failed:', RED)} {e}")

    print(f"\n{BOLD}To fix this, please run the following command in your terminal:{RESET}")
    print(f"  {c(f'{sys.executable} -m pip install -r requirements.txt', CYAN, BOLD)}")
    print()
    return False


# ── phase implementations ──────────────────────────────────────────────────────

def phase1_generate(n_normal, n_rings, n_legit):
    """Generate synthetic order dataset."""
    from data.generate_orders import build_dataset
    t0 = time.perf_counter()
    phase_start(1, "Data Generation",
                f"Generating {n_normal} normal orders + {n_rings} rings + {n_legit} legit lookalikes")
    orders = build_dataset(n_normal=n_normal, n_rings=n_rings, n_legit_lookalikes=n_legit)
    out = os.path.join(ROOT, "data", "orders.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(orders, f, indent=2)
    n_ring = sum(1 for o in orders if o["is_injected_ring"])
    phase_done("Data generation", time.perf_counter() - t0,
               f"{len(orders)} orders  ·  {n_ring} ring-injected  ·  {len(orders)-n_ring} normal")
    return orders


def phase2_graph(orders):
    """Build multi-attribute connection graph."""
    from graph.build_graph import build_graph
    t0 = time.perf_counter()
    phase_start(2, "Graph Construction",
                "Drawing edges between orders sharing device / address / promo / payment fingerprint")
    G = build_graph(orders)
    phase_done("Graph construction", time.perf_counter() - t0,
               f"{G.number_of_nodes()} nodes  ·  {G.number_of_edges()} edges")
    return G


def phase3_find_candidates(G):
    """Find all candidate clusters (connected components) for AI investigation."""
    from scoring.cluster_score import find_candidate_clusters
    t0 = time.perf_counter()
    phase_start(3, "Candidate Discovery",
                "Identifying all connected order clusters via multi-attribute graph")
    candidates = find_candidate_clusters(G)
    phase_done("Candidate discovery", time.perf_counter() - t0,
               f"{len(candidates)} candidate clusters found")
    return candidates


def phase4_ai_audit(candidates, orders):
    """AI Agent investigates each candidate cluster to determine if it's a fraud ring."""
    from llm.explain_cluster import explain_cluster, ACTIVE_PROVIDER
    t0 = time.perf_counter()
    mode = f"{ACTIVE_PROVIDER.upper()} (live)" if ACTIVE_PROVIDER != "offline" else "offline fallback"
    phase_start(4, "AI Investigation",
                f"Agent is auditing candidates via {mode}")

    orders_by_id = {o["order_id"]: o for o in orders}
    results = []
    actual_provider_used = "offline"

    for cluster in candidates:
        # The AI agent now DECIDES the verdict based on the evidence
        explanation, provider, model = explain_cluster(cluster, orders_by_id)

        if provider != "offline":
            actual_provider_used = provider

        # Parse the [VERDICT] section to set the flagged status
        # We look for 'FLAGGED' or 'CLEARED' in the verdict section
        is_flagged = False
        if explanation:
            # Extract the content after [VERDICT]
            try:
                verdict_part = explanation.split("[VERDICT]")[1].split("[")[0]
                if "FLAGGED" in verdict_part.upper():
                    is_flagged = True
            except IndexError:
                # Fallback: if no [VERDICT] tag, use a simple keyword check
                if "FLAGGED" in explanation.upper():
                    is_flagged = True

        results.append({
            **cluster,
            "llm_explanation": explanation,
            "llm_provider": provider,
            "llm_model": model,
            "flagged": is_flagged,
        })

    out = os.path.join(ROOT, "llm", "explained_clusters.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(results, f, indent=2)

    real_mode = f"{actual_provider_used.upper()} (live)" if actual_provider_used != "offline" else mode
    phase_done("AI investigation", time.perf_counter() - t0,
               f"{len(candidates)} clusters audited · {sum(1 for r in results if r['flagged'])} flagged · {real_mode}")
    return results


def phase5_evaluate(orders, clusters):
    """Compute precision / recall / queue-reduction metrics."""
    from metrics.evaluate import evaluate
    t0 = time.perf_counter()
    phase_start(5, "Metrics Evaluation",
                "Computing precision, recall, and review-queue reduction")
    report = evaluate(orders, clusters)
    out = os.path.join(ROOT, "metrics", "audit_report.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    phase_done("Metrics evaluation", time.perf_counter() - t0)
    return report


def phase6_dashboard(orders, explained_clusters, report):
    """
    Compile frontend/dashboard_data.json.

    Delegates the actual formatting to build_dashboard_data.py's
    format_dashboard_payload() — the same function the standalone
    `python build_dashboard_data.py` script uses — so the dashboard's data
    shape is defined in exactly one place, not reimplemented here.
    explained_clusters already carry "llm_explanation" inline (see
    phase4_explain), so no separate lookup table is needed here.
    """
    from build_dashboard_data import format_dashboard_payload
    t0 = time.perf_counter()
    phase_start(6, "Dashboard Build",
                "Compiling frontend/dashboard_data.json from pipeline artifacts")
    payload = format_dashboard_payload(orders, explained_clusters, report)
    elapsed_so_far = time.perf_counter() - t0
    # Phase 6 is writing the very file that records its own log entry, so it
    # can't observe its own "done" status honestly — approximate it here
    # (a few ms of inaccuracy) rather than leave the entry stuck on
    # "running", which would look like the pipeline hung when it didn't.
    log_snapshot = [dict(entry) for entry in PIPELINE_LOG]
    log_snapshot[-1].update(status="ok", elapsed_s=round(elapsed_so_far, 3),
                             detail=f"frontend/dashboard_data.json  ·  {len(payload['clusters'])} clusters")
    payload["pipeline_log"] = log_snapshot
    out = os.path.join(ROOT, "frontend", "dashboard_data.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(payload, f, indent=2)
    phase_done("Dashboard build", time.perf_counter() - t0,
               f"frontend/dashboard_data.json  ·  {len(payload['clusters'])} clusters")
    return out


def upload_to_supabase(orders, clusters, report):
    """
    Uploads pipeline results to Supabase.
    Optional: Only runs if SUPABASE_URL and SUPABASE_KEY are set.
    """
    if Client is None:
        info("Supabase client not installed. Skipping DB upload.")
        return

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        info("SUPABASE_URL or SUPABASE_KEY not set. Skipping DB upload.")
        return

    try:
        t0 = time.perf_counter()
        phase_start(7, "Supabase Sync", "Uploading pipeline artifacts to cloud database")
        supabase: Client = create_client(url, key)

        # 1. Upload Orders
        # Transform orders to match schema
        order_data = []
        for o in orders:
            order_data.append({
                "id": o["order_id"],
                "value": o.get("order_value"),
                "kyc_verified": o.get("kyc_verified"),
                "account_created_at": o.get("account_created_at"),
                "shipping_address": o.get("shipping_address"),
                "device_id": o.get("device_id"),
                "promo_code": o.get("promo_code"),
                "is_injected_ring": o.get("is_injected_ring", False)
            })
        # Clear old data for fresh batch
        supabase.table("orders").delete().neq("id", "keep-all").execute() # simple way to clear
        supabase.table("orders").insert(order_data).execute()

        # 2. Upload Clusters & Members
        # Clear old clusters
        supabase.table("clusters").delete().neq("id", "keep-all").execute()

        for c in clusters:
            # Note: we use the a list of order_ids as a unique key if we don't have a UUID
            # But for simplicity in this buildathon, we just insert
            cluster_res = supabase.table("clusters").insert({
                "total_weight": c["total_weight"],
                "flagged": c["flagged"],
                "explanation": c.get("llm_explanation"),
                "confidence_score": 0.98 if c["flagged"] else 0.12
            }).execute()

            if cluster_res.data:
                cluster_id = cluster_res.data[0]["id"]
                members = [{"cluster_id": cluster_id, "order_id": oid} for oid in c["order_ids"]]
                supabase.table("cluster_members").insert(members).execute()

        phase_done("Supabase sync", time.perf_counter() - t0, f"Synced {len(orders)} orders and {len(clusters)} clusters")

    except Exception as e:
        phase_fail("Supabase sync", e)

def summary(orders, clusters, report, t_total):
    flagged  = [c for c in clusters if c["flagged"]]
    recall   = report.get("recall_on_injected_rings", 0) or 0
    reduc    = report["review_queue_reduction"]["reduction_pct"]
    fp       = report.get("false_positive_clusters", 0)

    print(ruler("-"))
    print(f"  {c('Pipeline Summary', BOLD, WHITE)}\n")
    result_row("Orders scanned",           f"{len(orders):,}", CYAN)
    result_row("Clusters found",           len(clusters), CYAN)
    result_row("Rings flagged",            len(flagged), YELLOW)
    result_row("False-positive clusters",  fp, RED if fp else GREEN)
    result_row("Recall on known rings",    f"{recall*100:.0f}%", GREEN)
    result_row("Review-queue reduction",   f"{reduc:.1f}%", GREEN)
    result_row("Total pipeline time",      f"{t_total:.2f}s", CYAN)
    print()
    print(f"  {c('Honest caveat:', DIM)} {c('Numbers measured against known injected rings in synthetic data.', DIM)}")
    print(f"  {c('           Real-world generalization requires real (anonymized) order data.', DIM)}")
    print()
    print(ruler("="))
    print()


def phase7_serve(port, frontend_dir):
    """Start a non-blocking HTTP server and print the URL."""
    os.chdir(frontend_dir)

    class _Handler(SimpleHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # silence default request logging

        def do_POST(self):
            if self.path == '/check':
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                try:
                    new_order = json.loads(post_data)

                    # 1. Load existing orders
                    orders_path = os.path.join(ROOT, "data", "orders.json")
                    with open(orders_path, "r") as f:
                        orders = json.load(f)

                    # 2. Add new order
                    orders.append(new_order)

                    # 3. Run the pipeline for this specific order
                    from graph.build_graph import build_graph
                    from scoring.cluster_score import find_candidate_clusters
                    from llm.explain_cluster import explain_cluster

                    G = build_graph(orders)
                    candidates = find_candidate_clusters(G)

                    # Find the cluster containing our new order
                    target_oid = new_order["order_id"]
                    target_cluster = next((c for c in candidates if target_oid in c["order_ids"]), None)

                    if target_cluster:
                        orders_by_id = {o["order_id"]: o for o in orders}
                        explanation, provider, model = explain_cluster(target_cluster, orders_by_id)

                        is_flagged = False
                        if explanation:
                            try:
                                verdict_part = explanation.split("[VERDICT]")[1].split("[")[0]
                                if "FLAGGED" in verdict_part.upper():
                                    is_flagged = True
                            except IndexError:
                                if "FLAGGED" in explanation.upper():
                                    is_flagged = True

                        response = {
                            "status": "success",
                            "flagged": is_flagged,
                            "explanation": explanation,
                            "cluster_size": target_cluster["size"],
                            "weight": target_cluster["total_weight"]
                        }
                    else:
                        response = {
                            "status": "success",
                            "flagged": False,
                            "explanation": "No connections found. Order is isolated.",
                            "cluster_size": 1,
                            "weight": 0
                        }

                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode())

                except Exception as e:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(str(e).encode())
            else:
                self.send_response(404)
                self.end_headers()

    server = HTTPServer(("", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print(f"  {OK_TAG}  {c('Dashboard serving', GREEN)}")
    print()
    print(f"         {c('http://localhost:', DIM)}{c(str(port), BOLD, CYAN)}{c('/', DIM)}")
    print()
    print(f"  {c('Press Ctrl-C to stop.', DIM)}")
    print(ruler("═"))
    print()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.shutdown()
        print(f"\n  {c('Server stopped.', DIM)}\n")


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Abuse-Ring Sentinel — Unified AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--no-serve", action="store_true",
                    help="Run the pipeline only — skip serving the dashboard "
                         "(dashboard is served by default after a successful run)")
    ap.add_argument("--port",     type=int, default=8000,
                    help="Dashboard server port (default: 8000)")
    ap.add_argument("--no-regen", action="store_true",
                    help="Skip data generation, use existing data/orders.json")
    ap.add_argument("--fix-deps", action="store_true",
                    help="Attempt to automatically install missing dependencies into the active environment")
    ap.add_argument("--n-normal", type=int, default=3000,
                    help="Number of normal (non-ring) orders to generate (default: 3000)")
    ap.add_argument("--n-rings",  type=int, default=3,
                    help="Number of fraud rings to inject (default: 3)")
    ap.add_argument("--n-legit",  type=int, default=2,
                    help="Number of legit-lookalike pairs to inject (default: 2)")
    args = ap.parse_args()

    do_serve = not args.no_serve  # serve by default

    header()
    t_agent_start = time.perf_counter()

    if not verify_dependencies(args.fix_deps):
        sys.exit(1)

    errors = []

    # Phase 1 — data generation
    orders = None
    if args.no_regen:
        orders_path = os.path.join(ROOT, "data", "orders.json")
        info(f"--no-regen: loading existing {orders_path}")
        try:
            with open(orders_path) as f:
                orders = json.load(f)
            info(f"Loaded {len(orders)} orders from disk\n")
        except FileNotFoundError:
            phase_fail("Data load", "data/orders.json not found — run without --no-regen first")
            sys.exit(1)
    else:
        try:
            orders = phase1_generate(args.n_normal, args.n_rings, args.n_legit)
        except Exception as e:
            phase_fail("Data generation", e); errors.append(e); sys.exit(1)

    # Phase 2 — graph
    G = None
    try:
        G = phase2_graph(orders)
    except Exception as e:
        phase_fail("Graph construction", e); errors.append(e); sys.exit(1)

    # Phase 3 — candidate discovery
    candidates = None
    try:
        candidates = phase3_find_candidates(G)
    except Exception as e:
        phase_fail("Candidate discovery", e); errors.append(e); sys.exit(1)

    # Phase 4 — AI audit
    explained = None
    try:
        explained = phase4_ai_audit(candidates, orders)
    except Exception as e:
        phase_fail("AI investigation", e)
        explained = [{**c, "flagged": False, "explanation": None} for c in candidates]

    # Phase 5 — metrics
    report = None
    try:
        report = phase5_evaluate(orders, explained)
    except Exception as e:
        phase_fail("Metrics evaluation", e); errors.append(e); sys.exit(1)

    # Phase 6 — dashboard build
    try:
        phase6_dashboard(orders, explained, report)
    except Exception as e:
        phase_fail("Dashboard build", e)

    # Database Sync (Optional)
    try:
        upload_to_supabase(orders, explained, report)
    except Exception as e:
        phase_fail("Database sync", e)

    # Summary
    t_total = time.perf_counter() - t_agent_start
    summary(orders, explained, report, t_total)

    # Phase 7 — serve
    if do_serve:
        phase_start(7, "Dashboard Server",
                    f"Serving analyst dashboard at http://localhost:{args.port}/")
        print()
        frontend_dir = os.path.join(ROOT, "frontend")
        phase7_serve(args.port, frontend_dir)


if __name__ == "__main__":
    main()
