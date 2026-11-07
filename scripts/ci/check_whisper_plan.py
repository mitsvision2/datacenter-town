"""
Rules for planned whispers, checked in CI (.github/workflows/ci.yml). Run from
the repo root: python scripts/ci/check_whisper_plan.py

Runs the real step loop and the real delivery code against a throwaway run
folder, with stub agents and no API calls:

- A whisper goes out at the first step at or past its time and not before, to
  exactly the people it names, and two whispers can go to different people at
  the same step.
- A plan added while a run is going is picked up by that run. Commands wait for
  the run to end, so this is what makes scheduling work at all.
- One recipient failing is recorded and costs nobody else their whisper, and the
  run keeps going.
- A cancel stops whoever hasn't been reached, even partway through a whisper.
- Forking keeps what is scheduled and what was saved, and forgets a delivery that
  happened after the last save, since the fork's agents never heard it.
- A model answer that is empty or an API error never becomes a memory.
- Past the spending cap nothing goes out, and it goes out once the cap is raised.
- A whisper being delivered can't be edited, and console commands get the same
  per-recipient handling as the dashboard: one failure costs nobody else theirs.
- Console whispers go out mid-run like dashboard ones, instead of waiting behind
  the run in the command queue, and every other command still queues.
- The trace only asks about whispers someone in the conversation knows, follows
  them from person to person, reads who said what from the transcript, records a
  failed check as unchecked, makes no calls with no whispers, can't end a run, and
  doesn't touch an agent. A conversation in the same step as a whisper happened
  first, so it can't have carried it.
- The prompt keeps news about other people about them. The old one stored "The
  council published the figure" as "Tom Whitaker published the figure".
"""
import ast
import datetime
import inspect
import json
import os
import queue
import re
import sys
import tempfile
import types

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                       "reverie", "backend_server"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)

import dashboard_bridge
import reverie
import whisper_plan
import whisper_trace
from persona.prompt_template import run_gpt_prompt
from whisper_trace import WhisperTrace

problems = []


def check(ok, message):
  if not ok:
    problems.append(message)


START = datetime.datetime(2023, 2, 13, 8, 0, 0)
NAMES = ["Maya", "Luis", "Denise", "Tom", "Aisha"]


def game_time(step):
  return (START + datetime.timedelta(seconds=10 * step)).strftime(whisper_plan.TIME_FORMAT)


class StubScratch:
  planned_path = [(1, 1)]
  chat = None
  curr_time = START

  def get_curr_event_and_desc(self):
    return ("stub", None, None, None)

  def get_curr_obj_event_and_desc(self):
    return ("stub-object", None, None, None)


class StubPersona:
  def __init__(self, name, on_move=None):
    self.name = name
    self.scratch = StubScratch()
    self.on_move = on_move

  def move(self, maze, personas, tile, curr_time):
    self.scratch.curr_time = curr_time
    if self.on_move:
      self.on_move()
    return (tile, "x", "stub")


class StubMaze:
  maze_name = "stub"

  def __getattr__(self, name):
    return lambda *args: None


class StubLogger:
  def __init__(self):
    self.events = []
    self.new_conversations = []

  def set_step(self, step):
    pass

  def log_event(self, step, curr_time, event_type, agent=None, text=None, extra=None):
    self.events.append((step, event_type, agent, text))


def server(folder, on_move=None):
  """A ReverieServer past __init__, on stubs, in a folder of its own."""
  rs = reverie.ReverieServer.__new__(reverie.ReverieServer)
  rs.sim_code = os.path.basename(folder)
  rs.fork_sim_code = "stub"
  rs.step = 0
  rs.curr_time = START
  rs.sec_per_step = 10
  rs.server_sleep = 0
  rs.maze = StubMaze()
  rs.experiment_logger = StubLogger()
  rs.personas = {n: StubPersona(n, on_move) for n in NAMES}
  rs.personas_tile = {n: (1, 1) for n in NAMES}
  rs.whispers = whisper_plan.Plan(folder)
  rs.whisper_trace = WhisperTrace(folder, rs.whispers)
  os.makedirs(os.path.join(folder, "environment"), exist_ok=True)
  os.makedirs(os.path.join(folder, "movement"), exist_ok=True)
  with open(os.path.join(folder, "environment", "0.json"), "w") as f:
    json.dump({n: {"maze": "stub", "x": 1, "y": 1} for n in NAMES}, f)
  return rs


