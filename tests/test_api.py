"""Tests for the minimal iCSee feeder DVRIP client helpers."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest

API_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "icsee_feeder"
    / "api.py"
)
SPEC = importlib.util.spec_from_file_location("icsee_feeder_api", API_PATH)
assert SPEC is not None
assert SPEC.loader is not None
api = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = api
SPEC.loader.exec_module(api)

_build_packet = api._build_packet
feed_record_datetime = api.feed_record_datetime
latest_feed_record = api.latest_feed_record
sofia_hash = api.sofia_hash


class TestIcseeFeederApi(unittest.TestCase):
    """Tests for protocol helper behavior."""

    def test_sofia_hash_empty_password(self) -> None:
        """The known empty-password Sofia hash should remain stable."""

        self.assertEqual(sofia_hash(""), "tlJwpbo6")

    def test_build_packet_header_and_payload(self) -> None:
        """Packets should use the expected DVRIP header layout."""

        packet = _build_packet(
            2304,
            0x38,
            7,
            {"Name": "OPFeedManual", "OPFeedManual": {"Servings": 1}},
        )

        header = packet[:20]
        magic, version, session, sequence, message_id, payload_length = struct.unpack(
            "<BB2xII2xHI",
            header,
        )

        self.assertEqual(magic, 0xFF)
        self.assertEqual(version, 0)
        self.assertEqual(session, 0x38)
        self.assertEqual(sequence, 7)
        self.assertEqual(message_id, 2304)
        self.assertEqual(payload_length, len(packet[20:]))
        self.assertTrue(packet.endswith(b"\x0a\x00"))

        payload = json.loads(packet[20:-2].decode("utf-8"))
        self.assertEqual(payload["Name"], "OPFeedManual")
        self.assertEqual(payload["OPFeedManual"]["Servings"], 1)

    def test_feed_record_datetime_accepts_history_shape(self) -> None:
        """History records should parse their Date and Time fields."""

        parsed = feed_record_datetime(
            {"Date": "2026-09-08", "Time": "08:15:30", "Servings": 2}
        )

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.isoformat(), "2026-09-08T08:15:30")

    def test_latest_feed_record_sorts_by_timestamp(self) -> None:
        """Latest feed records should not depend on device list ordering."""

        older = {"Date": "2026-09-07", "Time": "18:00:00", "Servings": 1}
        newer = {"Date": "2026-09-08", "Time": "07:00:00", "Servings": 2}

        self.assertEqual(latest_feed_record([older, newer]), newer)


if __name__ == "__main__":
    unittest.main()
