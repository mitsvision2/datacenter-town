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