def run(rs, steps):
  reverie.fs_storage = os.path.dirname(rs.whispers.path.rsplit(os.sep, 2)[0])
  rs.sim_code = os.path.basename(rs.whispers.path.rsplit(os.sep, 2)[0])
  rs.start_server(steps)


heard = []


def stub_load(personas, whispers):
  for name, text in whispers:
    if text == "boom" and name == "Luis":
      raise RuntimeError("the API is down")
    heard.append((personas[name].scratch.curr_time, name, text))


reverie.load_history_via_whisper = stub_load
reverie.write_state = lambda *args, **kwargs: None
reverie.load_settings = lambda: {"opinion_steps": 0, "autosave_steps": 0, "budget_usd": None}


def add(path, id_, targets, text, at=None):
  whisper_plan.append(path, [{"op": "add", "id": id_, "text": text, "targets": targets, "at": at}])


with tempfile.TemporaryDirectory() as tmp:
  # -- Goes out on time, to the right people ----------------------------------
  folder = os.path.join(tmp, "timing")
  rs = server(folder)
  plan = rs.whispers.path
  add(plan, "a", NAMES[:3], "three of them", game_time(2))
  add(plan, "b", NAMES[3:], "the other two", game_time(2))
  add(plan, "c", NAMES[:1], "later", game_time(100))
  run(rs, 2)
  check(not heard, f"delivered before its time: {heard}")
  run(rs, 1)
  check([h[1:] for h in heard] == [(n, "three of them") for n in NAMES[:3]]
        + [(n, "the other two") for n in NAMES[3:]],
        f"wrong recipients at the due step: {heard}")
  # Stamped with the step's own time on the agent's clock, not the last step's.
  check(all(h[0] == START + datetime.timedelta(seconds=20) for h in heard),
        f"whisper stamped with the wrong game time: {heard}")
  check(("Maya" in [e[2] for e in rs.experiment_logger.events]
         and all(e[1] == "midrun_whisper" and e[0] == 2 for e in rs.experiment_logger.events)),
        "delivered whispers must log as midrun_whisper, which is what the stance "
        f"graph marks: {rs.experiment_logger.events}")
  by_id = {w["id"]: w for w in whisper_plan.summarize(whisper_plan.read(plan))}
  check(by_id["a"]["status"] == "sent" and by_id["b"]["status"] == "sent",
        "delivered whispers should read as sent")
  check(by_id["c"]["status"] == "scheduled", "a future whisper should still be waiting")

  # -- Added while the run is going -------------------------------------------
  heard.clear()
  folder = os.path.join(tmp, "midrun")
  added = []

  def add_once():
    if not added:
      added.append(True)
      add(os.path.join(folder, "experiment", "whispers.jsonl"), "m", ["Tom"], "mid-run", None)

  rs = server(folder, on_move=add_once)
  run(rs, 2)
  check([h[1:] for h in heard] == [("Tom", "mid-run")],
        f"a whisper added during a run must go out during it: {heard}")

  # -- One failure doesn't stop the rest or the run ---------------------------
  heard.clear()
  rs = server(os.path.join(tmp, "failure"))
  plan = rs.whispers.path
  add(plan, "f", ["Maya", "Luis", "Denise"], "boom")
  run(rs, 3)
  check(rs.step == 3, f"a failed whisper must not end the run, stopped at {rs.step}")
  w = whisper_plan.summarize(whisper_plan.read(plan))[0]
  check(w["status"] == "failed" and w["sent"] == ["Maya", "Denise"]
        and "API is down" in w["failed"].get("Luis", ""),
        f"failure not recorded per person: {w}")
  check(len(heard) == 2, f"a failed recipient must not be retried forever: {heard}")

  # -- A cancel stops whoever is left -----------------------------------------
  heard.clear()
  rs = server(os.path.join(tmp, "cancel"))
  plan = rs.whispers.path
  add(plan, "x", ["Maya", "Luis", "Denise"], "hello")

  def cancel_after_first(personas, whispers):
    stub_load(personas, whispers)
    whisper_plan.append(plan, [{"op": "cancel", "id": "x"}])

  reverie.load_history_via_whisper = cancel_after_first
  rs.deliver_due_whispers()
  reverie.load_history_via_whisper = stub_load
  check(len(heard) == 1, f"a cancel must stop the remaining recipients: {heard}")
  check(whisper_plan.summarize(whisper_plan.read(plan))[0]["status"] == "cancelled",
        "a cancelled whisper should read as cancelled")

  # -- Idle: nothing is delivered early, and context is put back ---------------
  heard.clear()
  rs = server(os.path.join(tmp, "idle"))
  plan = rs.whispers.path
  check(rs.deliver_due_whispers() is False, "nothing due should report False")
  add(plan, "n", ["Aisha"], "now")
  add(plan, "l", ["Aisha"], "later", game_time(50))
  before = dict(reverie.usage.context)
  check(rs.deliver_due_whispers() is True, "a due whisper should report True")
  check([h[2] for h in heard] == ["now"], f"idle delivery sent the wrong ones: {heard}")
  check(reverie.usage.context == before, "delivery must restore the usage context")

  # -- Forking ------------------------------------------------------------------
  path = os.path.join(tmp, "fork", "experiment", "whispers.jsonl")
  add(path, "before", ["Maya"], "saved", None)
  whisper_plan.append(path, [{"op": "sent", "id": "before", "agent": "Maya"},
                             {"op": "saved", "step": 10}])
  add(path, "after", ["Maya", "Tom"], "not saved", None)
  add(path, "waiting", ["Tom"], "still to come", game_time(500))
  whisper_plan.append(path, [{"op": "sent", "id": "after", "agent": "Maya"},
                             {"op": "failed", "id": "after", "agent": "Tom", "error": "x"}])
  whisper_plan.forget_unsaved(path)
  by_id = {w["id"]: w for w in whisper_plan.summarize(whisper_plan.read(path))}
  check(by_id["before"]["status"] == "sent", "a saved delivery must stay delivered in a fork")
  check(by_id["after"]["left"] == ["Maya", "Tom"],
        f"a delivery after the last save must go out again in a fork: {by_id['after']}")
  check(by_id["waiting"]["status"] == "scheduled", "a fork must keep what is still scheduled")

  # A "now" whisper keeps its moment in a fork instead of firing on load.
  path = os.path.join(tmp, "fork-now", "experiment", "whispers.jsonl")
  add(path, "n", ["Maya"], "said at step 500")
  whisper_plan.append(path, [{"op": "started", "id": "n", "time": game_time(500)},
                             {"op": "sent", "id": "n", "agent": "Maya", "time": game_time(500)}])
  whisper_plan.forget_unsaved(path)
  w = whisper_plan.summarize(whisper_plan.read(path))[0]
  check(w["at"] == game_time(500) and w["status"] == "scheduled",
        f"a forgotten 'now' whisper must keep its original time and restart: {w}")
  check(whisper_plan.next_due([w], START) is None,
        "a fork that hasn't reached that time yet must not send it")

  # -- The spending cap ---------------------------------------------------------
  heard.clear()
  rs = server(os.path.join(tmp, "cap"))
  add(rs.whispers.path, "c", ["Maya", "Tom"], "expensive")
  reverie.load_settings = lambda: {"budget_usd": 0.01}
  reverie.usage.run_cost = 1.0
  check(rs.deliver_due_whispers() is False and not heard, f"sent past the cap: {heard}")
  reverie.load_settings = lambda: {"budget_usd": 5.0}
  check(rs.deliver_due_whispers() is True and len(heard) == 2,
        f"raising the cap must release what was waiting: {heard}")
  reverie.usage.run_cost = 0.0
  reverie.load_settings = lambda: {"opinion_steps": 0, "autosave_steps": 0, "budget_usd": None}

  # -- Already delivering means too late to edit --------------------------------
  statuses = []
  rs = server(os.path.join(tmp, "started"))
  plan = rs.whispers.path
  add(plan, "s", ["Maya"], "hello")

  def note_status(personas, whispers):
    statuses.append(whisper_plan.summarize(whisper_plan.read(plan))[0]["status"])

  reverie.load_history_via_whisper = note_status
  rs.deliver_due_whispers()
  reverie.load_history_via_whisper = stub_load
  check(statuses == ["sending"],
        f"a whisper must read as sending before its first recipient's calls: {statuses}")

  # -- The real command loop: idle delivery, and failed seeds ---------------------
  heard.clear()
  rs = server(os.path.join(tmp, "console"))
  add(rs.whispers.path, "idle", ["Aisha"], "sent while idle")
  results = {}
  commands = iter([None, ("5", "call -- load history seeds.csv"), ("6", "exit")])
  # What had gone out when the first command arrived. Nothing else delivers before
  # then, so this can only be the idle loop.
  heard_while_idle = []

  class StubFeed:
    def __init__(self, on_stop, initial=(), on_whisper=None):
      pass

    def get(self, timeout=None):
      item = next(commands)
      if item and item[0] == "5":
        heard_while_idle.extend(h[1:] for h in heard)
      return item

  real_feed = reverie.CommandFeed
  reverie.CommandFeed = StubFeed
  reverie.record_result = lambda cmd_id, cmd, ok, output: results.update({cmd_id: (ok, output)})
  reverie.maze_assets_loc = tmp
  with open(os.path.join(tmp, "seeds.csv"), "w") as f:
    f.write('Name,Whisper\nMaya,"first; second"\nLuis,"boom; third"\n')
  rs.sim_code = "console"
  reverie.fs_storage = tmp
  logger = rs.experiment_logger
  rs.open_server()
  reverie.CommandFeed = real_feed
  check(heard_while_idle == [("Aisha", "sent while idle")],
        f"a whisper must go out from the idle loop with no command: {heard_while_idle}")
  check("Loaded 3 of 4" in results["5"][1] and "Failed for: Luis" in results["5"][1],
        f"a failed seed must be reported: {results.get('5')}")
  seeds = [e[3] for e in logger.events if e[1] == "history_whisper"]
  check(seeds == ["first", "second", "third"],
        f"every stored seed must be logged, even after one fails: {seeds}")

  # -- Console whispers go out mid-run, not when the run ends ----------------------
  heard.clear()
  said = {}
  dashboard_bridge.record_result = lambda cmd_id, cmd, ok, output: said.update({cmd_id: (ok, output)})
  rs = server(os.path.join(tmp, "console-midrun"))
  feed = dashboard_bridge.CommandFeed.__new__(dashboard_bridge.CommandFeed)
  feed.q = queue.Queue()
  feed.on_stop = lambda: None
  feed.on_whisper = rs.plan_console_whisper
  typed = []

  def type_once():
    if not typed:
      typed.append(True)
      feed._put("1", "call -- whisper Maya, Tom ;; to two people")

  for persona in rs.personas.values():
    persona.on_move = type_once
  run(rs, 2)
  check(feed.q.empty(), "a console whisper must not wait in the queue behind the run")
  check(sorted(h[1:] for h in heard) == [("Maya", "to two people"), ("Tom", "to two people")],
        f"a console whisper typed during a run must go out during it: {heard}")
  check(said["1"][0], f"a planned whisper should report success: {said.get('1')}")
  feed._put("2", "call -- whisper Nobody Here, Maya ;; not sent")
  check(not said["2"][0] and "Nobody Here" in said["2"][1], f"an unknown name: {said.get('2')}")
  feed._put("3", "call -- whisper all ;; ")
  check(not said["3"][0] and "Usage" in said["3"][1], f"an empty whisper: {said.get('3')}")
  feed._put("4", "CALL -- WHISPER all ;; shouting")
  check(said["4"][0], "the command is case-insensitive, as it was")
  feed._put("6", "call -- whisper Maya, ;; trailing comma")
  check(said["6"][0], f"a trailing comma isn't a person: {said.get('6')}")
  feed._put("7", f"call -- whisper Maya ;; {'x' * (whisper_plan.MAX_CHARS + 1)}")
  check(not said["7"][0] and "under" in said["7"][1], f"too long for the dashboard is too long here: {said.get('7')}")
  feed._put("8", "call -- whisper Maya ;;   two \n  lines ")
  check(said["8"][0], "a whisper with odd spacing is still a whisper")
  planned = {w["text"]: w["targets"] for w in rs.whispers.whispers()}
  check("not sent" not in planned and planned.get("shouting") == NAMES
        and planned.get("trailing comma") == ["Maya"] and "two lines" in planned,
        f"only valid whispers reach the plan, on one line: {planned}")
  feed._put("5", "print current time")
  check(feed.q.get_nowait() == ("5", "print current time"),
        "every other command still goes through the queue")

  # -- Following a whisper into conversations --------------------------------------
  asked = []

  def convo(step, a, b, lines=("first line", "second line")):
    return {"step": step, "time": game_time(step), "speakers": [a, b],
            "utterances": [[a if i % 2 == 0 else b, line] for i, line in enumerate(lines)]}

  def judge_says(answers):
    def judge(text, transcript, n_lines):
      asked.append((text, transcript, n_lines))
      return answers.get(text, {"came_up": False})
    return judge

  rs = server(os.path.join(tmp, "trace"))
  plan = rs.whispers.path
  trace = WhisperTrace(os.path.join(tmp, "trace"), rs.whispers)
  add(plan, "w", ["Maya"], "the vote moved")
  add(plan, "later", ["Tom"], "not yet sent", game_time(9999))
  add(plan, "gone", ["Tom"], "cancelled")
  whisper_plan.append(plan, [{"op": "cancel", "id": "gone"}])
  check(trace.check(convo(1, "Luis", "Tom"), judge_says({})) is None and not asked,
        f"nobody in the conversation knew, so there must be no call and no row: {asked}")
  whisper_plan.append(plan, [{"op": "sent", "id": "w", "agent": "Maya", "step": 2, "time": game_time(2)}])
  row = trace.check(convo(3, "Luis", "Tom"), judge_says({}))
  check(row is None and not asked, "still nobody who knew: no call")
  row = trace.check(convo(4, "Maya", "Tom"), judge_says({}))
  check([a[0] for a in asked] == ["the vote moved"],
        f"only whispers someone there knows are asked about: {asked}")
  check(row["checked"] == ["w"] and not row["mentions"] and not row["failed"],
        f"asked and not found: {row}")
  asked.clear()
  said_it = {"came_up": True, "line": 2, "how": "Denise raises it and Maya agrees."}
  row = trace.check(convo(5, "Maya", "Denise", ("hello", "the vote is Friday")),
                    judge_says({"the vote moved": said_it}))
  m = row["mentions"][0]
  check(m["speaker"] == "Denise" and m["quote"] == "the vote is Friday",
        f"who said it and what they said must come from the transcript: {m}")
  check(m["new_hearers"] == ["Denise"], f"Denise hadn't been told, so she has now heard it: {m}")
  asked.clear()
  trace.check(convo(6, "Denise", "Rachel"), judge_says({}))
  check(len(asked) == 1, f"someone who heard it in conversation can pass it on: {asked}")
  asked.clear()
  row = trace.check(convo(7, "Denise", "Maya", ("x", "y")), judge_says({"the vote moved": said_it}))
  check(row["mentions"][0]["new_hearers"] == [], "both already knew, so nobody new heard it")
  asked.clear()
  row = trace.check(convo(8, "Maya", "Tom"), lambda text, transcript, n: None)
  check(row["failed"] == ["w"] and not row["checked"] and not row["mentions"],
        f"no valid answer is unchecked, not a no: {row}")
  check(trace.check({"step": 9, "speakers": ["Maya", "Tom"], "utterances": []}, judge_says({})) is None,
        "an empty transcript is not a conversation")

  # A fork only keeps what its agents' saved memory can have heard.
  trace.forget_unsaved(6)
  rows = whisper_plan.read(trace.path)
  check([r["step"] for r in rows] == [4, 5], f"rows from the fork's step on must go: {rows}")
  asked.clear()
  trace.check(convo(9, "Denise", "Luis"), judge_says({}))
  check(len(asked) == 1, "what was heard before the fork still counts")
  trace.forget_unsaved(5)
  asked.clear()
  trace.check(convo(9, "Denise", "Luis"), judge_says({}))
  check(not asked, "what was heard after the fork point no longer counts")

  # The check above finds its lines by splitting on newlines, so a turn with one in
  # it must not shift the numbering.
  asked.clear()
  rs = server(os.path.join(tmp, "newline"))
  add(rs.whispers.path, "n", ["Maya"], "x")
  whisper_plan.append(rs.whispers.path, [{"op": "sent", "id": "n", "agent": "Maya", "step": 1, "time": "t"}])
  WhisperTrace(os.path.join(tmp, "newline"), rs.whispers).check(
    convo(2, "Maya", "Tom", ("two\nlines", "next")), judge_says({}))
  check(asked[0][1] == "1. Maya: two lines\n2. Tom: next", f"one line per turn: {asked[0][1]!r}")

  # -- In the real step loop: order, billing, and it can't end a run ----------------
  asked.clear()
  folder = os.path.join(tmp, "trace-loop")
  rs = server(folder)
  rs.experiment_logger.new_conversations = []
  rs.whisper_trace = WhisperTrace(folder, rs.whispers)
  add(rs.whispers.path, "due", ["Maya"], "due at step 1", game_time(1))
  billed = []
  reverie.run_gpt_prompt_whisper_mention = lambda text, transcript, n: (
    billed.append(dict(reverie.usage.context)) or asked.append(text) or {"came_up": False})
  talks = {1: "same step as the whisper", 2: "the step after"}

  def talk():
    if rs.step in talks and rs.personas["Maya"].scratch.curr_time:
      text = talks.pop(rs.step)
      rs.experiment_logger.new_conversations.append(convo(rs.step, "Maya", "Tom", (text, "ok")))

  rs.personas["Maya"].on_move = talk
  before = dict(reverie.usage.context)
  run(rs, 3)
  check(len(asked) == 1,
        f"a conversation in the same step as a whisper happened first, so only the "
        f"later one can carry it: {asked}")
  check(billed and billed[0]["source"] == "whisper_trace" and billed[0]["persona"] is None,
        f"trace calls must be billed apart from the step: {billed}")
  check(reverie.usage.context["source"] == "step" or reverie.usage.context == before,
        "the usage context must be put back")
  check(not rs.experiment_logger.new_conversations, "checked conversations must not be asked about twice")

  def broken(text, transcript, n):
    raise RuntimeError("the judge broke")

  reverie.run_gpt_prompt_whisper_mention = broken
  talks.update({rs.step: "another"})
  run(rs, 2)
  check(rs.step == 5, f"a broken trace must not end the run, stopped at {rs.step}")

  # -- An edit saved as the original starts going out tells nobody twice -----------
  heard.clear()
  rs = server(os.path.join(tmp, "edit-race"))
  plan = rs.whispers.path
  add(plan, "orig", ["Maya", "Tom"], "old text")
  whisper_plan.append(plan, [{"op": "started", "id": "orig", "time": "t"},
                             {"op": "sent", "id": "orig", "agent": "Maya"},
                             {"op": "cancel", "id": "orig"},
                             {"op": "add", "id": "edit", "text": "new text", "targets": ["Maya", "Tom"],
                              "at": None, "replaces": "orig"}])
  rs.deliver_due_whispers()
  check([h[1:] for h in heard] == [("Tom", "new text")],
        f"whoever got the original must not also get the edit: {heard}")

  # -- Logging can fail without the agent being told twice -----------------------
  heard.clear()
  rs = server(os.path.join(tmp, "log-fails"))
  add(rs.whispers.path, "l", ["Maya"], "logged or not")

  def no_log(*args, **kwargs):
    raise OSError("disk full")

  rs.experiment_logger.log_event = no_log
  rs.deliver_due_whispers()
  rs.deliver_due_whispers()
  check(len(heard) == 1, f"a whisper whose log failed must not be delivered again: {heard}")

  # -- An error mid-delivery still puts the billing context back --------------------
  rs = server(os.path.join(tmp, "context"))
  add(rs.whispers.path, "c", ["Maya"], "x")
  before = dict(reverie.usage.context)

  def broken_record(row):
    raise OSError("disk full")

  rs.whispers.record = broken_record
  try:
    rs.deliver_due_whispers()
  except OSError:
    pass
  check(reverie.usage.context == before, f"context must be restored after an error: {reverie.usage.context}")

  # -- save() marks the plan, but creates no file for runs without one ----------
  empty = whisper_plan.Plan(os.path.join(tmp, "no-plan"))
  empty.mark_saved(5)
  check(not os.path.exists(empty.path), "a run with no whispers must not grow a plan file")

  # -- A half-written row is not read ------------------------------------------
  path = os.path.join(tmp, "partial.jsonl")
  with open(path, "w") as f:
    f.write('{"op": "add", "id": "ok", "text": "x", "targets": []}\n{"op": "add", "id": "cu')
  check([r["id"] for r in whisper_plan.read(path)] == ["ok"],
        "a row still being written must be skipped, not crash the reader")

