"""
Web dashboard for controlling a simulation and watching its agents.

Talks to reverie.py through files in temp_storage/dashboard/ (see
reverie/backend_server/dashboard_bridge.py). Paths are relative to
environment/frontend_server, like the rest of translator/views.py.
"""
import collections
import datetime
import functools
import glob
import importlib.util
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import uuid

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from translator.views import _pid_alive as _alive
from translator.social_network import network_summary
from translator.activity_timeline import activity_timeline

log = logging.getLogger("frontend.dashboard")

DASH_DIR = "temp_storage/dashboard"
STATE_FILE = f"{DASH_DIR}/state.json"
CMD_FILE = f"{DASH_DIR}/commands.jsonl"
RESULT_FILE = f"{DASH_DIR}/results.jsonl"
LAUNCH_FILE = f"{DASH_DIR}/launch.json"
BACKEND_DIR = "../../reverie/backend_server"
BACKEND_LOG = f"{BACKEND_DIR}/logs/datacenter-town.log"
USAGE_FILE = f"{BACKEND_DIR}/logs/api_usage.jsonl"

SETTINGS_FILE = f"{DASH_DIR}/settings.json"

# Prices and the cost formula live in the backend's llm/usage.py, shared with
# the simulation's spending cap. That file imports nothing from the backend,
# so it's loaded straight from its path.
_spec = importlib.util.spec_from_file_location(
  "llm_usage", f"{BACKEND_DIR}/llm/usage.py")
_llm_usage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_llm_usage)
PRICES = _llm_usage.PRICES
# Same for the whisper plan, which this module and the simulation both write.
_spec = importlib.util.spec_from_file_location(
  "whisper_plan", f"{BACKEND_DIR}/whisper_plan.py")
whisper_plan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(whisper_plan)
WHISPER_MAX_CHARS = whisper_plan.MAX_CHARS
HISTORY_GLOB = "static_dirs/assets/the_ville/agent_history_init_*.csv"
SIM_NAME = re.compile(r"^[\w-]+$")
# Fields the roster needs every second; the rest is sent for the open agent.
ROSTER_FIELDS = ("name", "first_name", "act_description", "act_pronunciatio",
                 "act_address", "act_start_time", "path_left", "chatting_with",
                 "curr_tile", "currently", "living_area")


def _read_json(path, default=None):
  try:
    with open(path) as f:
      return json.load(f)
  except (OSError, ValueError):
    return default


def _tail_lines(path, n, max_bytes=256 * 1024):
  try:
    with open(path, "rb") as f:
      f.seek(0, os.SEEK_END)
      f.seek(max(0, f.tell() - max_bytes))
      lines = f.read().decode("utf-8", "replace").splitlines()
  except OSError:
    return []
  return lines[-n:]


def _tail_jsonl(path, n, max_bytes=256 * 1024):
  out = []
  for line in _tail_lines(path, n, max_bytes):
    try:
      out.append(json.loads(line))
    except ValueError:
      pass  # first line of the window can be cut in half
  return out


def _sims():
  sims = []
  for meta_path in glob.glob("storage/*/reverie/meta.json"):
    meta = _read_json(meta_path, {})
    name = meta_path.split("/")[1]
    sims.append({"name": name, "step": meta.get("step", 0),
                 "curr_time": meta.get("curr_time", ""),
                 "fork": meta.get("fork_sim_code"),
                 "maze": meta.get("maze_name"),
                 "agents": meta.get("persona_names", []),
                 "mtime": os.path.getmtime(meta_path)})
  return sorted(sims, key=lambda s: -s["mtime"])


def _run_start(sim):
  """The step a run began at. A new run copies everything from the run it
  continues, so anything logged before this step was inherited. Runs are
  never continued in place, so the parent's saved step is where this began."""
  meta = _read_json(f"storage/{sim}/reverie/meta.json", {})
  fork = meta.get("fork_sim_code")
  if not fork or fork == sim:
    return 0
  return _read_json(f"storage/{fork}/reverie/meta.json", {}).get("step", 0)


def _run_log(sim, name, n, start):
  rows = _tail_jsonl(f"storage/{sim}/experiment/{name}", n, max_bytes=2 << 20)
  for r in rows:
    r["inherited"] = (r.get("step") or 0) < start
  return rows


def _opinions(rows):
  """Stance readings without evidence ids or selection cosines; the graph only
  needs the numbers."""
  return [{k: v for k, v in r.items() if k not in ("evidence", "selection")}
          for r in rows]


EVIDENCE_SHOWN = 5
# nodes.json can be large; cached per path until its mtime changes. A small
# LRU, so the live run and a saved run open side by side don't evict each other.
_nodes_cache = collections.OrderedDict()
NODES_CACHED = 32


