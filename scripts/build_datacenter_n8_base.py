#!/usr/bin/env python3
"""
Build base_the_ville_datacenter_n8 from selected n25 donor homes/sprites.
Run from repo root or this script's directory.
"""
import json
import os
import shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STORAGE = os.path.join(ROOT, "environment", "frontend_server", "storage")
CHARS = os.path.join(
  ROOT, "environment", "frontend_server", "static_dirs", "assets", "characters")
N25 = os.path.join(STORAGE, "base_the_ville_n25")
OUT = os.path.join(STORAGE, "base_the_ville_datacenter_n8")

# new_name -> (donor_name, age, innate, learned, currently, lifestyle, daily_plan_req)
CAST = {
  "Maya Okonkwo": {
    "donor": "Ryan Park",
    "age": 34,
    "innate": "ambitious, optimistic, persuasive",
    "learned": "Maya Okonkwo is an AI founder who builds machine-learning products and champions regional tech growth. She networks widely and argues that modern infrastructure attracts talent.",
    "currently": "Maya Okonkwo supports a proposed datacenter on the outskirts of the Ville. She believes it will create high-skill jobs, bring investment, and put the town on the innovation map. She is talking to neighbors about the upside.",
    "lifestyle": "Maya Okonkwo goes to bed around midnight, wakes up around 7am, and often works from cafes in the afternoon.",
    "daily_plan_req": "Maya Okonkwo works on her startup during the day, takes meetings at Hobbs Cafe, and talks with residents about the datacenter proposal.",
  },
  "Luis Hernandez": {
    "donor": "Arthur Burton",
    "age": 41,
    "innate": "practical, loyal, cautious",
    "learned": "Luis Hernandez is a union electrician who cares about construction jobs, apprenticeships, and fair wages. He has worked major builds across the region.",
    "currently": "Luis Hernandez offers conditional support for the datacenter proposal: he wants firm local-hire and prevailing-wage commitments before he backs it. He is asking what the project would mean for union members.",
    "lifestyle": "Luis Hernandez goes to bed around 10pm, wakes up around 5:30am, and eats dinner around 6pm.",
    "daily_plan_req": "Luis Hernandez works job sites during the day and stops by the pub or market after work to talk with other residents.",
  },
  "Denise Brooks": {
    "donor": "Isabella Rodriguez",
    "age": 38,
    "innate": "friendly, entrepreneurial, pragmatic",
    "learned": "Denise Brooks owns a local shop and cares about foot traffic, the tax base, and keeping Main Street businesses alive.",
    "currently": "Denise Brooks leans in favor of the datacenter proposal because she expects temporary construction spending and a stronger tax base, though she worries about power bills and long-term customer mix.",
    "lifestyle": "Denise Brooks goes to bed around 11pm, wakes up around 6am, and keeps shop hours most weekdays.",
    "daily_plan_req": "Denise Brooks opens her shop in the morning, greets customers, and discusses the datacenter proposal with people who stop by.",
  },
  "Rachel Nguyen": {
    "donor": "Mei Lin",
    "age": 36,
    "innate": "thoughtful, empathetic, measured",
    "learned": "Rachel Nguyen is a teacher and parent who focuses on schools, household budgets, and whether big projects help kids in town.",
    "currently": "Rachel Nguyen is undecided about the datacenter proposal. She wants clear answers on school funding, electricity rates, and whether the town will see lasting benefits for families.",
    "lifestyle": "Rachel Nguyen goes to bed around 10:30pm, wakes up around 6:30am, and spends evenings with family or grading.",
    "daily_plan_req": "Rachel Nguyen teaches during the day, runs errands after school, and listens carefully when neighbors debate the datacenter.",
  },
  "Tom Whitaker": {
    "donor": "Tom Moreno",
    "age": 52,
    "innate": "stubborn, protective, straightforward",
    "learned": "Tom Whitaker is a long-term homeowner who watches property values, noise, and utility rates closely. He has lived in the Ville for decades.",
    "currently": "Tom Whitaker leans against the datacenter proposal. He worries about industrial noise, higher rates, and damage to nearby property values, and he tells people so.",
    "lifestyle": "Tom Whitaker goes to bed around 10pm, wakes up around 6am, and spends mornings around the house and market.",
    "daily_plan_req": "Tom Whitaker tends to home and neighborhood errands, and raises concerns about the datacenter with anyone who will listen.",
  },
  "Aisha Rahman": {
    "donor": "Latoya Williams",
    "age": 29,
    "innate": "principled, careful, articulate",
    "learned": "Aisha Rahman is an environmental advocate focused on water use, emissions, habitat, and climate impacts of large infrastructure.",
    "currently": "Aisha Rahman conditionally opposes the datacenter proposal until there are binding water, emissions, and habitat protections. She is organizing facts for a town discussion.",
    "lifestyle": "Aisha Rahman goes to bed around 11:30pm, wakes up around 7am, and often works from the park or cafe.",
    "daily_plan_req": "Aisha Rahman researches environmental impacts during the day and talks with residents about water and emissions risks from the datacenter.",
  },
  "Marcus Williams": {
    "donor": "Sam Moore",
    "age": 45,
    "innate": "outspoken, community-minded, skeptical of corporate power",
    "learned": "Marcus Williams is a community organizer who pushes for fair process, transparent hearings, and local voice against outside corporate influence.",
    "currently": "Marcus Williams opposes the datacenter proposal as currently framed. He argues the process has been rushed and that corporate power is sidelining residents.",
    "lifestyle": "Marcus Williams goes to bed around 11pm, wakes up around 6:30am, and spends afternoons meeting people around town.",
    "daily_plan_req": "Marcus Williams meets neighbors, posts flyers, and urges people to demand a fair process around the datacenter proposal.",
  },
  "Elena Chen": {
    "donor": "Yuriko Yamamoto",
    "age": 47,
    "innate": "analytical, reserved, evidence-driven",
    "learned": "Elena Chen is a utility planner who evaluates grid reliability, interconnection feasibility, and load growth. Colleagues call her Dr. Chen.",
    "currently": "Elena Chen is evidence-dependent on the datacenter proposal. She will not take a public stance until she sees credible grid studies on capacity, interconnection timelines, and ratepayer impacts.",
    "lifestyle": "Elena Chen goes to bed around 10:30pm, wakes up around 6am, and often reviews technical documents in the evening.",
    "daily_plan_req": "Elena Chen reviews utility planning documents and answers technical questions when residents ask about the datacenter's grid impacts.",
  },
}


