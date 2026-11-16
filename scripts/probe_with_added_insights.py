"""Reads each resident's stance with and without the v2 reflection insights.

Run from reverie/backend_server, because that is where the prompt template paths
and utils.py resolve from:

  cd reverie/backend_server
  python3 ../../scripts/compare_reflection_prompts.py <sim> --out insights.json
  python3 ../../scripts/probe_with_added_insights.py <sim> insights.json out.json

Why. compare_reflection_prompts.py shows that the v2 insight prompt writes
insights that name the resident and state what they want or worry about. This
asks whether those insights change what the stance probe reports.

What this does. For each resident, opinion_probe.probe runs twice on the memory
as saved (A), then the v2 insights are stored as thoughts the way reflection
stores them (an event triple, an importance score and an embedding, stamped at the
resident's current time) and the probe runs twice more (B). Everything stays in
RAM: no persona is saved and retrieval uses touch=False. A resident who is asleep
at the saved moment is set awake, since the probe declines to rate sleepers.

Read the output against the direction of each resident's starting stance:
Maya supports, Denise leans in favour, Luis conditionally supports, Rachel and
Elena are undecided, Aisha conditionally opposes, Tom leans against, Marcus
opposes. The Spearman figure ranks the scores against that order. With eight
residents and most scores tied it is a coarse check, so read the scores too.

B is an approximation: all the insights arrive at once as the newest memories,
where a run using v2 would have accumulated them across the day.
"""
import concurrent.futures
import datetime
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "reverie", "backend_server"))

import numpy as np  # noqa: E402
import utils  # noqa: E402
from persona.persona import Persona  # noqa: E402
from persona.cognitive_modules.reflect import (  # noqa: E402
  generate_action_event_triple, generate_poig_score)
from persona.prompt_template.gpt_structure import get_embedding  # noqa: E402
from opinion_probe import probe  # noqa: E402

SIM, INSIGHTS, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
REPEATS = 2
# Direction of each resident's starting persona, strongest support to strongest
# opposition (from "currently" in base_the_ville_datacenter_n8).
SEEDED = {"Maya Okonkwo": 3, "Denise Brooks": 2, "Luis Hernandez": 1,
          "Rachel Nguyen": 0, "Elena Chen": 0,
          "Aisha Rahman": -1, "Tom Whitaker": -2, "Marcus Williams": -3}

data = json.load(open(INSIGHTS))
insights = {}
for r in data["insights"]:
  if r["version"] == "v2" and r["insight"]:
    insights.setdefault(r["name"], [])
    if r["insight"] not in insights[r["name"]]:
      insights[r["name"]] += [r["insight"]]


def read(persona):
  return [probe(persona, with_metadata=True) for _ in range(REPEATS)]


def run(name):
  p = Persona(name, f"{utils.fs_storage}/{SIM}/personas/{name}")
  woke = "sleep" in (p.scratch.act_description or "").lower()
  if woke:
    p.scratch.act_description = "being awake"
  a = read(p)
  for text in insights[name]:
    created = p.scratch.curr_time
    s, pr, o = generate_action_event_triple(text, p)
    p.a_mem.add_thought(created, created + datetime.timedelta(days=30), s, pr, o,
                        text, set([s, pr, o]), generate_poig_score(p, "thought", text),
                        (text, get_embedding(text)), [])
  b = read(p)
  new = set(insights[name])
  used = [sum(1 for i in r["evidence"] if p.a_mem.id_to_node[i].embedding_key in new)
          for r in b]

  def keep(rs):
    return [{k: r[k] for k in ("score", "category", "withheld", "rationale")} for r in rs]

  return name, {"woke": woke, "n_insights": len(insights[name]),
                "A": keep(a), "B": keep(b), "slots_from_insights": used,
                "evidence_total_B": [len(r["evidence"]) for r in b]}


with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  results = dict(pool.map(run, sorted(insights)))
json.dump(results, open(OUT, "w"), indent=1)


def ranks(v):
  v = np.asarray(v, float)
  order = v.argsort(kind="mergesort")
  out = np.empty(len(v))
  i = 0
  while i < len(v):
    j = i
    while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
      j += 1
    out[order[i:j + 1]] = (i + j) / 2
    i = j + 1
  return out


def mean_score(rows):
  s = [r["score"] for r in rows if r["score"] is not None]
  return sum(s) / len(s) if s else None


print(f"\n{'resident':16s}{'seeded':>7s}{'A scores':>11s}{'B scores':>11s}  {'B category':28s}{'slots':>6s}")
for name in sorted(results, key=lambda n: -SEEDED[n]):
  r = results[name]
  show = lambda rows: "/".join("-" if x["score"] is None else str(x["score"]) for x in rows)
  cat = r["B"][0]["category"] or r["B"][0]["withheld"] or ""
  print(f"{name:16s}{SEEDED[name]:>7d}{show(r['A']):>11s}{show(r['B']):>11s}  {cat:28s}"
        f"{r['slots_from_insights'][0]:>3d}/{r['evidence_total_B'][0]}"
        + ("   (was asleep; set awake)" if r["woke"] else ""))

for cond in ("A", "B"):
  pairs = [(SEEDED[n], mean_score(results[n][cond])) for n in results
           if mean_score(results[n][cond]) is not None]
  x, y = zip(*pairs)
  rho = float(np.corrcoef(ranks(x), ranks(y))[0, 1]) if len(set(y)) > 1 else None
  shown = "n/a, all scores equal" if rho is None else f"{rho:+.2f}"
  print(f"{cond}: Spearman vs seeded direction {shown} (n={len(pairs)}), "
        f"score range {min(y):.0f}-{max(y):.0f}, spread (max-min) {max(y) - min(y):.0f}")
