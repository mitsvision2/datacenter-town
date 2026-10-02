#!/usr/bin/env python3
"""
Build base_the_ville_datacenter_n12: the 8 residents of build_datacenter_n8_base
plus four more (Caleb Rivera, Daniel Kim, Nora Wadia, Sofia Alvarez), and the
matching history file agent_history_init_datacenter_n12.csv.

The four new residents live in homes of n25 residents that the n8 cast does not
use (the homes are renamed in scripts/datacenter_map.py, so run
`python scripts/datacenter_map.py build-map` first). A resident's sprite can come
from a different donor than their home, so a woman does not get a man's sprite.

Run from anywhere:  python scripts/build_datacenter_n12_base.py
"""
import csv
import json
import os
import shutil

from build_datacenter_n8_base import (
  CAST as N8_CAST, CHARS, N25, STORAGE, copy_sprite, empty_memory)
from datacenter_map import DC_MAZE, rename_homes

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(STORAGE, "base_the_ville_datacenter_n12")
HISTORY_DIR = os.path.join(
  ROOT, "environment", "frontend_server", "static_dirs", "assets", "the_ville")
N8_HISTORY = os.path.join(HISTORY_DIR, "agent_history_init_datacenter_n8.csv")
N12_HISTORY = os.path.join(HISTORY_DIR, "agent_history_init_datacenter_n12.csv")

PROPOSAL = ("A company has proposed building a large datacenter on the "
            "outskirts of the Ville near Johnson Park")

# donor: n25 resident whose home, spatial memory and start tile are reused.
# sprite_donor: n25 resident whose sprite is copied (defaults to donor).
# places: sectors copied from another n25 resident's spatial memory, for
#   places the donor does not know but this resident's day needs.
# history: the resident's own memories, loaded through the history CSV (each
#   becomes a thought in their memory stream). No semicolons inside an entry.
NEW_CAST = {
  "Caleb Rivera": {
    "donor": "Rajiv Patel",
    "sprite_donor": "Rajiv Patel",
    "age": 27,
    "innate": "analytical, resourceful, a little cynical",
    "learned": "Caleb Rivera is a 27-year-old Oak Hill College graduate who studied computer science and has been looking for a job in his field for almost a year. He works evening shifts at The Rose and Crown Pub and tutors students to pay rent and about $38,000 in student loans. He reads a lot about technology.",
    "currently": "Caleb has heard a datacenter is proposed near the Ville and hopes it could create jobs he could apply for, but he does not know what jobs there would be or who would be hired.",
    "lifestyle": "Caleb goes to bed around 1am, wakes up around 9am, tutors in the afternoon, and works evening shifts at the pub.",
    "daily_plan_req": "Caleb sends out job applications in the morning, tutors in the afternoon, and works an evening shift at The Rose and Crown Pub.",
    "history": [
      "You have sent 91 job applications in 11 months and had 4 interviews but no offers",
      "You pay about $410 a month on $38,000 of student loans and work evening shifts at The Rose and Crown Pub",
      "You wonder whether a datacenter would hire people like you",
    ],
  },
  "Daniel Kim": {
    "donor": "Giorgio Rossi",
    "sprite_donor": "Giorgio Rossi",
    "age": 42,
    "innate": "practical, patient, cautious",
    "learned": "Daniel Kim is a 42-year-old small-scale farmer. Two dry summers in a row cut his harvest, and he owes about $84,000 on a farm loan and equipment. His well ran low last summer, so he writes down the water level every week. His farm is outside the map, so his mapped work is farm paperwork at home and supply trips. He enjoys cooking and music.",
    "currently": "Daniel is worried about his loan. He has heard a datacenter is proposed near the Ville and wonders whether a large new water user could affect his well. He does not know what the project would actually use and wants facts.",
    "lifestyle": "Daniel goes to bed around 10pm, wakes up around 6am, and eats dinner around 6pm.",
    "daily_plan_req": "Daniel does farm paperwork and accounts at home, buys supplies at Harvey Oak Supply Store or the market, cooks dinner, and listens to music in the evening.",
    "history": [
      "Two dry summers in a row cut your harvest and you owe about $84,000 on a farm loan and equipment",
      "Your well ran low last summer so you now write down the water level every week",
      "You wonder what a datacenter would use and whether it would affect your well",
    ],
  },
  "Nora Wadia": {
    "donor": "Adam Smith",
    "sprite_donor": "Carmen Ortiz",
    "places": {"Oak Hill College": "Klaus Mueller"},
    "age": 35,
    "innate": "curious, thoughtful, careful",
    "learned": "Nora Wadia is a 35-year-old librarian at Oak Hill College, on a grant-funded contract that ends in June. She pays about $540 a month on $61,000 of library-school debt. Her last city library branch cut hours and then closed when the city's tax income fell. She enjoys reading and walking.",
    "currently": "Nora has heard a datacenter is proposed near the Ville and thinks a large taxpayer could help fund public services such as libraries, but she has not seen any details.",
    "lifestyle": "Nora goes to bed around 11pm, wakes up around 7am, works at the college library during the day, and reads or walks after work.",
    "daily_plan_req": "Nora works her shift at the Oak Hill College library, helps students find books, and spends the evening reading or taking a walk.",
    "history": [
      "Your library job is a grant-funded contract that ends in June",
      "You pay about $540 a month on $61,000 of library-school debt",
      "Your last city library branch cut hours and then closed when the city's tax income fell",
    ],
  },
  "Sofia Alvarez": {
    "donor": "Carlos Gomez",
    "sprite_donor": "Tamara Taylor",
    "age": 31,
    "innate": "friendly, easygoing, curious",
    "learned": "Sofia Alvarez is a 31-year-old grocery assistant at The Willows Market and Pharmacy. Her hours were cut twice this year to about 26 a week, and her rent went up $120. She owes $6,800 on a credit card after an ER visit. Her manager says the store's power bill is a big reason for the cuts. She enjoys baking and movies.",
    "currently": "Sofia has heard a datacenter is proposed near the Ville but has not thought about how it affects her.",
    "lifestyle": "Sofia goes to bed around 11pm, wakes up around 7am, works grocery shifts, and spends evenings baking, watching movies, or with friends.",
    "daily_plan_req": "Sofia works her shift at The Willows Market and Pharmacy, restocks shelves and serves customers, then bakes or watches a movie in the evening.",
    "history": [
      "Your weekly hours at the grocery were cut twice this year to about 26",
      "You owe $6,800 on a credit card after an ER visit and your rent went up $120",
      "Your manager said the store's power bill is a big reason for the cuts",
    ],
  },
}


