"""
🌐 EARNER AGENT — Web Service (Render Deploy)
24/7 chalta hai, background mein earning karta hai
Dashboard se status dekh sakte ho
"""

import sys, os, threading, json, time
from pathlib import Path
from datetime import datetime
from io import StringIO

# ─── Flask ───
try:
    from flask import Flask, jsonify, render_template_string
except ImportError:
    os.system("uv add flask")
    from flask import Flask, jsonify, render_template_string

# ─── Agent imports ───
sys.path.insert(0, str(Path(__file__).parent))
from llm import LLM
from prompts import build_autonomous_prompt
import memory as mem

app = Flask(__name__)

# ─── Agent State ───
agent_state = {
    "status": "idle",
    "last_run": "",
    "last_output": "",
    "total_runs": 0,
    "earnings": [],
    "logs": [],
    "started_at": datetime.now().isoformat(),
}

MAX_LOGS = 50

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    agent_state["logs"].append(entry)
    if len(agent_state["logs"]) > MAX_LOGS:
        agent_state["logs"] = agent_state["logs"][-MAX_LOGS:]
    print(entry)


# ─── Background Agent ───
def run_agent_cycle():
    """One cycle of autonomous earning"""
    agent_state["status"] = "running"
    agent_state["last_run"] = datetime.now().isoformat()
    agent_state["total_runs"] += 1
    log(f"🚀 Run #{agent_state['total_runs']} started...")

    try:
        # Check LLM
        l = LLM()
        if not l.api_key:
            log("❌ No API key! Set GROQ_API_KEY in env vars.")
            agent_state["status"] = "error"
            return

        prompt = build_autonomous_prompt() + "\n\nFind a real earning opportunity. Do web search. Create something of value."

        resp = l.chat([
            {"role": "system", "content": "You are an autonomous earning agent. Think step by step."},
            {"role": "user", "content": prompt}
        ], max_tokens=300)

        if resp and resp.get("content"):
            output = resp["content"][:500]
            agent_state["last_output"] = output
            agent_state["earnings"].append({
                "time": datetime.now().isoformat(),
                "run": agent_state["total_runs"],
                "output": output[:200],
            })
            log(f"✅ Agent response: {output[:100]}...")
        else:
            log("⚠ No response from LLM")
            agent_state["last_output"] = "No response"

    except Exception as e:
        log(f"❌ Error: {str(e)[:200]}")
        agent_state["last_output"] = f"Error: {str(e)[:200]}"

    agent_state["status"] = "idle"
    log(f"💤 Run #{agent_state['total_runs']} done.")


def background_loop():
    """Runs the agent in background every N minutes"""
    log("🔄 Background loop started")
    while True:
        run_agent_cycle()
        log("⏰ Waiting 30 min before next run...")
        time.sleep(30 * 60)  # 30 min


# ─── Routes ───

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>💰 Earner Agent Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, 'Segoe UI', sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }
        h1 { color: #58a6ff; margin-bottom: 10px; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
        .row { display: flex; gap: 20px; flex-wrap: wrap; }
        .stat { background: #21262d; padding: 12px 20px; border-radius: 6px; min-width: 120px; }
        .stat-label { font-size: 12px; color: #8b949e; }
        .stat-value { font-size: 24px; font-weight: bold; }
        .status-running { color: #3fb950; }
        .status-idle { color: #8b949e; }
        .status-error { color: #f85149; }
        .log-entry { font-family: monospace; font-size: 13px; padding: 4px 0; border-bottom: 1px solid #21262d; }
        .badge { background: #21262d; border-radius: 12px; padding: 2px 10px; font-size: 12px; }
        .green { color: #3fb950; }
        a { color: #58a6ff; text-decoration: none; }
    </style>
</head>
<body>
    <h1>💰 Earner Agent</h1>
    <p style="color:#8b949e;margin-bottom:20px;">Status: <strong class="status-{{state.status}}">{{state.status.upper()}}</strong>
        | Runs: {{state.total_runs}} | Since: {{state.started_at[:10]}}</p>

    <div class="row">
        <div class="stat">
            <div class="stat-label">Total Runs</div>
            <div class="stat-value">{{state.total_runs}}</div>
        </div>
        <div class="stat">
            <div class="stat-label">Last Run</div>
            <div class="stat-value" style="font-size:14px">{{state.last_run[11:19] if state.last_run else '—'}}</div>
        </div>
        <div class="stat">
            <div class="stat-label">Status</div>
            <div class="stat-value status-{{state.status}}" style="font-size:16px">{{state.status.upper()}}</div>
        </div>
    </div>

    <div class="card">
        <h3>📋 Recent Output</h3>
        <pre style="background:#0d1117;padding:12px;border-radius:4px;margin-top:8px;white-space:pre-wrap;font-size:13px;">{{state.last_output or '— No runs yet —'}}</pre>
    </div>

    <div class="card">
        <h3>📊 Earning History</h3>
        {% for e in state.earnings[-10:]|reverse %}
        <div class="log-entry">#{{e.run}} | {{e.time[11:19]}} | {{e.output[:120]}}</div>
        {% endfor %}
        {% if not state.earnings %}<p style="color:#8b949e;">No earnings recorded yet.</p>{% endif %}
    </div>

    <div class="card">
        <h3>📜 Logs</h3>
        {% for line in state.logs|reverse %}
        <div class="log-entry">{{line}}</div>
        {% endfor %}
    </div>

    <p style="color:#8b949e;font-size:12px;margin-top:20px;">
        <a href="/health">Health</a> · <a href="/run">Trigger Run</a>
    </p>
</body>
</html>
"""

@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML, state=agent_state)

@app.route("/health")
def health():
    return jsonify({
        "status": agent_state["status"],
        "runs": agent_state["total_runs"],
        "uptime": agent_state["started_at"],
    })

@app.route("/run")
def trigger_run():
    """Manually trigger an agent run"""
    thread = threading.Thread(target=run_agent_cycle, daemon=True)
    thread.start()
    return jsonify({"status": "triggered", "message": "Agent run started!"})

@app.route("/status")
def status():
    return jsonify(agent_state)


# ─── Start ───
def start_background_thread():
    thread = threading.Thread(target=background_loop, daemon=True)
    thread.start()
    log("🌱 Background agent scheduler started")

if __name__ == "__main__":
    start_background_thread()
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Starting web server on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
