# Build Log

One entry per commit, added *before* committing and pushing. Ask Claude to draft the
entry based on what actually changed, then commit the log alongside the code change it
describes.

**Format:**


---

## 2026-09-11
- Time spent: ~2 hours
- Tokens used (approx): ~50k
- What shipped: Created GitHub repo, initialized git locally, pushed initial app.py (FastAPI backend + frontend for the Assignment Instructions Decoder) to main, created a feature branch, and committed plan.md with MVP scope and AI-involvement level.
## 2026-09-17
- Time spent: ~2 hours
- Tokens used (approx): ~40k
- What shipped: Built a custom Skill (skills/decode-assignment/SKILL.md) scoped to decoding assignment text into deliverables/ambiguities/definition-of-done. Built an agent (mcp_agent/agent.py) that runs a real perceive -> reason -> act -> observe loop: it reads input.txt through a filesystem MCP server, calls Gemini using the Skill's instructions, validates the JSON response (retrying up to 3 times if invalid), writes output.json back through the same MCP server, and reads it back to confirm the write succeeded. Ran successfully end-to-end on the real Assignment 2 prompt text.
- What broke: The agent initially crashed with "model models/gemini-2.5-flash is no longer available." Fixed by switching the model name to gemini-3.6-flash inside agent.py.
