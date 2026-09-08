#!/usr/bin/env python3
"""Low-level DVRIP login probe for iCSee/XMEye devices."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import struct
import time

COMMANDS = {
    "SystemInfo": (1020, {"Name": "SystemInfo"}),
    "SystemFunction": (1360, {"Name": "SystemFunction"}),
    "OPFeedHistory": (2306, {"Name": "OPFeedHistory"}),
    "OPFeedBook": (2302, {"Name": "OPFeedBook"}),
}


def sofia_hash(password: str = "") -> str:
    """Return the Sofia password hash used by DVRIP devices."""

    digest = hashlib.md5(password.encode("utf-8")).digest()
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    return "".join(
        alphabet[(first + second) % len(alphabet)]
        for first, second in zip(digest[::2], digest[1::2], strict=True)
    )


def recv_exact(sock: socket.socket, length: int) -> bytes:
    """Receive an exact number of bytes or raise a socket error."""

    buffer = bytearray()
    while len(buffer) < length:
        chunk = sock.recv(length - len(buffer))
        if not chunk:
            raise ConnectionError("socket closed while waiting for response")
        buffer.extend(chunk)
    return bytes(buffer)


def send_json(
    sock: socket.socket,
    message_id: int,
    session: int,
    sequence: int,
    payload: dict[str, object],
) -> tuple[int, dict[str, object]]:
    """Send a DVRIP JSON request and return response session plus payload."""

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    packet = (
        struct.pack("BB2xII2xHI", 255, 0, session, sequence, message_id, len(body) + 2)
        + body
        + b"\x0a\x00"
    )
    sock.sendall(packet)
    header = recv_exact(sock, 20)
    magic, version, response_session, response_sequence, msgid, length = struct.unpack(
        "BB2xII2xHI",
        header,
    )
    response_payload = recv_exact(sock, length)
    print(
        f"response magic={magic} version={version} session={response_session} "
        f"sequence={response_sequence} msgid={msgid} payload_length={length}"
    )
    decoded = json.loads(response_payload.rstrip(b"\x00\r\n").decode("latin1"))
    return response_session, decoded


def main() -> int:
    """Run the probe."""

    parser = argparse.ArgumentParser()
    parser.add_argument("host")
    parser.add_argument("--port", type=int, default=34567)
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--commands", action="store_true")
    args = parser.parse_args()

    print(f"connecting {args.host}:{args.port}")
    started = time.monotonic()
    with socket.create_connection((args.host, args.port), timeout=args.timeout) as sock:
        sock.settimeout(args.timeout)
        print(f"connected in {time.monotonic() - started:.3f}s")
        print("login")
        session, response = send_json(
            sock,
            1000,
            0,
            0,
            {
                "EncryptType": "MD5",
                "LoginType": "DVRIP-Web",
                "PassWord": sofia_hash(args.password),
                "UserName": args.username,
            },
        )
        print(f"payload={response}")

        if args.commands:
            sequence = 1
            for name, (message_id, payload) in COMMANDS.items():
                command_payload = dict(payload)
                command_payload["SessionID"] = f"0x{session:08X}"
                print(name)
                try:
                    session, command_response = send_json(
                        sock,
                        message_id,
                        session,
                        sequence,
                        command_payload,
                    )
                except Exception as err:
                    print(f"{name}_FAILED: {type(err).__name__}: {err}")
                else:
                    print(f"payload={command_response}")
                sequence += 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
