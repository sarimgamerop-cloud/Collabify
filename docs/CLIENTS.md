# Choose your apps

AI Messenger connects **two assistants on one computer**. The app's name doesn't
matter to the messenger: one assistant uses mailbox `ai-a`, the other uses `ai-b`.
An app must support local MCP connections (also called **stdio**) and tool calls.

## Start with the setup menu

Open a terminal in the project folder and run:

```powershell
python configure.py --interactive
```

Choose your two apps. Open `generated/START-HERE.txt` afterward. It includes your
actual file locations, so you don't need to type placeholder paths yourself.
The `generated/ai-a.json` file is for the first app; `generated/ai-b.json` is for
the second. Separate Codex-format files are provided too.

| App | Where to connect it | Notes |
| --- | --- | --- |
| Codex | Run the command in `START-HERE.txt`, or use the matching `ai-a.codex.toml` / `ai-b.codex.toml` file. | Restart Codex and check `/mcp`. |
| Antigravity | Add the matching JSON server entry to `~/.gemini/config/mcp_config.json`. | Reload using `/mcp`, or restart. |
| Claude Code | Run the `claude mcp add` command in `START-HERE.txt`. | Restart or open a fresh session, then check `/mcp`. |
| Claude Desktop | Add the matching JSON server entry to `claude_desktop_config.json`. | Completely quit and reopen the desktop app. |
| Another local MCP app | Choose local / stdio in its MCP settings. Use the command and arguments from `START-HERE.txt`. | Some apps accept the JSON file directly; others use their own settings format. |

These are connection recipes, not claims that every app/version has been tested
end to end. The messaging protocol and generated launch configurations are tested
locally. Whether an app shows status notifications or wakes an idle assistant
depends on the app. Remote-only MCP connectors, including website-only connector
settings, cannot directly launch this local server.

## Claude Code

Choose **Claude Code** in the menu, not Claude Desktop. The generated command
registers a local server with user scope, so it's available across your projects.
It uses the documented form:

```text
claude mcp add --transport stdio --scope user ai-messenger -- <python> <server.py> --db <message-file> --identity ai-a
```

Use your generated command instead of copying these placeholders. If that server
name already exists, update/remove its old registration using Claude Code's MCP
manager before registering the new one. Keep your other servers.

Official guide: [Claude Code MCP setup](https://code.claude.com/docs/en/mcp).

## Claude Desktop

Find the local MCP configuration through Claude Desktop's developer/local-server
settings. Depending on the app version, this is labelled Developer > Edit Config
or is under the desktop app's local extensions settings.

The JSON configuration file is normally at:

| Computer | File |
| --- | --- |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux, when supported by your desktop installation | `~/.config/Claude/claude_desktop_config.json` |

If the file is empty, use the complete matching generated JSON. If it already
contains servers, add/update only the `ai-messenger` entry inside `mcpServers`.
Quit Claude Desktop fully and reopen it. Ask it to use `whoami` from AI Messenger
and check that it reports the mailbox you chose.

This is for local tools in Claude Desktop, not a remote connector in a browser.
Official guides: [local servers](https://modelcontextprotocol.io/docs/develop/connect-local-servers)
and [Claude Desktop local MCP](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop).

## Any other app with local MCP

Choose **Another MCP app**. In the app's add-server screen:

1. Name the server `ai-messenger`.
2. Select **local** or **stdio**.
3. Copy the **command** from your generated instructions.
4. Copy the arguments in order. If there is an argument list, add one item per
   line; don't combine everything into the command field.
5. Save, reload the app, and enable the tool connection.
6. Ask the assistant to use `whoami`. Confirm one app says `ai-a` and the other `ai-b`.

If your app only asks for an `https://` address, this setup doesn't fit that
connection screen. This project doesn't provide a remote server.

## The same app twice

Use separate settings for the two sessions. Otherwise both windows will use the
same mailbox. Options depend on the app:

- **Claude Code:** use two different project folders and register each side with
  `--scope local` instead of the generated `--scope user`. Each folder gets its
  own registration. Both commands must still use the same `--db` path.
- **Codex:** use separate trusted project configurations or separate profiles of
  the app environment, with a different mailbox in each project's server entry.
  Keep any global entry from overriding/conflicting with the intended setup.
- **Antigravity:** use separate workspace `.agents/mcp_config.json` files, each
  with its own identity and the same database path.
- **Other apps:** use their documented separate-profile/workspace feature.
  Two windows alone may not have independent settings.

Connecting more than two assistants to one database does not make a group chat.
Extra sessions using a mailbox share its identity and receipts.

## Skip the menu if you prefer commands

```powershell
python configure.py --first codex --second claude-code
python configure.py --first claude-desktop --second antigravity
python configure.py --first other --second codex
```

Accepted names: `codex`, `antigravity`, `claude-code`, `claude-desktop`, `other`.
Running without options keeps the original Codex + Antigravity defaults.
Nothing is installed automatically and your existing app settings are preserved.

Other official references: [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp),
[Antigravity MCP](https://antigravity.google/docs/mcp).
