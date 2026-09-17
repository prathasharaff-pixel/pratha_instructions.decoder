import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not found. Check your .env file.")

client = genai.Client(api_key=GEMINI_API_KEY)

BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BASE_DIR / "mcp_workspace"
SKILL_PATH = BASE_DIR / "skills" / "decode-assignment" / "SKILL.md"

INPUT_FILENAME = "input.txt"
OUTPUT_FILENAME = "output.json"
MAX_ATTEMPTS = 3


def load_skill_instructions() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


async def read_file_via_mcp(session: ClientSession, filename: str) -> str:
    result = await session.call_tool("read_file", {"path": filename})
    text_parts = [block.text for block in result.content if hasattr(block, "text")]
    return "".join(text_parts)


async def write_file_via_mcp(session: ClientSession, filename: str, content: str) -> None:
    await session.call_tool("write_file", {"path": filename, "content": content})


def call_gemini(skill_instructions: str, assignment_text: str) -> str:
    prompt = (
        f"{skill_instructions}\n\n---\n\n"
        f"Here is the raw assignment text to decode:\n\n{assignment_text}"
    )
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
    )
    return response.text.strip()


def clean_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    return text.strip()


async def run_agent():
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", str(WORKSPACE_DIR)],
    )

    skill_instructions = load_skill_instructions()
    print(f"[PERCEIVE] Loaded skill instructions ({len(skill_instructions)} chars)")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            attempt = 0
            success = False

            while attempt < MAX_ATTEMPTS and not success:
                attempt += 1
                print(f"\n=== Attempt {attempt} ===")

                print("[PERCEIVE] Reading input.txt via filesystem MCP server...")
                assignment_text = await read_file_via_mcp(session, INPUT_FILENAME)
                print(f"[PERCEIVE] Read {len(assignment_text)} characters.")

                print("[ACT] Calling Gemini using the decode-assignment skill...")
                raw_response = call_gemini(skill_instructions, assignment_text)
                cleaned = clean_json_text(raw_response)

                print("[REASON] Checking whether the response is valid, complete JSON...")
                try:
                    parsed = json.loads(cleaned)
                    valid = all(
                        key in parsed
                        for key in ("deliverables", "ambiguities", "definition_of_done")
                    )
                except json.JSONDecodeError:
                    parsed = None
                    valid = False

                if not valid:
                    print("[REASON] Response was invalid or incomplete. Retrying...")
                    continue

                print("[REASON] Response looks valid. Proceeding to write it out.")

                output_str = json.dumps(parsed, indent=2)
                print("[ACT] Writing output.json via filesystem MCP server...")
                await write_file_via_mcp(session, OUTPUT_FILENAME, output_str)

                print("[OBSERVE] Reading output.json back to confirm the write worked...")
                confirm = await read_file_via_mcp(session, OUTPUT_FILENAME)
                if confirm.strip() == output_str.strip():
                    print("[OBSERVE] Confirmed: output.json matches what we wrote.")
                    success = True
                else:
                    print("[OBSERVE] Mismatch detected. Retrying...")

            if success:
                print("\nAgent finished successfully. See mcp_workspace/output.json")
            else:
                print(f"\nAgent failed after {MAX_ATTEMPTS} attempts.")


if __name__ == "__main__":
    asyncio.run(run_agent())
