"""Runs the reflection insight prompt in two versions over the same memories.

Run from reverie/backend_server, because that is where the prompt template path
and utils.py resolve from:

  cd reverie/backend_server
  python3 ../../scripts/compare_reflection_prompts.py <sim> [--agents N] [--out FILE]

Why. The stance probe reads 30 statements per rating and 20 of them come from
the memory pool, where reflection thoughts dominate. Measured on a finished run,
only a quarter of those thoughts name the resident, so they say what the town
is worried about and not what any one resident thinks. v1 asks for "high-level
insights"; v2 asks for insights about the resident's own wants, worries and
words. This replays both on identical inputs and counts what comes out.

What is held fixed. Each resident's focal points are generated once and the
retrieved memories are shared, so the only difference between the two columns is
the template. Nothing is written back: personas are loaded from the saved run,
retrieval uses touch=False, and no persona is saved.

What is measured, per insight:

  names resident   the resident's first or last name appears in the sentence.
  position verb    wants, supports, opposes, argues or objects, the verbs
                   docs/belief-change-cast-and-probe-log.md counts. A weak,
                   non-LLM check kept apart from the two model labels below.
  own view         a model label: does the sentence itself say that the resident
                   wants, worries about, believes, fears or has said something.
                   Judged from the sentence alone. Told only the resident's name
                   as context, the model called "Community engagement is vital"
                   the resident's own view.
  grounding        a model label, given only the statements the insight cites:
                   supported, partly or unsupported. This is the one that
                   matters most. Asking for a resident's views invites the model
                   to invent them, and an invented view that reaches the probe
                   would be read back as the resident's own opinion.
  control          the grounding label again, with each insight paired to a
                   different insight's citations. It should come back mostly
                   unsupported; how often it does not is the label's error rate.

Both labels come from the same model that wrote the insights, so absolute rates
are soft. The comparison between the columns, the control row, and the insights
saved with --out are what to read.
"""
import argparse
import collections
import concurrent.futures
import json
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "reverie", "backend_server"))

import utils  # noqa: E402
from persona.persona import Persona  # noqa: E402
from persona.cognitive_modules.reflect import generate_focal_points  # noqa: E402
from persona.cognitive_modules.retrieve import new_retrieve  # noqa: E402
from persona.prompt_template.gpt_structure import (  # noqa: E402
  ChatGPT_safe_generate_response)
from persona.prompt_template.run_gpt_prompt import (  # noqa: E402
  run_gpt_prompt_insight_and_guidance)

TEMPLATES = {
  "v1": "persona/prompt_template/v2/insight_and_evidence_v1.txt",
  "v2": "persona/prompt_template/v2/insight_and_evidence_v2.txt"}
POSITION_VERB = re.compile(
  r"\b(want|wants|support|supports|oppose|opposes|argue|argues|object|objects)\b",
  re.I)
INSIGHTS_PER_FOCAL_POINT = 5


def ask(prompt, instruction, answers, example):
  """One yes/no style label from the model, or None if it never answered."""
  seen = {"r": None}

  def validate(r, prompt=""):
    seen["r"] = r
    return str(r).strip().lower() in answers

  out = ChatGPT_safe_generate_response(
    prompt, example, instruction, 3, None, validate,
    lambda r, prompt="": str(r).strip().lower(), False, temperature=0)
  return out if out is not False else None


def label_own_view(name, insight):
  return ask(
    f'Sentence: "{insight}"\n\n'
    f"Does this sentence itself say that {name} wants, worries about, "
    f"believes, fears or has said something? Answer no if it does not mention "
    f"{name}, or only describes events, activities, or what the community or "
    f"a group thinks.",
    'The output should be "yes" or "no".', ("yes", "no"), "yes")


def label_grounding(name, insight, cited):
  statements = "\n".join(f"- {s}" for s in cited) or "- (nothing cited)"
  return ask(
    f"Statements:\n{statements}\n\n"
    f'Insight about {name}: "{insight}"\n\n'
    f"Judge the insight using only the statements above. \"supported\" if they "
    f"directly show it, \"partly\" if they show some of it, \"unsupported\" if "
    f"they do not show it or it goes beyond them. An insight that gives {name} "
    f"a view or motive is supported only if the statements show {name} holding "
    f"or voicing it.",
    'The output should be "supported", "partly" or "unsupported".',
    ("supported", "partly", "unsupported"), "partly")


