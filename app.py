import json
import os
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from pypdf import PdfReader
import docx
import io

import mcp_io

load_dotenv()

app = FastAPI(title="Assignment Decoder")

BASE_DIR = Path(__file__).resolve().parent
DECODE_SKILL_PATH = BASE_DIR / "skills" / "decode-assignment" / "SKILL.md"
VERIFY_SKILL_PATH = BASE_DIR / "skills" / "verify-submission" / "SKILL.md"

MAX_ATTEMPTS = 2

DECODE_SKILL = DECODE_SKILL_PATH.read_text(encoding="utf-8")
VERIFY_SKILL = VERIFY_SKILL_PATH.read_text(encoding="utf-8")

PROVIDER_CONFIG = {
    "gemini": {"label": "Google Gemini", "kind": "gemini", "model": "gemini-3.6-flash", "env_key": "GEMINI_API_KEY"},
    "openai": {"label": "OpenAI", "kind": "openai_compatible", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "env_key": "OPENAI_API_KEY"},
    "anthropic": {"label": "Anthropic Claude", "kind": "anthropic", "model": "claude-sonnet-4-6", "env_key": "ANTHROPIC_API_KEY"},
    "groq": {"label": "Groq", "kind": "openai_compatible", "base_url": "https://api.groq.com/openai/v1", "model": "openai/gpt-oss-120b", "env_key": "GROQ_API_KEY"},
    "mistral": {"label": "Mistral", "kind": "openai_compatible", "base_url": "https://api.mistral.ai/v1", "model": "mistral-small-latest", "env_key": "MISTRAL_API_KEY"},
}

ENV_KEY_NAMES = {name: cfg["env_key"] for name, cfg in PROVIDER_CONFIG.items()}


class DecodeResponse(BaseModel):
    deliverables: List[str]
    ambiguities: List[str]
    definition_of_done: str


class VerifyResultItem(BaseModel):
    item: str
    status: str
    note: str


class VerifyResponse(BaseModel):
    results: List[VerifyResultItem]


def extract_text_from_upload(upload: UploadFile) -> str:
    raw = upload.file.read()
    name = (upload.filename or "").lower()

    if name.endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not read PDF file: {e}")

    if name.endswith(".docx"):
        try:
            document = docx.Document(io.BytesIO(raw))
            return "\n".join(p.text for p in document.paragraphs)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not read Word file: {e}")

    try:
        return raw.decode("utf-8", errors="ignore")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read uploaded file: {e}")


async def resolve_text(pasted_text: Optional[str], upload: Optional[UploadFile]) -> str:
    if upload is not None and upload.filename:
        text = extract_text_from_upload(upload)
    else:
        text = pasted_text or ""

    text = text.strip()
    if not text:
        raise HTTPException(
            status_code=400,
            detail="No text found. Paste some text or upload a PDF/DOCX/TXT file.",
        )
    return text


async def perceive_via_mcp(text: str) -> str:
    """
    Writes the resolved text to the MCP filesystem workspace, then reads it
    back through the same MCP server - a real perceive/observe round trip,
    reusing the exact mechanism (mcp_io.py) proven out in the Assessment 2
    agent. If the MCP round trip fails for any reason (npx missing, server
    hiccup, etc.), fall back to using the text we already have in memory
    rather than breaking the request - MCP here is a real, active step, not
    a required single point of failure.
    """
    relative_path = f"uploads/request_{uuid.uuid4().hex[:8]}.txt"
    try:
        await mcp_io.write_file_via_mcp(relative_path, text)
        confirmed_text = await mcp_io.read_file_via_mcp(relative_path)
        if confirmed_text.strip():
            return confirmed_text
        return text
    except Exception as e:
        print(f"[warn] MCP round-trip failed, falling back to in-memory text: {e}")
        return text


def _make_gemini_caller(model: str):
    def caller(prompt: str, api_key: str) -> str:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents=prompt)
        return (response.text or "").strip()
    return caller


def _make_anthropic_caller(model: str):
    def caller(prompt: str, api_key: str) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()
    return caller


