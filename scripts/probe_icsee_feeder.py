#!/usr/bin/env python3
"""Probe an iCSee/XMEye feeder outside Home Assistant."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / "custom_components" / "icsee_feeder" / "api.py"
SPEC = importlib.util.spec_from_file_location("icsee_feeder_api", API_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load {API_PATH}")
api = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = api
SPEC.loader.exec_module(api)

IcseeFeederAuthError = api.IcseeFeederAuthError
IcseeFeederClient = api.IcseeFeederClient
IcseeFeederConnectionError = api.IcseeFeederConnectionError
IcseeFeederError = api.IcseeFeederError


def main() -> int:
    """Run the probe."""

    parser = argparse.ArgumentParser()
    parser.add_argument("host")
    parser.add_argument("--port", type=int, default=34567)
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="")
    parser.add_argument("--feed", type=int)
    args = parser.parse_args()

    client = IcseeFeederClient(
        args.host,
        args.username,
        args.password,
        port=args.port,
    )

    try:
        status = client.test_connection()
    except IcseeFeederAuthError as err:
        print(f"AUTH_FAILED: {err}")
        return 2
    except IcseeFeederConnectionError as err:
        print(f"CONNECT_FAILED: {err}")
        return 3
    except IcseeFeederError as err:
        print(f"PROTOCOL_FAILED: {err}")
        return 4

    print("CONNECTED")
    print(f"serial={status.serial or 'unknown'}")
    print(f"model={status.model or 'unknown'}")
    print(f"software_version={status.software_version or 'unknown'}")
    print(f"supports_feeder={status.supports_feeder}")
    print(f"feed_history_count={len(status.feed_history)}")
    print(f"feed_book_count={len(status.feed_book)}")

    if args.feed:
        try:
            result = client.feed_manual(args.feed)
        except IcseeFeederError as err:
            print(f"FEED_FAILED: {err}")
            return 5
        print("FEED_OK")
        print(f"requested_servings={result.requested_servings}")
        print(f"fed_servings={result.fed_servings}")
        print(f"not_feeding={result.not_feeding}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
