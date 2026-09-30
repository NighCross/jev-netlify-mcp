"""Where the server finds the endpoint and the key.

Lookup order for each value (first hit wins):
1. Process environment: JEV_PROXY_URL / JEV_PROXY_KEY, then TYPESAFE_BASE_URL / TYPESAFE_API_KEY.
2. On Windows, the same names in the user's registry environment (HKCU\\Environment).
   MCP clients started before the variable was set, or that filter the environment,
   would otherwise fail silently.
3. The config file written by scripts/setup.py:
   %APPDATA%\\jev-netlify-mcp\\config.env on Windows, ~/.config/jev-netlify-mcp/config.env elsewhere.

The key is never logged or returned.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

URL_NAMES = ("JEV_PROXY_URL", "TYPESAFE_BASE_URL")
KEY_NAMES = ("JEV_PROXY_KEY", "TYPESAFE_API_KEY")
DEFAULT_URL = "https://api.typesafe.ai"


def config_file() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "jev-netlify-mcp" / "config.env"


def registry_enabled() -> bool:
    """Windows registry use can be switched off (the tests do this) with JEV_NETLIFY_MCP_NO_REGISTRY=1."""
    return sys.platform == "win32" and os.environ.get("JEV_NETLIFY_MCP_NO_REGISTRY") != "1"


def _registry(name: str) -> str | None:
    if not registry_enabled():
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            value = str(winreg.QueryValueEx(k, name)[0]).strip()
            return value or None
    except OSError:
        return None


def _file_values() -> dict[str, str]:
    path = config_file()
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def _lookup(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    for name in names:
        value = _registry(name)
        if value:
            return value
    file_values = _file_values()
    for name in names:
        if file_values.get(name):
            return file_values[name]
    return None


def endpoint() -> tuple[str, str]:
    """Return (base_url, key). Raises RuntimeError with a setup hint if the key is missing."""
    key = _lookup(KEY_NAMES)
    if not key:
        raise RuntimeError(
            "No key found. Run `python scripts/setup.py new-key` (proxy) or set TYPESAFE_API_KEY."
        )
    url = _lookup(URL_NAMES) or DEFAULT_URL
    return url.rstrip("/"), key
