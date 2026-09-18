import json
import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from google import genai
from pydantic import BaseModel

from mcp_io import read_file_via_mcp, save_upload_bytes

load_dotenv()

app = FastAPI(title="Assignment Decoder")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not found. Check your .env file.")

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL = "gemini-3.6-flash"
MAX_ATTEMPTS = 3

SKILLS_DIR = Path(__file__).resolve().parent / "skills"


def load_skill(name: str) -> str:
    return (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")


DECODE_SKILL = load_skill("decode-assignment")
VERIFY_SKILL = load_skill("verify-submission")


# ---------- Request / response models ----------

class DecodeResponse(BaseModel):
    deliverables: List[str]
    ambiguities: List[str]
    definition_of_done: str


class VerifyResult(BaseModel):
    item: str
    status: str
    reason: str


class VerifyResponse(BaseModel):
    results: List[VerifyResult]


# ---------- Gemini call + reason/retry loop ----------
#
# Ported from mcp_agent/agent.py's perceive -> reason -> act -> observe loop:
# perceive (caller already resolved the input text), act (call the model),
# reason (validate the JSON shape), retry on garbage output, observe (return
# the validated dict, or fail gracefully after exhausting attempts) instead
# of ever crashing the request on a bad model response.

def _clean_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    return text.strip()


def _call_gemini(skill_instructions: str, user_content: str) -> str:
    prompt = f"{skill_instructions}\n\n---\n\n{user_content}"
    response = client.models.generate_content(model=MODEL, contents=prompt)
    return response.text.strip()


def run_skill_with_retry(skill_instructions: str, user_content: str, required_keys: tuple) -> dict:
    last_error: Optional[Exception] = None
    for _ in range(MAX_ATTEMPTS):
        try:
            raw = _call_gemini(skill_instructions, user_content)
        except Exception as exc:
            # Transient failures (rate limits, 503s, timeouts) surface here as
            # raw SDK exceptions, not JSON errors — first live test run hit a
            # real "503 UNAVAILABLE" from Gemini and this branch didn't exist
            # yet, so it crashed the request with a bare 500. Treat it the
            # same as a bad response: retry, then fail gracefully.
            last_error = exc
            continue

        cleaned = _clean_json_text(raw)
        try:
            parsed = json.loads(cleaned)
            if not all(key in parsed for key in required_keys):
                raise ValueError(f"missing required key(s): {required_keys}")
            return parsed
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            continue

    raise HTTPException(
        status_code=502,
        detail=(
            f"The AI didn't return a usable response after {MAX_ATTEMPTS} attempts "
            f"({last_error}). Please try again."
        ),
    )


# ---------- Shared input resolution (paste or file, file goes through MCP) ----------

async def _resolve_text(pasted: Optional[str], file: Optional[UploadFile]) -> str:
    if file is not None and file.filename:
        data = await file.read()
        rel_path = save_upload_bytes(file.filename, data)
        try:
            text = await read_file_via_mcp(rel_path)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Could not read '{file.filename}' as text. Please upload a plain text file. ({exc})",
            )
        if not text.strip():
            raise HTTPException(status_code=400, detail=f"'{file.filename}' is empty.")
        return text

    if pasted and pasted.strip():
        return pasted

    raise HTTPException(status_code=400, detail="Paste some text or upload a file first.")


# ---------- API routes ----------

