"""
Bridge between a running ReverieServer and the web dashboard
(environment/frontend_server, /dashboard).

Files under temp_storage/dashboard/:
  commands.jsonl  dashboard -> reverie  {"id", "cmd"}
  results.jsonl   reverie -> dashboard  {"id", "cmd", "ok", "output", "time"}
  state.json      reverie -> dashboard  live snapshot of the sim and every persona

Terminal input keeps working: stdin lines and dashboard commands feed the
same queue. "stop" is handled out of band so it can end a run mid-way.
"""
import collections
import json
import os
import queue
import sys
import threading
import time
import traceback
from datetime import datetime

from utils import fs_temp_storage

DASH_DIR = f"{fs_temp_storage}/dashboard"
CMD_FILE = f"{DASH_DIR}/commands.jsonl"
RESULT_FILE = f"{DASH_DIR}/results.jsonl"
STATE_FILE = f"{DASH_DIR}/state.json"

# Recent LLM calls per persona: the closest thing to watching an agent think.
# Filled from print_run_prompts, so it needs debug = True in utils.py.
_llm_trace = collections.defaultdict(lambda: collections.deque(maxlen=12))
_last_state_write = 0.0


def _now():
  return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _append_jsonl(path, obj):
  os.makedirs(DASH_DIR, exist_ok=True)
  with open(path, "a") as f:
    f.write(json.dumps(obj, default=str) + "\n")


def record_llm(persona_name, template, prompt, output):
  _llm_trace[persona_name].append({
    "at": datetime.now().strftime("%H:%M:%S"),
    "template": os.path.basename(str(template or "")).replace(".txt", ""),
    # The end of a prompt holds the actual question being asked.
    "prompt": str(prompt or "")[-900:],
    "output": str(output)[:900],
  })


def record_result(cmd_id, cmd, ok, output):
  _append_jsonl(RESULT_FILE, {"id": cmd_id, "cmd": cmd, "ok": ok,
                              "output": output, "time": _now()})


class CommandFeed:
  """Merges terminal input and dashboard commands into one blocking queue."""

  def __init__(self, on_stop, initial=()):
    os.makedirs(DASH_DIR, exist_ok=True)
    self.q = queue.Queue()
    self.on_stop = on_stop
    # Start at the current end of the file so commands left over from an
    # earlier session (e.g. "fin") never replay.
    self.offset = os.path.getsize(CMD_FILE) if os.path.exists(CMD_FILE) else 0
    for cmd in initial:
      self.q.put((None, cmd))
    threading.Thread(target=self._read_stdin, daemon=True).start()
    threading.Thread(target=self._tail_file, daemon=True).start()

  def get(self):
    return self.q.get()

  def _put(self, cmd_id, cmd):
    if cmd.strip().lower() == "stop":
      self.on_stop()
      record_result(cmd_id, cmd, True, "Stopping after the current step.")
      return
    self.q.put((cmd_id, cmd))

  def _read_stdin(self):
    try:
      for line in sys.stdin:
        if line.strip():
          self._put(None, line.strip())
    except (OSError, ValueError):
      pass  # no terminal attached (launched from the dashboard)

  def _tail_file(self):
    while True:
      try:
        if os.path.exists(CMD_FILE) and os.path.getsize(CMD_FILE) > self.offset:
          with open(CMD_FILE, "rb") as f:
            f.seek(self.offset)
            chunk = f.read()
          complete = chunk[:chunk.rfind(b"\n") + 1]
          self.offset += len(complete)
          for line in complete.decode("utf-8").splitlines():
            if line.strip():
              msg = json.loads(line)
              self._put(msg.get("id"), str(msg.get("cmd", "")).strip())
      except Exception:
        traceback.print_exc()
      time.sleep(0.3)


def _node(n):
  out = {"type": n.type, "created": n.created, "description": n.description,
         "poignancy": n.poignancy}
  if n.type == "chat" and isinstance(n.filling, list):
    out["lines"] = n.filling
  return out


def _persona_state(p):
  s = p.scratch
  schedule_idx = None
  if s.curr_time and s.f_daily_schedule:
    try:
      schedule_idx = s.get_f_daily_schedule_index()
    except Exception:
      pass
  return {
    "name": s.name, "first_name": s.first_name, "age": s.age,
    "innate": s.innate, "learned": s.learned, "lifestyle": s.lifestyle,
    "living_area": s.living_area, "currently": s.currently,
    "daily_plan_req": s.daily_plan_req, "daily_req": s.daily_req,
    "act_description": s.act_description,
    "act_pronunciatio": s.act_pronunciatio,
    "act_address": s.act_address, "act_start_time": s.act_start_time,
    "act_duration": s.act_duration,
    "act_obj_description": s.act_obj_description,
    "chatting_with": s.chatting_with, "chat": s.chat,
    "chatting_end_time": s.chatting_end_time,
    "curr_tile": s.curr_tile, "path_left": len(s.planned_path or []),
    "schedule": s.f_daily_schedule, "schedule_idx": schedule_idx,
    "hourly_org": s.f_daily_schedule_hourly_org,
    "reflect_trigger": [s.importance_trigger_curr, s.importance_trigger_max],
    "memory_counts": {"event": len(p.a_mem.seq_event),
                      "thought": len(p.a_mem.seq_thought),
                      "chat": len(p.a_mem.seq_chat)},
    "events": [_node(n) for n in p.a_mem.seq_event[:15]],
    "thoughts": [_node(n) for n in p.a_mem.seq_thought[:15]],
    "chats": [_node(n) for n in p.a_mem.seq_chat[:6]],
    "llm": list(_llm_trace[s.name])[::-1],
  }


def write_state(rs, status, run_left=0, force=True):
  """Atomically writes the live snapshot. Unforced writes are throttled so
  fast (sleeping) steps don't rewrite the file ten times a second."""
  global _last_state_write
  if not force and time.time() - _last_state_write < 0.5:
    return
  _last_state_write = time.time()
  state = {
    "sim_code": rs.sim_code, "fork_sim_code": rs.fork_sim_code,
    "maze_name": rs.maze.maze_name, "pid": os.getpid(),
    "status": status, "run_left": run_left, "step": rs.step,
    "curr_time": rs.curr_time.strftime("%B %d, %Y, %H:%M:%S"),
    "sec_per_step": rs.sec_per_step, "updated_at": time.time(),
    "persona_order": list(rs.personas.keys()),
    "personas": {n: _persona_state(p) for n, p in rs.personas.items()},
  }
  os.makedirs(DASH_DIR, exist_ok=True)
  tmp = STATE_FILE + ".tmp"
  with open(tmp, "w") as f:
    json.dump(state, f, default=str)
  os.replace(tmp, STATE_FILE)