def empty_memory(path):
  os.makedirs(path, exist_ok=True)
  for name, default in [
    ("nodes.json", {}),
    ("embeddings.json", {}),
    ("kw_strength.json", {"kw_strength_event": {}, "kw_strength_thought": {}}),
  ]:
    with open(os.path.join(path, name), "w") as f:
      json.dump(default, f, indent=2)


def copy_sprite(donor, new_name):
  donor_u = donor.replace(" ", "_")
  new_u = new_name.replace(" ", "_")
  for folder in ["", "profile"]:
    src_dir = os.path.join(CHARS, folder) if folder else CHARS
    dst_dir = src_dir
    src = os.path.join(src_dir, f"{donor_u}.png")
    dst = os.path.join(dst_dir, f"{new_u}.png")
    if os.path.exists(src) and not os.path.exists(dst):
      shutil.copy2(src, dst)


def main():
  if os.path.exists(OUT):
    shutil.rmtree(OUT)
  os.makedirs(OUT)

  os.makedirs(os.path.join(OUT, "environment"), exist_ok=True)
  os.makedirs(os.path.join(OUT, "personas"), exist_ok=True)
  os.makedirs(os.path.join(OUT, "reverie"), exist_ok=True)

  n25_env = json.load(open(os.path.join(N25, "environment", "0.json")))
  env0 = {}
  persona_names = []

  for new_name, spec in CAST.items():
    donor = spec["donor"]
    persona_names.append(new_name)
    donor_folder = os.path.join(N25, "personas", donor)
    out_folder = os.path.join(OUT, "personas", new_name)
    os.makedirs(os.path.join(out_folder, "bootstrap_memory"), exist_ok=True)

    donor_scratch = json.load(open(
      os.path.join(donor_folder, "bootstrap_memory", "scratch.json")))
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
      "living_area": donor_scratch["living_area"],
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

    shutil.copy2(
      os.path.join(donor_folder, "bootstrap_memory", "spatial_memory.json"),
      os.path.join(out_folder, "bootstrap_memory", "spatial_memory.json"))
    empty_memory(os.path.join(out_folder, "bootstrap_memory", "associative_memory"))

    env0[new_name] = dict(n25_env[donor])
    copy_sprite(donor, new_name)

  with open(os.path.join(OUT, "environment", "0.json"), "w") as f:
    json.dump(env0, f, indent=2)

  meta = {
    "fork_sim_code": "base_the_ville_datacenter_n8",
    "start_date": "February 13, 2023",
    "curr_time": "February 13, 2023, 00:00:00",
    "sec_per_step": 10,
    "maze_name": "the_ville",
    "persona_names": persona_names,
    "step": 0,
  }
  with open(os.path.join(OUT, "reverie", "meta.json"), "w") as f:
    json.dump(meta, f, indent=2)

  print(f"Wrote {OUT}")
  print("Personas:", ", ".join(persona_names))


if __name__ == "__main__":
  main()
