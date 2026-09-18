# Assignment Decoder

Assignment prompts are often dense or ambiguous — students miss requirements
not from lack of effort, but from misreading the prompt itself. Assignment
Decoder fixes this in two stages:

- **Stage 1 — Decode.** Paste an assignment prompt, or upload it as a file.
  The app turns it into a checklist of concrete deliverables, a list of
  genuinely ambiguous points, and a plain-language definition of done.
- **Stage 2 — Verify.** Paste or upload your completed submission. The app
  checks it against the Stage 1 checklist, item by item, and reports whether
  each requirement is present — a completeness check, not a quality check.
  ("Did you include a methodology section?", not "Is it any good?")

Both stages run live in one browser tab — decode a prompt, then verify a
draft against the exact checklist that came out of it.

## How it's built

- **Skills** (`skills/decode-assignment`, `skills/verify-submission`) — each
  scoped to exactly one task, with a strict output contract. The FastAPI
  backend loads these files directly and sends them to the model as-is; the
  Skill file is the single source of truth for both.
- **Reason/retry loop** — every model call goes through
  `run_skill_with_retry()` in `app.py`: call the model, validate the JSON
  shape, retry up to 3 times on a bad or failed response, and fail with a
  clean error only after exhausting attempts. This is the same
  perceive-reason-act-observe discipline built for `mcp_agent/agent.py` in
  the previous milestone, now running in the live request path instead of a
  standalone script.
- **Filesystem MCP** — when you upload a file (either stage), the app saves
  it to `mcp_workspace/uploads/` and reads it back through a real MCP
  filesystem server (`mcp_io.py`), not a plain `open()`. Pasted text skips
  MCP since it's already in memory — there's nothing to read from disk.
- **`mcp_agent/agent.py`** stays in the repo as a standalone batch/offline
  companion tool (see [mcp_agent/README.md](mcp_agent/README.md)) — useful
  for decoding a saved prompt file without spinning up the web app.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

You'll also need [Node.js](https://nodejs.org) installed (for `npx`) — the
MCP filesystem server is launched as a subprocess via `npx`.

Create a `.env` file in the repo root (never committed):

```
GEMINI_API_KEY="your-key-here"
```

## Run it

```bash
source venv/bin/activate
uvicorn app:app --reload --port 8000
```

Open http://localhost:8000, paste or upload an assignment prompt, click
**Decode it**, then paste or upload a completed submission and click
**Verify against checklist**.

## Known limitations

- The model name (`gemini-3.6-flash`) is hardcoded in `app.py`. If Google
  retires it, requests will fail after 3 retries with a 502 naming the
  error — update the `MODEL` constant to whatever the error suggests.
- File uploads are read as plain text (`.txt`, `.md`). A binary file (e.g. a
  PDF) will fail with a clear 400 error rather than garbage output.
- No accounts, no database — the Stage 1 checklist lives only in the
  browser tab's memory for the duration of the session.