# -- The mention judge's answers are checked, not repaired -----------------------
parse = run_gpt_prompt.parse_whisper_mention
check(parse({"came_up": False}, 3) == {"came_up": False}, "a no needs nothing else")
check(parse({"came_up": True, "line": 3, "how": " he raised it "}, 3)
      == {"came_up": True, "line": 3, "how": "he raised it"}, "a yes keeps its line and how")
for bad in [{}, [], None, {"came_up": "yes"}, {"came_up": 1},
            {"came_up": True}, {"came_up": True, "line": 1},
            {"came_up": True, "line": 0, "how": "x"}, {"came_up": True, "line": 4, "how": "x"},
            {"came_up": True, "line": 1.0, "how": "x"}, {"came_up": True, "line": True, "how": "x"},
            {"came_up": True, "line": "1", "how": "x"}, {"came_up": True, "line": 1, "how": "  "}]:
  try:
    parse(bad, 3)
    check(False, f"an invalid answer must be refused, not repaired: {bad}")
  except (ValueError, TypeError):
    pass
source = inspect.getsource(run_gpt_prompt.run_gpt_prompt_whisper_mention)
template = re.search(r'"(persona/prompt_template/[^"]+)"', source).group(1)
prompt = run_gpt_prompt.generate_prompt(["the vote moved", "1. A: hi"], template)
check('"the vote moved"' in prompt and "1. A: hi" in prompt and "came_up" in prompt,
      f"{template} must carry the information, the transcript and the answer shape")
