#!/usr/bin/env bash
# Set Groq API key and run earner agent
export GROQ_API_KEY="gsk_7h...AOHZ"
cd ~/agent-earner
exec uv run python earner.py "$@"
