# Agent: decode-assignment loop

This runs the decode-assignment Skill inside a real perceive -> reason -> act ->
observe loop, using a filesystem MCP server to read the input and write/verify
the output.

## What it does

1. Perceive - reads mcp_workspace/input.txt through a filesystem MCP server.
2. Act - sends that text, plus the instructions in
   skills/decode-assignment/SKILL.md, to Gemini.
3. Reason - checks whether Gemini's response is valid, complete JSON
   (has deliverables, ambiguities, and definition_of_done). If not,
   loops back to step 1 and retries, up to 3 attempts total.
4. Act - writes the valid result to mcp_workspace/output.json through
   the same filesystem MCP server.
5. Observe - reads output.json back and confirms it matches what was
   written, as a sanity check that the write actually succeeded.

## How to run it

1. Make sure you have Python 3.10+ and Node.js (for npx) installed.
2. From the repo root, run these three lines:
   python3 -m venv venv
   source venv/bin/activate
   pip install anthropic mcp google-genai python-dotenv
3. Create a .env file in the repo root (never committed - see .gitignore)
   containing one line:
   GEMINI_API_KEY="your-key-here"
4. Put the assignment text you want decoded into mcp_workspace/input.txt.
5. Run:
   python mcp_agent/agent.py
6. Read the result in mcp_workspace/output.json.

## Known limitation

The model name is currently hardcoded (gemini-3.6-flash) inside
agent.py. If Google retires this model in the future, the agent will
fail with a 404 error naming the model - update the model= line in
call_gemini() to whatever model the error message suggests.
