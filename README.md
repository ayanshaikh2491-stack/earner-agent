"""
╔═════════════════════════════════════════╗
║   💰 EARNER AGENT — Setup Instructions  ║
╚═════════════════════════════════════════╝

Step 1: Get a FREE Groq API Key
  → https://console.groq.com/keys
  → Sign up (free, no credit card)
  → Create API key → Copy it

Step 2: Setup the agent
  python earner.py --setup
  → Paste your API key when asked

Step 3: Run it!
  python earner.py              → Interactive REPL mode
  python earner.py --earn       → Autonomous earning mode
  python earner.py "task here"  → One-shot task

💡 Tips:
  - Groq gives 1000 requests/day FREE
  - Best free model: llama3-70b-8192 (fast, smart)
  - All files saved in workspace/ folder
  - Agent remembers past sessions automatically

Commands in REPL:
  /earn     → Autonomous earning mode
  /model X  → Switch model (e.g. /model llama3-70b-8192)
  /tools    → List available tools
  /memory   → See what agent remembers
  /knowledge→ See knowledge base
  /reset    → Reset conversation
  /resetmem → Clear all memory
"""