def collect(personas, limit):
  """Every insight each version writes, with what it cited."""
  rows, focal = [], {}
  for name, persona in list(personas.items())[:limit]:
    points = generate_focal_points(persona, 3)
    focal[name] = points
    retrieved = new_retrieve(persona, points, touch=False)
    for point, nodes in retrieved.items():
      statements = "".join(f"{i}. {n.embedding_key}\n"
                           for i, n in enumerate(nodes))
      for version, template in TEMPLATES.items():
        result = run_gpt_prompt_insight_and_guidance(
          persona, statements, INSIGHTS_PER_FOCAL_POINT, template=template)[0]
        if not isinstance(result, dict):
          rows += [{"name": name, "version": version, "point": point,
                    "insight": None}]
          continue
        for insight, evidence in result.items():
          cited = [nodes[i].embedding_key for i in evidence
                   if 0 <= i < len(nodes)]
          rows += [{"name": name, "version": version, "point": point,
                    "insight": insight, "cited": cited}]
  return rows, focal


def label(rows):
  jobs = [r for r in rows if r["insight"]]
  # Control: each insight judged against the next insight's citations, from
  # the same version. If the grounding label calls these supported it is not
  # reading the citations at all.
  mismatched = {}
  for version in TEMPLATES:
    mine = [r for r in jobs if r["version"] == version]
    for i, r in enumerate(mine):
      mismatched[id(r)] = mine[(i + 1) % len(mine)]["cited"]
  with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    own = list(pool.map(lambda r: label_own_view(r["name"], r["insight"]), jobs))
    ground = list(pool.map(
      lambda r: label_grounding(r["name"], r["insight"], r["cited"]), jobs))
    control = list(pool.map(
      lambda r: label_grounding(r["name"], r["insight"], mismatched[id(r)]), jobs))
  for r, o, g, c in zip(jobs, own, ground, control):
    parts = r["name"].lower().split()
    r["names_resident"] = any(p in r["insight"].lower() for p in parts)
    r["position_verb"] = bool(POSITION_VERB.search(r["insight"]))
    r["own_view"] = o
    r["grounding"] = g
    r["control_grounding"] = c


def report(rows):
  pct = lambda a, b: f"{100 * a / b:3.0f}%" if b else "  n/a"
  print(f"\n{'':44s}{'v1':>12s}{'v2':>12s}")
  cells = {}
  for v in TEMPLATES:
    mine = [r for r in rows if r["version"] == v]
    ok = [r for r in mine if r["insight"]]
    own = [r for r in ok if r["own_view"] == "yes"]
    cells[v] = {
      "unreadable": len(mine) - len(ok),
      "insights": len(ok),
      "names": pct(sum(r["names_resident"] for r in ok), len(ok)),
      "verb": pct(sum(r["position_verb"] for r in ok), len(ok)),
      "own": pct(len(own), len(ok)),
      "sup_all": pct(sum(r["grounding"] == "supported" for r in ok), len(ok)),
      "uns_all": pct(sum(r["grounding"] == "unsupported" for r in ok), len(ok)),
      "sup_own": pct(sum(r["grounding"] == "supported" for r in own), len(own)),
      "uns_own": pct(sum(r["grounding"] == "unsupported" for r in own), len(own)),
      "control": pct(sum(r["control_grounding"] == "supported" for r in ok), len(ok)),
      "usable": sum(r["grounding"] == "supported" for r in own)}
  lines = [("insights written", "insights"),
           ("replies that gave no readable insight", "unreadable"),
           ("name the resident", "names"),
           ("contain a position verb (weak check)", "verb"),
           ("state the resident's own view", "own"),
           ("  all insights: supported by their citations", "sup_all"),
           ("  all insights: unsupported", "uns_all"),
           ("  own-view insights: supported", "sup_own"),
           ("  own-view insights: unsupported", "uns_own"),
           ("control: wrong citations still judged supported", "control"),
           ("own-view AND supported (count)", "usable")]
  for text, key in lines:
    print(f"{text:44s}{str(cells['v1'][key]):>12s}{str(cells['v2'][key]):>12s}")


def main():
  ap = argparse.ArgumentParser(description=__doc__)
  ap.add_argument("sim", help="simulation code under storage/")
  ap.add_argument("--agents", type=int, default=0,
                  help="only the first N residents (a dry run)")
  ap.add_argument("--out", default="", help="save every insight here as JSON")
  args = ap.parse_args()

  base = os.path.join(utils.fs_storage, args.sim, "personas")
  personas = {name: Persona(name, os.path.join(base, name))
              for name in sorted(os.listdir(base))}
  rows, focal = collect(personas, args.agents or len(personas))
  label(rows)
  report(rows)

  if args.out:
    with open(args.out, "w", encoding="utf-8") as f:
      json.dump({"sim": args.sim, "focal_points": focal, "insights": rows},
                f, indent=1)
    print(f"\nevery insight saved to {args.out}")


if __name__ == "__main__":
  main()
