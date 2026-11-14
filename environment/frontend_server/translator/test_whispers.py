import json
import os
import tempfile
from pathlib import Path

from django.test import Client, SimpleTestCase

from translator import dashboard
from translator.dashboard import whisper_plan

NAMES = ["Maya Okonkwo", "Luis Hernandez", "Denise Brooks", "Tom Whitaker"]


class WhisperApiTests(SimpleTestCase):
  """The dashboard side of a planned whisper, against a real folder layout and a
  live-looking state file. The pid is this test's own, so it reads as running."""

  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    previous = os.getcwd()
    os.chdir(self.temp.name)
    self.addCleanup(os.chdir, previous)
    self.sim = "stg-test"
    Path(f"storage/{self.sim}/reverie").mkdir(parents=True)
    Path(f"storage/{self.sim}/reverie/meta.json").write_text(json.dumps({
      "persona_names": NAMES, "step": 720, "fork_sim_code": "base",
      "curr_time": "February 13, 2023, 02:00:00", "sec_per_step": 10}))
    Path("temp_storage/dashboard").mkdir(parents=True)
    self.write_state()
    self.client = Client()
    self.plan = whisper_plan.path_for(f"storage/{self.sim}")

  def write_state(self, **changes):
    Path(dashboard.STATE_FILE).write_text(json.dumps({
      "sim_code": self.sim, "fork_sim_code": "base", "pid": os.getpid(),
      "status": "idle", "run_left": 0, "step": 720, "sec_per_step": 10,
      "curr_time": "February 13, 2023, 02:00:00", "persona_order": NAMES,
      "personas": {}, **changes}))

  def post(self, *whispers, sim=None):
    return self.client.post(
      "/dashboard/whispers/",
      json.dumps({"sim": sim or self.sim, "whispers": list(whispers)}),
      content_type="application/json")

  def state_whispers(self):
    return self.client.get("/dashboard/state/").json()["whispers"]

  def test_two_whispers_to_different_people_in_one_request(self):
    res = self.post(
      {"targets": NAMES[:3], "text": "The vote moved to Friday", "at": "2023-02-13T14:00"},
      {"targets": NAMES[3:], "text": "The site was surveyed", "at": "2023-02-13T14:00"})
    self.assertEqual(res.status_code, 200)
    first, second = self.state_whispers()
    self.assertEqual(first["targets"], NAMES[:3])
    self.assertEqual(second["targets"], NAMES[3:])
    self.assertEqual(first["at"], "February 13, 2023, 14:00:00")
    self.assertEqual(first["status"], "scheduled")
    self.assertEqual(first["left"], NAMES[:3])

  def test_now_has_no_time(self):
    self.post({"targets": NAMES[:1], "text": "Hello", "at": None})
    self.assertIsNone(self.state_whispers()[0]["at"])

  def test_one_bad_whisper_plans_none_of_them(self):
    res = self.post({"targets": NAMES[:1], "text": "Fine", "at": None},
                    {"targets": [], "text": "Nobody hears this", "at": None})
    self.assertEqual(res.status_code, 400)
    self.assertIn("Whisper 2: pick at least one person", res.json()["error"])
    self.assertEqual(self.state_whispers(), [])

  def test_what_gets_rejected(self):
    cases = [
      ({"targets": [], "text": "x", "at": None}, "Pick at least one person"),
      ({"targets": NAMES[:1], "text": "   ", "at": None}, "Write what they should hear"),
      ({"targets": ["Nobody Here"], "text": "x", "at": None}, "isn't in this run"),
      ({"targets": NAMES[:1], "text": "x" * 1001, "at": None}, "under 1000"),
      ({"targets": NAMES[:1], "text": "x", "at": ""}, "Pick a date and time"),
      ({"targets": NAMES[:1], "text": "x", "at": "soon"}, "Pick a date and time"),
      ({"targets": NAMES[:1], "text": "x", "at": "2023-02-13T01:59"}, "has passed"),
      ({"targets": NAMES[:1], "text": "x", "at": "2023-02-13T14:00+00:00"}, "Pick a date and time"),
      ("not a whisper", "couldn't be read"),
    ]
    for item, message in cases:
      with self.subTest(item=item):
        res = self.post(item)
        self.assertEqual(res.status_code, 400)
        self.assertIn(message, res.json()["error"])
    self.assertFalse(os.path.exists(self.plan))

  def test_the_current_minute_is_still_allowed(self):
    # The picker has no seconds, so "now" at 02:00:30 is written as 02:00.
    self.write_state(curr_time="February 13, 2023, 02:00:30")
    self.assertEqual(self.post({"targets": NAMES[:1], "text": "x",
                                "at": "2023-02-13T02:00"}).status_code, 200)

  def test_text_is_stored_on_one_line(self):
    self.post({"targets": NAMES[:1], "text": " Vote \n moved\tto Friday ", "at": None})
    self.assertEqual(self.state_whispers()[0]["text"], "Vote moved to Friday")

  def test_needs_a_loaded_run(self):
    self.write_state(status="finished")
    self.assertEqual(self.post({"targets": NAMES[:1], "text": "x", "at": None}).status_code, 409)
    os.remove(dashboard.STATE_FILE)
    self.assertEqual(self.post({"targets": NAMES[:1], "text": "x", "at": None}).status_code, 409)

  def test_refuses_a_page_looking_at_another_run(self):
    res = self.post({"targets": NAMES[:1], "text": "x", "at": None}, sim="stg-other")
    self.assertEqual(res.status_code, 409)
    self.assertIn("stg-test", res.json()["error"])

  def test_works_while_a_run_is_going(self):
    self.write_state(status="running", run_left=100)
    self.assertEqual(self.post({"targets": NAMES[:1], "text": "x", "at": None}).status_code, 200)

  def test_cancel(self):
    self.post({"targets": NAMES[:2], "text": "x", "at": "2023-02-13T14:00"})
    w = self.state_whispers()[0]
    res = self.client.post(f"/dashboard/whispers/{w['id']}/cancel/")
    self.assertEqual(res.status_code, 200)
    w = self.state_whispers()[0]
    self.assertEqual(w["status"], "cancelled")
    self.assertEqual(w["left"], [])
    self.assertEqual(self.client.post("/dashboard/whispers/nope/cancel/").status_code, 404)

  def test_a_sent_whisper_cannot_be_cancelled(self):
    self.post({"targets": NAMES[:1], "text": "x", "at": None})
    w = self.state_whispers()[0]
    whisper_plan.append(self.plan, [{"op": "sent", "id": w["id"], "agent": NAMES[0]}])
    self.assertEqual(self.client.post(f"/dashboard/whispers/{w['id']}/cancel/").status_code, 409)

  def test_an_unreadable_request_is_a_400(self):
    for body in ("{not json", "[1, 2]", '"text"'):
      res = self.client.post("/dashboard/whispers/", body, content_type="application/json")
      self.assertEqual(res.status_code, 400, body)

  def test_editing_replaces_the_original(self):
    self.post({"targets": NAMES[:1], "text": "Typo", "at": "2023-02-13T14:00"})
    old = self.state_whispers()[0]
    self.post({"targets": NAMES[:2], "text": "Fixed", "at": "2023-02-13T15:00", "replaces": old["id"]})
    before, after = self.state_whispers()
    self.assertEqual(before["status"], "cancelled")
    self.assertEqual((after["text"], after["status"]), ("Fixed", "scheduled"))
    self.assertEqual(after["replaces"], old["id"])

  def test_cannot_replace_one_already_going_out(self):
    self.post({"targets": NAMES[:2], "text": "x", "at": None})
    w = self.state_whispers()[0]
    whisper_plan.append(self.plan, [{"op": "sent", "id": w["id"], "agent": NAMES[0]}])
    res = self.post({"targets": NAMES[:2], "text": "y", "at": None, "replaces": w["id"]})
    self.assertEqual(res.status_code, 400)
    self.assertEqual(len(self.state_whispers()), 1)

  def test_two_drafts_cannot_replace_the_same_whisper(self):
    self.post({"targets": NAMES[:1], "text": "x", "at": "2023-02-13T14:00"})
    old = self.state_whispers()[0]
    edit = {"targets": NAMES[:1], "text": "y", "at": "2023-02-13T14:00", "replaces": old["id"]}
    self.assertEqual(self.post(edit, edit).status_code, 400)
    self.assertEqual([w["status"] for w in self.state_whispers()], ["scheduled"])

  def test_cannot_edit_once_delivery_has_begun(self):
    # Before the first recipient has been recorded, so nothing else shows it yet.
    self.post({"targets": NAMES[:2], "text": "x", "at": None})
    w = self.state_whispers()[0]
    whisper_plan.append(self.plan, [{"op": "started", "id": w["id"], "time": "t"}])
    self.assertEqual(self.state_whispers()[0]["status"], "sending")
    res = self.post({"targets": NAMES[:2], "text": "y", "at": None, "replaces": w["id"]})
    self.assertEqual(res.status_code, 400)

  def test_retrying_a_failed_whisper_replaces_it(self):
    self.post({"targets": NAMES[:1], "text": "x", "at": None})
    w = self.state_whispers()[0]
    whisper_plan.append(self.plan, [{"op": "failed", "id": w["id"], "agent": NAMES[0], "error": "boom"}])
    self.assertEqual(self.state_whispers()[0]["status"], "failed")
    self.assertEqual(self.post({"targets": NAMES[:1], "text": "x", "at": None,
                                "replaces": w["id"]}).status_code, 200)
    self.assertEqual([x["status"] for x in self.state_whispers()], ["cancelled", "scheduled"])

  def test_state_reports_who_received_it_and_where_it_came_up(self):
    self.post({"targets": NAMES[:1], "text": "x", "at": None})
    w = self.state_whispers()[0]
    whisper_plan.append(self.plan, [{"op": "sent", "id": w["id"], "agent": NAMES[0],
                                     "step": 700, "time": "t"}])
    self.assertEqual(self.state_whispers()[0]["received"], {NAMES[0]: {"step": 700, "time": "t"}})
    row = {"step": 710, "time": "t", "speakers": NAMES[:2], "checked": [w["id"]], "failed": [],
           "mentions": [{"whisper_id": w["id"], "speaker": NAMES[0], "quote": "q", "how": "h",
                         "new_hearers": [NAMES[1]]}]}
    whisper_plan.append(f"storage/{self.sim}/experiment/whisper_mentions.jsonl", [row])
    for body in (self.client.get("/dashboard/state/").json(),
                 self.client.get(f"/dashboard/run/{self.sim}/").json()):
      self.assertEqual(body["mentions"][0]["mentions"][0]["quote"], "q")

  def test_no_mentions_file_is_fine(self):
    self.assertEqual(self.client.get("/dashboard/state/").json()["mentions"], [])

  def test_saved_run_view_shows_its_plan(self):
    self.post({"targets": NAMES[:1], "text": "x", "at": "2023-02-13T14:00"})
    res = self.client.get(f"/dashboard/run/{self.sim}/").json()
    self.assertEqual(res["whispers"][0]["text"], "x")
