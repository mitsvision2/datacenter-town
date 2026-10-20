"""Rubric contract and observer regression tests. No external API calls."""
import datetime
import json
import os
import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                      "reverie", "backend_server"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)

import opinion_probe
from persona.prompt_template import gpt_structure, run_gpt_prompt as prompts
import reverie


class RubricTests(unittest.TestCase):
  def setUp(self):
    quiet = patch.object(prompts, "debug", False)
    quiet.start()
    self.addCleanup(quiet.stop)

  def rating(self, score=50, category="neutral_mixed", **extra):
    return {"category": category, "score": score,
            "rationale": "The agent explicitly states a balanced view.", **extra}

  def persona(self):
    return NS(scratch=NS(name="Rachel Nguyen", age=36,
                        curr_time=datetime.datetime(2023, 2, 13, 12),
                        act_description="working"))

  def test_all_band_boundaries(self):
    expected = [(0, 19, "very_strong_opposition"),
                (20, 39, "moderate_opposition"), (40, 49, "slight_opposition"),
                (50, 50, "neutral_mixed"), (51, 60, "slight_support"),
                (61, 80, "moderate_support"), (81, 100, "very_strong_support")]
    for low, high, category in expected:
      for score in {low, high}:
        with self.subTest(score=score):
          r = prompts.parse_rubric_stance(self.rating(score, category))
          self.assertEqual((r["score"], r["category"]), (score, category))
          self.assertEqual(r["scoring_version"], "rubric_v1")

  def test_runtime_prompt_uses_the_exact_validated_bands(self):
    with patch.object(gpt_structure, "ChatGPT_request",
                      return_value=json.dumps({"output": self.rating()})):
      _, diagnostics = prompts.run_gpt_prompt_datacenter_stance(self.persona(), "evidence")
    prompt_path, text = "persona/prompt_template/v3_ChatGPT/datacenter_stance_rubric_v1.txt", diagnostics[1]
    self.assertTrue(os.path.isfile(prompt_path))
    for category, low, high in prompts.STANCE_BANDS:
      band = f"{low}-{high}" if low != high else f"{low} only"
      self.assertIn(f"{category}: {band}", text)
    self.assertIn("CURRENT FORM", text)

  def test_rejects_invalid_and_inconsistent_outputs(self):
    invalid = [self.rating(s) for s in [-1, 101, True, 50.0, "50", float("nan")]]
    invalid += [self.rating(51), self.rating(50, "neutral"), self.rating(None),
                self.rating(category=None), self.rating(rationale=""),
                self.rating(conditions="local hiring"), self.rating(conditions=[1]),
                {}, "nonsense", [50], None]
    for r in invalid:
      with self.subTest(response=r), self.assertRaises((ValueError, TypeError)):
        prompts.parse_rubric_stance(r)

  def test_fenced_structured_json_and_conditions(self):
    raw = self.rating(61, "moderate_support", conditions=["Enforce local hiring"])
    r = prompts.parse_rubric_stance("```json\n" + json.dumps(raw) + "\n```")
    self.assertEqual(r["conditions"], raw["conditions"])

  def call_model(self, responses):
    with patch.object(gpt_structure, "ChatGPT_request", side_effect=responses) as api:
      r = prompts.run_gpt_prompt_datacenter_stance(
        self.persona(), 'Rachel Nguyen said: "I am genuinely torn."',
        with_metadata=True)
    return r, api

  def test_abstention_is_valid_and_never_becomes_fifty(self):
    (r, _), api = self.call_model([json.dumps({"output": self.rating(None, None)})])
    self.assertIsNone(r["score"])
    self.assertIsNone(r["category"])
    self.assertEqual(r["withheld"], "abstained")
    self.assertEqual(api.call_count, 1)

  def test_invalid_retries_and_failure_becomes_null(self):
    (r, _), api = self.call_model(["invalid"] * 3)
    self.assertIsNone(r["score"])
    self.assertEqual(r["withheld"], "evaluator_invalid")
    self.assertEqual(api.call_count, 3)
    (r, _), api = self.call_model([json.dumps({"output": self.rating(51)}),
                                  json.dumps({"output": self.rating()})])
    self.assertEqual(r["score"], 50)
    self.assertEqual(api.call_count, 2)
    self.assertEqual(api.call_args.args[1], 0)

  def test_legacy_consumer_shape_is_preserved(self):
    with patch.object(gpt_structure, "ChatGPT_request",
                      return_value=json.dumps({"output": self.rating()})):
      value, _ = prompts.run_gpt_prompt_datacenter_stance(self.persona(), "evidence")
    self.assertEqual(value, (50, self.rating()["rationale"]))

  def test_no_api_for_asleep_or_empty_memory(self):
    p = self.persona()
    p.a_mem = NS(seq_event=[], seq_thought=[], seq_chat=[], embeddings={})
    with patch.object(opinion_probe, "new_retrieve") as retrieve:
      for action, reason in [("sleeping", "asleep"), ("working", "no_memory")]:
        p.scratch.act_description = action
        r = opinion_probe.probe(p, with_metadata=True)
        self.assertIsNone(r["score"])
        self.assertEqual(r["withheld"], reason)
        self.assertEqual(r["scoring_version"], "rubric_v1")
      retrieve.assert_not_called()

  def test_only_idle_records_are_also_unmeasurable(self):
    p = self.persona()
    p.a_mem = NS(seq_event=[NS(embedding_key="table is idle")], seq_thought=[])
    with patch.object(opinion_probe, "new_retrieve") as retrieve:
      r = opinion_probe.probe(p, with_metadata=True)
    self.assertIsNone(r["score"])
    self.assertEqual(r["withheld"], "no_memory")
    retrieve.assert_not_called()

  def test_evidence_is_read_only_attributed_filtered_and_chronological(self):
    p = self.persona()
    now = p.scratch.curr_time
    good = NS(node_id="good", created=now, embedding_key="a water concern")
    bad = NS(node_id="bad", created=now, embedding_key="breakfast")
    p.a_mem = NS(seq_event=[good, bad], seq_thought=[], embeddings={})
    utterance = (now - datetime.timedelta(hours=1), "I oppose the current proposal")
    rated = prompts.parse_rubric_stance(self.rating(19, "very_strong_opposition"))
    with patch.object(opinion_probe, "own_utterances", return_value=[utterance]), \
         patch.object(opinion_probe, "rank_utterances", return_value=[utterance]), \
         patch.object(opinion_probe, "new_retrieve",
                      return_value={prompts.STANCE_QUESTION: [good, bad]}) as retrieve, \
         patch.object(opinion_probe, "pool_relevance", return_value={"good": .8, "bad": .2}), \
         patch.object(opinion_probe, "run_gpt_prompt_datacenter_stance",
                      return_value=(rated, [])) as model:
      r = opinion_probe.probe(p, with_metadata=True)
      self.assertTrue(retrieve.call_args.kwargs["touch"] is False)
      text = model.call_args.args[1]
      self.assertIn('Rachel Nguyen said: "I oppose the current proposal"', text)
      self.assertLess(text.index("said:"), text.index("a water concern"))
      self.assertNotIn("breakfast", text)
      self.assertEqual(r["evidence"], ["good"])
      self.assertEqual(r["quoted"]["n"], 1)
      self.assertEqual(p.a_mem.embeddings, {})

  def test_low_relevance_abstains_before_model(self):
    p = self.persona()
    p.a_mem = NS(seq_event=[NS(node_id="x", embedding_key="breakfast")], seq_thought=[])
    with patch.object(opinion_probe, "own_utterances", return_value=[]), \
         patch.object(opinion_probe, "rank_utterances", return_value=[]), \
         patch.object(opinion_probe, "new_retrieve",
                      return_value={prompts.STANCE_QUESTION: p.a_mem.seq_event}), \
         patch.object(opinion_probe, "pool_relevance", return_value={"x": .2}), \
         patch.object(opinion_probe, "run_gpt_prompt_datacenter_stance") as model:
      r = opinion_probe.probe(p, with_metadata=True)
      self.assertIsNone(r["score"])
      self.assertEqual(r["withheld"], "low_relevance")
      model.assert_not_called()

  def test_logged_record_preserves_old_metadata_and_adds_rubric_fields(self):
    p = self.persona()
    server = reverie.ReverieServer.__new__(reverie.ReverieServer)
    server.personas = {p.scratch.name: p}
    server.step, server.curr_time = 360, p.scratch.curr_time
    from unittest.mock import Mock
    server.experiment_logger = Mock()
    reading = {**prompts.parse_rubric_stance(self.rating(0, "very_strong_opposition")),
               "evidence": ["node_1"], "relevance": {"shown": .8, "best": .9},
               "quoted": {"n": 1, "first": "earlier", "last": "now"}}
    with patch.object(reverie, "probe_opinion", return_value=reading):
      server.probe_opinions()
    row = server.experiment_logger.log_opinions.call_args.args[2][0]
    self.assertEqual(row["score"], 0)
    self.assertEqual(row["scoring_version"], "rubric_v1")
    self.assertEqual(row["evidence"], ["node_1"])
    self.assertEqual(row["quoted"]["n"], 1)
    self.assertTrue({"name", "model", "run_env", "withheld", "conditions"} <= row.keys())


if __name__ == "__main__":
  unittest.main()
