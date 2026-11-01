import unittest
from reacciona import MetricStream, Score, judge

class GameTests(unittest.TestCase):
    def test_escape_judgement(self):
        self.assertEqual(judge("escape", [140, 140, 140, 140, 95], 100), (True, False))
        self.assertEqual(judge("escape", [100] * 5, 100), (False, False))

    def test_defend_and_recover(self):
        self.assertEqual(judge("defend", [100] * 8, 100), (True, True))
        self.assertEqual(judge("recover", [60] * 8, 100), (True, True))
        self.assertEqual(judge("recover", [100] * 8, 100), (False, False))

    def test_shield_absorbs_escape_failure(self):
        score = Score()
        score.apply("defend", True)
        score.apply("defend", True)
        self.assertEqual(score.shield, 1)
        score.apply("escape", False)
        self.assertEqual(score.lives, 3)
        self.assertEqual(score.shield, 0)
        score.apply("escape", False)
        self.assertEqual(score.lives, 2)

    def test_streak_bonus(self):
        score = Score()
        self.assertEqual(score.apply("recover", True)["earned"], 100)
        self.assertEqual(score.apply("recover", True)["earned"], 100)
        self.assertEqual(score.apply("recover", True)["earned"], 150)

    def test_stale_data(self):
        stream = MetricStream()
        stream.update(110, now=10)
        self.assertEqual(stream.recent_power(10), 110)
        self.assertIsNone(stream.recent_power(13))
        stream.update(-1, now=14)
        self.assertIsNone(stream.recent_power(14))

if __name__ == "__main__":
    unittest.main()
