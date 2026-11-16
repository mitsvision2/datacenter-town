"""Compares finished runs of scripts/run_identity_ab.py.

Run from reverie/backend_server, because that is where utils.py resolves from:

  cd reverie/backend_server
  python3 ../../scripts/analyze_identity_ab.py ab-v1-1 ab-v1-2 ab-v2-2 [--out FILE]

Run names are the <name> given to run_identity_ab.py; the saved runs are
stg-<name>. A run counts toward an arm by the "-v1-" or "-v2-" in its name.

Two things per run.

  identity   a model reads each resident's saved "currently" (after one midnight
             rewrite) and returns supports, opposes, undecided or none. "Kept"
             means the label equals the label of the starting text, "dropped"
             that the stance is gone, "changed" that it became a different stance.
  readings   the stance probe's scores from experiment/opinions.jsonl, ranked
             against the direction of each resident's starting stance (Spearman,
             rho). Day 1 is 12:00 to midnight on Feb 13 and day 2 is 06:00 to
             13:00 on Feb 14, so day 2 is the readings after the rewrite, with
             sleeping residents (withheld readings) left out. "spread d2" is the
             gap between the highest and lowest resident mean on day 2, and
             "d2 at 30" the share of day-2 readings that are exactly 30, where the
             probe is known to pile up.

Read day 2 against the same run's day 1, not against the other arm. Both arms run
the same code until midnight, so a difference on day 1 is run-to-run variation.

Both the identity label and the arm comparison are soft: the label comes from the
same model that wrote the identities, and a few runs per arm cannot show a small
effect.
"""
import argparse
import collections
import concurrent.futures
import datetime
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "reverie", "backend_server"))

import numpy as np  # noqa: E402
import utils  # noqa: E402
from persona.prompt_template.gpt_structure import ChatGPT_safe_generate_response  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("runs", nargs="+")
ap.add_argument("--out", default="", help="save the per-run results and labels here")
args = ap.parse_args()
RUNS = args.runs

FMT = "%B %d, %Y, %H:%M:%S"
BASE = f"{utils.fs_storage}/base_the_ville_datacenter_n8/personas"
# Direction of each resident's starting persona, strongest support to strongest opposition.
SEEDED = {"Maya Okonkwo": 3, "Denise Brooks": 2, "Luis Hernandez": 1,
          "Rachel Nguyen": 0, "Elena Chen": 0,
          "Aisha Rahman": -1, "Tom Whitaker": -2, "Marcus Williams": -3}
DAY1 = (datetime.datetime(2023, 2, 13, 12), datetime.datetime(2023, 2, 14, 0))
DAY2 = (datetime.datetime(2023, 2, 14, 6), datetime.datetime(2023, 2, 14, 13))


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


def spearman(by_name):
  pairs = [(SEEDED[n], float(np.mean(s))) for n, s in by_name.items() if s]
  if len(pairs) < 3:
    return None
  x, y = zip(*pairs)
  if len(set(y)) == 1:
    return 0.0
  return float(np.corrcoef(ranks(x), ranks(y))[0, 1])


def readings(sim):
  d1, d2 = collections.defaultdict(list), collections.defaultdict(list)
  for line in open(f"{utils.fs_storage}/{sim}/experiment/opinions.jsonl"):
    r = json.loads(line)
    if r["score"] is None:
      continue
    t = datetime.datetime.strptime(r["time"], FMT)
    if DAY1[0] <= t < DAY1[1]:
      d1[r["name"]].append(r["score"])
    elif DAY2[0] <= t < DAY2[1]:
      d2[r["name"]].append(r["score"])
  return d1, d2


seed_text = {n: json.load(open(f"{BASE}/{n}/bootstrap_memory/scratch.json"))["currently"]
             for n in SEEDED}
jobs = [("seed", n, seed_text[n]) for n in SEEDED]
ended = {}
for run in RUNS:
  sim = f"stg-{run}"
  meta = json.load(open(f"{utils.fs_storage}/{sim}/reverie/meta.json"))
  ended[run] = meta["step"]
  for n in SEEDED:
    text = json.load(open(f"{utils.fs_storage}/{sim}/personas/{n}/bootstrap_memory/scratch.json"))["currently"]
    jobs += [(run, n, text)]
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  labels = list(pool.map(lambda j: label(j[1], j[2]), jobs))
by = collections.defaultdict(dict)
for (run, n, text), lab in zip(jobs, labels):
  by[run][n] = (lab, text, text == seed_text[n])


def num(v, p=2):
  return "n/a" if v is None else f"{v:+.{p}f}"


results = {}
print(f"{'run':10s}{'step':>7s}  {'identity after the night: kept/dropped/changed':>47s}  {'rho day1':>9s}{'rho day2':>9s}{'spread d2':>10s}{'d2 at 30':>9s}")
for run in RUNS:
  sim = f"stg-{run}"
  kept = dropped = changed = unrewritten = 0
  for n in SEEDED:
    lab, _, same = by[run][n]
    if same:
      unrewritten += 1
    elif lab == by["seed"][n][0]:
      kept += 1
    elif lab == "none":
      dropped += 1
    else:
      changed += 1
  d1, d2 = readings(sim)
  means2 = [float(np.mean(s)) for s in d2.values() if s]
  scores2 = [x for s in d2.values() for x in s]
  results[run] = {"kept": kept, "dropped": dropped, "changed": changed,
                  "rho1": spearman(d1), "rho2": spearman(d2),
                  "spread2": (max(means2) - min(means2)) if means2 else None,
                  "at30": (sum(1 for x in scores2 if x == 30) / len(scores2)) if scores2 else None,
                  "unrewritten": unrewritten}
  r = results[run]
  note = f"  ({unrewritten} not rewritten)" if unrewritten else ""
  print(f"{run:10s}{ended[run]:>7d}  {kept:>16d}/{dropped}/{changed}{note:>26s}"
        f"  {num(r['rho1']):>9s}{num(r['rho2']):>9s}"
        f"{'n/a' if r['spread2'] is None else format(r['spread2'], '.0f'):>10s}"
        f"{'n/a' if r['at30'] is None else format(100 * r['at30'], '.0f') + '%':>9s}")

for arm in ("v1", "v2"):
  runs = [r for r in RUNS if f"-{arm}-" in r]
  if not runs:
    continue
  tot = collections.Counter()
  for r in runs:
    for k in ("kept", "dropped", "changed"):
      tot[k] += results[r][k]
  rho1 = [results[r]["rho1"] for r in runs if results[r]["rho1"] is not None]
  rho2 = [results[r]["rho2"] for r in runs if results[r]["rho2"] is not None]
  n = len(runs) * len(SEEDED)
  print(f"\n{arm} ({len(runs)} runs): identity kept {tot['kept']}/{n}, dropped {tot['dropped']}, changed {tot['changed']}"
        f" | mean rho day1 {np.mean(rho1):+.2f}, day2 {np.mean(rho2):+.2f}"
        f" (day2 range {min(rho2):+.2f} to {max(rho2):+.2f})")

if args.out:
  json.dump({"results": results,
             "identity": {run: {n: {"label": by[run][n][0], "currently": by[run][n][1]}
                                for n in SEEDED} for run in RUNS},
             "seed_labels": {n: by["seed"][n][0] for n in SEEDED}},
            open(args.out, "w"), indent=1)
