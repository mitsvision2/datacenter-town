import json
import os
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from translator import activity_timeline as tl


class TimelineTests(SimpleTestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    previous = os.getcwd()
    os.chdir(self.temp.name)
    self.addCleanup(os.chdir, previous)
    tl._cache.clear()
    self.folder = Path("storage/test/movement")
    self.folder.mkdir(parents=True)

  def move(self, step, where, action="reading"):
    (self.folder / f"{step}.json").write_text(json.dumps({"persona": {
      "Maya": {"description": f"{action} @ the Ville:{where}:room", "movement": [1, 1]}}}))

  def test_samples_merge_into_stays_and_the_last_stretches_to_now(self):
    for step, where in [(0, "Cafe"), (6, "Cafe"), (12, "Park"), (13, "Store")]:
      self.move(step, where)
    r = tl.activity_timeline("test", every=6)
    self.assertEqual(r["agents"]["Maya"], [[0, 6, "Cafe", "reading"], [12, 13, "Park", "reading"]])

  def test_a_live_run_only_reads_new_steps(self):
    self.move(0, "Cafe")
    tl.activity_timeline("test", every=6)
    self.move(6, "Park", "walking")
    r = tl.activity_timeline("test", every=6)
    self.assertEqual(r["agents"]["Maya"], [[0, 0, "Cafe", "reading"], [6, 6, "Park", "walking"]])

  def test_no_movement_folder_is_empty(self):
    self.assertEqual(tl.activity_timeline("nothing")["agents"], {})

  def test_place_is_the_sector(self):
    self.assertEqual(tl.place_of("the Ville:Hobbs Cafe:cafe:seating"), "Hobbs Cafe")
    self.assertEqual(tl.place_of("home"), "home")

  def test_a_relaunched_run_with_the_same_name_starts_over(self):
    for step in (0, 6, 12):
      self.move(step, "Cafe")
    tl.activity_timeline("test", every=6)
    for f in self.folder.iterdir():
      f.unlink()
    self.folder.rmdir()
    self.folder.mkdir()
    self.move(0, "Park")
    r = tl.activity_timeline("test", every=6)
    self.assertEqual(r["agents"]["Maya"], [[0, 0, "Park", "reading"]])

  def test_an_unreadable_step_is_read_again_later(self):
    self.move(0, "Cafe")
    (self.folder / "6.json").write_text("{half")
    self.move(12, "Park")
    tl.activity_timeline("test", every=6)
    self.move(6, "Store")
    r = tl.activity_timeline("test", every=6)
    self.assertEqual([s[2] for s in r["agents"]["Maya"]], ["Cafe", "Store", "Park"])


class DayTests(SimpleTestCase):
  def setUp(self):
    from translator import dashboard
    dashboard._day_cache.clear()
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    previous = os.getcwd()
    os.chdir(self.temp.name)
    self.addCleanup(os.chdir, previous)
    tl._cache.clear()
    folder = Path("storage/test/movement")
    folder.mkdir(parents=True)
    Path("storage/test/reverie").mkdir(parents=True)
    Path("storage/test/reverie/meta.json").write_text(json.dumps({"persona_names": ["Maya", "Luis"]}))
    # A long cafe stay, a short walk, then the park.
    for step in range(0, 120, 6):
      where = "Cafe" if step < 60 else "Road" if step == 60 else "Park"
      (folder / f"{step}.json").write_text(json.dumps({"meta": {"curr_time": f"t{step}"}, "persona": {
        "Maya": {"description": f"being at {where} @ the Ville:{where}:x", "movement": [step, 1], "pronunciatio": "☕"},
        "Luis": {"description": "idle @ the Ville:Home:x", "movement": [5, 5], "pronunciatio": "💤"}}}))

  def test_stays_long_enough_to_count_with_everyone_where_they_stood(self):
    from translator import dashboard
    stays = dashboard.agent_day("test", "Maya")["stays"]
    self.assertEqual([s["place"] for s in stays], ["Cafe", "Park"])  # the short walk is dropped
    self.assertEqual(stays[0]["step"], 30)  # a little after arriving
    self.assertEqual(stays[0]["people"]["Luis"][:3], [5, 5, "💤"])
    self.assertEqual(stays[0]["people"]["Maya"][3:], ["r", False])  # facing the way they last moved
    self.assertEqual(stays[0]["time"], "t30")

  def test_a_stay_with_a_conversation_is_shown_at_it_with_the_two_facing(self):
    from translator import dashboard
    Path("storage/test/experiment").mkdir(parents=True)
    Path("storage/test/experiment/conversations.jsonl").write_text(json.dumps(
      {"step": 84, "speakers": ["Maya", "Luis"], "utterances": [["Maya", "hi"]]}) + "\n")
    move = Path("storage/test/movement/84.json")
    d = json.loads(move.read_text())
    for n in d["persona"]:
      d["persona"][n]["chat"] = [["Maya", "hi"]]
    move.write_text(json.dumps(d))
    park = dashboard.agent_day("test", "Maya")["stays"][1]
    self.assertEqual((park["step"], park["convo"]["speakers"]), (84, ["Maya", "Luis"]))
    self.assertEqual(park["people"]["Luis"][3], "r")  # faces the person they're talking to

  def test_the_runs_asleep_flag_wins_over_the_activity_text(self):
    from translator import dashboard
    # A step just before, one tile away: without the flag she would show as walking.
    d29 = json.loads(Path("storage/test/movement/30.json").read_text())
    d29["persona"]["Maya"]["movement"] = [29, 1]
    Path("storage/test/movement/29.json").write_text(json.dumps(d29))
    self.assertTrue(dashboard.agent_day("test", "Maya")["stays"][0]["people"]["Maya"][4])
    dashboard._day_cache.clear()
    for step in (30, 36):
      move = Path(f"storage/test/movement/{step}.json")
      d = json.loads(move.read_text())
      d["persona"]["Maya"]["asleep"] = True  # the probe's rule says asleep, though the text doesn't
      move.write_text(json.dumps(d))
    self.assertFalse(dashboard.agent_day("test", "Maya")["stays"][0]["people"]["Maya"][4])

  def test_only_agents_of_the_run(self):
    from translator import dashboard
    self.assertEqual(dashboard.dashboard_day(type("R", (), {"GET": {"agent": "Nobody"}})(), "test").status_code, 404)
    self.assertEqual(dashboard.dashboard_day(type("R", (), {"GET": {"agent": "Maya"}})(), "../x").status_code, 404)
