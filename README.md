# Assignment Decoder

Assignment prompts are often dense or ambiguous - students miss requirements
not from lack of effort, but from misreading the prompt itself. Assignment
Decoder fixes this in two stages.

## What it does

**Stage 1 - Decode:** Paste an assignment prompt (or upload it as a PDF,
Word doc, or text file). The AI parses it into a checklist of every concrete
deliverable, flags anything genuinely ambiguous instead of guessing, and
states a plain-language definition of done.

**Stage 2 - Verify:** Paste your completed submission (or upload it). The
app checks it against the Stage 1 checklist and marks each item present,
missing, or unclear. This is a completeness check, not a quality or grading
check - "did you include a methodology section?" not "is your methodology
any good?"

## Choosing your own AI provider

Click the gear icon (top right) to pick which AI provider powers the app:
Google Gemini, OpenAI, Anthropic Claude, Groq, or Mistral. Paste your own
API key there, or leave it blank to use the server's default key (set in
.env). Your key is stored only in your browser, never on the server.

## How to run it yourself

1. Clone this repo and `cd` into it.
2. Create a Python virtual environment (Python 3.10+ required) and activate it:
   python3 -m venv venv
   source venv/bin/activate
3. Install dependencies:
   pip install fastapi uvicorn python-multipart pypdf python-docx python-dotenv google-genai anthropic openai mcp
4. Node.js (with npx) must also be installed, since the app spins up a real
   MCP filesystem server on every request (see below).
5. Create a `.env` file in the repo root with at least one provider's key, for example:
   GEMINI_API_KEY="your-key-here"
6. Run the app:
   uvicorn app:app --reload
7. Open http://127.0.0.1:8000 in your browser.

## How this incorporates Assessment 2

Assessment 2 built a standalone agent (see mcp_agent/agent.py) that used a
Skill and a filesystem MCP server inside a perceive-reason-act-observe loop.

For this MVP, that mechanism is genuinely incorporated, not just referenced:

- The decode-assignment Skill is reused directly (see
  skills/decode-assignment/SKILL.md), and a new verify-submission Skill was
  added for Stage 2 (see skills/verify-submission/SKILL.md).
- The reasoning/retry loop from Assessment 2 (call the AI, validate the JSON
  response, retry on failure) lives in app.py's call_ai_for_json function.
- The filesystem MCP mechanism itself is reused via mcp_io.py: every request
  (pasted text or an uploaded file, once its text is extracted) is written
  to the MCP workspace and read back through a real MCP filesystem server
  before being sent to the AI - the same perceive/observe round trip the
  Assessment 2 agent used for input.txt and output.json. You can see this
  happening for yourself in mcp_workspace/uploads/, where a new file appears
  for every request.
- If the MCP round trip ever fails (e.g. npx unavailable), the app falls
  back to using the text it already has in memory rather than crashing -
  MCP is a real, active step here, not a single point of failure.

## Known limitations

- Each AI provider needs its own valid API key to actually work - there is
  no universal key that unlocks all five.
- Free tiers (especially Gemini's) can hit daily rate limits quickly during
  testing. Groq's free tier has proven more generous in practice.
- Model names are hardcoded per provider in PROVIDER_CONFIG inside app.py.
  If a provider retires a model, update the "model" value there.
- Every request spins up a fresh MCP filesystem server subprocess, adding
  roughly 1-2 seconds of latency. This is a deliberate trade-off to keep
  the Assessment 2 mechanism genuinely active, not a bug.
