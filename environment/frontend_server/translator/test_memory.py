import json
import os
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from translator import dashboard


class MemoryTests(SimpleTestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    previous = os.getcwd()
    os.chdir(self.temp.name)
    self.addCleanup(os.chdir, previous)
    dashboard._nodes_cache.clear()
    mem = Path("storage/test/personas/Maya/bootstrap_memory/associative_memory")
    mem.mkdir(parents=True)
    node = lambda i, kind, filling=None: {"node_count": i, "type": kind, "created": f"2023-02-13 0{i}:00:00",
                                          "description": f"{kind} {i}", "poignancy": i, "filling": filling}
    (mem / "nodes.json").write_text(json.dumps({
      "node_1": node(1, "event"),
      "node_2": node(2, "chat", [["Maya", "hi"], ["Rachel", "hello"]]),
      "node_3": node(3, "thought", ["node_1"]),
      "node_4": node(4, "thought", ["node_2"]),
    }))
    Path("storage/test/experiment").mkdir(parents=True)
    rows = [{"name": "Maya", "step": 10, "score": 40, "evidence": ["node_1", "node_3"],
             "selection": {"memories": [{"id": "node_1", "cos": 0.61}, {"id": "node_3", "cos": 0.48}],
                           "quoted": [{"cos": 0.22, "created": "t"}]}},
            {"name": "Maya", "step": 20, "score": None},
            {"name": "Rachel", "step": 10, "score": 70, "evidence": ["node_9"]}]
    Path("storage/test/experiment/opinions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))

  def test_kinds_newest_first_and_chat_lines(self):
    r = dashboard.agent_memory("test", "Maya")
    self.assertEqual([(n["id"], n["kind"]) for n in r["nodes"]],
                     [("node_4", "thought"), ("node_3", "reflection"), ("node_2", "chat"), ("node_1", "event")])
    self.assertEqual(r["nodes"][1]["filling"], ["node_1"])
    self.assertEqual(r["nodes"][2]["lines"], [["Maya", "hi"], ["Rachel", "hello"]])
    self.assertEqual(r["nodes"][2]["filling"], [])

  def test_only_this_agents_readings_with_evidence(self):
    r = dashboard.agent_memory("test", "Maya")
    self.assertEqual([(x["step"], x["evidence"]) for x in r["readings"]], [(10, ["node_1", "node_3"])])

  def test_each_reading_carries_its_evidence_cosines(self):
    r = dashboard.agent_memory("test", "Maya")["readings"][0]
    self.assertEqual(r["cos"], {"node_1": 0.61, "node_3": 0.48})
    self.assertEqual(r["quoted"], [0.22])

  def test_the_endpoint_only_serves_this_runs_agents(self):
    from django.test import RequestFactory
    get = lambda agent: dashboard.dashboard_memory(RequestFactory().get("/", {"agent": agent}), "test")
    self.assertEqual(get("Maya").status_code, 200)
    self.assertEqual(get("../../etc").status_code, 404)
    self.assertEqual(get("Nobody").status_code, 404)


class ReflectionTests(SimpleTestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    previous = os.getcwd()
    os.chdir(self.temp.name)
    self.addCleanup(os.chdir, previous)
    dashboard._nodes_cache.clear()
    dashboard._jsonl_cache.clear()
    mem = Path("storage/test/personas/Maya/bootstrap_memory/associative_memory")
    mem.mkdir(parents=True)
    node = lambda i, kind, filling=None: {"node_count": i, "type": kind, "created": f"2023-02-13 0{i}:00:00",
                                          "description": f"{kind} {i}", "poignancy": i, "filling": filling}
    (mem / "nodes.json").write_text(json.dumps({
      "node_1": node(1, "event"),
      "node_2": node(2, "thought"),               # a whisper as it landed
      "node_3": node(3, "chat", [["Maya", "hi"]]),
      "node_4": node(4, "thought", ["node_3"]),   # after a conversation: not a reflection
      "node_5": node(5, "thought", ["node_1", "node_2"]),
      "node_6": node(6, "thought", ["node_5", "node_4"]),
    }))
    Path("storage/test/reverie").mkdir(parents=True)
    Path("storage/test/reverie/meta.json").write_text(json.dumps({"persona_names": ["Maya"], "curr_time": "t"}))
    Path("storage/test/experiment").mkdir(parents=True)
    Path("storage/test/experiment/whispers.jsonl").write_text("".join(json.dumps(r) + "\n" for r in [
      {"op": "add", "id": "w1", "text": "x", "targets": ["Maya"], "at": None},
      {"op": "sent", "id": "w1", "agent": "Maya", "step": 1, "time": "t", "node_id": "node_2"}]))
    rows = [{"name": "Maya", "step": 10, "score": 40, "evidence": ["node_6", "node_1"]},
            {"name": "Maya", "step": 20, "score": 45, "evidence": ["node_6"]}]
    Path("storage/test/experiment/opinions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))

  def test_each_reflection_with_its_sources_down_to_whispers_and_chats(self):
    r = json.loads(dashboard.dashboard_reflections(None, "test").content)["reflections"]
    self.assertEqual([(x["id"], x["cited"]) for x in r], [("node_6", 2), ("node_5", 0)])
    top = r[0]
    self.assertEqual([(c["id"], c["kind"]) for c in top["children"]], [("node_5", "reflection"), ("node_4", "thought")])
    self.assertEqual([(c["id"], c["kind"]) for c in top["children"][0]["children"]], [("node_2", "whisper"), ("node_1", "event")])
    self.assertEqual(top["children"][0]["children"][0]["whisper_id"], "w1")
    self.assertEqual(top["children"][1]["children"][0]["lines"], [["Maya", "hi"]])

  def test_unknown_run_is_404(self):
    self.assertEqual(dashboard.dashboard_reflections(None, "nope").status_code, 404)
    self.assertEqual(dashboard.dashboard_reflections(None, "../x").status_code, 404)
