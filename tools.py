"""Tool system - web search, file ops, shell, and more"""
import os, sys, json, re, subprocess, shutil, tempfile
from pathlib import Path
from urllib.parse import quote_plus
from typing import Optional

HOME = Path.home()
WORKSPACE = HOME / "agent-earner" / "workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)

# ─── Web Search (free DuckDuckGo) ───────────────────────────────────
def web_search(query: str, limit: int = 5) -> str:
    """Search web via DuckDuckGo HTML (no API key needed)"""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        # Use curl subprocess to avoid Python socket DLL issues on Windows
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False)
        tmp.close()
        cmd = ["curl", "-s", "-L", url, "-H", f"User-Agent: {headers['User-Agent']}", "-o", tmp.name]
        subprocess.run(cmd, capture_output=True, timeout=15)
        html = Path(tmp.name).read_text(encoding="utf-8", errors="replace")
        os.unlink(tmp.name)
        
        # Parse results
        results = []
        # Find result blocks
        for m in re.finditer(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            html, re.DOTALL
        ):
            url_val = m.group(1)
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            results.append(f"• {title}\n  {url_val}")
            if len(results) >= limit:
                break
        
        if results:
            return "\n\n".join(results)
        else:
            # Alternative parsing if first pattern fails
            for m in re.finditer(
                r'<a[^>]*rel="nofollow"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                html, re.DOTALL
            ):
                url_val = m.group(1)
                title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                results.append(f"• {title}\n  {url_val}")
                if len(results) >= limit:
                    break
            if results:
                return "\n\n".join(results)
            return "(no results found)"
    except Exception as e:
        return f"✗ Search error: {e}"

# ─── File Operations ────────────────────────────────────────────────
def file_read(path: str) -> str:
    """Read a file"""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = WORKSPACE / p
    if not p.exists():
        return f"✗ File not found: {p}"
    if p.is_dir():
        return f"✗ '{p}' is a directory"
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        if len(lines) > 200:
            return content + f"\n\n[... {len(lines) - 200} more lines]"
        return content
    except Exception as e:
        return f"✗ Error: {e}"

def file_write(path: str, content: str) -> str:
    """Write content to a file"""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = WORKSPACE / p
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        # Extract code from fences if present
        cb = re.search(r"```\w*\s*\n(.+?)\n```", content, re.DOTALL)
        if cb:
            content = cb.group(1)
        p.write_text(content.strip(), encoding="utf-8")
        size = len(content.encode("utf-8"))
        return f"✓ Wrote {size} bytes to {p}"
    except Exception as e:
        return f"✗ Error: {e}"

def file_list(path: str = ".") -> str:
    """List files in a directory"""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = WORKSPACE / p
    if not p.exists():
        return f"✗ Directory not found: {p}"
    items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    lines = []
    for item in items:
        icon = "📁" if item.is_dir() else "📄"
        size = item.stat().st_size if item.is_file() else ""
        lines.append(f"{icon} {item.name}{'  '+str(size)+' B' if size else ''}")
    return "\n".join(lines) if lines else "(empty directory)"

# ─── Shell Execution ────────────────────────────────────────────────
def shell_run(cmd: str) -> str:
    """Run a shell command"""
    if not cmd.strip():
        return "✗ No command provided"
    # Fix common Windows issues
    cmd_fixed = re.sub(r'\bpython3\b', 'python', cmd)
    try:
        # Use bash on Windows for Unix commands
        is_unix = any(cmd_fixed.startswith(u) for u in ["find ", "grep ", "ls ", "cat "])
        if is_unix and sys.platform == "win32":
            result = subprocess.run(
                ["bash", "-c", cmd_fixed],
                capture_output=True, timeout=30, text=True,
            )
        else:
            result = subprocess.run(
                cmd_fixed, shell=True, capture_output=True, timeout=30, text=True
            )
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        output = out
        if err:
            output += f"\n\nSTDERR:\n{err[:500]}"
        if result.returncode != 0 and not out:
            return f"✗ exit={result.returncode}\n{err[:1000]}"
        if not output:
            return f"✓ exit={result.returncode} (no output)"
        lines = output.split("\n")
        if len(lines) > 60:
            return "\n".join(lines[:60]) + f"\n[... {len(lines) - 60} more lines]"
        return output
    except subprocess.TimeoutExpired:
        return "✗ Command timed out (30s)"
    except Exception as e:
        return f"✗ Error: {e}"

# ─── Tool Registry ──────────────────────────────────────────────────
class ToolRegistry:
    """Registry of all available tools"""
    
    def __init__(self):
        self.tools = {
            "web_search": {
                "fn": self._safe_call(web_search),
                "desc": "Search the web: web_search(<query>)",
                "usage": "web_search|best freelancing sites for python developers",
            },
            "read": {
                "fn": self._safe_call(file_read),
                "desc": "Read a file: read(<path>)",
                "usage": "read|/path/to/file.py",
            },
            "write": {
                "fn": self._safe_call(file_write),
                "desc": "Write a file: write(<path>)```content```",
                "usage": "write|/path/to/file.py```print('hello')```",
            },
            "ls": {
                "fn": self._safe_call(file_list),
                "desc": "List directory: ls(<path>)",
                "usage": "ls|.",
            },
            "shell": {
                "fn": self._safe_call(shell_run),
                "desc": "Run shell command: shell(<command>)",
                "usage": "shell|python script.py",
            },
        }
    
    def _safe_call(self, fn):
        """Wrap in try/except"""
        def wrapped(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                return f"✗ Tool error: {e}"
        return wrapped
    
    def execute(self, call_str: str) -> str:
        """Parse 'toolname|args' and execute"""
        parts = call_str.strip().split("|", 1)
        name = parts[0].strip().lower()
        args = parts[1] if len(parts) > 1 else ""
        args = args.strip().strip("\"'`")
        
        if name not in self.tools:
            return f"✗ Unknown tool: {name}. Available: {', '.join(self.tools.keys())}"
        
        info = self.tools[name]
        # For write, pass raw (includes ``` fences)
        if name == "write":
            result = info["fn"](args)
        else:
            result = info["fn"](args)
        return result
    
    def list_tools(self) -> str:
        """Pretty list of tools"""
        lines = ["📦 Available Tools:", ""]
        for name, info in self.tools.items():
            lines.append(f"  • TOOL:{name}|PROMPT:{info.get('usage', 'args')}")
            lines.append(f"    {info['desc']}")
        return "\n".join(lines)