check("same subject" in prompt,
      f"{template} must rule out a shared subject: nearly every conversation here is "
      "about the datacenter, and without it the judge flags most of them")
check("temperature=0" in source, "a measurement has to give the same answer twice")

# -- A yes is checked against the lines it pointed at ------------------------------
# It also marks whoever heard it as knowing the whisper, so a false one draws a path
# that never happened. In a real run one false yes did exactly that.
answers, calls = [], []


def scripted(prompt, example, instruction, repeat, fail_safe, validate, clean_up,
             verbose=False, temperature=None):
  calls.append((prompt, temperature))
  answer = answers.pop(0)
  if answer is False:
    return False
  check(validate(answer), f"expected a valid scripted answer: {answer}")
  return clean_up(answer)


real_safe = run_gpt_prompt.ChatGPT_safe_generate_response
run_gpt_prompt.ChatGPT_safe_generate_response = scripted
ask = run_gpt_prompt.run_gpt_prompt_whisper_mention
lines = "\n".join(f"{i}. A: line{i}" for i in range(1, 9))
yes = {"came_up": True, "line": 4, "how": "raised it"}
for script, want, n_calls in [
    ([{"came_up": False}], {"came_up": False}, 1),
    ([yes, {"carries": True}], {"came_up": True, "line": 4, "how": "raised it"}, 2),
    ([yes, {"carries": False}], {"came_up": False}, 2),
    ([yes, False], None, 2),
    ([False], None, 1)]:
  answers[:] = list(script)
  calls.clear()
  got = ask("the vote moved", lines, 8)
  check(got == want and len(calls) == n_calls,
        f"{script} should give {want} in {n_calls} calls, got {got} in {len(calls)}")
