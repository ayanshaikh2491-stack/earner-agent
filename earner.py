"""Earner Agent - main agent loop with REPL, autonomous mode, tools"""
import os, sys, re, json, time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from llm import LLM
from tools import ToolRegistry
from prompts import build_earner_prompt, build_autonomous_prompt
import memory

HOME = Path.home()
WORKSPACE = HOME / "agent-earner" / "workspace"

# ─── Config ─────────────────────────────────────────────────────────
CONFIG_FILE = HOME / "agent-earner" / "config.json"

def load_config() -> dict:
    defaults = {
        "model": "llama3-70b-8192",
        "api_key": "",
        "autonomous_interval": 3600,
    }
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            defaults.update(data)
        except:
            pass
    return defaults

def save_config(config: dict):
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")

# ─── Tool Call Parser ───────────────────────────────────────────────
TOOL_PATTERN = r'TOOL:\s*(\w+)\s*\|\s*PROMPT:\s*((?:(?!TOOL:).)*)'

def parse_tool_calls(text: str) -> list:
    """Extract all TOOL:name|PROMPT:... directives from text"""
    matches = list(re.finditer(TOOL_PATTERN, text, re.DOTALL))
    calls = []
    for m in matches:
        name = m.group(1).strip().lower()
        prompt = m.group(2).strip()
        calls.append((name, prompt))
    return calls

def strip_tool_calls(text: str) -> str:
    """Remove TOOL directives from text for display"""
    return re.sub(TOOL_PATTERN, '', text).strip()

# ─── Agent Loop ─────────────────────────────────────────────────────

class EarnerAgent:
    def __init__(self):
        config = load_config()
        self.config = config
        self.llm = LLM(api_key=config.get("api_key", ""), model=config.get("model", "llama3-70b-8192"))
        self.tools = ToolRegistry()
        self.messages = []
        self.turn_count = 0
        self.max_turns = 10
    
    def build_system_prompt(self) -> str:
        """Build full system prompt with memory context"""
        prompt = build_earner_prompt(self.config)
        
        # Add session memory
        ctx = memory.read_context()
        if ctx:
            prompt += f"\n\n## 🧠 Session Memory (past work)\n{ctx}\n"
        
        # Add knowledge base
        kb = memory.read_knowledge()
        if kb:
            prompt += f"\n\n## 📚 Knowledge Base\n{kb}\n"
        
        return prompt
    
    def show_thinking(self, text: str):
        """Display thinking/reasoning indicators"""
        sys.stdout.write(text)
        sys.stdout.flush()
    
    def execute_tools(self, text: str) -> int:
        """Execute all TOOL directives found in text, return count"""
        calls = parse_tool_calls(text)
        if not calls:
            return 0
        
        for tool_name, prompt in calls:
            print(f"\n  🛠️  → {tool_name} ...")
            result = self.tools.execute(f"{tool_name}|{prompt}")
            
            # Show result
            if result:
                for line in result.strip().split("\n")[:30]:
                    print(f"     {line}")
            
            # Track file creation
            if tool_name == "write" and not result.startswith("✗"):
                # Extract path from write prompt
                path_part = prompt.split("```")[0].strip()
                memory.track_file(path_part.strip("\"'`"))
        
        return len(calls)
    
    def process_turn(self, user_input: str) -> str:
        """Process one user input through the agent loop"""
        # Build system prompt fresh each time (memory may have updated)
        if not self.messages:
            sys_prompt = self.build_system_prompt()
            self.messages = [
                {"role": "system", "content": sys_prompt},
            ]
        
        # Add user message
        self.messages.append({"role": "user", "content": user_input})
        
        # Run tool loop (max N turns)
        self.turn_count = 0
        tool_executed = False
        final_response = ""
        
        response_text = ""
        
        while self.turn_count < self.max_turns:
            self.turn_count += 1
            
            # Call LLM
            print(f"\n  💭 Thinking...", end="")
            sys.stdout.flush()
            
            resp = self.llm.chat(self.messages, max_tokens=4096)
            if not resp or not resp.get("content"):
                print(" ⚠ No response from LLM")
                if not response_text:
                    response_text = "⚠ LLM did not respond. Check API key."
                break
            
            content = resp["content"]
            usage = resp.get("usage", {})
            print(f" ({usage.get('total_tokens', '?')} tokens)")
            
            # Show conversational text (without tool calls)
            clean_text = strip_tool_calls(content)
            if clean_text.strip():
                print(f"\n{clean_text.strip()}")
            
            # Store final content
            if not response_text:
                response_text = clean_text.strip()
            
            # Check for tool calls
            calls = parse_tool_calls(content)
            if not calls:
                break  # No tools = done with this turn
            
            # Execute tools
            self.execute_tools(content)
            tool_executed = True
            
            # Add assistant response to history
            self.messages.append({"role": "assistant", "content": content})
            
            # Add tool results as new user message
            tool_results = []
            for tool_name, prompt in calls[:10]:
                result = self.tools.execute(f"{tool_name}|{prompt}")
                tool_results.append(f"Tool [{tool_name}] result:\n{result[:2000]}")
            
            self.messages.append({
                "role": "user",
                "content": "[Tool results]\n" + "\n\n".join(tool_results)
            })
            
            # Trim history if too long
            self._trim_history()
        
        # Log to memory
        if user_input.strip() and response_text:
            memory.add_turn(user_input, response_text)
        
        return response_text or "⚠ No response generated."
    
    def _trim_history(self):
        """Keep context manageable"""
        # Keep system prompt + last 20 messages
        if len(self.messages) > 22:
            self.messages = [self.messages[0]] + self.messages[-20:]
    
    def reset(self):
        """Reset conversation"""
        self.messages = []
        self.turn_count = 0
        return "✓ Conversation reset!"
    
    def set_model(self, model: str):
        """Change model"""
        self.llm.model = model
        self.config["model"] = model
        save_config(self.config)
        self.messages = []  # Reset context
        return f"✓ Model changed to: {model}"
    
    def set_api_key(self, key: str):
        """Change API key"""
        self.llm.api_key = key
        self.config["api_key"] = key
        save_config(self.config)
        return "✓ API key updated!"