def _saved_nodes(sim, name):
  path = f"storage/{sim}/personas/{name}/bootstrap_memory/associative_memory/nodes.json"
  try:
    mtime = os.path.getmtime(path)
  except OSError:
    return {}
  hit = _nodes_cache.get(path)
  if not hit or hit[0] != mtime:
    nodes = _read_json(path)
    if not isinstance(nodes, dict):
      return {}  # caught mid-save; don't cache, read again next poll
    hit = _nodes_cache[path] = (mtime, nodes)
  _nodes_cache.move_to_end(path)
  while len(_nodes_cache) > NODES_CACHED:
    _nodes_cache.popitem(last=False)
  return hit[1]


def _stance_evidence(sim, name, rows):
  """Memories behind the agent's latest rated reading. Ids newer than the last
  save don't resolve yet and are skipped."""
  latest = next((r for r in reversed(rows)
                 if r.get("name") == name and r.get("score") is not None), None)
  if not latest or not latest.get("evidence"):
    return []
  nodes = _saved_nodes(sim, name)
  out = []
  for node_id in latest["evidence"]:
    n = nodes.get(node_id)
    if n:
      out.append({"id": node_id, "type": n.get("type"),
                  "description": n.get("description"), "created": n.get("created")})
    if len(out) == EVIDENCE_SHOWN:
      break
  return out


def _whispers(sim):
  path = whisper_plan.path_for(f"storage/{sim}")
  return whisper_plan.summarize(whisper_plan.read(path))


def _mentions(sim, start):
  """Where whispers came up in conversation, for the whisper chart."""
  return _run_log(sim, "whisper_mentions.jsonl", 2000, start)


def _view_history(sim, persona):
  """Each distinct "currently" an agent has had, from the periodic snapshots,
  to show how their view changed over the run."""
  out = []
  for r in _tail_jsonl(f"storage/{sim}/experiment/agent_snapshots.jsonl",
                       4000, max_bytes=8 << 20):
    if r.get("name") == persona and r.get("currently") and (
        not out or out[-1]["currently"] != r["currently"]):
      out.append({"step": r.get("step"), "time": r.get("time"),
                  "currently": r["currently"]})
  return out


def _schedule_index(schedule, curr_time):
  # Same rule as Scratch.get_f_daily_schedule_index.
  m = re.search(r"(\d{2}):(\d{2}):\d{2}$", curr_time or "")
  if not m or not schedule:
    return None
  elapsed, total = int(m.group(1)) * 60 + int(m.group(2)), 0
  for i, (_, duration) in enumerate(schedule):
    total += duration
    if total > elapsed:
      return i
  return len(schedule) - 1


# Same rule as reverie/backend_server/dashboard_bridge.py:_is_reflection, which
# does this for the live run off ConceptNode objects. This module cannot import
# that one (it reaches utils.py and the API keys), the way _run_env and
# DEFAULT_SETTINGS are also duplicated. check_memory_categories.py runs one
# fixture table through both and fails if they disagree.
#
# Nothing marks a reflection at write time, and depth does not separate it: an
# insight whose evidence is all events has depth 1, exactly like a daily plan
# or a whisper. The evidence is what differs. Insight evidence comes from
# new_retrieve, which draws only on events and thoughts and so never cites a
# chat, while the two thoughts written after a conversation cite exactly the
# last chat. So: evidence that resolves, with no chat in it.
def _is_reflection(node, by_id):
  filling = node.get("filling")
  if node.get("type") != "thought" or not isinstance(filling, list):
    return False
  kinds = {by_id[i].get("type") for i in filling if i in by_id}
  return bool(kinds) and "chat" not in kinds


# Reflections are cut by episode rather than by row: every insight a reflection
# writes shares one timestamp, so a row limit would show the tail of an episode
# as if that were the whole of it.
REFLECTION_EPISODES = 5


def _episodes(nodes):
  """The distinct timestamps in a list of insight nodes, newest first."""
  seen = []
  for n in nodes:
    if n.get("created") not in seen:
      seen.append(n.get("created"))
  return seen


