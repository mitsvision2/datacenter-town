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
