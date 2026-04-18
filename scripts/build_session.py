"""Build a richer, trackable session through the Shard HTTP API.

Spawns four top-level subprocessors with descriptive prefixes and runs a
multi-turn dialogue on each — sometimes queue-then-answer, sometimes
answer-first, sometimes a mix. Writes ``scripts/last_session.json`` so the
session can be referenced (or replayed) later.

Run with the Shard app already running on http://127.0.0.1:8765.
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8765"
HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "last_session.json"


# ---- tiny HTTP helper -------------------------------------------------------
def _req(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = r.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def _ask(worker: str, text: str) -> None:
    _req("POST", f"/workers/{worker}/prompt", {"text": text})


def _say(worker: str, text: str) -> None:
    _req("POST", f"/workers/{worker}/reply", {"text": text})


def _drain(workers: list[str], poll: float = 0.4) -> None:
    """Block until every named worker has an empty queue and isn't busy."""
    while True:
        snap = _req("GET", "/workers")["workers"]
        pending = sum(s["queue"] + (1 if s["busy"] else 0)
                      for s in snap if s["name"] in workers)
        if pending == 0:
            return
        time.sleep(poll)


# ---- conversation scripts ---------------------------------------------------
# Each turn is (mode, text) where mode is "ask" (queue a user prompt) or
# "say" (post an authored assistant reply). The order matters and is the
# whole point of this script — different threads use different patterns.

ARCHITECT = [  # classic Q -> A -> Q -> A (queue-then-answer)
    ("ask", "Sketch a small service for tracking forked conversations."),
    ("say", "Single Python process, SQLite for history, an HTTP layer that "
            "speaks JSON, and a thin Qt UI as one of many possible clients."),
    ("ask", "Where does state live, and who owns the write path?"),
    ("say", "The manager owns the in-memory worker registry; SQLite is the "
            "only durable store; the HTTP API is a thin facade over the "
            "manager so the UI and external callers share one source of truth."),
    ("ask", "How do you keep the API responsive while a worker is busy?"),
    ("say", "Each worker runs on its own thread with a bounded queue; the "
            "API just drops items on the queue and returns 202. Streaming "
            "responses go out via signals so the UI updates without polling."),
]

SCRIBE = [  # answer-first: state a thesis, then probe it
    ("say", "Persistence should be boring: append-only history with atomic "
            "writes, one file per worker, no schema migrations, ever."),
    ("ask", "Why one file per worker rather than a single database?"),
    ("say", "Because workers are independent units of failure and inspection. "
            "A bad write corrupts one transcript, never the whole archive, "
            "and `git diff` works on the result."),
    ("ask", "What about querying across workers?"),
    ("say", "That's a separate index built on demand. The source of truth "
            "stays human-readable; the index can be rebuilt from scratch."),
]

SCOUT = [  # mixed: short bursts, alternating
    ("ask", "What's the smallest interesting feature to add next?"),
    ("say", "A `/workers/<n>/tail?since=<idx>` endpoint so external clients "
            "can stream new history entries without re-fetching the whole list."),
    ("ask", "And the largest one we should NOT add yet?"),
    ("say", "Multi-process workers. Threads are sufficient until they aren't, "
            "and the GIL is not the bottleneck for a text-tracking service."),
    ("ask", "Risks?"),
    ("say", "Two: unbounded history growth, and silent loss if disk fills. "
            "Cap history length per worker; surface write errors to the UI."),
]

ORACLE = [  # all answers — a manifesto, no prompts
    ("say", "Treat every long-running agent as a worker with a name, a queue, "
            "and a transcript. That trio is the whole abstraction."),
    ("say", "Forking is cheap when state is just a list. Make it cheap."),
    ("say", "The API and the UI are peers. Neither is the source of truth; "
            "the manager is."),
    ("say", "Pause/resume is a property of the worker, not the transport. "
            "A paused worker rejects mutations from every client equally."),
    ("say", "Persistence is a side effect of state changes, not a separate "
            "step a caller has to remember."),
]

PLAN: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("architect", "service-design", ARCHITECT),
    ("scribe",    "persistence",    SCRIBE),
    ("scout",     "next-steps",     SCOUT),
    ("oracle",    "principles",     ORACLE),
]


# ---- runner -----------------------------------------------------------------
def main() -> None:
    print("=== shard session builder ===")
    print(f"api: {API}")

    created: list[dict] = []
    for prefix, topic, turns in PLAN:
        name = _req("POST", "/workers", {"prefix": prefix})["name"]
        created.append({"name": name, "prefix": prefix, "topic": topic,
                        "turns": len(turns)})
        print(f"  spawned {name:<24} topic={topic}  turns={len(turns)}")

    # Run each thread's turns in order. Drain after each "ask" so the echo
    # lands before the next "say" (otherwise an authored reply could appear
    # ahead of the echo and read out of order).
    for spec, (_prefix, topic, turns) in zip(created, PLAN):
        name = spec["name"]
        print(f"\n--- {name}  ({topic}) ---")
        for i, (mode, text) in enumerate(turns, 1):
            preview = text if len(text) <= 60 else text[:57] + "..."
            print(f"  {i:>2}. {mode}: {preview}")
            if mode == "ask":
                _ask(name, text)
                _drain([name])
            elif mode == "say":
                _say(name, text)
            else:
                raise ValueError(f"unknown mode: {mode}")

    # Final wait + summary into root for visibility.
    print("\n--- finalizing ---")
    _drain([s["name"] for s in created])

    workers = _req("GET", "/workers")["workers"]
    by_name = {w["name"]: w for w in workers}
    summary_lines = ["session built. threads:"]
    for spec in created:
        info = by_name.get(spec["name"], {})
        spec["history_len"] = info.get("history_len", 0)
        summary_lines.append(
            f"  · {spec['name']}  topic={spec['topic']}  "
            f"history_len={spec['history_len']}")

    # Find the root worker and post the index there.
    root = next((w["name"] for w in workers if w["name"].startswith("root-")), None)
    if root:
        _say(root, "\n".join(summary_lines))
        print(f"  posted index into {root}")

    MANIFEST.write_text(json.dumps({
        "api": API,
        "root": root,
        "threads": created,
    }, indent=2), encoding="utf-8")
    print(f"  manifest: {MANIFEST}")

    print("\n--- done ---")
    for spec in created:
        print(f"  {spec['name']}  history_len={spec['history_len']}")


if __name__ == "__main__":
    main()
