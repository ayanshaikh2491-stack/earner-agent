"""Session memory - persists across calls so agent remembers past work"""
import os, json, re
from pathlib import Path
from datetime import datetime

HOME = Path.home()
MEMORY_DIR = HOME / "agent-earner" / "memory"
CONTEXT_FILE = MEMORY_DIR / "context.md"
CONV_FILE = MEMORY_DIR / "conversation.md"
FILES_FILE = MEMORY_DIR / "files.md"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

# ─── Core Memory Functions ──────────────────────────────────────────

def init():
    """Create memory files if fresh"""
    if not CONTEXT_FILE.exists():
        CONTEXT_FILE.write_text(
            "# 🧠 Agent Memory\n"
            "*Persistent context across sessions*\n\n"
            "## 📁 Files Created\n\n"
            "## 💬 Recent Activity\n\n",
            encoding="utf-8"
        )

def add_turn(user_input: str, agent_response: str):
    """Log a conversation turn"""
    init()
    ts = datetime.now().strftime("%H:%M %d/%m")
    conv = CONV_FILE.read_text(encoding="utf-8") if CONV_FILE.exists() else ""
    conv += f"\n### [{ts}] User\n{user_input.strip()[:500]}\n\n### Agent\n{agent_response.strip()[:1000]}\n"
    lines = conv.strip().split("\n")
    if len(lines) > 300:
        lines = lines[-300:]
    CONV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _rebuild_context()

def track_file(path: str, action: str = "created"):
    """Track a file creation (deduplicated)"""
    init()
    files = FILES_FILE.read_text(encoding="utf-8") if FILES_FILE.exists() else ""
    entry = f"- `{path}` ({action})"
    if entry not in files:
        files += entry + "\n"
    f_lines = files.strip().split("\n")
    if len(f_lines) > 100:
        f_lines = f_lines[-100:]
    FILES_FILE.write_text("\n".join(f_lines) + "\n", encoding="utf-8")
    _rebuild_context()

def add_decision(decision: str):
    """Record a significant event or decision"""
    init()
    ts = datetime.now().strftime("%H:%M %d/%m")
    context = CONTEXT_FILE.read_text(encoding="utf-8")
    context += f"\n- [{ts}] {decision.strip()[:300]}"
    CONTEXT_FILE.write_text(context, encoding="utf-8")

def _rebuild_context():
    """Rebuild context.md from conversation + files"""
    conv = CONV_FILE.read_text(encoding="utf-8") if CONV_FILE.exists() else ""
    files = FILES_FILE.read_text(encoding="utf-8") if FILES_FILE.exists() else ""
    
    # Get last 5 conversation turns
    turns = []
    current = ""
    for line in conv.split("\n"):
        if line.startswith("### [") and current.strip():
            turns.append(current.strip())
            current = line
        else:
            current += "\n" + line
    if current.strip():
        turns.append(current.strip())
    recent_conv = "\n\n".join(turns[-10:]) if turns else "*(session just started)*"
    files_section = files.strip() if files.strip() else "*(none yet)*"
    
    CONTEXT_FILE.write_text(
        "# 🧠 Agent Memory\n"
        "*Persistent context across sessions*\n\n"
        f"## 📁 Files & Outputs\n{files_section}\n\n"
        f"## 💬 Recent Activity\n{recent_conv}\n",
        encoding="utf-8"
    )

def read_context() -> str:
    """Read structured context for agent prompt injection"""
    init()
    return CONTEXT_FILE.read_text(encoding="utf-8")

def read_conversation() -> str:
    """Read full conversation history"""
    if CONV_FILE.exists():
        return CONV_FILE.read_text(encoding="utf-8")
    return ""

def reset():
    """Clear all memory"""
    for f in [CONTEXT_FILE, CONV_FILE, FILES_FILE]:
        if f.exists():
            f.unlink()
    init()
    return "✓ Memory reset. Fresh start!"

# ─── Knowledge Base ─────────────────────────────────────────────────

def save_knowledge(topic: str, content: str):
    """Save a knowledge entry that persists across sessions"""
    kb_file = MEMORY_DIR / "knowledge.md"
    entry = f"\n## {topic}\n{content.strip()}\n"
    current = kb_file.read_text(encoding="utf-8") if kb_file.exists() else "# 📚 Knowledge Base\n"
    current += entry
    kb_file.write_text(current, encoding="utf-8")
    return f"✓ Knowledge saved: {topic}"

def read_knowledge() -> str:
    """Read knowledge base"""
    kb = MEMORY_DIR / "knowledge.md"
    if kb.exists():
        return kb.read_text(encoding="utf-8")
    return "# 📚 Knowledge Base\n*(empty - use 'remember this: ...' to add)*\n"