answers[:] = [yes, {"carries": True}]
calls.clear()
ask("the vote moved", lines, 8)
seen = calls[1][0]
check(all(f"line{i}" in seen for i in (2, 3, 4, 5, 6)) and "line1" not in seen and "line7" not in seen,
      f"the check should see two turns either side of the line: {seen}")
check(calls[1][1] == 0, "the check is a measurement too, so temperature 0")
answers[:] = [{"carries": False}]
check(run_gpt_prompt.run_gpt_prompt_whisper_mention_check("x", lines, 1) is False,
      "the check's no must not read as the safe call running out of tries")
answers[:] = [False]
check(run_gpt_prompt.run_gpt_prompt_whisper_mention_check("x", lines, 1) is None,
      "running out of tries must not read as a no")
run_gpt_prompt.ChatGPT_safe_generate_response = real_safe
source = inspect.getsource(run_gpt_prompt.run_gpt_prompt_whisper_mention_check)
template = re.search(r'"(persona/prompt_template/[^"]+)"', source).group(1)
prompt = run_gpt_prompt.generate_prompt(["the vote moved", "4. A: x"], template)
check("the vote moved" in prompt and "4. A: x" in prompt and "carries" in prompt and "not enough" in prompt,
      f"{template} must carry the information, the lines, and rule out a shared subject")

