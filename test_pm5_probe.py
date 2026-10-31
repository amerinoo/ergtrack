import unittest
from unittest.mock import patch
import sys
import types

# Tests can run without a physical PM5 or installed HID library.
sys.modules.setdefault("hid", types.SimpleNamespace(enumerate=lambda: []))
import pm5_probe


class ProtocolTests(unittest.TestCase):
    def test_standard_frame_xor_checksum(self):
        self.assertEqual(pm5_probe.frame(0x91), bytes([0xF1, 0x91, 0x91, 0xF2]))

    def test_filters_unrelated_devices(self):
        devices = [
            {"vendor_id": 0x1234, "manufacturer_string": "Other"},
            {"vendor_id": 0x17A4, "manufacturer_string": "Concept2"},
        ]
        with patch.object(pm5_probe.hid, "enumerate", return_value=devices):
            self.assertEqual(len(pm5_probe.devices()), 1)


if __name__ == "__main__":
    unittest.main()
