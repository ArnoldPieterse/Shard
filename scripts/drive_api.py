"""Drive the running Shard instance via API:
- discover the root worker
- fork 3 subprocessors
- send 10 prompts to each
- post 10 assistant replies to each (authored here)
"""
from __future__ import annotations

import json
import time
import urllib.request

API = "http://127.0.0.1:8765"


def _req(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = r.read().decode("utf-8")
    return json.loads(raw) if raw else {}


# ---- conversation content (3 subprocs × 10 Q/A) ----------------------------
TOPICS: dict[str, list[tuple[str, str]]] = {
    "stargazer": [
        ("What is the most distant object visible to the naked eye?",
         "The Andromeda galaxy at ~2.5 million light-years — a smudge older than your whole species."),
        ("Why do stars twinkle but planets don't?",
         "Stars are point sources so atmospheric turbulence smears them; planets are tiny disks that average out."),
        ("How long would it take to walk to the Sun?",
         "About 3,400 years at 5 km/h — and you'd be vapor for the last 3,399 of them."),
        ("What's a Dyson swarm?",
         "A constellation of solar collectors orbiting a star to harvest a meaningful fraction of its output."),
        ("Why is the night sky dark?",
         "Olbers' paradox: a finite, expanding universe means most starlight never reaches us, or arrives redshifted."),
        ("What dies brighter, a supernova or a kilonova?",
         "Supernovae usually win in raw luminosity, but kilonovae forge most of the universe's gold."),
        ("Could we ever see the cosmic dark ages?",
         "Possibly via the redshifted 21-cm hydrogen line, if we build a quiet enough radio array on the far side of the Moon."),
        ("Is there sound in space?",
         "Vacuum carries no pressure waves, but plasma supports magnetosonic modes — space hums, just not for ears."),
        ("Why does the Moon always show one face?",
         "Tidal locking: Earth's pull synced its rotation and orbital periods over billions of years."),
        ("What's the loneliest place in the universe?",
         "The Boötes void — 330 million light-years across with almost nothing in it."),
    ],
    "luthier": [
        ("Why does spruce dominate soundboards?",
         "High stiffness-to-weight: it moves a lot of air for very little mass, which is exactly what a soundboard wants."),
        ("What does an arched top do that a flat top doesn't?",
         "It trades sustain for projection and focus — punchy mids that cut through a horn section."),
        ("Bone or synthetic nut?",
         "Bone for crispness and overtone clarity; synthetics for consistency, but the high frequencies feel a touch glassy."),
        ("Why scallop a brace?",
         "To free the soundboard's mass where it wants to vibrate while keeping stiffness where it needs to resist string tension."),
        ("Hide glue or aliphatic?",
         "Hide for tone transmission and reversibility; aliphatic for speed and forgiveness on the bench."),
        ("How does a guitar break in?",
         "Cellulose chains relax under cyclic load; the top loosens and the fundamentals bloom over months and years."),
        ("Why is rosewood restricted?",
         "CITES Appendix II: overharvesting threatened wild populations, so cross-border movement now needs paperwork."),
        ("What is the wolf note?",
         "A pitch where a body resonance fights the string mode, producing a beating, unstable tone — usually around F on a cello."),
        ("Why fan-fret?",
         "Per-string scale length tunes tension and intonation, especially helpful for extended-range basses and baritones."),
        ("What does French polish actually do?",
         "Builds a microscopically thin shellac film that lets the top breathe — minimal damping, maximum gloss."),
    ],
    "cartographer": [
        ("Why is Greenland so huge on Mercator?",
         "Mercator preserves angles by stretching area toward the poles — Greenland looks Africa-sized but is ~14× smaller."),
        ("What projection should a hiker use?",
         "A local conformal one like UTM: shapes and small distances stay accurate within each 6° zone."),
        ("Are there still blank spots on Earth?",
         "Yes — most of the deep ocean floor is mapped only at multi-kilometer resolution, coarser than Mars."),
        ("Why do borders follow rivers?",
         "Rivers were natural, defensible, and easy to describe in treaties — until they meander and start a lawsuit."),
        ("What's a contour line, intuitively?",
         "A horizontal slice of the landscape: walk along one and you neither climb nor descend."),
        ("Why is true north different from magnetic north?",
         "The magnetic pole wanders with the molten core; true north is the rotational axis. The gap is called declination."),
        ("Can a map be politically neutral?",
         "No. Every choice — projection, label, border style, what to omit — encodes a worldview."),
        ("What is a geodesic?",
         "The shortest path on a curved surface — on Earth, a great-circle arc, which is why flights look bent on flat maps."),
        ("Why are old maps so beautiful?",
         "When the data was sparse, cartographers filled the gaps with art — sea monsters were honest about uncertainty."),
        ("What replaces paper maps?",
         "Vector tiles streamed on demand, styled client-side — the map is now a query, not a document."),
    ],
}


def main() -> None:
    print("=== shard api driver ===")
    workers = _req("GET", "/workers")["workers"]
    if not workers:
        raise SystemExit("no workers running")
    root = workers[0]["name"]
    print(f"root worker: {root}")

    # Fork 3 subprocessors.
    children: list[str] = []
    for _ in range(3):
        child = _req("POST", f"/workers/{root}/fork")["name"]
        children.append(child)
        print(f"  forked: {child}")

    # Pair each child with a topic.
    pairs = list(zip(children, TOPICS.items()))

    # Phase 1 — send 10 prompts to each.
    print("\n--- phase 1: prompts ---")
    for child, (topic, qa) in pairs:
        print(f"[{child}] topic={topic}")
        for i, (q, _a) in enumerate(qa, 1):
            r = _req("POST", f"/workers/{child}/prompt", {"text": q})
            print(f"  prompt {i:2d}: queued={r.get('queued')} qsize={r.get('queue')}")

    # Wait for the queues to drain (each prompt streams the echo back).
    print("\n--- waiting for echoes to drain ---")
    while True:
        snap = _req("GET", "/workers")["workers"]
        pending = sum(s["queue"] + (1 if s["busy"] else 0)
                      for s in snap if s["name"] in children)
        print(f"  pending={pending}")
        if pending == 0:
            break
        time.sleep(0.5)

    # Phase 2 — author replies via /reply.
    print("\n--- phase 2: replies ---")
    for child, (_topic, qa) in pairs:
        for i, (_q, a) in enumerate(qa, 1):
            r = _req("POST", f"/workers/{child}/reply", {"text": a})
            print(f"[{child}] reply {i:2d}: history_len={r.get('history_len')}")

    # Final summary.
    print("\n--- final ---")
    for child in children:
        info = _req("GET", f"/workers/{child}")
        print(f"  {child}: history_len={info['history_len']} queue={info['queue']} busy={info['busy']}")


if __name__ == "__main__":
    main()
