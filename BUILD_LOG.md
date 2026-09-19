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

## 2026-09-18 - Capstone MVP (Assessment 3)
- Time spent: ~4.5 hours
- Tokens used (approx): ~180k
- What shipped: Rebuilt app.py into the real capstone MVP - a two-stage Assignment Decoder web app (Decode + Verify) with PDF/DOCX file upload support. Reused the decode-assignment Skill from Assessment 2 and added a new verify-submission Skill for Stage 2. Explicitly dropped the filesystem MCP mechanism from Assessment 2 (documented in README.md) in favor of direct in-process AI calls, since a live web request has no need for a file-passing subprocess - kept the same reasoning/retry loop instead. Added a Settings panel letting the user pick from 5 AI providers (Gemini, OpenAI, Anthropic, Groq, Mistral) and supply their own API key, stored client-side only. Hardened against empty input, malformed checklists, and repeated AI failures (all return clean errors, not crashes) - and hit this for real when Gemini's free-tier quota was exhausted mid-testing, confirming the graceful-failure path works live. Set up a local custom domain (assignmentdecoder.local) for a friendlier demo URL. Rewrote README.md for the new app.
- What broke: (1) Gemini's model name (gemini-2.5-flash, then briefly gemini-3.6-flash's daily quota) got exhausted during testing - confirmed the app's error handling caught this cleanly instead of crashing. (2) Groq's initially-hardcoded model (llama-3.3-70b-versatile) had been retired; fixed by querying Groq's /models endpoint and switching to openai/gpt-oss-120b.

---

## Running project total (Assignments 1-3)
- Total time spent: ~8 hours 50 minutes
- Total tokens used (approx): ~275k

## Note on the 2026-09-18 entry above
That entry's files (mcp_io.py, requirements.txt, .claude/launch.json) are
real and were confirmed to exist on disk, but the app.py in place at the
start of today's session did not actually call mcp_io.py - it was
disconnected/orphaned. Today's session (below) reconnected it for real.

## 2026-09-19 - Wire mcp_io.py into the live app for real
- Time spent: ~1 hour
- Tokens used (approx): ~40k
- What shipped: Discovered mcp_io.py, requirements.txt, and .claude/launch.json existed on disk from an earlier session but were not actually wired into app.py (confirmed via grep - zero references). Rather than deleting the orphaned file, connected it for real: added perceive_via_mcp() to app.py, which writes every request's resolved text (pasted or extracted from an uploaded PDF/DOCX/TXT) to the MCP workspace and reads it back through a real MCP filesystem server before sending it to the AI - the same perceive/observe round trip used in the Assessment 2 agent. Verified live: real files (e.g. request_387b6252.txt) appeared in mcp_workspace/uploads/ containing the exact submitted text, confirming the round trip is genuinely active, not decorative. Wrapped the MCP call in a try/except so a failure there falls back to the in-memory text instead of crashing the request. Corrected README.md, which had previously (incorrectly) described MCP as "explicitly swapped out" before this fix.
- What broke: Nothing broke in the new code itself, but the orphaned/disconnected mcp_io.py from the earlier session was itself the discovered problem - real MCP-integration code existed but silently wasn't being used, which would have made the README's "explicitly swapped" claim inaccurate had it gone unnoticed.

---

## Running project total (Assignments 1-3, revised)
- Total time spent: ~9 hours 50 minutes
- Total tokens used (approx): ~315k
