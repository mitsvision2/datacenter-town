"""
The whispers planned for one run: what to say, to whom, and when.

Lives in storage/<sim>/experiment/whispers.jsonl, append-only, written by two
processes. The dashboard adds and cancels; the simulation records what it sent.
Every status is worked out from the rows, so neither side ever rewrites the
other's work, and a run's plan travels with it when the run is forked.

  {"op": "add", "id", "text", "targets", "at",   at is game time, None for now
   "replaces"}                                   an edit: who already got the
                                                 old one doesn't get this
  {"op": "cancel", "id"}
  {"op": "started", "id", "time"}                delivery has begun, so it's too
                                                 late to edit
  {"op": "sent", "id", "agent", "step", "time"}
  {"op": "failed", "id", "agent", "step", "time", "error"}
  {"op": "saved", "step"}                        the agents' memory was saved

No imports from the rest of the backend: the dashboard loads this file directly,
the way it loads llm/usage.py, because the rest reaches utils.py and the API keys.
"""
import datetime
import json
import os

TIME_FORMAT = "%B %d, %Y, %H:%M:%S"
# Longest whisper, from the dashboard or the console.
MAX_CHARS = 1000
DELIVERY_OPS = ("started", "sent", "failed")


def path_for(sim_folder):
  return os.path.join(sim_folder, "experiment", "whispers.jsonl")


def append(path, rows):
  """One unbuffered write, so a row from the other process can't land inside
  these and a batch of rows is all there or not at all."""
  os.makedirs(os.path.dirname(path), exist_ok=True)
  data = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
  with open(path, "ab", buffering=0) as f:
    f.write(data.encode("utf-8"))


def rewrite(path, rows):
  """Replaces the file whole, so a crash leaves the old one rather than half of it."""
  tmp = f"{path}.tmp"
  with open(tmp, "w", encoding="utf-8") as f:
    for row in rows:
      f.write(json.dumps(row, ensure_ascii=False) + "\n")
  os.replace(tmp, path)


def read(path):
  try:
    with open(path, "rb") as f:
      lines = f.read().split(b"\n")
  except OSError:
    return []
  rows = []
  # The last piece is empty, or a row the other process is still writing.
  for line in lines[:-1]:
    try:
      row = json.loads(line)
    except ValueError:
      continue
    if isinstance(row, dict):
      rows.append(row)
  return rows


def summarize(rows):
  """One entry per whisper, in the order they were added. <left> is who it has
  yet to reach; <status> is scheduled, sending, sent, failed or cancelled."""
  whispers = {}
  for row in rows:
    op, w = row.get("op"), whispers.get(row.get("id"))
    if op == "add":
      whispers[row.get("id")] = {
        "id": row.get("id"), "text": row.get("text"),
        "targets": row.get("targets") or [], "at": row.get("at"),
        "sent": [], "received": {}, "failed": {}, "cancelled": False,
        "started": False, "replaces": row.get("replaces")}
    elif w and op == "cancel":
      w["cancelled"] = True
    elif w and op == "started":
      w["started"] = True
    elif w and op == "sent":
      w["sent"].append(row.get("agent"))
      w["received"][row.get("agent")] = {"step": row.get("step"), "time": row.get("time")}
    elif w and op == "failed":
      w["failed"][row.get("agent")] = row.get("error")
  for w in whispers.values():
    done = set(w["sent"]) | set(w["failed"])
    # An edit saved while the original was starting to go out: whoever got the
    # original has heard it, so the edit skips them instead of telling them twice.
    if w["replaces"] in whispers:
      done |= set(whispers[w["replaces"]]["sent"])
    w["left"] = [] if w["cancelled"] else [t for t in w["targets"] if t not in done]
    w["status"] = ("cancelled" if w["cancelled"]
                   else ("sending" if done or w["started"] else "scheduled") if w["left"]
                   else "failed" if w["failed"] else "sent")
  return list(whispers.values())


def next_due(whispers, now):
  """(whisper, agent) for the next delivery owed at game time <now>, or None."""
  for w in whispers:
    if w["left"] and (w["at"] is None
                      or datetime.datetime.strptime(w["at"], TIME_FORMAT) <= now):
      return w, w["left"][0]
  return None


def forget_unsaved(path):
  """Drops delivery records written after the last save.

  A fork starts from the agents' saved memory but copies this whole file. A
  whisper delivered after that save isn't in the memory the fork loads, so
  keeping its record would mark it sent to agents who never heard it. A "now"
  whisper takes the time it first went out, so the fork hears it at the same
  point in the story instead of as soon as it loads.
  """
  rows = read(path)
  saved = [i for i, row in enumerate(rows) if row.get("op") == "saved"]
  last_save = saved[-1] if saved else -1
  unsaved = [row for i, row in enumerate(rows)
             if i > last_save and row.get("op") in DELIVERY_OPS]
  if not unsaved:
    return
  first_sent = {}
  for row in unsaved:
    first_sent.setdefault(row.get("id"), row.get("time"))
  keep = []
  for i, row in enumerate(rows):
    if i > last_save and row.get("op") in DELIVERY_OPS:
      continue
    if row.get("op") == "add" and row.get("at") is None and row.get("id") in first_sent:
      row = {**row, "at": first_sent[row.get("id")]}
    keep.append(row)
  rewrite(path, keep)


class Plan:
  """The simulation's view of the plan. It asks after every step, so the file
  is only read again when it has grown."""

  def __init__(self, sim_folder):
    self.path = path_for(sim_folder)
    self._size = None
    self._whispers = []

  def whispers(self):
    size = os.path.getsize(self.path) if os.path.exists(self.path) else 0
    if size != self._size:
      self._whispers = summarize(read(self.path))
      self._size = size
    return self._whispers

  def next_due(self, now):
    return next_due(self.whispers(), now)

  def record(self, row):
    append(self.path, [row])

  def forget_unsaved(self):
    forget_unsaved(self.path)
    self._size = None

  def mark_saved(self, step):
    if os.path.exists(self.path):
      self.record({"op": "saved", "step": step})