# -- The trace watches and doesn't touch -----------------------------------------
tree = ast.parse(inspect.getsource(whisper_trace))
names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {
  n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
touched = names & {"a_mem", "scratch", "new_retrieve", "add_thought", "add_event", "add_chat", "personas"}
check(not touched, f"whisper_trace must not reach into agents: {touched}")
method = next(n for n in ast.walk(ast.parse(inspect.getsource(reverie.ReverieServer)))
              if isinstance(n, ast.FunctionDef) and n.name == "trace_whispers")
names = {n.attr for n in ast.walk(method) if isinstance(n, ast.Attribute)}
check(not names & {"a_mem", "scratch", "personas"}, f"trace_whispers must not reach into agents: {names}")

# -- Only real thoughts become memories ----------------------------------------
replies = []
run_gpt_prompt.safe_generate_response = (
  lambda prompt, param, repeat, fail_safe, validate, clean_up, verbose=False:
  clean_up(replies[0]) if validate(replies[0]) else fail_safe)
run_gpt_prompt.debug = False
persona = types.SimpleNamespace(scratch=types.SimpleNamespace(name="Maya Okonkwo"))
for reply, expected in [
    ('Maya knows the vote moved."', "Maya knows the vote moved."),
    ('"Maya knows the vote moved."', "Maya knows the vote moved."),
    ('Maya heard the mayor said "no" at the meeting."', 'Maya heard the mayor said "no" at the meeting.'),
    ('Maya heard the vote moved."\nStatement: "Maya heard', "Maya heard the vote moved."),
    ('Maya heard "no" from them."\nText: "x"\nStatement: "y"', 'Maya heard "no" from them.'),
    ('Maya heard the mayor said "no"', 'Maya heard the mayor said "no"'),
    ("TOKEN LIMIT EXCEEDED", run_gpt_prompt.WHISPER_THOUGHT_FAILED),
    ('""', run_gpt_prompt.WHISPER_THOUGHT_FAILED),
    ("   ", run_gpt_prompt.WHISPER_THOUGHT_FAILED)]:
  replies[:] = [reply]
  got = run_gpt_prompt.run_gpt_prompt_generate_whisper_inner_thought(persona, "x")[0]
  check(got == expected, f"whisper thought from {reply!r} was {got!r}, not {expected!r}")

# -- News stays about whoever did it --------------------------------------------
# The path comes from the code, so this can't keep passing on a template the
# whisper no longer uses. Examples use the agent's own name because a made-up
# one leaked into real memories when the prompt was first measured.
source = inspect.getsource(run_gpt_prompt.run_gpt_prompt_generate_whisper_inner_thought)
template = re.search(r'"(persona/prompt_template/[^"]+)"', source).group(1)
prompt = run_gpt_prompt.generate_prompt(["Zed Test", "The council met"], template)
check("Zed Test heard that the mayor" in prompt,
      f"{template} must show news staying about who did it, not the agent")
check("Zed Test left the spare key" in prompt,
      f"{template} must show that 'you' means the agent")
check(prompt.rstrip().endswith('Text: "The council met"\nStatement: "'),
      f"{template} must end on the open quote its clean-up expects")
check(re.search(r'"max_tokens": (\d+)', source) and
      int(re.search(r'"max_tokens": (\d+)', source).group(1)) >= 1000,
      "a 1000-character whisper must fit in the thought without being cut off")

from persona.cognitive_modules import converse

converse.generate_inner_thought = lambda persona, whisper: run_gpt_prompt.WHISPER_THOUGHT_FAILED
stored = []
memory = types.SimpleNamespace(add_thought=lambda *args: stored.append(args))
try:
  converse.load_history_via_whisper(
    {"Maya": types.SimpleNamespace(a_mem=memory, scratch=types.SimpleNamespace(curr_time=START))},
    [["Maya", "x"]])
  check(False, "a failed thought must raise so the whisper is marked failed")
except RuntimeError:
  pass
check(not stored, "a failed thought must never be stored as a memory")

for p in problems:
  print(p)
print(f"whisper plan rules checked, {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