def _make_openai_compatible_caller(base_url: str, model: str):
    # Covers OpenAI, Groq, and Mistral - all expose the same
    # POST {base_url}/chat/completions shape, so one implementation works
    # for all three (Groq and Mistral are explicitly OpenAI-compatible).
    def caller(prompt: str, api_key: str) -> str:
        import requests
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    return caller


def _build_caller(config: dict):
    kind = config["kind"]
    if kind == "gemini":
        return _make_gemini_caller(config["model"])
    if kind == "anthropic":
        return _make_anthropic_caller(config["model"])
    if kind == "openai_compatible":
        return _make_openai_compatible_caller(config["base_url"], config["model"])
    raise ValueError(f"Unknown provider kind: {kind}")


PROVIDER_CALLERS = {name: _build_caller(cfg) for name, cfg in PROVIDER_CONFIG.items()}


def resolve_api_key(provider: str, user_supplied_key: Optional[str]) -> str:
    if user_supplied_key and user_supplied_key.strip():
        return user_supplied_key.strip()

    env_key_name = ENV_KEY_NAMES.get(provider)
    fallback_key = os.environ.get(env_key_name) if env_key_name else None
    if fallback_key:
        return fallback_key

    raise HTTPException(
        status_code=400,
        detail=(
            f"No API key available for {provider}. "
            "Add one in Settings (top right), or set it on the server's .env file."
        ),
    )


def clean_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    return text.strip()


def call_ai_for_json(
    skill_instructions: str,
    user_content: str,
    required_keys: List[str],
    provider: str,
    api_key: str,
) -> dict:
    caller = PROVIDER_CALLERS.get(provider)
    if caller is None:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    last_error = "Unknown error."
    prompt = f"{skill_instructions}\n\n---\n\n{user_content}"

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            raw_text = caller(prompt, api_key)
        except Exception as e:
            last_error = f"{provider} request failed (attempt {attempt}): {e}"
            continue

        cleaned = clean_json_text(raw_text)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            last_error = f"{provider} did not return valid JSON on attempt {attempt}."
            continue

        if not all(key in parsed for key in required_keys):
            last_error = f"{provider} response was missing required fields on attempt {attempt}."
            continue

        return parsed

    raise HTTPException(
        status_code=502,
        detail=(
            "The AI didn't return a usable response after multiple attempts. "
            f"Last issue: {last_error} Please try again, or switch providers in Settings."
        ),
    )


@app.post("/api/decode", response_model=DecodeResponse)
async def decode_instructions(
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    provider: str = Form("gemini"),
    api_key: Optional[str] = Form(None),
):
    assignment_text = await resolve_text(text, file)
    assignment_text = await perceive_via_mcp(assignment_text)
    resolved_key = resolve_api_key(provider, api_key)
    data = call_ai_for_json(
        DECODE_SKILL,
        f"Here is the raw assignment text to decode:\n\n{assignment_text}",
        required_keys=["deliverables", "ambiguities", "definition_of_done"],
        provider=provider,
        api_key=resolved_key,
    )
    return DecodeResponse(**data)


