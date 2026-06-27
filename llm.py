"""Groq LLM layer - streaming chat completions, free API"""
import os, json, sys, time
from pathlib import Path
import httpx
from typing import Optional

GROQ_BASE = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"  # 128K context, smartest free model

def _load_key_from_env_file() -> str:
    """Fallback: read GROQ_API_KEY from .env file next to this module"""
    try:
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("GROQ_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip("\"'")
                    if val:
                        return val
    except Exception:
        pass
    return ""

class LLM:
    def __init__(self, api_key: str = "", model: str = DEFAULT_MODEL):
        # Priority: constructor arg > env var > .env file
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "") or _load_key_from_env_file()
        self.model = model
        if not self.api_key:
            print("⚠  GROQ_API_KEY env var ya config me set nahi hai!")
            print("   Get free key: https://console.groq.com/keys")
            print("   Then: export GROQ_API_KEY=<your-key>")

    def chat(self, messages: list, max_tokens: int = 4096, temperature: float = 0.7) -> Optional[dict]:
        """Call Groq API, return {content, usage} or None"""
        if not self.api_key:
            print("⚠  GROQ_API_KEY not set! Use setup or set env var.")
            return None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            resp = httpx.post(
                GROQ_BASE,
                headers=headers,
                json=body,
                timeout=120,
            )
            if resp.status_code != 200:
                print(f"  ⚠ Groq API error: {resp.status_code} {resp.text[:200]}")
                return None
            data = resp.json()
            choice = data["choices"][0]
            content = choice.get("message", {}).get("content", "").strip()
            usage = data.get("usage", {})
            return {"content": content, "usage": usage}
        except httpx.TimeoutException:
            print("  ⚠ Groq API timed out")
            return None
        except Exception as e:
            print(f"  ⚠ Groq API error: {e}")
            return None

    def chat_stream(self, messages: list, max_tokens: int = 4096, temperature: float = 0.7):
        """Stream response from Groq, yield tokens"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        try:
            with httpx.stream("POST", GROQ_BASE, headers=headers, json=body, timeout=120) as resp:
                if resp.status_code != 200:
                    yield f"⚠ API error: {resp.status_code}"
                    return
                for line in resp.iter_lines():
                    if not line or line.startswith(":"):
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0]["delta"]
                            if delta.get("content"):
                                yield delta["content"]
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"\n⚠ Error: {e}"