@app.post("/api/decode", response_model=DecodeResponse)
async def decode_instructions(
    instructions: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    text = await _resolve_text(instructions, file)
    data = run_skill_with_retry(
        DECODE_SKILL, text, ("deliverables", "ambiguities", "definition_of_done")
    )
    return DecodeResponse(**data)


@app.post("/api/verify", response_model=VerifyResponse)
async def verify_submission(
    checklist: str = Form(...),
    submission_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    try:
        checklist_items = json.loads(checklist)
        if not isinstance(checklist_items, list) or not checklist_items:
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Missing or invalid checklist — decode an assignment first.")

    text = await _resolve_text(submission_text, file)

    user_content = (
        "Checklist items:\n"
        + "\n".join(f"- {item}" for item in checklist_items)
        + "\n\n---\n\nSubmission text:\n\n"
        + text
    )

    data = run_skill_with_retry(VERIFY_SKILL, user_content, ("results",))
    results = data["results"]

    if len(results) != len(checklist_items):
        raise HTTPException(
            status_code=502,
            detail="The AI returned a different number of results than checklist items. Please try again.",
        )

    return VerifyResponse(results=[VerifyResult(**r) for r in results])


# ---------- Frontend (served directly, no separate static folder) ----------

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Assignment Decoder</title>
<style>
  :root {
    --bg: #0f1115; --card: #171a21; --border: #2a2e38;
    --text: #e8e9ec; --muted: #9096a3; --accent: #6c8cff; --warn: #ffb454;
    --good: #4ade80; --bad: #ff6b6b;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; display: flex; align-items: flex-start; justify-content: center;
    background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; padding: 24px;
  }
  .wrap { width: 100%; max-width: 560px; display: flex; flex-direction: column; gap: 20px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 32px; }
  .card.disabled { opacity: 0.5; }
  h1 { font-size: 1.3rem; margin: 0 0 4px; }
  h2.stage { font-size: 1rem; margin: 0 0 4px; }
  p.sub { color: var(--muted); margin: 0 0 20px; font-size: 0.9rem; }
  textarea {
    width: 100%; min-height: 120px; background: #0f1115; border: 1px solid var(--border);
    border-radius: 10px; color: var(--text); padding: 12px 14px; font-size: 0.9rem;
    font-family: inherit; margin-bottom: 10px; resize: vertical;
  }
  input[type="file"] { color: var(--muted); font-size: 0.85rem; margin-bottom: 12px; width: 100%; }
  button {
    width: 100%; padding: 12px; border: none; border-radius: 10px; background: var(--accent);
    color: white; font-size: 0.95rem; font-weight: 600; cursor: pointer;
  }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .section { margin-top: 22px; }
  .section h3 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); margin: 0 0 10px; }
  ul { margin: 0; padding-left: 20px; }
  li { margin-bottom: 6px; font-size: 0.92rem; line-height: 1.4; }
  .ambiguity { color: var(--warn); }
  .done-box { background: rgba(108,140,255,0.08); border: 1px solid rgba(108,140,255,0.3); border-radius: 10px; padding: 14px; font-size: 0.92rem; }
  .error { color: var(--bad); font-size: 0.85rem; margin-top: 8px; }
  .hidden { display: none; }
  .empty { color: var(--muted); font-size: 0.88rem; font-style: italic; }
  .verify-item { display: flex; gap: 8px; align-items: flex-start; }
  .badge { flex-shrink: 0; font-size: 0.8rem; }
  .badge.present { color: var(--good); }
  .badge.missing { color: var(--bad); }
  .verify-reason { color: var(--muted); font-size: 0.85rem; margin-left: 4px; }
</style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Assignment Decoder</h1>
      <p class="sub">Stage 1 — paste or upload an assignment prompt. Get a checklist, flagged ambiguities, and what "done" means.</p>

      <textarea id="instructions-input" placeholder="Paste the assignment instructions here..."></textarea>
      <input type="file" id="instructions-file" accept=".txt,.md" />
      <button id="decode-btn">Decode it</button>
      <div id="decode-error" class="error hidden"></div>

      <div id="decode-results" class="hidden">
        <div class="section">
          <h3>Deliverables checklist</h3>
          <ul id="deliverables-list"></ul>
        </div>
        <div class="section">
          <h3>Flagged ambiguities</h3>
          <ul id="ambiguities-list"></ul>
        </div>
        <div class="section">
          <h3>Definition of done</h3>
          <div class="done-box" id="done-box"></div>
        </div>
      </div>
    </div>

    <div class="card disabled" id="verify-card">
      <h2 class="stage">Stage 2 — Verify</h2>
      <p class="sub">Paste or upload your completed submission. We'll check it against the Stage 1 checklist — completeness only, not quality.</p>

      <textarea id="submission-input" placeholder="Paste your completed assignment here..."></textarea>
      <input type="file" id="submission-file" accept=".txt,.md" />
      <button id="verify-btn" disabled>Decode Stage 1 first</button>
      <div id="verify-error" class="error hidden"></div>

      <div id="verify-results" class="hidden section">
        <h3>Checklist coverage</h3>
        <ul id="verify-list"></ul>
      </div>
    </div>
  </div>