def _saved_agent(sim, name):
  """A saved agent in the same shape the live state uses."""
  mem = f"storage/{sim}/personas/{name}/bootstrap_memory"
  s = _read_json(f"{mem}/scratch.json", {})
  by_id = _saved_nodes(sim, name)
  nodes = sorted(by_id.values(), key=lambda n: -n.get("node_count", 0))
  def row(x, kind=None):
    return {"type": x["type"], "created": x.get("created"),
            "description": x.get("description"), "poignancy": x.get("poignancy"),
            **({"lines": x["filling"]} if kind == "chat" and isinstance(x.get("filling"), list) else {})}
  def pick(kind, n):
    return [row(x, kind) for x in nodes if x.get("type") == kind][:n]
  insights = [x for x in nodes if _is_reflection(x, by_id)]
  thoughts = [x for x in nodes
              if x.get("type") == "thought" and not _is_reflection(x, by_id)]
  shown = _episodes(insights)[:REFLECTION_EPISODES]
  counts = {k: sum(1 for x in nodes if x.get("type") == k) for k in ("event", "chat")}
  counts["thought"] = len(thoughts)
  counts["reflection"] = len(_episodes(insights))
  schedule = s.get("f_daily_schedule") or []
  return {
    "name": s.get("name", name), "first_name": s.get("first_name"), "age": s.get("age"),
    "innate": s.get("innate"), "learned": s.get("learned"), "lifestyle": s.get("lifestyle"),
    "living_area": s.get("living_area"), "currently": s.get("currently"),
    "values": s.get("values"), "stake": s.get("stake"),
    "persuadability": s.get("persuadability"),
    "daily_plan_req": s.get("daily_plan_req"), "daily_req": s.get("daily_req"),
    "act_description": s.get("act_description"), "act_pronunciatio": s.get("act_pronunciatio"),
    "act_address": s.get("act_address"), "act_start_time": s.get("act_start_time"),
    "act_duration": s.get("act_duration"), "chatting_with": s.get("chatting_with"),
    "chat": s.get("chat"), "curr_tile": s.get("curr_tile"),
    "path_left": len(s.get("planned_path") or []),
    "schedule": schedule, "schedule_idx": _schedule_index(schedule, s.get("curr_time")),
    "reflect_trigger": [s.get("importance_trigger_curr"), s.get("importance_trigger_max")],
    "memory_counts": counts, "events": pick("event", 15),
    "thoughts": [row(x) for x in thoughts][:15], "chats": pick("chat", 6),
    "reflections": [row(x) for x in insights if x.get("created") in shown],
    "llm": [],
  }


def dashboard_run(request, sim):
  """Read-only view of a saved run, in the same shape as dashboard_state."""
  meta = _read_json(f"storage/{sim}/reverie/meta.json") if SIM_NAME.match(sim) else None
  if not meta:
    return JsonResponse({"error": f"No saved run named {sim}."}, status=404)
  names = meta.get("persona_names", [])
  agent = request.GET.get("agent")
  agents = {n: _saved_agent(sim, n) for n in names}
  start = _run_start(sim)
  manifest = _read_json(f"storage/{sim}/experiment/run_manifest.json", {})
  view = {
    "sim_code": sim, "fork_sim_code": meta.get("fork_sim_code"),
    "step": meta.get("step", 0), "curr_time": meta.get("curr_time"),
    "sec_per_step": meta.get("sec_per_step", 10), "start_step": start,
    "created_at": manifest.get("created_at"), "chat_model": manifest.get("chat_model"),
    # Runs from before staging existed have no run_env; they were production.
    "run_env": manifest.get("run_env") or "production",
    "persona_order": names,
    "roster": [{k: agents[n].get(k) for k in ROSTER_FIELDS} for n in names],
    "agent": agents.get(agent),
  }
  opinions = _run_log(sim, "opinions.jsonl", 4000, start)
  if view["agent"]:
    view["agent"]["history"] = _view_history(sim, agent)
    view["agent"]["evidence"] = _stance_evidence(sim, agent, opinions)
  return JsonResponse({
    "sim": view,
    "conversations": _run_log(sim, "conversations.jsonl", 300, start),
    "events": _run_log(sim, "events.jsonl", 300, start),
    "opinions": _opinions(opinions),
    "whispers": _whispers(sim),
    "mentions": _mentions(sim, start),
    "network": network_summary(sim, names, view["step"]),
    "results": [r for r in _tail_jsonl(RESULT_FILE, 400) if r.get("sim") == sim][-60:],
  })


def dashboard_activity(request, sim):
  """What one agent was doing at a step, from that step's movement file."""
  name = request.GET.get("name", "")
  try:
    step = int(request.GET.get("step", ""))
  except ValueError:
    step = -1
  if SIM_NAME.match(sim) and step >= 0:
    # Steps can be missing on disk; take the nearest earlier one.
    for s in range(step, max(-1, step - 60), -1):
      move = _read_json(f"storage/{sim}/movement/{s}.json")
      p = (move or {}).get("persona", {}).get(name)
      if p:
        desc, _, addr = (p.get("description") or "").partition(" @ ")
        others = {c[0] for c in p.get("chat") or [] if c and c[0] != name}
        return JsonResponse({"step": s, "description": desc, "address": addr,
                             "pronunciatio": p.get("pronunciatio"),
                             "chatting_with": min(others) if others else None})
  return JsonResponse({}, status=404)


