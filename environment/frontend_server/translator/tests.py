from django.test import SimpleTestCase

from translator.dashboard import _cost, _price


class CostTests(SimpleTestCase):
  def test_prefix_match_prefers_longest(self):
    self.assertEqual(_price("gpt-4o-mini"), (0.15, 0.075, 0.60))
    self.assertEqual(_price("gpt-4o-2024-08-06"), (2.50, 1.25, 10.00))
    self.assertIsNone(_price("claude-sonnet-5-5"))

  def test_cached_tokens_billed_at_cached_rate(self):
    # 1M input of which 400k cached, plus 100k output, on gpt-4o:
    # 600k * 2.50 + 400k * 1.25 + 100k * 10.00 = 1.50 + 0.50 + 1.00
    row = {"model": "gpt-4o", "in": 1_000_000, "cached": 400_000, "out": 100_000}
    self.assertAlmostEqual(_cost(row), 3.00)

  def test_embedding_and_unpriced(self):
    self.assertAlmostEqual(_cost({"model": "text-embedding-3-small", "in": 1_000_000}), 0.02)
    self.assertIsNone(_cost({"model": "mystery-model", "in": 10}))
