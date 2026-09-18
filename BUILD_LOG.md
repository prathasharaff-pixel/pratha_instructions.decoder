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

## 2026-09-17 (2)
- Time spent: ~20 minutes
- Tokens used (approx): ~5k
- What shipped: Added mcp_agent/README.md documenting how to run the agent end-to-end (setup, .env, running it, and the known model-name limitation), so the workflow from the previous commit is reproducible by anyone reviewing this repo.
- What broke: Nothing broke in this commit - it's documentation only, written after confirming the agent already ran successfully in the previous commit.

## 2026-09-18
- Time spent: ~1.5 hours
- Tokens used (approx): ~100k
- What shipped: Brought the Assessment 2 mechanism into the actual capstone MVP for the first real end-to-end run. Switched app.py from Claude to Gemini (no Anthropic key available). Added Stage 2 (Verify): a new skills/verify-submission/SKILL.md scoped to completeness-checking only, plus a /api/verify endpoint that checks a submission against the Stage 1 checklist item-by-item. Ported the perceive-reason-act-observe retry loop from mcp_agent/agent.py directly into app.py's live request path (run_skill_with_retry) for both endpoints. Added real file-upload support for both stages: uploaded files are saved to mcp_workspace/uploads/ and read back through the filesystem MCP server (mcp_io.py) - a genuine use of MCP in the live app, not filesystem-for-text-that-was-already-in-memory theater. Installed fastapi (was never actually installed - app.py had never been run before this session). Added requirements.txt, top-level README.md, and a .claude/launch.json for local dev. Ran the whole thing live in a browser: pasted this exact assignment prompt into Stage 1, got a real checklist/ambiguities/definition-of-done back, then pasted a partial self-description into Stage 2 and got a correct per-item present/missing verdict (correctly flagged the one item - "update BUILD_LOG.md" - that hadn't happened yet). Also confirmed the file-upload -> MCP-read path via curl for both endpoints.
- What broke: The first real request to Gemini during browser testing came back as a raw "503 UNAVAILABLE" server error and crashed the endpoint with an unhandled 500 - the retry loop only caught JSON-parsing failures (json.JSONDecodeError/ValueError), not transient API/network exceptions. Fixed by wrapping the model call itself in the retry loop's try/except, so a 503, timeout, or any other transient failure now gets retried up to 3 times and only then fails with a clean 502 instead of a bare crash. This became the "handles one realistic failure case gracefully" requirement, discovered by actually running the app rather than assumed in advance.

**Running total across whole project: ~5h50m, ~195k tokens.**