def agent_memory(sim, name):
  """Every memory one agent has, as of its last save, plus the memories each
  of its stance readings was based on. Reflections are told apart from other
  thoughts by what they cite (see _is_reflection)."""
  by_id = _saved_nodes(sim, name)
  nodes = []
  for node_id, n in by_id.items():
    kind = "reflection" if _is_reflection(n, by_id) else n.get("type")
    # A chat's filling is its lines; anything else's is the ids it was drawn from.
    filling = n.get("filling") or []
    nodes.append({"id": node_id, "kind": kind, "created": n.get("created"),
                  "description": n.get("description"), "poignancy": n.get("poignancy"),
                  "count": n.get("node_count", 0),
                  "filling": [f for f in filling if isinstance(f, str) and f in by_id],
                  **({"lines": filling} if n.get("type") == "chat" else {})})
  nodes.sort(key=lambda n: -n["count"])  # newest first: node_count grows as memories are added
  # The whole file, not a tail: any reading on the stance chart can be clicked.
  readings = []
  try:
    with open(f"storage/{sim}/experiment/opinions.jsonl", encoding="utf-8") as f:
      for line in f:
        if name not in line:
          continue
        try:
          r = json.loads(line)
        except ValueError:
          continue  # a line still being written
        if r.get("name") == name and r.get("evidence"):
          readings.append({"step": r.get("step"), "time": r.get("time"), "score": r.get("score"),
                           "scale": r.get("scale"), "evidence": r["evidence"]})
  except OSError:
    pass
  meta = _read_json(f"storage/{sim}/reverie/meta.json", {})
  return {"name": name, "saved_time": meta.get("curr_time"), "nodes": nodes, "readings": readings}


def dashboard_memory(request, sim):
  """One agent's whole memory, for the Memory tab."""
  name = request.GET.get("agent", "")
  # Only an agent of this run: the name becomes part of a file path.
  try:
    agents = os.listdir(f"storage/{sim}/personas") if SIM_NAME.match(sim) else []
  except OSError:
    agents = []
  if name not in agents:
    return JsonResponse({"error": "No such run or agent."}, status=404)
  return JsonResponse(agent_memory(sim, name))


def dashboard_timeline(request, sim):
  """Where each agent was over the run, for the Activity chart."""
  if not SIM_NAME.match(sim):
    return JsonResponse({"error": "Bad run name."}, status=400)
  return JsonResponse(activity_timeline(sim))


def _backend_status(state):
  """running / idle / finished come from reverie itself; starting and
  stopped are inferred from process liveness."""
  pid = state.get("pid") if state else None
  if pid and _alive(pid) and state.get("status") != "finished":
    return state["status"]
  launch = _read_json(LAUNCH_FILE, {})
  # A launched process that hasn't written its own state yet is starting;
  # one that already reported "finished" is just exiting.
  if _alive(launch.get("pid")) and launch.get("pid") != pid:
    return "starting"
  return "stopped"


def dashboard(request):
  histories = sorted(p.split("static_dirs/assets/")[1]
                     for p in glob.glob(HISTORY_GLOB))
  return render(request, "dashboard/dashboard.html",
                {"histories_json": json.dumps(histories)})


def dashboard_state(request):
  state = _read_json(STATE_FILE)
  status = _backend_status(state)
  agent = request.GET.get("agent")
  data = {"status": status, "sims": _sims(), "settings": _settings(),
          "run_env": _run_env(),
          "results": _tail_jsonl(RESULT_FILE, 40),
          "launch": _read_json(LAUNCH_FILE, {})}
  if state:
    personas = state.pop("personas", {})
    state["roster"] = [{k: personas[n].get(k) for k in ROSTER_FIELDS}
                       for n in state.get("persona_order", []) if n in personas]
    state["agent"] = personas.get(agent)
    sim = state["sim_code"]
    state["start_step"] = start = _run_start(sim)
    opinions = _run_log(sim, "opinions.jsonl", 4000, start)
    if state["agent"]:
      state["agent"]["history"] = _view_history(sim, agent)
      state["agent"]["evidence"] = _stance_evidence(sim, agent, opinions)
    data["conversations"] = _run_log(sim, "conversations.jsonl", 300, start)
    data["events"] = _run_log(sim, "events.jsonl", 300, start)
    data["opinions"] = _opinions(opinions)
    data["whispers"] = _whispers(sim)
    data["mentions"] = _mentions(sim, start)
    data["network"] = network_summary(sim, state.get("persona_order", []), state["step"])
    # Results from before runs were tagged have no "sim"; keep showing those.
    data["results"] = [r for r in data["results"] if r.get("sim") in (None, sim)]
  data["sim"] = state
  return JsonResponse(data)


_price = _llm_usage.price


def _cost(row):
  return _llm_usage.cost(row.get("model"), row.get("in", 0),
                         row.get("cached", 0), row.get("out", 0))


# The usage log covers every run ever made and grows with each API call, so
# it is read incrementally into running totals rather than kept as rows. Only
# the last day's rows are kept, for the "today" and "last 5 minutes" figures.
RECENT_SECS = 26 * 3600


def _blank():
  return {"calls": 0, "chat": 0, "embedding": 0, "errors": 0,
          "in": 0, "cached": 0, "out": 0, "cost": 0.0}


def _add(t, r):
  t["calls"] += 1
  t[r.get("kind", "chat")] = t.get(r.get("kind", "chat"), 0) + 1
  t["errors"] += not r.get("ok", True)
  for k in ("in", "cached", "out"):
    t[k] += r.get(k, 0)
  t["cost"] += r["cost"] or 0


