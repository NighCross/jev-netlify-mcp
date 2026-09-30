"""End-to-end test of the MCP server over stdio against a fake Jev endpoint. Run: python -m pytest tests"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
KEY = "jevp_test_key"


class FakeJev(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep test output clean
        pass

    def _reply(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _ok(self) -> bool:
        if self.headers.get("Authorization") != f"Bearer {KEY}":
            self._reply(401, {"error": {"type": "authentication_error"}})
            return False
        return True

    def do_GET(self):
        if self._ok():
            self._reply(200, {"models": [{"name": "jev-latest"}]})

    def do_POST(self):
        if self._ok():
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            answers = {name: {"noul": 0.87} for name in body["questions"]}
            self._reply(200, {"answers": answers, "echo_state": body["state"], "model": body["model"]})


def _serve() -> HTTPServer:
    server = HTTPServer(("127.0.0.1", 0), FakeJev)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


async def _session_run(env: dict[str, str]):
    params = StdioServerParameters(command=sys.executable, args=["-m", "jev_netlify_mcp"], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = sorted(t.name for t in (await session.list_tools()).tools)
            models = await session.call_tool("jev_models", {})
            evaluated = await session.call_tool("jev_evaluate", {
                "state": "The package is late.",
                "questions": {"late": {"type": "noul", "instructions": "The package is late"}},
            })
            return tools, models, evaluated


def _base_env(tmp_path: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("JEV_", "TYPESAFE_"))}
    env["PYTHONPATH"] = str(ROOT / "src")
    env["XDG_CONFIG_HOME"] = str(tmp_path)  # isolate from any real config file
    env["APPDATA"] = str(tmp_path)
    env["JEV_NETLIFY_MCP_NO_REGISTRY"] = "1"  # never read or write the real Windows registry
    return env


def test_tools_over_stdio(tmp_path):
    server = _serve()
    try:
        env = _base_env(tmp_path) | {"JEV_PROXY_URL": f"http://127.0.0.1:{server.server_port}", "JEV_PROXY_KEY": KEY}
        tools, models, evaluated = asyncio.run(_session_run(env))
    finally:
        server.shutdown()
    assert tools == ["jev_evaluate", "jev_models"]
    assert not models.is_error and "jev-latest" in models.content[0].text
    assert not evaluated.is_error
    payload = json.loads(evaluated.content[0].text)
    assert payload["answers"]["late"]["noul"] == 0.87
    assert payload["model"] == "jev-latest"


def test_wrong_key_is_reported_without_leaking_it(tmp_path):
    server = _serve()
    try:
        env = _base_env(tmp_path) | {"JEV_PROXY_URL": f"http://127.0.0.1:{server.server_port}", "JEV_PROXY_KEY": "jevp_wrong"}
        _, models, _ = asyncio.run(_session_run(env))
    finally:
        server.shutdown()
    assert models.is_error
    text = models.content[0].text
    assert "401" in text and "jevp_wrong" not in text


def test_setup_builds_dist_without_printing_key(tmp_path):
    env = _base_env(tmp_path)
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "setup.py"), "new-key"],
                         env=env, capture_output=True, text=True, check=True).stdout
    config = (tmp_path / "jev-netlify-mcp" / "config.env").read_text()
    key = next(l.split("=", 1)[1] for l in config.splitlines() if l.startswith("JEV_PROXY_KEY="))
    assert key not in out
    fn = (ROOT / "dist" / "site" / "netlify" / "functions" / "jev.mjs").read_text()
    assert "__JEV_PROXY_KEY_SHA256__" not in fn and key not in fn
    assert (ROOT / "dist" / "jev-proxy.zip").is_file()
