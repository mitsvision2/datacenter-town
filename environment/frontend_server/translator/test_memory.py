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
    rows = [{"name": "Maya", "step": 10, "score": 40, "evidence": ["node_1", "node_3"]},
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

  def test_the_endpoint_only_serves_this_runs_agents(self):
    from django.test import RequestFactory
    get = lambda agent: dashboard.dashboard_memory(RequestFactory().get("/", {"agent": agent}), "test")
    self.assertEqual(get("Maya").status_code, 200)
    self.assertEqual(get("../../etc").status_code, 404)
    self.assertEqual(get("Nobody").status_code, 404)