# ─── REPL (Interactive Mode) ────────────────────────────────────────

def run_repl():
    """Interactive REPL mode"""
    agent = EarnerAgent()
    
    print("""
╔══════════════════════════════════════════════╗
║     💰 EARNER AGENT — Autonomous Earning     ║
║   Khud sochta hai, khud kamata hai!         ║
╚══════════════════════════════════════════════╝

Commands:
  /reset     — Reset conversation
  /model     — Show current model
  /model X   — Switch model (e.g. /model llama3-70b-8192)
  /key X     — Set API key
  /tools     — List available tools
  /memory    — Show session memory
  /knowledge — Show knowledge base
  /earn      — Autonomous: find & execute earning opportunity
  /resetmem  — Clear all memory
  /exit      — Quit
""")
    
    while True:
        try:
            user_input = input("\n💡 you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Bye!")
            break
        
        if not user_input:
            continue
        
        # Handle commands
        if user_input.startswith("/"):
            cmd = user_input[1:].strip().split(None, 1)
            base = cmd[0].lower() if cmd else ""
            args = cmd[1] if len(cmd) > 1 else ""
            
            if base == "exit" or base == "quit":
                print("👋 Bye! Phir milte hain!")
                break
            elif base == "reset":
                print(agent.reset())
            elif base == "model":
                if args:
                    print(agent.set_model(args))
                else:
                    print(f"  Current model: {agent.llm.model}")
            elif base == "key":
                if args:
                    print(agent.set_api_key(args))
                else:
                    print(f"  API key: {agent.llm.api_key[:8]}...{agent.llm.api_key[-4:] if len(agent.llm.api_key) > 8 else '(not set)'}")
            elif base == "tools":
                print(agent.tools.list_tools())
            elif base == "memory":
                print(f"\n{memory.read_context()}")
            elif base == "knowledge":
                print(f"\n{memory.read_knowledge()}")
            elif base == "resetmem":
                print(memory.reset())
            elif base == "earn":
                print("\n🔄 AUTONOMOUS MODE — Soch raha hu kya kama sakta hoon...")
                try:
                    agent.process_turn(
                        "Autonomous mode: Socho aur earning opportunity dhundho. "
                        "Web search karo trending freelance projects ke liye. "
                        "Phir decide karo kya banao aur execute karo. "
                        "Complete working project banao."
                    )
                except KeyboardInterrupt:
                    print("\n⏹ Stopped")
            else:
                print(f"  Unknown command: /{base}")
            continue
        
        # Process normal input
        try:
            agent.process_turn(user_input)
        except KeyboardInterrupt:
            print("\n⏹ Stopped")
        except Exception as e:
            print(f"\n⚠ Error: {e}")


# ─── One-Shot Mode ──────────────────────────────────────────────────

def run_one_shot(task: str):
    """Run one task and exit"""
    agent = EarnerAgent()
    print(f"\n📋 Task: {task}\n")
    print("━" * 50)
    try:
        agent.process_turn(task)
    except KeyboardInterrupt:
        print("\n⏹ Stopped")
    except Exception as e:
        print(f"\n⚠ Error: {e}")


# ─── Entry Point ────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="💰 Earner Agent - Autonomous Earning Agent")
    parser.add_argument("task", nargs="*", help="One-shot task to execute")
    parser.add_argument("--setup", action="store_true", help="Setup API key")
    parser.add_argument("--reset-memory", action="store_true", help="Clear all memory")
    parser.add_argument("--earn", action="store_true", help="Autonomous earning mode")
    args = parser.parse_args()
    
    if args.reset_memory:
        print(memory.reset())
        return
    
    if args.setup:
        print("\n🔧 Setup Wizard")
        current = load_config()
        key = input(f"GROQ API Key (current: {current.get('api_key', '')[:8]}...): ").strip()
        if key:
            current["api_key"] = key
            save_config(current)
            print("✓ API key saved!")
        
        model = input(f"Model (default: {current.get('model', 'llama3-70b-8192')}): ").strip()
        if model:
            current["model"] = model
            save_config(current)
            print(f"✓ Model saved: {model}")
        print("\nSetup complete! Run: python earner.py")
        return
    
    if args.earn:
        run_one_shot(
            "AUTONOMOUS EARNING MODE: Socho aur earning opportunity dhundho. "
            "Web search karo trending freelance projects ke liye. "
            "Decide karo kya banao. Execute karo. Complete working project banao."
        )
        return
    
    if args.task:
        run_one_shot(" ".join(args.task))
        return
    
    # Default: REPL mode
    run_repl()


if __name__ == "__main__":
    main()
