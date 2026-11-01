import unittest
import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace
from reacciona import MetricStream, Score, judge, calibrate, Simulator, rest_phase, measure, load_baseline, save_baseline, resolve_baseline, play_game, Audio
from pm5_ble import GENERAL, ADDITIONAL, POWER, decode_notification

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

    def test_ble_packet_decoding(self):
        general = bytearray(19)
        general[:3] = (1234).to_bytes(3, "little")
        general[3:6] = (1543).to_bytes(3, "little")
        general[18] = 100
        metric = decode_notification(GENERAL, general, 12)
        self.assertEqual(metric.distance_m, 154.3)
        self.assertEqual(metric.drag_factor, 100)
        power = decode_notification(POWER, bytes([0,0,0,220,0]), 13)
        self.assertEqual(power.watts, 220)
        self.assertEqual(decode_notification(ADDITIONAL, bytes([0,0,0,0,0,24]), 14).cadence_spm,24)
        self.assertIsNone(decode_notification(POWER, b"\\x00"))

    def test_stale_data(self):
        stream = MetricStream()
        stream.update(110, now=10)
        self.assertEqual(stream.recent_power(10), 110)
        self.assertIsNone(stream.recent_power(13))
        stream.update(-1, now=14)
        self.assertIsNone(stream.recent_power(14))

class BaselineTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_and_reuse_without_calibration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            save_baseline(path, 112)
            self.assertEqual(load_baseline(path), 112)
            args = SimpleNamespace(baseline=None, recalibrate=False, calibration_file=str(path), tick=0)
            self.assertEqual(await resolve_baseline(args, MetricStream(), None), 112)

    async def test_manual_override_without_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            args = SimpleNamespace(baseline=112, recalibrate=False, calibration_file=str(path), tick=0)
            self.assertEqual(await resolve_baseline(args, MetricStream(), None), 112)
            self.assertFalse(path.exists())

    async def test_invalid_file_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            path.write_text('{"baseline_w": -100}', encoding="utf-8")
            self.assertIsNone(load_baseline(path))

class GUIEventTests(unittest.IsolatedAsyncioTestCase):
    async def test_simulated_single_round_events(self):
        events = []
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(
                rounds=1, baseline=112, recalibrate=False, tick=0, seed=42,
                calibration_file=str(Path(directory) / "calibration.json"),
                output=str(Path(directory) / "session.json"),
                on_event=events.append, should_stop=lambda: False,
            )
            audio = Audio(enabled=False)
            try:
                await play_game(args, MetricStream(), audio, Simulator(MetricStream(), 112, 42))
            finally:
                audio.close()
        kinds = [event["event"] for event in events]
        self.assertIn("start", kinds)
        self.assertIn("rest", kinds)
        self.assertIn("challenge", kinds)
        self.assertIn("countdown", kinds)
        self.assertIn("result", kinds)
        self.assertIn("finished", kinds)

class RestTests(unittest.IsolatedAsyncioTestCase):
    async def test_rest_without_power_does_not_fail(self):
        stream = MetricStream()
        await rest_phase(0, None, stream, 0)
        self.assertIsNone(stream.recent_power(100))

    async def test_simulated_active_challenge(self):
        stream = MetricStream()
        sim = Simulator(stream, 110, 4)
        readings = await measure(stream, 5, sim, "escape", 0)
        self.assertEqual(len(readings), 5)
        self.assertTrue(all(power > 130 for power in readings))

class CalibrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_simulated_calibration(self):
        stream = MetricStream()
        baseline = await calibrate(stream, Simulator(stream, 110, 42), 0)
        self.assertGreater(baseline, 100)
        self.assertLess(baseline, 120)

    async def test_waits_for_movement_instead_of_failing_immediately(self):
        stream = MetricStream()
        async def start_later():
            await asyncio.sleep(.05)
            async def feed():
                for _ in range(48):
                    stream.update(110)
                    await asyncio.sleep(.001)
            await feed()
        task = asyncio.create_task(start_later())
        baseline = await calibrate(stream, None, .001, wait_timeout=1)
        await task
        self.assertEqual(baseline, 110)

if __name__ == "__main__":
    unittest.main()
