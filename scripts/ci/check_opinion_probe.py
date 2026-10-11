"""
Rules for the datacenter stance probe, checked in CI (.github/workflows/ci.yml).
Run from the repo root: python scripts/ci/check_opinion_probe.py

The probe reads where each agent stands every game hour and the dashboard
graphs it, so two things have to hold:

- A response with no whole number from 1 to STANCE_SCALE in it scores None.
  Every other rating in this codebase falls back to a middling default on a
  parse failure (poignancy returns 4); here that would be a fabricated opinion
  sitting in the graph next to real ones, indistinguishable from an agent that
  is torn.
- The probe retrieves read-only. check_retrieval.py proves touch=False leaves
  last_accessed alone; this checks the probe actually passes it.
- The prompt does not hand the model a list of numbers to choose from. With
  anchors spelled out as "1 -- against, 3 -- leans against, 5 -- torn, ...",
  gpt-4o-mini used only those six values across 192 readings and nothing else,
  so a conditional position had to flip between 3 and 7 while the belief behind
  it never moved.
- The probe passes temperature explicitly. ChatGPT_request ignores the
  gpt_param dict every other prompt builds, so without this the readings are
  sampled at the chat_completion default and repeat reads of an unchanged
  memory set disagree with each other.
- Evidence reaches the model oldest-first and dated, or "what this agent
  thinks now" is indistinguishable from "what it thought yesterday".
"""
import inspect
import os
import re
import sys

BACKEND = os.path.join(os.path.dirname(__file__), "..", "..",
                       "reverie", "backend_server")
BACKEND = os.path.abspath(BACKEND)
# run_gpt_prompt resolves its prompt templates relative to the backend
# directory, the way reverie.py is run.
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)

import opinion_probe
from persona.prompt_template import run_gpt_prompt
from persona.prompt_template.run_gpt_prompt import (
  STANCE_SCALE, STANCE_SEPARATOR, parse_stance)

problems = []

# -- A rating is either 1 to STANCE_SCALE, or nothing ------------------------
rated = {
  f"58 {STANCE_SEPARATOR} the jobs would help": (58, "the jobs would help"),
  "58": (58, ""),
  "  100  ": (100, ""),
  "1": (1, ""),
  "57.4 || rounds down": (57, "rounds down"),
}
for raw, expected in rated.items():
  got = parse_stance(raw)
  if got != expected:
    problems.append(f"parse_stance({raw!r}) is {got!r}, expected {expected!r}")

# Out of range, non-numeric, empty, and a model that would rather not answer.
for raw in ["0", "101", "-3", "", None, "neutral", "I'd rather not say",
            "somewhere in the middle || hedging"]:
  score, rationale = parse_stance(raw)
  if score is not None:
    problems.append(f"parse_stance({raw!r}) produced a score of {score}; a "
                    f"response with no usable rating must score None rather "
                    f"than a made-up number")
  if raw and rationale != str(raw).strip():
    problems.append(f"parse_stance({raw!r}) dropped the raw response, so a "
                    f"failed reading can't be told apart from an empty one")

# -- The probe reads memory without marking it as accessed -------------------
with open(os.path.join(BACKEND, "opinion_probe.py"), encoding="utf-8") as f:
  source = f.read()
if not re.search(r"new_retrieve\([^)]*touch=False", source, re.S):
  problems.append("opinion_probe.probe does not retrieve with touch=False, so "
                  "probing an agent changes what that agent retrieves next")

# -- The probe reads the newest memory last, and dated -----------------------
# Retrieval hands back its 30 nodes ranked by score. Fed to the model in that
# order they are a jumble with no trajectory in them.
probe_src = inspect.getsource(opinion_probe.probe)
if "sorted(" not in probe_src or "created" not in probe_src:
  problems.append("opinion_probe.probe no longer sorts the retrieved memories "
                  "by created, so the model cannot tell a memory from an hour "
                  "ago from one from yesterday")
if "strftime" not in probe_src:
  problems.append("opinion_probe.probe no longer dates the statements it "
                  "passes to the model, so 'right now' has no meaning in the "
                  "prompt")

# -- The reading is deterministic --------------------------------------------
stance_src = inspect.getsource(run_gpt_prompt.run_gpt_prompt_datacenter_stance)
if "temperature=" not in stance_src:
  problems.append("run_gpt_prompt_datacenter_stance does not pass temperature, "
                  "so ChatGPT_request falls back to the chat_completion "
                  "default and two reads of the same memories disagree")

# -- The prompt asks for the ends of the scale, without naming values --------
# Chat models soften firm positions unless the extremes are called for. But an
# enumerated list of anchors is worse: the model treats it as the set of legal
# answers and snaps to it, which is what turned a 10-point scale into six.
template = os.path.join(BACKEND, "persona", "prompt_template", "v3_ChatGPT",
                        "datacenter_stance_v1.txt")
try:
  with open(template, encoding="utf-8") as f:
    prompt = f.read()
except OSError:
  prompt = ""
  problems.append(f"{template} is missing")
for phrase in [f"1 to {STANCE_SCALE}", "completely against",
               "completely in support", "Do not round"]:
  if phrase not in prompt:
    problems.append(f"datacenter_stance_v1.txt no longer says {phrase!r}, so "
                    f"the model is free to keep every rating near the middle "
                    f"or round it to the nearest 10")
# "<number> --" is the anchor-list shape that caused the snapping.
anchors = re.findall(r"^\s*\d+\s+--", prompt, re.M)
if anchors:
  problems.append(f"datacenter_stance_v1.txt lists {len(anchors)} numbered "
                  f"anchors ({', '.join(a.strip() for a in anchors)}); the "
                  f"model answers from that list and nothing between")

if opinion_probe.EVIDENCE_N <= 0:
  problems.append("opinion_probe.EVIDENCE_N is not positive, so ratings would "
                  "be based on no memories at all")
if STANCE_SCALE < 100:
  problems.append(f"STANCE_SCALE is {STANCE_SCALE}; below 100 there is no room "
                  f"between 'leans against' and 'leans in support' for a "
                  f"conditional position to rest, and the line flips instead")

for p in problems:
  print(p)
print(f"opinion probe rules checked, {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
