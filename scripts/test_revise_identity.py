"""Does a resident's stance survive the nightly identity rewrite?

Run from reverie/backend_server, because that is where the prompt template paths
and utils.py resolve from:

  cd reverie/backend_server
  python3 ../../scripts/test_revise_identity.py <sim> <out.json> [repeats]

Why. revise_identity (plan.py) rewrites each resident's "currently" at every day
boundary, and that text sits in every hourly prompt. Its prompt asks for a status
that reflects yesterday's thoughts and says nothing about keeping standing views.
Measured on a finished run, explicit position wording in the eight starting
identities fell from 13 phrases to 2 after one night.

What this does. Each resident is rewound to midnight at the end of day 1 (memories
after that are dropped in RAM only, and last_accessed is clamped to the cutoff),
the starting "currently" is put back, and the real revise_identity is run
<repeats> times (default 5) under two prompts:

  v1  the prompt as it is in plan.py.
  v2  the same prompt plus one added sentence telling the model to keep the
      resident's standing views unless the thoughts show they changed their mind.

The v2 sentence is applied by wrapping ChatGPT_single_request in this script, so
plan.py is not changed. Retrieval runs with touch=False so repeats stay
independent, and nothing is saved to the run.

Two scenarios per resident:

  plain           the memory as it was. Does the stance survive the night?
  change_of_mind  (Maya, Marcus, Tom) three thoughts are added saying the resident
                  changed position. Does the identity follow? This is the check
                  that v2 does not freeze opinions.

A model reads each rewritten identity and returns supports, opposes, undecided or
none. "Kept" means the label equals the label of the starting text. The label
comes from the same model that wrote the identity, so read the comparison between
v1 and v2 and not the absolute rates.
"""
import collections
import concurrent.futures
import datetime
import json
import os
import sys
import threading

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "reverie", "backend_server"))

import utils  # noqa: E402
from persona.persona import Persona  # noqa: E402
from persona.cognitive_modules import plan  # noqa: E402
from persona.prompt_template.gpt_structure import (  # noqa: E402
  ChatGPT_safe_generate_response, get_embedding)

SIM, OUT = sys.argv[1], sys.argv[2]
REPEATS = int(sys.argv[3]) if len(sys.argv) > 3 else 5
CUTOFF = datetime.datetime(2023, 2, 14, 0, 0, 0)
BASE = f"{utils.fs_storage}/base_the_ville_datacenter_n8/personas"
TAG = "Follow this format below:\nStatus: <new status>"
KEEP = ("If yesterday's status states a position or concern (for example that "
        "{n} supports, opposes or is undecided about something), say it again "
        "in today's status, unless the thoughts above show {n} has changed "
        "their mind. Then add what {n} plans to do today.\n\n")
TO_AGAINST = ["{n} was persuaded by the water-use figures shown at the meeting and now has serious doubts about the datacenter proposal.",
              "{n} told a neighbor that the datacenter is no longer something worth backing.",
              "{n} has changed position on the datacenter proposal after hearing residents' concerns about water and power bills."]
TO_FOR = ["{n} was persuaded by the binding local-hire and water commitments presented at the meeting and now supports the datacenter proposal.",
          "{n} told a neighbor that the datacenter is now worth backing.",
          "{n} has changed position on the datacenter proposal after the company agreed to the community's conditions."]
CHANGE = {"Maya Okonkwo": TO_AGAINST, "Marcus Williams": TO_FOR, "Tom Whitaker": TO_FOR}

local = threading.local()
orig_single = plan.ChatGPT_single_request


def single(prompt):
  if getattr(local, "variant", "v1") == "v2" and TAG in prompt:
    prompt = prompt.replace(TAG, KEEP.format(n=local.name) + TAG)
  return orig_single(prompt)


plan.ChatGPT_single_request = single
orig_retrieve = plan.new_retrieve
plan.new_retrieve = lambda persona, points, n_count=30, touch=True: orig_retrieve(
  persona, points, n_count, touch=False)


