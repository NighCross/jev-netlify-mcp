# jev-netlify-mcp

[Türkçe](README.tr.md)

Use TypeSafe's **Jev** (a System One decision model) from Claude Code, Codex CLI, Claude Desktop
or any MCP client, paid for by your free Netlify credits and locked with a key only you have.

It has two parts:

1. **A key-locked Netlify proxy** (`proxy/`). One small function that exposes the TypeSafe API
   routes (`POST /v1/systemone`, `GET /v1/models`) and forwards calls through
   [Netlify AI Gateway](https://docs.netlify.com/build/ai-gateway/overview/). Netlify injects the
   gateway credentials, so you never create a TypeSafe API key. Requests without your key get
   `401` and never reach the model.
2. **An MCP server** (`src/jev_netlify_mcp/`). Two tools, `jev_evaluate` and `jev_models`, plus
   instructions that teach the agent how to ask Jev good questions (atomic questions, the three
   question types, translating non-English input to English and reporting back in the user's
   language, flagging low-confidence answers).

The MCP server also works directly against the TypeSafe API if you already have a key.

## Why

There are many Jev MCP servers already. This one exists for the part they do not cover: getting
private Jev access without a TypeSafe balance, by using the Netlify free plan (300 credits per
month). In our measurement 18,000 Jev tokens cost 0.11 credits. The larger cost is deploying:
each production deploy uses 15 credits, so deploy once and leave it.

## Requirements

- Python 3.10+
- A Netlify account (the free plan is enough) with AI features left enabled
- Node.js 20+ only if you want to run the proxy tests

## Setup

```bash
git clone <this repo URL>
cd jev-netlify-mcp
pip install .                         # installs the jev-netlify-mcp command

python scripts/setup.py new-key       # creates your key, builds dist/jev-proxy.zip
```

Sign in to Netlify, then deploy `dist/jev-proxy.zip` with [Netlify Drop](https://app.netlify.com/drop)
(drag the zip or the `dist/site` folder). Without signing in, Drop sites expire. Netlify Drop sites are production deploys, which is what activates
AI Gateway. Then save the site address and check it:

```bash
python scripts/setup.py set-url https://<your-site>.netlify.app
python scripts/setup.py check          # expects 401 without key and 200 with key
python scripts/setup.py check --live   # also asks Jev one question (tiny credit use)
```

The key is stored in your user config file (`%APPDATA%\jev-netlify-mcp\config.env` on Windows,
`~/.config/jev-netlify-mcp/config.env` elsewhere) and, on Windows, in your user environment
variables. Only its SHA-256 hash is put into the function. `setup.py` never prints the key unless
you run `show-key`.

If you would rather keep the hash out of the deployed file, set a Netlify environment variable named
`JEV_PROXY_KEY_SHA256` to the hash and redeploy. Do not name it `TYPESAFE_*`: if you set those
yourself, Netlify stops injecting the AI Gateway credentials.

## Connect your agent

**Claude Code**

```bash
claude mcp add --scope user jev -- jev-netlify-mcp
```

**Codex CLI** (`~/.codex/config.toml`)

```toml
[mcp_servers.jev]
command = "jev-netlify-mcp"

# optional: let `codex exec` call the tools without asking
[mcp_servers.jev.tools.jev_evaluate]
approval_mode = "approve"

[mcp_servers.jev.tools.jev_models]
approval_mode = "approve"
```

**Claude Desktop** (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "jev": { "command": "jev-netlify-mcp" }
  }
}
```

If the command is not on your PATH, use the full path to your Python and
`["-m", "jev_netlify_mcp"]` as arguments.

Then just ask, for example: *"Use Jev: is this support email urgent, and which team should get it:
sales, logistics or tech support?"*

## Configuration

| Variable | Meaning |
|---|---|
| `JEV_PROXY_URL` | Your Netlify site address |
| `JEV_PROXY_KEY` | Your proxy key |
| `TYPESAFE_BASE_URL`, `TYPESAFE_API_KEY` | Fallbacks, so the server also works with the TypeSafe API directly |

Each value is looked up in the process environment, then (Windows) the user registry environment,
then the config file. The registry step matters because some MCP clients do not pass environment
variables to the server. Set `JEV_NETLIFY_MCP_NO_REGISTRY=1` to skip the registry.

The official TypeSafe SDKs also work with the proxy: point `TYPESAFE_BASE_URL` at your site and set
`TYPESAFE_API_KEY` to your proxy key (`python scripts/setup.py show-key`).

## Tools

- `jev_evaluate(state, questions, model="jev-latest")`: one call per text, as many questions as you
  like. Question types: `noul` (yes/no, returns a probability), `choice` (one of named options) and
  `score` (ordered levels, up to 10). State and questions share about 32k tokens.
- `jev_models()`: lists the models on the endpoint.

## Security notes

- Keep your site address and key to yourself. Anyone with both can spend your credits.
- If the key leaks: `python scripts/setup.py new-key --force`, then deploy `dist/` again.
- Free plan AI Gateway limit is 90 credits per minute. When credits run out the site stops until
  the next month; there are no overage charges on the free plan.

## Tests

```bash
node --test tests/*.test.mjs     # proxy function, offline
python -m pytest tests -q        # MCP server over stdio (fake Jev) plus setup.py
```

## Disclaimer

Not affiliated with TypeSafe or Netlify. Jev, TypeSafe and Netlify are their owners' trademarks.
Check the current Netlify and TypeSafe terms before relying on this.

## License

MIT
