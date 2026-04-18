"""Drive the running Shard API with several long, varied queues.

Spawns 5 themed children of the live root worker, queues 25 prompts into
each, lets the echoes drain, then pours in 25 authored /reply answers per
worker so the chat panes fill up across many turns.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

API = "http://127.0.0.1:8765"


def _req(method: str, path: str, body: dict | None = None) -> dict:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def _spawn(prefix: str) -> str:
    return _req("POST", "/workers", {"prefix": prefix})["name"]


def _ask(name: str, text: str) -> dict:
    return _req("POST", f"/workers/{name}/prompt", {"text": text})


def _say(name: str, text: str) -> dict:
    return _req("POST", f"/workers/{name}/reply", {"text": text})


def _drain(names: list[str], poll: float = 0.4, timeout: float = 120.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = _req("GET", "/workers")["workers"]
        target = {w["name"]: w for w in data if w["name"] in names}
        pending = sum(w["queue"] + (1 if w["busy"] else 0) for w in target.values())
        if pending == 0:
            return
        time.sleep(poll)


THREADS: list[tuple[str, list[str], list[str]]] = [
    (
        "navigator",
        [f"Plot a route through sector {i:02d}." for i in range(1, 26)],
        [
            "Burn 0.4g for 11 minutes, then coast past the third beacon.",
            "Watch the magnetar at 28\u00b0 — its sweep distorts inertial gyros.",
            "Slingshot the icy moon for a free 1.2 km/s, exit retrograde.",
            "Drop a relay at the L2 saddle so the next hop has comms.",
            "Cut thrust 90 seconds early; the corridor narrows at high v.",
            "Flip-and-burn at midpoint; passenger comfort beats fuel margin.",
            "Take the long arc — pirates hunt the obvious geodesic.",
            "Ride the solar wind on jib sail; engines for the last 6%.",
            "Hold 12 km from the wreck field; debris cone widens hourly.",
            "Skim the gas giant's exosphere for a coolant top-up.",
            "Aim for the Lagrange node, not the planet — gravity tax is steep.",
            "Pull a shallow Hohmann; the deep one wastes a window.",
            "Sync orbit with the survey drone before you commit.",
            "Use the ringplane crossing as a cheap inclination change.",
            "Shadow the freighter convoy for the first 200 Mm.",
            "Fire RCS in pairs; one nozzle is icing over.",
            "Dock with the tug, not the station — fees are murder this cycle.",
            "Plot return early; outbound is the easy half of any trip.",
            "Loiter at the heliopause node until the storm front clears.",
            "Brake against the stellar wind, not against your own tank.",
            "Park behind the asteroid; its shadow is your only ECM.",
            "Cross the void on autopilot; no human reflex helps at 0.1c.",
            "Update the chart — the listed gate moved 4,000 km last refit.",
            "Trust the old beacon over the new one; new ones lie about drift.",
            "End the route at fuel reserve 18% — anything less is bravado.",
        ],
    ),
    (
        "alchemist",
        [f"What does reagent #{i:02d} actually do?" for i in range(1, 26)],
        [
            "Catalyzes nothing alone; pair it with a copper salt for the cascade.",
            "Eats sulfur bonds — handy for breaking polymers, awful near hair.",
            "Glows under UV because of a europium dopant, not magic.",
            "Sequesters iron; never store near rusted tools.",
            "Buffers pH at 7.4 \u00b1 0.05; the body's own choice for a reason.",
            "Volatile above 60 \u00b0C — fume hood or regret.",
            "Acts as a cryoprotectant; cells survive freezes they shouldn't.",
            "Photosensitive; brown bottles aren't decoration, they're necessity.",
            "Quenches free radicals faster than vitamin E by a factor of 30.",
            "Stains skin yellow for a week — wear nitrile or accept the look.",
            "Dimerizes in dry conditions; keep a humidity log.",
            "Mimics adrenaline at receptors but doesn't cross blood-brain.",
            "Cleaves disulfides — perfect for unfolding stubborn proteins.",
            "Smells like almonds, contains zero almond — your nose is fooled.",
            "Fluoresces at 488 nm; cheap blue lasers light it up nicely.",
            "Forms a hydrate that weighs 40% more than the anhydrous form.",
            "Polymerizes if you sneeze near it — argon blanket recommended.",
            "Reduces silver salts to mirror in seconds; impressive, useless.",
            "Chelates lead; first-line for heavy-metal pulls in the field.",
            "Decomposes to CO\u2082 and water on heating; safer than it looks.",
            "Inhibits the Krebs cycle at micromolar concentrations.",
            "Antibacterial against gram-positives; gram-negatives shrug it off.",
            "Plasticizer leeches into PE bottles; use glass for stock.",
            "Crystallizes into needles that are sharp enough to draw blood.",
            "Costs 40\u00d7 the catalog price after the supply cuts \u2014 substitute if you can.",
        ],
    ),
    (
        "scribe",
        [f"How should we phrase clause {i:02d}?" for i in range(1, 26)],
        [
            "Active voice, present tense, single subject, single verb.",
            "Drop the adverbs; the clause earns its weight in nouns.",
            "Replace 'shall' with 'will' — courts read them the same now.",
            "If three commas creep in, you have two clauses, not one.",
            "Say what triggers the obligation, not who hopes for it.",
            "Define the term once at the top, then trust the reader.",
            "Cut hedge words: 'reasonable', 'appropriate', 'as needed'.",
            "Pin the deadline to a calendar date, never to another deadline.",
            "Name the remedy alongside the breach or the breach is decorative.",
            "Quantify everything quantifiable; courts hate \"some\".",
            "Avoid 'hereinafter' — it's a smell, not a term of art.",
            "Reference exhibits by letter and version; stale exhibits sue you.",
            "If both parties can read it the same way, you've succeeded.",
            "Mirror the structure of the prior clause for parsing speed.",
            "Front-load the actor; passive voice hides accountability.",
            "Keep number words consistent: 'five (5)' or '5', never both.",
            "End with the exception, not the rule, when the exception bites.",
            "Use 'including, without limitation' only when you mean it.",
            "Lists of three+ get bullets; lists of two stay inline.",
            "Cap defined terms; never invent two cases for one term.",
            "Write the title last — it's a promise the body must keep.",
            "Replace 'best efforts' with concrete, measurable obligations.",
            "If the clause survives termination, say so in the clause.",
            "Cross-reference by section number, never by page.",
            "Read it aloud — if you stumble, the judge will too.",
        ],
    ),
    (
        "luthier",
        [f"How do I shape facet {i:02d} of the body?" for i in range(1, 26)],
        [
            "Plane against the grain, then with — twice the work, half the tear-out.",
            "Match the radius to the player's wrist, not the catalog jig.",
            "Hollow the back 3 mm under the bridge for a brighter top end.",
            "Chamfer the binding so light catches it from across the room.",
            "Bevel the bout at 7\u00b0 — the forearm thanks you for hours.",
            "Score the heel before you carve; the cut wants a starting line.",
            "Listen to the tap tone; if it thuds, scrape the brace lighter.",
            "Match the kerfing pattern to the top thickness, not the species.",
            "Slot the nut last — measurements drift across a build.",
            "Round the edges where the strap rubs; sharp wood makes scars.",
            "Burnish, don't sand, the final pass — pores stay open and sing.",
            "Sight down the neck after every glue-up; truss rods can't fix twist.",
            "Carve the peghead overlay flush with a card scraper, never a sander.",
            "Set the saddle compensation by ear after a week of play, not before.",
            "Match the wood, even the rosette — the eye catches species mismatch.",
            "Brace lighter than you think; the top wants to move.",
            "Cool glue-ups slowly; thermal stress haunts cheap hide glue.",
            "Plane the binding flush with the top before the lacquer or never.",
            "Dye the inside of the soundhole black; eyes drift inward, then home.",
            "Round-over the fret ends only after the second leveling pass.",
            "Polish the frets with 12,000 grit micro-mesh; lower grits dull tone.",
            "Match the heel cap grain to the back, not the sides.",
            "Bevel the saddle for a clean break angle — buzz lives in flat saddles.",
            "Final-coat in thin passes; thick lacquer kills resonance.",
            "Sign the inside in pencil, not ink — ink bleeds through 50 years on.",
        ],
    ),
    (
        "gardener",
        [f"What should I plant in plot #{i:02d}?" for i in range(1, 26)],
        [
            "Tomatoes — the south wall holds heat well past dusk.",
            "Cilantro now, dill in eight weeks, basil only after the last frost.",
            "Garlic in fall, harvested in midsummer; nothing easier earns more.",
            "A pollinator strip — bees triple yields three plots over.",
            "Squash, but trellised; ground sprawl invites borers.",
            "Radishes as a quick row marker; harvest before main crops shade them.",
            "Beans climb corn; corn shades lettuce — the old three sisters work.",
            "Comfrey at the edge — chop-and-drop fertilizer all season.",
            "Strawberries; renew the patch every three years or yields tank.",
            "A clover cover crop — nitrogen for next season, beauty now.",
            "Beets for the root, the greens for the cook — twice the harvest.",
            "Carrots in deep loose soil only; they fork in clay.",
            "Sunflowers along the north fence; they shade nothing important.",
            "Kale survives a freeze that kills lettuce — late season insurance.",
            "Mint, but in a sunken pot; loose mint becomes a lawn.",
            "Asparagus once, harvest for twenty years; pick the spot carefully.",
            "Chard for color and yield; cut outer leaves, the plant rebuilds.",
            "Brassicas with a netting frame; cabbage moths are relentless.",
            "Onions long-day variety this far north; short-day will bolt.",
            "Borage near tomatoes — the bees love it, hornworms don't.",
            "Pumpkins along the compost edge; volunteers outproduce planted.",
            "Sweet potatoes in raised mounds; clay drowns the tubers.",
            "Rhubarb in the worst corner; it forgives everything except wet feet.",
            "Lavender for the dry spot — water it and you'll kill it.",
            "Leave one bed fallow; soil microbes thank you with next year's harvest.",
        ],
    ),
]


def main() -> None:
    print(f"=== shard long queues ===")
    print(f"api: {API}\n")

    workers: list[tuple[str, str, list[str], list[str]]] = []
    for prefix, prompts, replies in THREADS:
        name = _spawn(prefix)
        workers.append((name, prefix, prompts, replies))
        print(f"  spawned {name:<24}  topic={prefix:<10}  prompts={len(prompts)} replies={len(replies)}")
    print()

    print("--- phase 1: queue prompts ---")
    for name, prefix, prompts, _ in workers:
        for i, q in enumerate(prompts, 1):
            r = _ask(name, q)
            if i == 1 or i % 5 == 0 or i == len(prompts):
                print(f"  [{name}] q{i:02d}/{len(prompts)} qsize={r.get('queue', '?')}")
    print()

    print("--- waiting for echoes to drain ---")
    _drain([w[0] for w in workers], poll=0.5, timeout=300)
    print("  all idle\n")

    print("--- phase 2: authored replies ---")
    for name, prefix, _, replies in workers:
        for i, a in enumerate(replies, 1):
            r = _say(name, a)
            if i == 1 or i % 5 == 0 or i == len(replies):
                print(f"  [{name}] a{i:02d}/{len(replies)} hist={r.get('history_len', '?')}")
    print()

    print("--- final ---")
    snap = _req("GET", "/workers")["workers"]
    for w in snap:
        if w["name"] in {n for n, *_ in workers}:
            print(f"  {w['name']:<24} hist={w['history_len']:>3}  queue={w['queue']}  busy={w['busy']}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        raise SystemExit(f"could not reach {API}: {exc}")
