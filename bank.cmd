@echo off
cd /d "%~dp0"
uv run python bank_agent.py %*