<script>
  let currentChecklist = null;

  const decodeBtn = document.getElementById('decode-btn');
  const decodeError = document.getElementById('decode-error');
  const decodeResults = document.getElementById('decode-results');
  const instructionsInput = document.getElementById('instructions-input');
  const instructionsFile = document.getElementById('instructions-file');

  const verifyCard = document.getElementById('verify-card');
  const verifyBtn = document.getElementById('verify-btn');
  const verifyError = document.getElementById('verify-error');
  const verifyResults = document.getElementById('verify-results');
  const submissionInput = document.getElementById('submission-input');
  const submissionFile = document.getElementById('submission-file');

  decodeBtn.addEventListener('click', async () => {
    decodeError.classList.add('hidden');
    const form = new FormData();
    if (instructionsFile.files[0]) {
      form.append('file', instructionsFile.files[0]);
    } else if (instructionsInput.value.trim()) {
      form.append('instructions', instructionsInput.value.trim());
    } else {
      decodeError.textContent = 'Paste some text or choose a file first.';
      decodeError.classList.remove('hidden');
      return;
    }

    decodeBtn.disabled = true;
    decodeBtn.textContent = 'Decoding...';

    try {
      const res = await fetch('/api/decode', { method: 'POST', body: form });
      if (!res.ok) throw new Error((await res.json()).detail || 'Something went wrong.');
      const data = await res.json();

      document.getElementById('deliverables-list').innerHTML =
        data.deliverables.map(d => `<li>${d}</li>`).join('');

      const ambiguitiesList = document.getElementById('ambiguities-list');
      ambiguitiesList.innerHTML = data.ambiguities.length
        ? data.ambiguities.map(a => `<li class="ambiguity">${a}</li>`).join('')
        : '<li class="empty">Nothing flagged — instructions look clear.</li>';

      document.getElementById('done-box').textContent = data.definition_of_done;
      decodeResults.classList.remove('hidden');

      currentChecklist = data.deliverables;
      verifyCard.classList.remove('disabled');
      verifyBtn.disabled = false;
      verifyBtn.textContent = 'Verify against checklist';
    } catch (err) {
      decodeError.textContent = err.message;
      decodeError.classList.remove('hidden');
    } finally {
      decodeBtn.disabled = false;
      decodeBtn.textContent = 'Decode it';
    }
  });

  verifyBtn.addEventListener('click', async () => {
    verifyError.classList.add('hidden');
    if (!currentChecklist) {
      verifyError.textContent = 'Decode Stage 1 first.';
      verifyError.classList.remove('hidden');
      return;
    }

    const form = new FormData();
    form.append('checklist', JSON.stringify(currentChecklist));
    if (submissionFile.files[0]) {
      form.append('file', submissionFile.files[0]);
    } else if (submissionInput.value.trim()) {
      form.append('submission_text', submissionInput.value.trim());
    } else {
      verifyError.textContent = 'Paste your submission or choose a file first.';
      verifyError.classList.remove('hidden');
      return;
    }

    verifyBtn.disabled = true;
    verifyBtn.textContent = 'Verifying...';

    try {
      const res = await fetch('/api/verify', { method: 'POST', body: form });
      if (!res.ok) throw new Error((await res.json()).detail || 'Something went wrong.');
      const data = await res.json();

      document.getElementById('verify-list').innerHTML = data.results.map(r => `
        <li class="verify-item">
          <span class="badge ${r.status}">${r.status === 'present' ? '✅' : '❌'}</span>
          <span>${r.item}<span class="verify-reason"> — ${r.reason}</span></span>
        </li>
      `).join('');
      verifyResults.classList.remove('hidden');
    } catch (err) {
      verifyError.textContent = err.message;
      verifyError.classList.remove('hidden');
    } finally {
      verifyBtn.disabled = false;
      verifyBtn.textContent = 'Verify against checklist';
    }
  });
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE
