# Local validation

The client-neutral setup helper also passed three tests covering all 25 app
pairings in its menu, opposite mailbox assignments with one shared database,
backward-compatible default filenames, and actual MCP launches from generated
settings in a folder containing spaces and an apostrophe. This verifies generated
settings and process launches; it is not an end-to-end test inside each AI app.

Validated 2026-11-08 on Windows using Python 3.15.2.

```text
python test_messenger.py
Ran 10 tests in 27.107s
OK

Delivery (UDP wake, 20 samples):
median=46.0ms p95=58.1ms max=65.0ms
```

The measurement covers a real waiting MCP client receiving a message sent through
another MCP subprocess, including local JSON-RPC and database work. It excludes
model inference. This is a local sample, not a cross-platform performance guarantee.

Passed checks: identity and discovery; bidirectional and simultaneous exchange;
Unicode; thread/reply links; pagination and cursors; retry deduplication; per-message
and out-of-order receipts; input and protocol validation; persistence; v1 database
migration; status expiry; resource subscription notifications; request cancellation;
send durability after cancellation; delivery with UDP disabled; and EOF shutdown.

The GitHub Actions workflow is provided for Windows/Linux and Python 3.11/3.13.
Those CI jobs have not run yet. Notification handling was verified with the test
MCP client. Automatic subscription, UI alerts, and model wakeups in Codex or
Antigravity have not been verified. Both clients must reload the new server code
before their live sessions can use the additional tools.
