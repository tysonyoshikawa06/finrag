"""Bare tool-use loop against the raw Anthropic SDK.

Sends a question to a Sonnet class model, executes whatever tool_use blocks
it returns via the MCP bridge, feeds the results back, and repeats until the
model ends its turn or MAX_ITERATIONS is hit."""

import os
from collections.abc import Callable
from pathlib import Path

import anthropic
from dotenv import dotenv_values

from agent.mcp_bridge import MCPBridge

_env = dotenv_values(".env")

MODEL = "claude-sonnet-5"
MAX_ITERATIONS = 10
MAX_TOKENS = 1024
_RESULT_PREVIEW_CHARS = 300

_client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY", _env.get("ANTHROPIC_API_KEY"))
)

# Loaded once at import time and reused across every run_loop call
_SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text(encoding="utf-8")


def _extract_text(content: list) -> str:
    """Join the text blocks in a response's content list into one string"""
    return "\n".join(block.text for block in content if block.type == "text")


def _run_tool_calls(
    bridge: MCPBridge,
    content: list,
    on_call: Callable[[str, dict], None] | None = None,
    on_result: Callable[[str], None] | None = None,
) -> list[dict]:
    """Execute every tool_use block in a response, announcing each call and result"""
    results = []
    for block in content:
        if block.type != "tool_use":
            continue
        if on_call is not None:
            on_call(block.name, block.input)
        else:
            print(f"  [tool call] {block.name}({block.input})")
        result_text = bridge.call_tool(block.name, block.input)
        preview = result_text[:_RESULT_PREVIEW_CHARS]
        if len(result_text) > _RESULT_PREVIEW_CHARS:
            preview += "..."
        if on_result is not None:
            on_result(preview)
        else:
            print(f"  [tool result] {preview}")
        results.append({"type": "tool_result", "tool_use_id": block.id, "content": result_text})
    return results


def run_turn(
    messages: list,
    question: str,
    bridge: MCPBridge,
    tools: list[dict],
    on_call: Callable[[str, dict], None] | None = None,
    on_result: Callable[[str], None] | None = None,
) -> tuple[str, "anthropic.types.Message | None"]:
    """Run one question through the tool-use loop against a persistent messages list

    Appends the user question and every assistant/tool_result turn generated
    while resolving it to messages"""

    messages.append({"role": "user", "content": question})

    response = None
    for _ in range(MAX_ITERATIONS):
        response = _client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            return _extract_text(response.content), response

        # Append all blocks of assistant turn (not just tool_use)
        messages.append({"role": "assistant", "content": response.content})

        tool_results = _run_tool_calls(
            bridge, response.content, on_call=on_call, on_result=on_result
        )
        messages.append({"role": "user", "content": tool_results})

    # Iteration cap reached without the model ending its turn
    fallback_text = _extract_text(response.content) if response is not None else ""
    cap_msg = f"[hit iteration cap of {MAX_ITERATIONS} without a final answer]"
    answer = f"{cap_msg}\n{fallback_text}" if fallback_text else cap_msg
    return answer, response


def run_loop(question: str) -> str:
    """Run one question end-to-end with a fresh, throwaway history and return the answer"""
    bridge = MCPBridge()
    tools = bridge.list_tools()
    messages: list = []
    answer, _ = run_turn(messages, question, bridge, tools)
    return answer
