"""Wraps the async fastmcp.Client in sync methods via asyncio.run.
Tools should never raise
"""

import asyncio
import json

from fastmcp import Client

from mcp_server.server import mcp


def _tool_to_dict(tool) -> dict:
    """Convert an mcp.types.Tool into an Anthropic tool definition dict"""
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.inputSchema,
    }


def _result_to_text(result) -> str:
    """Flatten a CallToolResult's content blocks into one string"""
    parts = [block.text for block in result.content if hasattr(block, "text")]
    return "\n".join(parts) if parts else str(result.content)


async def _list_tools_async() -> list[dict]:
    async with Client(mcp) as client:
        tools = await client.list_tools()
    return [_tool_to_dict(tool) for tool in tools]


async def _call_tool_async(name: str, arguments: dict) -> str:
    """Tool calls should never raise on tool-level failure. Client.call_tool
defaults to raise_on_error=True, so we must explicitly set it to be False"""
    async with Client(mcp) as client:
        result = await client.call_tool(name, arguments, raise_on_error=False)
    return _result_to_text(result)


class MCPBridge:
    """Sync methods onto the in-process streaming-rag MCP server"""

    def list_tools(self) -> list[dict]:
        """Return Anthropic-shaped tool definitions for every registered MCP tool."""
        return asyncio.run(_list_tools_async())

    def call_tool(self, name: str, arguments: dict) -> str:
        """Call an MCP tool by name and return its result as text.

        Errors (validation failures, unknown tool names, etc.) come back as
        text content, never as a raised exception, so the caller can hand the
        result straight to a model as a tool_result block regardless of
        success or failure
        """
        try:
            return asyncio.run(_call_tool_async(name, arguments))
        except Exception as exc:  # defensive: keep connection-level failures as content
            return f"MCP call to {name!r} failed: {exc}"


if __name__ == "__main__":
    bridge = MCPBridge()

    print("=== list_tools() ===")
    for tool_def in bridge.list_tools():
        print(f"\n--- {tool_def['name']} ---")
        print(f"description: {tool_def['description']}")
        print(f"input_schema: {json.dumps(tool_def['input_schema'], indent=2)}")

    print("\n=== call_tool('system_freshness', {}) ===")
    print(bridge.call_tool("system_freshness", {}))

    print("\n=== call_tool('query_stats', {'group_by': 'banana'}) ===")
    print(bridge.call_tool("query_stats", {"group_by": "banana"}))
