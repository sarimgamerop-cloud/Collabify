# AI Messenger

**Let two AI assistants talk to each other on your computer.**

For example, ask Codex to plan something and Claude to review it. They can send
each other questions, share progress, and reply without you copying every message
between windows.

You can choose Codex, Antigravity, Claude Code, Claude Desktop, or another app
that supports **local MCP servers**. MCP is simply the way an AI app connects to
extra tools. Here, those extra tools let it send and receive messages.

## What you need

- Two AI apps or sessions on the **same computer**.
- Python 3.11 or newer. If you need it, get it from [python.org](https://www.python.org/downloads/).
- An option in both apps to add a **local MCP server**, sometimes called **stdio**.

AI Messenger needs no extra Python packages, account, or API key. Your AI apps
still use their own accounts and plans as usual. Apps that only accept a website
address for remote tools cannot connect to this local version.

## Set it up

### 1. Keep this folder somewhere permanent

Download or clone this project. Avoid moving the folder after setup, because
your apps will need to find it again.

### 2. Choose your two apps

Open a terminal in this folder. On Windows, you can open the folder in File
Explorer, type `powershell` in its address bar, and press Enter.

Run:

```powershell
python configure.py --interactive
```

Choose your first app and then your second app from the numbered menus.
If Windows doesn't recognise `python`, try `py` in its place. On macOS/Linux,
you may need `python3`.

### 3. Follow your connection instructions

Open **`generated/START-HERE.txt`**. It contains commands or settings prepared
for your computer and your chosen apps. Follow the steps for both apps.

The first assistant gets the name **AI A** and the second gets **AI B**. These
are just mailbox names: either one can be Codex, Claude, Antigravity, or another
compatible app.

If you need help finding the right settings, see the [app-by-app guide](docs/CLIENTS.md).
The setup helper creates instructions; it does not change your app settings itself.

### 4. Restart both apps and try a hello

In the **second app**, say:

> Use AI Messenger to check who you are. Then wait up to 20 seconds for a message
> from the other assistant. When one arrives, reply with a short hello. Stop after
> two empty waits.

While it is waiting, say this in the **first app**:

> Use AI Messenger to send "Hello from the other app!" and wait for a reply.

If both apps can see the messaging tools, you're ready to experiment.

## Try working together

Give both assistants the same task, then say:

> Work with the other assistant through AI Messenger. Agree on who does what.
> Share useful findings and questions. Keep track of messages you've already read.
> Stop after five outgoing messages, two empty waits, or when the task is finished,
> and report the result to me.

The [longer example prompts](docs/AGENT-PROMPTS.md) include tips for dividing work
and avoiding repeated messages. You can use either prompt with any supported app;
choose the one matching its mailbox, AI A or AI B.

## What it can do

- Send messages and wait for replies.
- Show short updates such as "thinking" or "working" when an assistant sets them.
- Keep different topics separate and link replies to earlier messages.
- Show which messages the other assistant has marked as read.
- Save the conversation so it survives an app restart.
- Avoid duplicate sends when an assistant retries the same message correctly.

Messages are stored on your computer. Your chosen AI apps can read them, and
those apps may process them using their own cloud services.

## A few things to know

**Both assistants need to be active.** Receiving a message doesn't necessarily
make an idle app start thinking. Ask the receiving assistant to wait first.

**This connects two mailboxes at a time.** It doesn't create a group chat for
three or more assistants. For a different pair, run setup again and connect the
new apps. Only use one intended assistant per mailbox in a given conversation.

**You can use the same app twice** if it provides separate profiles or workspace
settings. Two windows sharing one global configuration will use the same mailbox.

**No app is guaranteed just because it says MCP.** It must support local stdio
servers and let the assistant call tools. See the [compatibility notes](docs/CLIENTS.md).

## If something doesn't work

| What you see | What to try |
| --- | --- |
| No AI Messenger tools | Follow `START-HERE.txt` for that app, then restart it. |
| Both assistants say they are AI A | Use the AI B settings in the second app. |
| No reply | Ask the other assistant to wait; check both apps use the same message file. |
| The same messages keep appearing | Ask the assistant to save and reuse the inbox cursor returned by each read. |
| Status says "unknown" | The other assistant hasn't set a recent status. It doesn't necessarily mean it is offline. |

More help: [detailed setup and troubleshooting](docs/SETUP.md).

## For people who want the technical details

There are no extra dependencies or separate services. The server uses Python,
SQLite, and small local wake signals, with a fallback if those signals are blocked.

- [Tools and how they work](docs/TOOLS.md)
- [Architecture and limitations](docs/ARCHITECTURE.md)
- [Test results](docs/VALIDATION.md)
- Run the messaging tests: `python test_messenger.py`
- Run the setup-helper tests: `python -m unittest test_configure -v`

The repository leaves private conversations and generated settings out of Git.
Nothing is uploaded automatically. See [how to publish your copy](docs/SETUP.md#prepare-a-github-upload).

[MIT license](LICENSE).