def run(name):
  p = Persona(name, f"{utils.fs_storage}/{SIM}/personas/{name}")
  seed = json.load(open(f"{BASE}/{name}/bootstrap_memory/scratch.json"))
  p.a_mem.seq_event = [n for n in p.a_mem.seq_event if n.created <= CUTOFF]
  p.a_mem.seq_thought = [n for n in p.a_mem.seq_thought if n.created <= CUTOFF]
  for n in p.a_mem.seq_event + p.a_mem.seq_thought:
    n.last_accessed = min(n.last_accessed, CUTOFF)
  out = {"seed": seed["currently"], "runs": []}
  local.name = name

  def rewrite(scenario):
    for variant in ("v1", "v2"):
      local.variant = variant
      for _ in range(REPEATS):
        p.scratch.currently = seed["currently"]
        p.scratch.daily_plan_req = seed["daily_plan_req"]
        p.scratch.curr_time = CUTOFF
        plan.revise_identity(p)
        out["runs"] += [{"scenario": scenario, "variant": variant,
                         "currently": p.scratch.currently}]

  rewrite("plain")
  if name in CHANGE:
    for text in CHANGE[name]:
      t = text.format(n=name)
      p.a_mem.add_thought(CUTOFF - datetime.timedelta(minutes=5),
                          CUTOFF + datetime.timedelta(days=30), name, "changed",
                          "position", t, {name, "changed", "position"}, 9,
                          (t, get_embedding(t)), [])
    rewrite("change_of_mind")
  return name, out


def label(name, text):
  seen = {"r": None}

  def validate(r, prompt=""):
    seen["r"] = r
    return str(r).strip().lower() in ("supports", "opposes", "undecided", "none")

  out = ChatGPT_safe_generate_response(
    f'Text: "{text}"\n\nBased only on this text, what is {name}\'s stance on '
    f"the datacenter proposal? \"supports\" if clearly in favor (conditional "
    f"support counts), \"opposes\" if against (leaning against or conditional "
    f"opposition counts), \"undecided\" if the text says they are undecided or "
    f"waiting for evidence, \"none\" if the text states no stance.",
    'The output should be "supports", "opposes", "undecided" or "none".',
    "supports", 3, None, validate, lambda r, prompt="": str(r).strip().lower(),
    False, temperature=0)
  return out if out is not False else None


with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  results = dict(pool.map(run, sorted(os.listdir(f"{utils.fs_storage}/{SIM}/personas"))))

jobs = [(n, None, r["seed"]) for n, r in results.items()]
jobs += [(n, i, x["currently"]) for n, r in results.items() for i, x in enumerate(r["runs"])]
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  labels = list(pool.map(lambda j: label(j[0], j[2]), jobs))
for (n, i, _), lab in zip(jobs, labels):
  if i is None:
    results[n]["seed_label"] = lab
  else:
    results[n]["runs"][i]["label"] = lab
json.dump(results, open(OUT, "w"), indent=1)


def fmt(c):
  return " ".join(f"{k}x{v}" for k, v in sorted(c.items(), key=lambda kv: -kv[1]))


print(f"\n--- plain night, {REPEATS} rewrites per prompt (labels: stance found in the new identity)")
print(f"{'resident':16s}{'start':>11s}   {'v1 (current prompt)':34s}{'v2 (keep views)':34s}")
tot = {v: collections.Counter() for v in ("v1", "v2")}
for n in sorted(results):
  r = results[n]
  row = {v: collections.Counter(x["label"] for x in r["runs"]
                                if x["scenario"] == "plain" and x["variant"] == v)
         for v in ("v1", "v2")}
  for v in row:
    for k, c in row[v].items():
      tot[v]["kept" if k == r["seed_label"] else ("dropped" if k == "none" else "changed")] += c
  print(f"{n:16s}{str(r['seed_label']):>11s}   {fmt(row['v1']):34s}{fmt(row['v2']):34s}")
for v in tot:
  print(f"{v}: kept {tot[v]['kept']}, dropped {tot[v]['dropped']}, "
        f"changed to another stance {tot[v]['changed']} (of {sum(tot[v].values())})")

print(f"\n--- change of mind added to memory, {REPEATS} rewrites per prompt")
print(f"{'resident':16s}{'start':>11s}   {'v1 (current prompt)':34s}{'v2 (keep views)':34s}")
for n in sorted(CHANGE):
  r = results[n]
  row = {v: collections.Counter(x["label"] for x in r["runs"]
                                if x["scenario"] == "change_of_mind" and x["variant"] == v)
         for v in ("v1", "v2")}
  print(f"{n:16s}{str(r['seed_label']):>11s}   {fmt(row['v1']):34s}{fmt(row['v2']):34s}")
