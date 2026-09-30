"""
Web dashboard for controlling a simulation and watching its agents.

Talks to reverie.py through files in temp_storage/dashboard/ (see
reverie/backend_server/dashboard_bridge.py). Paths are relative to
environment/frontend_server, like the rest of translator/views.py.
"""
import glob
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

log = logging.getLogger("frontend.dashboard")

DASH_DIR = "temp_storage/dashboard"
STATE_FILE = f"{DASH_DIR}/state.json"
CMD_FILE = f"{DASH_DIR}/commands.jsonl"
RESULT_FILE = f"{DASH_DIR}/results.jsonl"
LAUNCH_FILE = f"{DASH_DIR}/launch.json"
BACKEND_DIR = "../../reverie/backend_server"
BACKEND_LOG = f"{BACKEND_DIR}/logs/datacenter-town.log"
USAGE_FILE = f"{BACKEND_DIR}/logs/api_usage.jsonl"

# USD per 1M tokens: (input, cached input, output). Standard tier, from
# developers.openai.com/api/docs/pricing (checked 2026-09-29). Edit here if
# prices change; every past call is re-costed from its stored token counts.
PRICES = {
  "gpt-4o": (2.50, 1.25, 10.00),
  "gpt-4o-mini": (0.15, 0.075, 0.60),
  "gpt-4.1": (2.00, 0.50, 8.00),
  "gpt-4.1-mini": (0.40, 0.10, 1.60),
  "text-embedding-3-small": (0.02, 0.02, 0.0),
  "text-embedding-3-large": (0.13, 0.13, 0.0),
}
HISTORY_GLOB = "static_dirs/assets/the_ville/agent_history_init_*.csv"
SIM_NAME = re.compile(r"^[\w-]+$")
# Fields the roster needs every second; the rest is sent for the open agent.
ROSTER_FIELDS = ("name", "first_name", "act_description", "act_pronunciatio",
                 "act_address", "chatting_with", "curr_tile", "currently")


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


def _tail_jsonl(path, n):
  out = []
  for line in _tail_lines(path, n):
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
                 "mtime": os.path.getmtime(meta_path)})
  return sorted(sims, key=lambda s: -s["mtime"])


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
  data = {"status": status, "sims": _sims(),
          "results": _tail_jsonl(RESULT_FILE, 40),
          "launch": _read_json(LAUNCH_FILE, {})}
  if state:
    personas = state.pop("personas", {})
    state["roster"] = [{k: personas[n].get(k) for k in ROSTER_FIELDS}
                       for n in state.get("persona_order", []) if n in personas]
    state["agent"] = personas.get(agent)
    exp = f"storage/{state['sim_code']}/experiment"
    data["conversations"] = _tail_jsonl(f"{exp}/conversations.jsonl", 40)
    data["events"] = _tail_jsonl(f"{exp}/events.jsonl", 60)
  data["sim"] = state
  return JsonResponse(data)


def _price(model):
  # Longest matching prefix, so "gpt-4o-mini" isn't priced as "gpt-4o" and
  # dated names like "gpt-4o-2024-08-06" still match.
  keys = [k for k in PRICES if (model or "").startswith(k)]
  return PRICES[max(keys, key=len)] if keys else None


def _cost(row):
  p = _price(row.get("model"))
  if not p:
    return None
  cached = min(row.get("cached", 0), row.get("in", 0))
  return ((row.get("in", 0) - cached) * p[0] + cached * p[1]
          + row.get("out", 0) * p[2]) / 1e6


# Rows parsed so far, read incrementally so each poll only parses new lines.
_usage = {"offset": 0, "rows": []}


def _usage_rows():
  try:
    size = os.path.getsize(USAGE_FILE)
  except OSError:
    return []
  if size < _usage["offset"]:
    _usage.update(offset=0, rows=[])  # file was replaced
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
      _usage["rows"].append(row)
  return _usage["rows"]


def _totals(rows):
  t = {"calls": len(rows), "chat": 0, "embedding": 0, "errors": 0,
       "in": 0, "cached": 0, "out": 0, "cost": 0.0}
  for r in rows:
    t[r.get("kind", "chat")] = t.get(r.get("kind", "chat"), 0) + 1
    t["errors"] += not r.get("ok", True)
    for k in ("in", "cached", "out"):
      t[k] += r.get(k, 0)
    t["cost"] += r["cost"] or 0
  return t


def _group(rows, key):
  groups = {}
  for r in rows:
    groups.setdefault(r.get(key) or "other", []).append(r)
  return sorted(({"name": k, **_totals(v)} for k, v in groups.items()),
                key=lambda g: -g["cost"])


def dashboard_usage(request):
  rows = _usage_rows()
  sim = (_read_json(STATE_FILE) or {}).get("sim_code")
  sec_per_step = (_read_json(STATE_FILE) or {}).get("sec_per_step") or 10
  now = time.time()
  midnight = time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1))
  run_rows = [r for r in rows if r.get("sim") == sim]
  recent = [r for r in rows if r["ts"] > now - 300]

  # Average cost per game hour over the steps this run has simulated.
  steps = [r["step"] for r in run_rows if r.get("source") == "step"
           and r.get("step") is not None]
  step_cost = sum(r["cost"] or 0 for r in run_rows if r.get("source") == "step")
  game_hours = ((max(steps) - min(steps) + 1) * sec_per_step / 3600
                if steps else 0)

  ok_chat = [r["secs"] for r in rows if r.get("ok") and r.get("kind") == "chat"][-200:]
  ok_chat_sorted = sorted(ok_chat)
  return JsonResponse({
    "since": rows[0]["ts"] if rows else None,
    "sim": sim,
    "run": _totals(run_rows),
    "today": _totals([r for r in rows if r["ts"] >= midnight]),
    "all": _totals(rows),
    "last5": {**_totals(recent), "minutes": 5},
    "per_game_hour": step_cost / game_hours if game_hours else None,
    "game_hours": game_hours,
    "latency": {
      "avg": sum(ok_chat) / len(ok_chat) if ok_chat else None,
      "p95": ok_chat_sorted[int(len(ok_chat_sorted) * 0.95)] if ok_chat else None,
      "n": len(ok_chat)},
    "agents": _group([r for r in run_rows if r.get("persona")], "persona"),
    "sources": _group(run_rows, "source"),
    "models": _group(rows, "model"),
    "unpriced": sorted({r.get("model") for r in rows if r["cost"] is None}),
    "errors": [{"ts": r["ts"], "model": r.get("model"),
                "status": r.get("status"), "error": r.get("error"),
                "persona": r.get("persona")}
               for r in rows if not r.get("ok", True)][-8:][::-1],
    "prices": {k: list(v) for k, v in PRICES.items()},
  })


def dashboard_log(request):
  return JsonResponse({"lines": _tail_lines(BACKEND_LOG, 300)})


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
  if os.path.exists(f"storage/{sim}"):
    return JsonResponse({"error": f"{sim} already exists. Pick a new name."},
                        status=400)
  allowed = [p.split("static_dirs/assets/")[1] for p in glob.glob(HISTORY_GLOB)]
  if history and history not in allowed:
    return JsonResponse({"error": "Unknown history file."}, status=400)

  args = [sys.executable, "-u", "reverie.py", fork, sim]
  if history:
    args += ["--history", history]
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
  log.info("launched reverie pid=%s fork=%s sim=%s history=%s",
           proc.pid, fork, sim, history)
  return JsonResponse({"pid": proc.pid})