def _bucket(sums, at, r):
  s = sums.setdefault(at, [0, 0, 0])
  s[0] += r["cost"] or 0
  s[1] += r.get("in", 0) + r.get("out", 0)
  s[2] += 1


class _UsageTotals:
  """Running totals for one scope (all runs, or one run)."""

  def __init__(self):
    self.totals = _blank()
    self.groups = {"persona": {}, "source": {}, "model": {}}
    self.errors = collections.deque(maxlen=8)
    self.hours, self.days, self.steps = {}, {}, {}
    self.step_totals, self.step_span = _blank(), None
    self.first = self.last = None

  def add(self, r):
    _add(self.totals, r)
    if r.get("persona"):
      _add(self.groups["persona"].setdefault(r["persona"], _blank()), r)
    for key in ("source", "model"):
      _add(self.groups[key].setdefault(r.get(key) or "other", _blank()), r)
    if not r.get("ok", True):
      self.errors.append({"ts": r["ts"], "model": r.get("model"), "status": r.get("status"),
                          "error": r.get("error"), "persona": r.get("persona")})
    hour = int(r["ts"] // 3600) * 3600
    _bucket(self.hours, hour, r)
    _bucket(self.days, _hour_day(hour), r)
    if r.get("step") is not None:
      _bucket(self.steps, r["step"], r)
    if r.get("source") == "step":
      _add(self.step_totals, r)
      if r.get("step") is not None:
        lo, hi = self.step_span or (r["step"], r["step"])
        self.step_span = (min(lo, r["step"]), max(hi, r["step"]))
    self.first = r["ts"] if self.first is None else self.first
    self.last = r["ts"]

  def scope(self, series):
    groups = lambda g: sorted(({"name": k, **v} for k, v in g.items()), key=lambda x: -x["cost"])
    return {"totals": dict(self.totals), "agents": groups(self.groups["persona"]),
            "sources": groups(self.groups["source"]), "models": groups(self.groups["model"]),
            "errors": list(self.errors)[::-1], "series": series}

  def wall_series(self):
    """Hourly buckets, or daily once the span exceeds 72 hours."""
    if self.first is None:
      return {"kind": "wall", "size": 3600, "points": []}
    daily = self.last - self.first > 72 * 3600
    return {"kind": "wall", "size": 86400 if daily else 3600,
            "points": _fill(self.days if daily else self.hours, 86400 if daily else 3600, daily)}

  def game_series(self, sec_per_step):
    sums = {}
    for step, (cost, tokens, calls) in self.steps.items():
      s = sums.setdefault(int(step * sec_per_step // 3600) * 3600, [0, 0, 0])
      s[0] += cost; s[1] += tokens; s[2] += calls
    return {"kind": "game", "size": 3600, "sec_per_step": sec_per_step,
            "points": _fill(sums, 3600, False)}


def _usage_reset():
  _usage.update(offset=0, all=_UsageTotals(), runs={}, recent=collections.deque(),
                latency=collections.deque(maxlen=200), unpriced=set(), since=None)


_usage = {"ino": None, "head": b""}
_usage_reset()
_usage_lock = threading.Lock()


def _usage_read():
  """Folds lines appended to the usage log since the last call into the totals."""
  try:
    st = os.stat(USAGE_FILE)
    with open(USAGE_FILE, "rb") as f:
      head = f.read(256)
  except OSError:
    return
  size = st.st_size
  # Reset if the file was replaced or rewritten rather than appended to.
  if (size < _usage["offset"] or st.st_ino != _usage["ino"]
      or head[:len(_usage["head"])] != _usage["head"]):
    _usage_reset()
  _usage.update(ino=st.st_ino, head=head)
  if size > _usage["offset"]:
    with open(USAGE_FILE, "rb") as f:
      f.seek(_usage["offset"])
      chunk = f.read()
    complete = chunk[:chunk.rfind(b"\n") + 1]
    _usage["offset"] += len(complete)
    for line in complete.decode("utf-8", "replace").splitlines():
      try:
        row = json.loads(line)
      except ValueError:
        continue
      row["cost"] = _cost(row)
      _usage["since"] = row["ts"] if _usage["since"] is None else _usage["since"]
      _usage["all"].add(row)
      _usage["runs"].setdefault(row.get("sim"), _UsageTotals()).add(row)
      _usage["recent"].append(row)
      if row.get("ok") and row.get("kind") == "chat":
        _usage["latency"].append(row["secs"])
      if row["cost"] is None:
        _usage["unpriced"].add(row.get("model"))
  recent = _usage["recent"]
  while recent and recent[0]["ts"] < time.time() - RECENT_SECS:
    recent.popleft()


def _totals(rows):
  t = _blank()
  for r in rows:
    _add(t, r)
  return t


def _group(rows, key):
  groups = {}
  for r in rows:
    _add(groups.setdefault(r.get(key) or "other", _blank()), r)
  return sorted(({"name": k, **v} for k, v in groups.items()), key=lambda g: -g["cost"])


def _local_day(ts):
  """Local midnight at or before <ts>."""
  return int(time.mktime(time.localtime(ts)[:3] + (0, 0, 0, 0, 0, -1)))


@functools.lru_cache(maxsize=4096)
def _hour_day(hour):
  return _local_day(hour)


def _fill(sums, size, local_days=False):
  """[[bucket start, cost, tokens, calls], ...] from {bucket start: sums},
  zero-filled between the first and last bucket."""
  if not sums:
    return []
  out, b = [], min(sums)
  while b <= max(sums):
    out.append([b, *sums.get(b, [0, 0, 0])])
    # Days can be 23 or 25 hours across a DST change.
    b = _local_day(b + 26 * 3600) if local_days else b + size
  return out


def _scope(rows, series):
  return {
    "totals": _totals(rows),
    "agents": _group([r for r in rows if r.get("persona")], "persona"),
    "sources": _group(rows, "source"),
    "models": _group(rows, "model"),
    "errors": [{"ts": r["ts"], "model": r.get("model"),
                "status": r.get("status"), "error": r.get("error"),
                "persona": r.get("persona")}
               for r in rows if not r.get("ok", True)][-8:][::-1],
    "series": series,
  }


def _wall_series(rows):
  """Hourly buckets, or daily once the span exceeds 72 hours."""
  if not rows:
    return {"kind": "wall", "size": 3600, "points": []}
  size = 3600 if rows[-1]["ts"] - rows[0]["ts"] <= 72 * 3600 else 86400
  sums = {}
  for r in rows:
    _bucket(sums, _local_day(r["ts"]) if size == 86400 else int(r["ts"] // size) * size, r)
  return {"kind": "wall", "size": size, "points": _fill(sums, size, size == 86400)}


def dashboard_usage(request):
  sim = request.GET.get("sim") or (_read_json(STATE_FILE) or {}).get("sim_code")
  sec_per_step = (_read_json(f"storage/{sim}/reverie/meta.json", {}) or {}).get("sec_per_step") or 10
  now = time.time()
  midnight = _local_day(now)
  with _usage_lock:
    _usage_read()
    every, run = _usage["all"], _usage["runs"].get(sim) or _UsageTotals()
    today_rows = [r for r in _usage["recent"] if r["ts"] >= midnight]
    recent = [r for r in _usage["recent"] if r["ts"] > now - 300]
    span = run.step_span
    game_hours = (span[1] - span[0] + 1) * sec_per_step / 3600 if span else 0
    ok_chat = list(_usage["latency"])
    ok_chat_sorted = sorted(ok_chat)
    return JsonResponse({
      "since": _usage["since"],
      "sim": sim,
      "run": dict(run.totals),
      "today": _totals(today_rows),
      "all": dict(every.totals),
      "last5": {**_totals(recent), "minutes": 5},
      "game_hours": game_hours,
      # Per-game-hour figures use step calls only.
      "steps": dict(run.step_totals),
      "latency": {
        "avg": sum(ok_chat) / len(ok_chat) if ok_chat else None,
        "p95": ok_chat_sorted[int(len(ok_chat_sorted) * 0.95)] if ok_chat else None,
        "n": len(ok_chat)},
      "scopes": {"run": run.scope(run.game_series(sec_per_step)),
                 "today": _scope(today_rows, _wall_series(today_rows)),
                 "all": every.scope(every.wall_series())},
      "unpriced": sorted(_usage["unpriced"], key=str),
      "prices": {k: list(v) for k, v in PRICES.items()},
    })


def dashboard_log(request):
  # Enough for several runs; the page groups them by run.
  return JsonResponse({"lines": _tail_lines(BACKEND_LOG, 2000, max_bytes=1024 * 1024)})


@require_POST
def dashboard_command(request):
  cmd = json.loads(request.body or "{}").get("cmd", "").strip()
  if not cmd:
    return JsonResponse({"error": "Type a command first."}, status=400)
  if _backend_status(_read_json(STATE_FILE)) not in ("idle", "running"):
    return JsonResponse({"error": "The simulation isn't running. Start one "
                                  "first."}, status=409)
  cmd_id = uuid.uuid4().hex[:10]
  os.makedirs(DASH_DIR, exist_ok=True)
  with open(CMD_FILE, "a") as f:
    f.write(json.dumps({"id": cmd_id, "cmd": cmd}) + "\n")
  log.info("dashboard command %s: %s", cmd_id, cmd)
  return JsonResponse({"id": cmd_id})


def _whisper_rows(item, state, known):
  """The rows that plan one whisper from the composer, or a ValueError saying
  what to fix. Times are game time; a run's clock only moves while it runs."""
  if not isinstance(item, dict):
    raise ValueError("it couldn't be read. Close this and try again.")
  names = state.get("persona_order", [])
  wanted = item.get("targets")
  wanted = wanted if isinstance(wanted, list) else []
  unknown = [str(n) for n in wanted if n not in names]
  if unknown:
    raise ValueError(f"{', '.join(unknown)} isn't in this run.")
  targets = [n for n in names if n in wanted]
  if not targets:
    raise ValueError("pick at least one person.")
  # One line: a whisper is stored as a single statement in an agent's memory.
  text = " ".join(str(item.get("text") or "").split())
  if not text:
    raise ValueError("write what they should hear.")
  if len(text) > WHISPER_MAX_CHARS:
    raise ValueError(f"keep it under {WHISPER_MAX_CHARS} characters.")

  at = item.get("at")
  if at is not None:
    try:
      due = datetime.datetime.fromisoformat(str(at))
    except ValueError:
      raise ValueError("pick a date and time.")
    # Game time has no time zone, and an aware time can't be compared with it.
    if due.tzinfo is not None:
      raise ValueError("pick a date and time.")
    now = datetime.datetime.strptime(state["curr_time"], whisper_plan.TIME_FORMAT)
    # The picker only goes down to the minute, so the current minute still counts.
    if due < now.replace(second=0):
      raise ValueError(f"that time has passed. The game clock is at "
                       f"{now.strftime('%B %d, %H:%M')}.")
    at = due.strftime(whisper_plan.TIME_FORMAT)

  rows = []
  replaces = item.get("replaces")
  if replaces:
    if known.get(str(replaces), {}).get("status") not in ("scheduled", "failed"):
      raise ValueError("the whisper you were editing has already started going "
                       "out. Close this and check the list.")
    del known[str(replaces)]  # A second draft can't replace it again.
    rows.append({"op": "cancel", "id": str(replaces)})
  rows.append({"op": "add", "id": uuid.uuid4().hex[:10], "text": text,
               "targets": targets, "at": at, "replaces": str(replaces) if replaces else None})
  return rows


def _live_state():
  """The state of the loaded run, or None when no run is loaded."""
  state = _read_json(STATE_FILE)
  return state if _backend_status(state) in ("idle", "running") else None


@require_POST
def dashboard_whispers(request):
  """Plans whispers for the live run, all of them or none. The simulation picks
  them up from the file, including in the middle of a run."""
  try:
    body = json.loads(request.body or "{}")
  except ValueError:
    body = None
  if not isinstance(body, dict):
    return JsonResponse({"error": "That request couldn't be read."}, status=400)
  state = _live_state()
  if not state:
    return JsonResponse({"error": "No run is loaded. Start one first; 0 steps "
                                  "is enough."}, status=409)
  sim = state["sim_code"]
  if body.get("sim") != sim:
    return JsonResponse({"error": f"The loaded run is now {sim}. Close this and "
                                  f"try again."}, status=409)
  items = body.get("whispers")
  if not items or not isinstance(items, list):
    return JsonResponse({"error": "Add a whisper first."}, status=400)
  known = {w["id"]: w for w in _whispers(sim)}
  rows = []
  for i, item in enumerate(items):
    try:
      rows += _whisper_rows(item, state, known)
    except ValueError as e:
      message = str(e)
      error = (f"Whisper {i + 1}: {message}" if len(items) > 1
               else message[0].upper() + message[1:])
      return JsonResponse({"error": error}, status=400)
  whisper_plan.append(whisper_plan.path_for(f"storage/{sim}"), rows)
  log.info("dashboard whispers for %s: %s", sim, rows)
  return JsonResponse({"whispers": _whispers(sim)})


@require_POST
def dashboard_whisper_cancel(request, whisper_id):
  """Stops a whisper that hasn't finished going out, or dismisses a failed one."""
  state = _live_state()
  if not state:
    return JsonResponse({"error": "No run is loaded."}, status=409)
  sim = state["sim_code"]
  whisper = next((w for w in _whispers(sim) if w["id"] == whisper_id), None)
  if not whisper:
    return JsonResponse({"error": "That whisper isn't in this run."}, status=404)
  if whisper["status"] == "sent":
    return JsonResponse({"error": "That whisper has already gone out."}, status=409)
  whisper_plan.append(whisper_plan.path_for(f"storage/{sim}"),
                      [{"op": "cancel", "id": whisper_id}])
  log.info("dashboard whisper %s cancelled for %s", whisper_id, sim)
  return JsonResponse({"whispers": _whispers(sim)})


DEFAULT_SETTINGS = {"autosave_steps": 360, "budget_usd": None,
                    "opinion_steps": 360}


# Same as reverie/backend_server/run_env.py. Git tracks prod-* runs only.
RUN_PREFIXES = {"staging": "stg-", "production": "prod-"}


def _run_env(utils_path=f"{BACKEND_DIR}/utils.py"):
  """run_env from the backend's utils.py, read as text rather than imported
  (it holds API keys). "staging" when it isn't set, matching run_env.py."""
  try:
    with open(utils_path) as f:
      m = re.search(r"""^run_env\s*=\s*["'](\w+)["']""", f.read(), re.M)
  except OSError:
    return "staging"
  return m.group(1) if m else "staging"


def _run_name(sim, env):
  """stg-<name> in staging, prod-<name> in production, matching
  run_env.run_name: a prefix from the other mode is replaced, not stacked."""
  for prefix in RUN_PREFIXES.values():
    if sim.startswith(prefix):
      sim = sim[len(prefix):]
      break
  return RUN_PREFIXES.get(env, RUN_PREFIXES["staging"]) + sim


def _settings():
  return {**DEFAULT_SETTINGS, **(_read_json(SETTINGS_FILE, {}) or {})}


def dashboard_settings(request):
  """GET returns the auto-save and spending-cap settings; POST updates them.
  The running simulation re-reads the file after every step."""
  if request.method != "POST":
    return JsonResponse(_settings())
  body = json.loads(request.body or "{}")
  new = _settings()
  if "autosave_steps" in body:
    try:
      steps = int(body["autosave_steps"] or 0)
    except (TypeError, ValueError):
      return JsonResponse({"error": "Auto-save needs a whole number of steps."}, status=400)
    if not 0 <= steps <= 100000:
      return JsonResponse({"error": "Auto-save must be between 0 (off) and 100000 steps."}, status=400)
    new["autosave_steps"] = steps
  if "opinion_steps" in body:
    try:
      steps = int(body["opinion_steps"] or 0)
    except (TypeError, ValueError):
      return JsonResponse({"error": "Stance readings need a whole number of steps."}, status=400)
    if not 0 <= steps <= 100000:
      return JsonResponse({"error": "Stance readings must be between 0 (off) and 100000 steps."}, status=400)
    new["opinion_steps"] = steps
  if "budget_usd" in body:
    raw = body["budget_usd"]
    if raw in (None, ""):
      new["budget_usd"] = None
    else:
      try:
        cap = float(raw)
      except (TypeError, ValueError):
        return JsonResponse({"error": "The spending cap needs to be a dollar amount."}, status=400)
      if not 0 < cap <= 10000:
        return JsonResponse({"error": "The spending cap must be more than $0 and at most $10,000."}, status=400)
      new["budget_usd"] = round(cap, 2)
  os.makedirs(DASH_DIR, exist_ok=True)
  tmp = SETTINGS_FILE + ".tmp"
  with open(tmp, "w") as f:
    json.dump(new, f)
  os.replace(tmp, SETTINGS_FILE)
  log.info("dashboard settings: %s", new)
  return JsonResponse(new)


@require_POST
def dashboard_launch(request):
  body = json.loads(request.body or "{}")
  fork, sim = body.get("fork", ""), body.get("sim", "").strip()
  history = body.get("history") or None
  if _backend_status(_read_json(STATE_FILE)) != "stopped":
    return JsonResponse({"error": "A simulation is already running. Finish "
                                  "it before starting another."}, status=409)
  if not os.path.exists(f"storage/{fork}/reverie/meta.json"):
    return JsonResponse({"error": f"No saved simulation named {fork}."},
                        status=400)
  if not SIM_NAME.match(sim):
    return JsonResponse({"error": "Use letters, numbers, - or _ for the new "
                                  "name."}, status=400)
  sim = _run_name(sim, _run_env())
  if os.path.exists(f"storage/{sim}"):
    return JsonResponse({"error": f"{sim} already exists. Pick a new name."},
                        status=400)
  allowed = [p.split("static_dirs/assets/")[1] for p in glob.glob(HISTORY_GLOB)]
  if history and history not in allowed:
    return JsonResponse({"error": "Unknown history file."}, status=400)
  try:
    run_steps = int(body.get("run_steps") or 0)
  except (TypeError, ValueError):
    return JsonResponse({"error": "Steps must be a whole number."}, status=400)
  if not 0 <= run_steps <= 100000:
    return JsonResponse({"error": "Steps must be between 0 and 100000."}, status=400)

  args = [sys.executable, "-u", "reverie.py", fork, sim]
  if history:
    args += ["--history", history]
  if run_steps:
    args += ["--run", str(run_steps)]
  os.makedirs(f"{BACKEND_DIR}/logs", exist_ok=True)
  out = open(f"{BACKEND_DIR}/logs/reverie_console.log", "a")
  proc = subprocess.Popen(args, cwd=BACKEND_DIR, stdin=subprocess.DEVNULL,
                          stdout=out, stderr=subprocess.STDOUT,
                          start_new_session=True)
  # Reap it when it exits so a finished run doesn't linger as a zombie that
  # still looks alive to os.kill(pid, 0).
  threading.Thread(target=proc.wait, daemon=True).start()
  os.makedirs(DASH_DIR, exist_ok=True)
  with open(LAUNCH_FILE, "w") as f:
    json.dump({"pid": proc.pid, "fork": fork, "sim": sim, "history": history,
               "at": time.time()}, f)
  log.info("launched reverie pid=%s fork=%s sim=%s history=%s run_steps=%s",
           proc.pid, fork, sim, history, run_steps)
  return JsonResponse({"pid": proc.pid, "sim": sim})
