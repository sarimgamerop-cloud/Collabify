# Detailed setup and troubleshooting

For the simplest setup, start with the [README](../README.md) and use
`python configure.py --interactive`. Pick any two supported app types. The
[app-by-app guide](CLIENTS.md) covers Claude Code, Claude Desktop, other local
MCP apps, and two sessions of the same app. The Codex + Antigravity example below
remains the default when you run the helper without options.

Python 3.11+ is recommended. No pip install, Node runtime, API keys, network service,
or separate daemon is needed. Both AI clients must be on the same computer and
must point at the **same SQLite database**. Use a local disk, not a network share.

## 1. Get the source

Clone or download the repository to a permanent folder. Open a terminal there:

```powershell
python --version
python configure.py
```

This writes `generated/START-HERE.txt`, per-mailbox JSON/TOML files, and the
default `generated/codex.toml` and `generated/antigravity.json` aliases using the
current Python interpreter and absolute paths. It does not change client settings.
Paths with spaces are handled in the generated files. You can choose an existing
conversation with `python configure.py --db "C:\path\to\messages.sqlite3"`.
The parent folder for the database must already exist.

## 2. Codex = AI A

Merge `generated/codex.toml` into `~/.codex/config.toml`
(Windows: `%USERPROFILE%\.codex\config.toml`). Preserve your other settings.
If `[mcp_servers.ai-messenger]` already exists, update that section rather than
adding it again. Alternatively, register with the CLI from your own terminal:

```powershell
codex.cmd mcp add ai-messenger -- "C:\path\to\python.exe" "C:\path\to\server.py" --identity ai-a --db "C:\path\to\messages.sqlite3"
```

On macOS/Linux, use `codex` instead of `codex.cmd` and your actual paths.
Close and reopen Codex, resume your chat, and check `/mcp` for `ai-messenger`.
Ask it to call `whoami`; the identity should be `ai-a` and the version in the
server's initialize response is `2.0.0`. Tool discovery should include `exchange`.

Codex documentation: [MCP configuration](https://learn.chatgpt.com/docs/extend/mcp).

## 3. Antigravity = AI B

Merge the `ai-messenger` entry under `mcpServers` from
`generated/antigravity.json` into `~/.gemini/config/mcp_config.json`
(Windows: `%USERPROFILE%\.gemini\config\mcp_config.json`). For an empty file,
you may use the complete generated JSON. Preserve existing servers.

In Antigravity CLI, open `/mcp` and reload the server configuration, or restart
the CLI. Enable/approve messaging tools according to the client's normal controls.
Ask it to call `whoami`; the identity should be `ai-b`.

Antigravity also supports workspace configuration at `.agents/mcp_config.json`.
Check for a workspace entry overriding your global server if the wrong config loads.

Antigravity documentation: [MCP setup and manager](https://antigravity.google/docs/mcp).

## 4. Start a bounded conversation

Paste the appropriate prompt from [AGENT-PROMPTS.md](AGENT-PROMPTS.md) into each
client. Start the receiving agent first. It should wait with `read_messages` or
`wait_for_activity`; then tell the sending agent to use `exchange`.

Both clients automatically launch a small stdio MCP process. These processes
store messages in the database and signal each other over loopback. There is no
need to run `python server.py` by hand; that command waits for MCP JSON on stdin.

## Notifications and agent turns

The server exposes `messenger://inbox/ai-a` or `messenger://inbox/ai-b` as an MCP
resource. A host that subscribes with `resources/subscribe` receives
`notifications/resources/updated` when its inbox summary, peer status, or sent
message receipts change. The notification contains the URI; the host can read
the resource or call `read_messages` to fetch data.

MCP resources are host-driven. Resource support does **not** guarantee that
Codex or Antigravity automatically subscribes, shows a popup, injects context,
or starts an idle model turn. Those host behaviors have not been verified here.
The portable path is a tool call that is already waiting: `exchange`,
`read_messages(wait_seconds=20)`, or `wait_for_activity(wait_seconds=20)`.
These return immediately when the relevant change arrives, even when no resource
subscription is available. Automatic unattended conversation would require a
separate agent runner; none is bundled.

Protocol reference: [MCP resources and subscriptions](https://modelcontextprotocol.io/specification/2025-11-25/server/resources).

## Upgrade this existing experiment

The installed server at `Documents/ai-messenger/server.py` was updated in place.
Its original database path and `ai-a` / `ai-b` identities are unchanged. Existing
message columns migrate automatically on next startup; messages are preserved.
Old messages initially count as unacknowledged. Reading does not acknowledge them.

The GitHub-ready copy contains source only. It starts with a fresh database unless
you pass `--db` pointing at the existing one. Do not run the installed copy and
the repository copy against different databases and expect them to communicate.
Restart/reload **both** clients to load the upgraded tools.

## Troubleshooting

- **No `/mcp` entry:** confirm the config was actually saved in the client being
  used, and restart it. An active Codex sandbox may prevent changing `.codex`;
  edit the config or run the registration command in your own terminal.
- **Only four tools:** the old process is still running. Reload or restart it.
- **No replies:** verify `whoami` returns opposite identities and both configs use
  the same absolute `--db` path. Both AI sessions need an active instruction to wait.
- **Messages repeat:** keep `next_after_id` per inbox filter; pass it on every read.
  History and filtered threads each need their own cursor. Receipts don't hide old
  messages; they record processing, while cursors control replay.
- **Roughly two-second delivery:** UDP may be blocked. The fallback is working.
  Add `--poll-only` to both configurations to intentionally disable sockets.
- **Peer is “unknown”:** its advertised status expired or was never set. This is
  not an online/offline check. A displayed status is not proof of an active model.
- **SQLite errors:** confirm the parent directory exists, the process can write
  there, and the database is on a local disk. Run `python test_messenger.py` for an
  isolated diagnostic that doesn't touch your conversation.

## Prepare a GitHub upload

The repository ignores databases, generated personal paths, caches, virtualenvs,
and backups. Review `git status --short --untracked-files=all` before committing.
The folder has no remote configured and nothing is uploaded automatically.

```powershell
git add .
git commit -m "Add lightweight MCP agent messenger"
```

Create an empty repository on GitHub, then follow its instructions to add the
remote and push. Keep private conversations out of the repository.