@app.post("/api/verify", response_model=VerifyResponse)
async def verify_submission(
    checklist: str = Form(...),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    provider: str = Form("gemini"),
    api_key: Optional[str] = Form(None),
):
    try:
        checklist_items = json.loads(checklist)
        if not isinstance(checklist_items, list) or not checklist_items:
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Checklist was empty or malformed.")

    submission_text = await resolve_text(text, file)
    submission_text = await perceive_via_mcp(submission_text)
    resolved_key = resolve_api_key(provider, api_key)

    checklist_str = "\n".join(f"- {item}" for item in checklist_items)
    user_content = (
        f"Checklist of required deliverables:\n{checklist_str}\n\n"
        f"---\n\nSubmission text to check against the checklist:\n\n{submission_text}"
    )

    data = call_ai_for_json(
        VERIFY_SKILL,
        user_content,
        required_keys=["results"],
        provider=provider,
        api_key=resolved_key,
    )
    return VerifyResponse(**data)


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Assignment Decoder</title>
<style>
  :root {
    --bg: #0b0d12; --card: #14171f; --border: #262b38;
    --text: #eef0f4; --muted: #9399a8; --accent: #7c9bff; --accent2: #57d9a3; --warn: #ffb454; --danger: #ff6b6b;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh;
    background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    padding: 32px 16px; display: flex; justify-content: center;
  }
  .wrap { width: 100%; max-width: 720px; position: relative; }
  .header-row { display: flex; justify-content: space-between; align-items: flex-start; }
  h1 { font-size: 1.6rem; margin: 0 0 4px; }
  p.sub { color: var(--muted); margin: 0 0 28px; font-size: 0.95rem; }

  .gear-btn {
    width: 48px; height: 48px; border-radius: 12px; background: var(--card);
    border: 1px solid var(--border); color: var(--text); font-size: 1.6rem;
    cursor: pointer; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center; line-height: 1;
  }
  .gear-btn:hover { border-color: var(--accent); }

  .settings-panel {
    position: absolute; top: 50px; right: 0; z-index: 10;
    width: 280px; background: var(--card); border: 1px solid var(--border);
    border-radius: 14px; padding: 18px; box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  }
  .settings-panel.hidden { display: none; }
  .settings-panel label { display: block; font-size: 0.78rem; color: var(--muted); margin: 10px 0 4px; text-transform: uppercase; letter-spacing: 0.04em; }
  .settings-panel select, .settings-panel input {
    width: 100%; background: #0b0d12; border: 1px solid var(--border); border-radius: 8px;
    color: var(--text); padding: 8px 10px; font-size: 0.88rem; font-family: inherit;
  }
  .settings-panel .save-row { display: flex; justify-content: flex-end; margin-top: 14px; }
  .settings-panel button.save { padding: 7px 14px; font-size: 0.85rem; }
  .settings-note { font-size: 0.74rem; color: var(--muted); margin-top: 8px; line-height: 1.4; }
  .saved-tag { font-size: 0.72rem; color: var(--accent2); margin-top: 8px; display: none; }

  .stage {
    background: var(--card); border: 1px solid var(--border); border-radius: 16px;
    padding: 28px; margin-bottom: 24px;
  }
  .stage.disabled { opacity: 0.45; pointer-events: none; }
  .stage-title { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
  .stage-num {
    width: 26px; height: 26px; border-radius: 50%; background: var(--accent);
    color: #0b0d12; font-weight: 700; font-size: 0.85rem;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  }
  .stage h2 { font-size: 1.1rem; margin: 0; }
  .stage p.desc { color: var(--muted); font-size: 0.88rem; margin: 4px 0 18px; }
  textarea {
    width: 100%; min-height: 120px; background: #0b0d12; border: 1px solid var(--border);
    border-radius: 10px; color: var(--text); padding: 12px 14px; font-size: 0.9rem;
    font-family: inherit; margin-bottom: 10px; resize: vertical;
  }
  .filerow { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
  .filerow input[type=file] { color: var(--muted); font-size: 0.85rem; flex: 1; }
  .or { color: var(--muted); font-size: 0.8rem; }
  button {
    padding: 11px 18px; border: none; border-radius: 10px; background: var(--accent);
    color: #0b0d12; font-size: 0.92rem; font-weight: 600; cursor: pointer;
  }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .section { margin-top: 20px; }
  .section h3 { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin: 0 0 8px; }
  ul { margin: 0; padding-left: 20px; }
  li { margin-bottom: 6px; font-size: 0.9rem; line-height: 1.4; }
  .ambiguity { color: var(--warn); }
  .done-box { background: rgba(124,155,255,0.08); border: 1px solid rgba(124,155,255,0.3); border-radius: 10px; padding: 12px 14px; font-size: 0.9rem; }
  .error { color: var(--danger); font-size: 0.85rem; margin-top: 10px; }
  .hidden { display: none; }
  .empty { color: var(--muted); font-size: 0.86rem; font-style: italic; }
  .result-row { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 8px; font-size: 0.9rem; }
  .badge { font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 6px; flex-shrink: 0; margin-top: 1px; }
  .badge.present { background: rgba(87,217,163,0.15); color: var(--accent2); }
  .badge.missing { background: rgba(255,107,107,0.15); color: var(--danger); }
  .badge.unclear { background: rgba(255,180,84,0.15); color: var(--warn); }
  .note { color: var(--muted); font-size: 0.82rem; display: block; margin-top: 2px; }
</style>
</head>
<body>
<div class="wrap">
  <div class="header-row">
    <div>
      <h1>Assignment Decoder</h1>
      <p class="sub">Decode a confusing assignment into a checklist, then check your own submission against it.</p>
    </div>
    <button class="gear-btn" id="gear-btn" title="Settings">&#9881;</button>
  </div>

  <div class="settings-panel hidden" id="settings-panel">
    <label for="provider-select">AI Provider</label>
    <select id="provider-select">
      <option value="gemini">Google Gemini</option>
      <option value="openai">OpenAI</option>
      <option value="anthropic">Anthropic Claude</option>
      <option value="groq">Groq</option>
      <option value="mistral">Mistral</option>
    </select>
    <label for="api-key-input">Your API Key</label>
    <input type="password" id="api-key-input" placeholder="Leave blank to use server default" />
    <div class="settings-note">Your key is stored only in this browser (not on our server) and sent only with your own requests. Leave blank to use whatever key the app owner configured.</div>
    <div class="save-row"><button class="save" id="save-settings-btn">Save</button></div>
    <div class="saved-tag" id="saved-tag">Saved.</div>
  </div>

  <div class="stage" id="stage1">
    <div class="stage-title"><div class="stage-num">1</div><h2>Decode the assignment</h2></div>
    <p class="desc">Paste the assignment prompt, or upload it as a PDF, Word doc, or text file.</p>
    <textarea id="decode-text" placeholder="Paste assignment instructions here..."></textarea>
    <div class="filerow">
      <span class="or">or upload:</span>
      <input type="file" id="decode-file" accept=".pdf,.docx,.txt" />
    </div>
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

  <div class="stage disabled" id="stage2">
    <div class="stage-title"><div class="stage-num">2</div><h2>Verify your submission</h2></div>
    <p class="desc">Paste your completed work, or upload it, to check it against the checklist above. This checks completeness only, not quality.</p>
    <textarea id="verify-text" placeholder="Paste your completed submission here..."></textarea>
    <div class="filerow">
      <span class="or">or upload:</span>
      <input type="file" id="verify-file" accept=".pdf,.docx,.txt" />
    </div>
    <button id="verify-btn">Check my submission</button>
    <div id="verify-error" class="error hidden"></div>

    <div id="verify-results" class="hidden">
      <div class="section">
        <h3>Coverage check</h3>
        <div id="results-list"></div>
      </div>
    </div>
  </div>
</div>

<script>
  let lastDeliverables = null;

  const gearBtn = document.getElementById('gear-btn');
  const settingsPanel = document.getElementById('settings-panel');
  const providerSelect = document.getElementById('provider-select');
  const apiKeyInput = document.getElementById('api-key-input');
  const saveSettingsBtn = document.getElementById('save-settings-btn');
  const savedTag = document.getElementById('saved-tag');

  function loadSettings() {
    const provider = localStorage.getItem('ad_provider') || 'gemini';
    const key = localStorage.getItem('ad_api_key') || '';
    providerSelect.value = provider;
    apiKeyInput.value = key;
  }
  function getSettings() {
    return {
      provider: localStorage.getItem('ad_provider') || 'gemini',
      apiKey: localStorage.getItem('ad_api_key') || '',
    };
  }
  loadSettings();

  gearBtn.addEventListener('click', () => {
    settingsPanel.classList.toggle('hidden');
  });
  saveSettingsBtn.addEventListener('click', () => {
    localStorage.setItem('ad_provider', providerSelect.value);
    localStorage.setItem('ad_api_key', apiKeyInput.value.trim());
    savedTag.style.display = 'block';
    setTimeout(() => { savedTag.style.display = 'none'; }, 1500);
  });
  document.addEventListener('click', (e) => {
    if (!settingsPanel.contains(e.target) && e.target !== gearBtn) {
      settingsPanel.classList.add('hidden');
    }
  });

  const decodeText = document.getElementById('decode-text');
  const decodeFile = document.getElementById('decode-file');
  const decodeBtn = document.getElementById('decode-btn');
  const decodeError = document.getElementById('decode-error');
  const decodeResults = document.getElementById('decode-results');

  const stage2 = document.getElementById('stage2');
  const verifyText = document.getElementById('verify-text');
  const verifyFile = document.getElementById('verify-file');
  const verifyBtn = document.getElementById('verify-btn');
  const verifyError = document.getElementById('verify-error');
  const verifyResults = document.getElementById('verify-results');

  decodeBtn.addEventListener('click', async () => {
    decodeError.classList.add('hidden');
    const hasFile = decodeFile.files.length > 0;
    const hasText = decodeText.value.trim().length > 0;
    if (!hasFile && !hasText) {
      decodeError.textContent = 'Paste some text or upload a file first.';
      decodeError.classList.remove('hidden');
      return;
    }

    decodeBtn.disabled = true;
    decodeBtn.textContent = 'Decoding...';

    try {
      const { provider, apiKey } = getSettings();
      const formData = new FormData();
      if (hasFile) {
        formData.append('file', decodeFile.files[0]);
      } else {
        formData.append('text', decodeText.value.trim());
      }
      formData.append('provider', provider);
      formData.append('api_key', apiKey);

      const res = await fetch('/api/decode', { method: 'POST', body: formData });
      if (!res.ok) throw new Error((await res.json()).detail || 'Something went wrong.');
      const data = await res.json();

      document.getElementById('deliverables-list').innerHTML =
        data.deliverables.map(d => `<li>${d}</li>`).join('');

      const ambiguitiesList = document.getElementById('ambiguities-list');
      ambiguitiesList.innerHTML = data.ambiguities.length
        ? data.ambiguities.map(a => `<li class="ambiguity">${a}</li>`).join('')
        : '<li class="empty">Nothing flagged - instructions look clear.</li>';

      document.getElementById('done-box').textContent = data.definition_of_done;
      decodeResults.classList.remove('hidden');

      lastDeliverables = data.deliverables;
      stage2.classList.remove('disabled');
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
    if (!lastDeliverables) {
      verifyError.textContent = 'Decode an assignment first.';
      verifyError.classList.remove('hidden');
      return;
    }
    const hasFile = verifyFile.files.length > 0;
    const hasText = verifyText.value.trim().length > 0;
    if (!hasFile && !hasText) {
      verifyError.textContent = 'Paste your submission or upload a file first.';
      verifyError.classList.remove('hidden');
      return;
    }

    verifyBtn.disabled = true;
    verifyBtn.textContent = 'Checking...';

    try {
      const { provider, apiKey } = getSettings();
      const formData = new FormData();
      formData.append('checklist', JSON.stringify(lastDeliverables));
      if (hasFile) {
        formData.append('file', verifyFile.files[0]);
      } else {
        formData.append('text', verifyText.value.trim());
      }
      formData.append('provider', provider);
      formData.append('api_key', apiKey);

      const res = await fetch('/api/verify', { method: 'POST', body: formData });
      if (!res.ok) throw new Error((await res.json()).detail || 'Something went wrong.');
      const data = await res.json();

      const resultsList = document.getElementById('results-list');
      resultsList.innerHTML = data.results.map(r => `
        <div class="result-row">
          <span class="badge ${r.status}">${r.status}</span>
          <span>${r.item}${r.note ? `<span class="note">${r.note}</span>` : ''}</span>
        </div>
      `).join('');
      verifyResults.classList.remove('hidden');
    } catch (err) {
      verifyError.textContent = err.message;
      verifyError.classList.remove('hidden');
    } finally {
      verifyBtn.disabled = false;
      verifyBtn.textContent = 'Check my submission';
    }
  });
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE
