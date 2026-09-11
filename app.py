import os
import json
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import anthropic

app = FastAPI(title="Assignment Instructions Decoder")

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-5"  # swap for whatever model your API key has access to


# ---------- Request / response models ----------

class InstructionsRequest(BaseModel):
    instructions: str


class DecodeResponse(BaseModel):
    deliverables: List[str]
    ambiguities: List[str]
    definition_of_done: str


# ---------- Prompt ----------

DECODE_SYSTEM_PROMPT = """You help students understand confusing assignment instructions. \
Given the raw text of an assignment prompt, do three things:

1. Extract a concrete checklist of every distinct deliverable or required action. Each item \
should be something the student can literally check off. Do not invent requirements that \
aren't implied by the text.

2. Flag anything genuinely ambiguous or underspecified — requirements where a reasonable \
student could interpret the instructions two different ways, or where a concrete detail \
(format, length, deadline, submission method) is missing. Do not flag things that are actually \
clear. If nothing is ambiguous, return an empty list.

3. Write one or two sentences stating what "done" concretely looks like for this assignment.

Respond ONLY with valid JSON, no preamble, no markdown fences, in this exact shape:
{"deliverables": ["...", "..."], "ambiguities": ["...", "..."], "definition_of_done": "..."}
"""


def _call_claude(system: str, user: str) -> dict:
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"Claude API error: {e}")

    text = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=502, detail=f"Could not parse Claude's response: {text}"
        )


# ---------- API route ----------

@app.post("/api/decode", response_model=DecodeResponse)
def decode_instructions(req: InstructionsRequest):
    if not req.instructions.strip():
        raise HTTPException(status_code=400, detail="Paste some assignment text first.")

    data = _call_claude(DECODE_SYSTEM_PROMPT, req.instructions)

    for field in ("deliverables", "ambiguities", "definition_of_done"):
        if field not in data:
            raise HTTPException(status_code=502, detail=f"Claude's response was missing '{field}'.")

    return DecodeResponse(**data)


# ---------- Frontend (served directly, no separate static folder) ----------

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Assignment Instructions Decoder</title>
<style>
  :root {
    --bg: #0f1115; --card: #171a21; --border: #2a2e38;
    --text: #e8e9ec; --muted: #9096a3; --accent: #6c8cff; --warn: #ffb454;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
    background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; padding: 24px;
  }
  .card { width: 100%; max-width: 560px; background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 32px; }
  h1 { font-size: 1.3rem; margin: 0 0 4px; }
  p.sub { color: var(--muted); margin: 0 0 20px; font-size: 0.9rem; }
  textarea {
    width: 100%; min-height: 140px; background: #0f1115; border: 1px solid var(--border);
    border-radius: 10px; color: var(--text); padding: 12px 14px; font-size: 0.9rem;
    font-family: inherit; margin-bottom: 12px; resize: vertical;
  }
  button {
    width: 100%; padding: 12px; border: none; border-radius: 10px; background: var(--accent);
    color: white; font-size: 0.95rem; font-weight: 600; cursor: pointer;
  }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .section { margin-top: 22px; }
  .section h2 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); margin: 0 0 10px; }
  ul { margin: 0; padding-left: 20px; }
  li { margin-bottom: 6px; font-size: 0.92rem; line-height: 1.4; }
  .ambiguity { color: var(--warn); }
  .done-box { background: rgba(108,140,255,0.08); border: 1px solid rgba(108,140,255,0.3); border-radius: 10px; padding: 14px; font-size: 0.92rem; }
  .error { color: #ff6b6b; font-size: 0.85rem; margin-top: 8px; }
  .hidden { display: none; }
  .empty { color: var(--muted); font-size: 0.88rem; font-style: italic; }
</style>
</head>
<body>
  <div class="card">
    <h1>Assignment Instructions Decoder</h1>
    <p class="sub">Paste a confusing assignment prompt. Get a checklist, flagged ambiguities, and what "done" means.</p>

    <textarea id="instructions-input" placeholder="Paste the assignment instructions here..."></textarea>
    <button id="decode-btn">Decode it</button>
    <div id="error" class="error hidden"></div>

    <div id="results" class="hidden">
      <div class="section">
        <h2>Deliverables checklist</h2>
        <ul id="deliverables-list"></ul>
      </div>
      <div class="section">
        <h2>Flagged ambiguities</h2>
        <ul id="ambiguities-list"></ul>
      </div>
      <div class="section">
        <h2>Definition of done</h2>
        <div class="done-box" id="done-box"></div>
      </div>
    </div>
  </div>

<script>
  const input = document.getElementById('instructions-input');
  const btn = document.getElementById('decode-btn');
  const errorBox = document.getElementById('error');
  const results = document.getElementById('results');

  btn.addEventListener('click', async () => {
    const instructions = input.value.trim();
    errorBox.classList.add('hidden');
    if (!instructions) {
      errorBox.textContent = 'Paste some assignment text first.';
      errorBox.classList.remove('hidden');
      return;
    }

    btn.disabled = true;
    btn.textContent = 'Decoding...';

    try {
      const res = await fetch('/api/decode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instructions }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Something went wrong.');
      const data = await res.json();

      const deliverablesList = document.getElementById('deliverables-list');
      deliverablesList.innerHTML = data.deliverables.map(d => `<li>${d}</li>`).join('');

      const ambiguitiesList = document.getElementById('ambiguities-list');
      ambiguitiesList.innerHTML = data.ambiguities.length
        ? data.ambiguities.map(a => `<li class="ambiguity">${a}</li>`).join('')
        : '<li class="empty">Nothing flagged — instructions look clear.</li>';

      document.getElementById('done-box').textContent = data.definition_of_done;

      results.classList.remove('hidden');
    } catch (err) {
      errorBox.textContent = err.message;
      errorBox.classList.remove('hidden');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Decode it';
    }
  });
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE
