"""Filesystem MCP helper shared by the live web app and the batch agent.

Uploaded files are saved to disk, then read back through a real MCP
filesystem server (not a direct open()) - the same mechanism proven out in
mcp_agent/agent.py during Assessment 2.
"""

from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR / "mcp_workspace"
UPLOADS_DIR = WORKSPACE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _server_params() -> StdioServerParameters:
    return StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", str(WORKSPACE_DIR)],
    )


async def read_file_via_mcp(relative_path: str) -> str:
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("read_file", {"path": relative_path})
            return "".join(block.text for block in result.content if hasattr(block, "text"))


async def write_file_via_mcp(relative_path: str, content: str) -> None:
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool("write_file", {"path": relative_path, "content": content})


def save_upload_bytes(filename: str, data: bytes) -> str:
    safe_name = Path(filename).name
    dest = UPLOADS_DIR / safe_name
    dest.write_bytes(data)
    return f"uploads/{safe_name}"
