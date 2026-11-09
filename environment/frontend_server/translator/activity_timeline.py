"""
Where each agent was over a run, as stays at one place, from the per-step
movement files (storage/<sim>/movement/<step>.json).

Reading every step of a long run is slow, so steps are sampled every EVERY
steps (6 steps of 10 seconds is one game minute) and the result is cached
per run; a live run only reads the steps written since the last request.
"""
import json
import os
import threading

EVERY = 6

# sim -> {"every", "folder" (inode), "next" (first step not yet read), "agents": {name: [stay, ...]}}
_cache = {}
_lock = threading.Lock()


def place_of(address):
  """The sector of an address: "the Ville:Hobbs Cafe:cafe:seating" is "Hobbs Cafe"."""
  parts = [p for p in str(address or "").split(":") if p]
  return parts[1] if len(parts) > 1 else (parts[0] if parts else "")


def _steps(folder):
  try:
    names = os.listdir(folder)
  except FileNotFoundError:
    return []
  return sorted(int(n[:-5]) for n in names if n.endswith(".json") and n[:-5].isdigit())


def activity_timeline(sim, every=EVERY):
  """{"every", "last", "agents": {name: [[from_step, to_step, place, action], ...]}}.
  A stay runs from the first sampled step at a place to the last one, and keeps
  the action seen first there; the last stay of each agent is stretched to the
  newest step on disk."""
  folder = f"storage/{sim}/movement"
  with _lock:
    steps = _steps(folder)
    try:
      inode = os.stat(folder).st_ino
    except OSError:
      inode = None
    c = _cache.get(sim)
    # A run deleted and relaunched under the same name gets a new folder, and a
    # resumed run can rewind past steps that were never saved: start over.
    if (not c or c["every"] != every or c["folder"] != inode
        or (steps and steps[-1] < c["next"] - 1)):
      c = _cache[sim] = {"every": every, "folder": inode, "next": 0, "agents": {}}
    for step in steps:
      if step < c["next"] or step % every:
        continue
      try:
        with open(f"{folder}/{step}.json") as f:
          personas = json.load(f).get("persona", {})
      except (OSError, ValueError):
        break  # being written right now; read it and the rest next time
      for name, p in personas.items():
        action, _, address = (p.get("description") or "").partition(" @ ")
        place = place_of(address)
        stays = c["agents"].setdefault(name, [])
        if stays and stays[-1][2] == place:
          stays[-1][1] = step
        else:
          stays.append([step, step, place, action])
      c["next"] = step + 1
    last = steps[-1] if steps else 0
    agents = {name: [s[:] for s in stays] for name, stays in c["agents"].items()}
  for stays in agents.values():
    if stays:
      stays[-1][1] = max(stays[-1][1], last)
  return {"every": every, "last": last, "agents": agents}