def read_spatial(persona):
  path = os.path.join(N25, "personas", persona, "bootstrap_memory", "spatial_memory.json")
  with open(path) as f:
    return json.load(f)


def build_persona(new_name, spec, n25_env, env0):
  donor = spec["donor"]
  donor_folder = os.path.join(N25, "personas", donor)
  out_folder = os.path.join(OUT, "personas", new_name)
  os.makedirs(os.path.join(out_folder, "bootstrap_memory"), exist_ok=True)

  with open(os.path.join(donor_folder, "bootstrap_memory", "scratch.json")) as f:
    donor_scratch = json.load(f)
  first, last = new_name.split(" ", 1)
  scratch = dict(donor_scratch)
  scratch.update({
    "name": new_name,
    "first_name": first,
    "last_name": last,
    "age": spec["age"],
    "innate": spec["innate"],
    "learned": spec["learned"],
    "currently": spec["currently"],
    "lifestyle": spec["lifestyle"],
    "daily_plan_req": spec["daily_plan_req"],
    "living_area": rename_homes(donor_scratch["living_area"]),
    "act_event": [new_name, None, None],
    "curr_time": None,
    "curr_tile": None,
    "daily_req": [],
    "f_daily_schedule": [],
    "f_daily_schedule_hourly_org": [],
    "act_address": None,
    "act_start_time": None,
    "act_duration": None,
    "act_description": None,
    "act_pronunciatio": None,
    "act_obj_description": None,
    "act_obj_pronunciatio": None,
    "act_obj_event": [None, None, None],
    "chatting_with": None,
    "chat": None,
    "chatting_with_buffer": {},
    "chatting_end_time": None,
    "act_path_set": False,
    "planned_path": [],
    "importance_trigger_curr": scratch.get("importance_trigger_max", 150),
    "importance_ele_n": 0,
  })
  with open(os.path.join(out_folder, "bootstrap_memory", "scratch.json"), "w") as f:
    json.dump(scratch, f, indent=2)

  spatial = read_spatial(donor)
  for sector, source in spec.get("places", {}).items():
    spatial["the Ville"][sector] = read_spatial(source)["the Ville"][sector]
  with open(os.path.join(out_folder, "bootstrap_memory", "spatial_memory.json"), "w") as f:
    f.write(rename_homes(json.dumps(spatial, indent=2)))
  empty_memory(os.path.join(out_folder, "bootstrap_memory", "associative_memory"))

  env0[new_name] = dict(n25_env[donor])
  copy_sprite(spec.get("sprite_donor", donor), new_name)


def build_history():
  with open(N8_HISTORY, newline="", encoding="utf-8") as f:
    rows = list(csv.reader(f))
  for name, spec in NEW_CAST.items():
    rows.append([name, "; ".join([PROPOSAL] + spec["history"])])
  with open(N12_HISTORY, "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(rows)


def main():
  if os.path.exists(OUT):
    shutil.rmtree(OUT)
  for sub in ("environment", "personas", "reverie"):
    os.makedirs(os.path.join(OUT, sub))

  with open(os.path.join(N25, "environment", "0.json")) as f:
    n25_env = json.load(f)
  env0 = {}
  names = []
  for name, spec in list(N8_CAST.items()) + list(NEW_CAST.items()):
    names.append(name)
    build_persona(name, spec, n25_env, env0)

  with open(os.path.join(OUT, "environment", "0.json"), "w") as f:
    json.dump(env0, f, indent=2)
  meta = {
    "fork_sim_code": "base_the_ville_datacenter_n12",
    "start_date": "February 13, 2023",
    "curr_time": "February 13, 2023, 00:00:00",
    "sec_per_step": 10,
    "maze_name": DC_MAZE,
    "persona_names": names,
    "step": 0,
  }
  with open(os.path.join(OUT, "reverie", "meta.json"), "w") as f:
    json.dump(meta, f, indent=2)
  build_history()

  print(f"Wrote {OUT}")
  print(f"Wrote {N12_HISTORY}")
  print("Personas:", ", ".join(names))


if __name__ == "__main__":
  main()
