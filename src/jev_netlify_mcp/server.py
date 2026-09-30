"""Jev as MCP tools for Claude Code, Codex CLI, Claude Desktop and other MCP clients (stdio)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .config import endpoint

INSTRUCTIONS = """Jev (TypeSafe) is a System One decision model: it does NOT generate text. Give it a text
"state" plus typed questions and it returns calibrated probabilities. Use it for classification,
routing, scoring, yes/no checks and guardrails, especially over many items.
Rules:
- Jev works best in English. If the user writes in another language, translate the state faithfully
  to English (keep numbers, dates, names, urgency and threats), write the questions in English and
  report the answer back in the user's language. Show the English text you sent so the user can check it.
- Keep questions atomic: one idea per question. Split compound questions.
- noul: a yes/no statement; the answer is the probability that it is true.
- choice: pick one option; criteria is {option_name: description}; use meaningful snake_case names.
- score: ordered levels from low to high; criteria is a list of level descriptions (max 10).
- Put many questions about the same text into ONE call; call once per text when processing many texts.
- confidence < 0.5 (choice/score) or noul between 0.35 and 0.65 means the model is unsure: say so.
- State and questions share a budget of roughly 32k tokens per call."""

mcp = MCPServer(name="jev", instructions=INSTRUCTIONS)


def _request(path: str, body: dict | None = None, timeout: float = 120) -> dict:
    # ToolError messages reach the client; other exceptions are hidden by the MCP SDK.
    try:
        base, key = endpoint()
    except RuntimeError as e:
        raise ToolError(str(e)) from None
    req = urllib.request.Request(
        base + path,
        data=None if body is None else json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "jev-netlify-mcp",
        },
        method="GET" if body is None else "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        hint = {401: " (wrong key, or the proxy was deployed with a different key hash)",
                422: " (question format is invalid)",
                429: " (rate or credit limit reached, wait and retry)"}.get(e.code, "")
        raise ToolError(f"Jev API error {e.code}{hint}: {detail}") from None
    except urllib.error.URLError as e:
        raise ToolError(f"Cannot reach {base}: {e.reason}") from None


@mcp.tool(
    name="jev_evaluate",
    description=(
        "Evaluate one text (state) against typed questions with Jev and return calibrated answers. "
        "state: string or JSON object (English works best). "
        "questions: {name: {type: 'noul'|'choice'|'score', instructions: str, criteria?: ...}}. "
        "noul criteria optional {true, false}; choice criteria {option: description}; "
        "score criteria [level0, level1, ...] from low to high. model defaults to jev-latest."
    ),
)
def jev_evaluate(state: Any, questions: dict[str, Any], model: str = "jev-latest") -> dict:
    return _request("/v1/systemone", {"state": state, "questions": questions, "model": model})


@mcp.tool(name="jev_models", description="List the Jev models and aliases available on this endpoint.")
def jev_models() -> dict:
    return _request("/v1/models")


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
