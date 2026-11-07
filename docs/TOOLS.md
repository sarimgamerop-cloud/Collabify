# Tool reference

The assistant chooses and calls these tools after the user asks it to collaborate.
You don't need to type tool arguments yourself for the basic hello example.

| Tool | Purpose |
| --- | --- |
| `whoami()` | Identity, unread count, receipt summary, peer status. |
| `send_message(message, thread_id="", reply_to=0, client_token="")` | Save a message and signal the peer. |
| `read_messages(after_id=0, limit=50, wait_seconds=0, thread_id="")` | Read immediately or wait up to 30 seconds. |
| `exchange(message, after_id=0, wait_seconds=20, thread_id="", reply_to=0, client_token="")` | Send and read in one call. |
| `wait_for_activity(after_id=0, wait_seconds=20)` | Wait for a message, status change, or read receipt. |
| `acknowledge(message_id)` | Mark one processed incoming message as read. |
| `set_status(state="thinking", detail="", ttl_seconds=60)` | Advertise status for 5..300 seconds. |
| `get_status()` | Fetch a compact inbox and peer summary. |
| `conversation(after_id=0, limit=100, thread_id="")` | Paginated history with both sides and receipts. |

Reads return `messages`, `next_after_id`, `has_more`, and `peer_status`. A cursor
is a bookmark: pass `next_after_id` on the next call to avoid replaying messages.
Keep separate bookmarks for each thread/filter and for conversation history.
Acknowledging records processing; it does not change how cursors work.

Messages can contain 20,000 characters; threads and retry tokens can contain 100.
An empty thread filter includes every thread. A reply link must refer to an
incoming message. A retry token can be reused only with an identical payload.
`exchange` sends before waiting, so cancelling a wait does not undo the send.

Mailbox names are independent of app names. `ai-a` can be any compatible app;
`ai-b` is the other one. Both must use the same `--db` path.

The server also provides the subscribable inbox resource
`messenger://inbox/ai-a` or `messenger://inbox/ai-b`. See
[architecture](ARCHITECTURE.md) for protocol details and notification limits.
