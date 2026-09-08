"""Minimal DVRIP/Sofia client for iCSee/XMEye feeder devices."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import logging
import socket
import struct
from typing import Any, Self, TypeVar
from urllib.parse import quote

_LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T")

LOGIN = 1000
SYSTEM_INFO = 1020
SYSTEM_FUNCTION = 1360
OP_FEED_BOOK_SET = 2300
OP_FEED_BOOK_GET = 2302
OP_FEED_MANUAL_SET = 2304
OP_FEED_HISTORY_GET = 2306
OP_FEED_HISTORY_SET = 2308

OK_RET_CODES = {100, 515}
AUTH_RET_CODES = {106, 203, 205, 207}

RESPONSE_CODE_DESCRIPTIONS = {
    100: "OK",
    101: "Unknown error",
    102: "Unsupported version",
    103: "Request not permitted",
    104: "User already logged in",
    105: "User is not logged in",
    106: "Username or password is incorrect",
    107: "User does not have necessary permissions",
    124: "Algorithm error",
    203: "Password is incorrect",
    205: "User does not exist or IP is locked",
    207: "Blacklisted",
    515: "Upgrade successful",
}


class IcseeFeederError(Exception):
    """Base error for iCSee feeder communication."""


class IcseeFeederConnectionError(IcseeFeederError):
    """Raised when a feeder cannot be reached."""


class IcseeFeederAuthError(IcseeFeederError):
    """Raised when authentication fails."""


class IcseeFeederProtocolError(IcseeFeederError):
    """Raised when the device returns an unexpected response."""


class IcseeFeederUnsupportedError(IcseeFeederError):
    """Raised when the target device does not expose feeder functions."""


@dataclass(slots=True)
class ManualFeedResult:
    """Result from an OPFeedManual command."""

    requested_servings: int
    fed_servings: int | None
    not_feeding: int | None
    response: dict[str, Any]


@dataclass(slots=True)
class IcseeFeederStatus:
    """Current feeder metadata and feed history."""

    system_info: dict[str, Any]
    capabilities: dict[str, Any]
    feed_history: list[dict[str, Any]]
    feed_book: list[dict[str, Any]]

    @property
    def serial(self) -> str | None:
        """Return the device serial number if reported."""

        return _first_str(
            self.system_info,
            "SerialNo",
            "SerialNumber",
            "SerialID",
            "SN",
        )

    @property
    def model(self) -> str | None:
        """Return the model name if reported."""

        return _first_str(
            self.system_info,
            "DeviceModel",
            "HardWare",
            "HardWareVersion",
        )

    @property
    def software_version(self) -> str | None:
        """Return the software version if reported."""

        return _first_str(self.system_info, "SoftWareVersion", "SoftwareVersion")

    @property
    def supports_feeder(self) -> bool | None:
        """Return whether the device reports feeder support, if known."""

        other_function = self.capabilities.get("OtherFunction")
        if not isinstance(other_function, Mapping):
            return None

        support = other_function.get("SupportFeederFunction")
        if support is None:
            return None
        return bool(support)


def sofia_hash(password: str = "") -> str:
    """Return the Sofia password hash used by DVRIP devices."""

    digest = hashlib.md5(password.encode("utf-8")).digest()
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    return "".join(
        alphabet[(first + second) % len(alphabet)]
        for first, second in zip(digest[::2], digest[1::2], strict=True)
    )


def build_rtsp_url(
    host: str,
    username: str,
    password: str,
    *,
    port: int = 554,
    channel: int = 1,
    stream: int = 1,
) -> str:
    """Build the RTSP URL used by iCSee/XMEye camera firmware."""

    encoded_username = quote(username, safe="")
    encoded_password = quote(password, safe="")
    return (
        f"rtsp://{encoded_username}:{encoded_password}@{host}:{port}/"
        f"user={encoded_username}_password={encoded_password}_"
        f"channel={channel}_stream={stream}.sdp?real_stream"
    )


def feed_record_datetime(record: Mapping[str, Any]) -> datetime | None:
    """Parse the date and time from a feed history record."""

    date = record.get("Date") or record.get("RecDate")
    time = record.get("Time") or record.get("RecTime")
    if not isinstance(date, str) or not isinstance(time, str):
        return None

    for time_format in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(f"{date} {time}", time_format)
        except ValueError:
            continue
    return None


def latest_feed_record(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the most recent feed record."""

    dated_records = [
        (parsed, record)
        for record in records
        if (parsed := feed_record_datetime(record)) is not None
    ]
    if not dated_records:
        return records[0] if records else None
    return max(dated_records, key=lambda item: item[0])[1]


def _build_packet(
    message_id: int,
    session_id: int,
    sequence: int,
    payload: Mapping[str, Any] | bytes = b"",
) -> bytes:
    """Build a DVRIP request packet."""

    if isinstance(payload, bytes):
        body = payload
    else:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    body += b"\x0a\x00"
    return (
        struct.pack(
            "<BB2xII2xHI",
            0xFF,
            0,
            session_id,
            sequence,
            message_id,
            len(body),
        )
        + body
    )


class IcseeFeederClient:
    """Short-lived local client for an iCSee/XMEye feeder."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        *,
        port: int = 34567,
        timeout: float = 10.0,
    ) -> None:
        """Initialize the client."""

        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout

    def get_status(self, *, include_feed_details: bool = False) -> IcseeFeederStatus:
        """Fetch metadata, capabilities, schedule, and feed history."""

        def action(session: _DvripSession) -> IcseeFeederStatus:
            system_info = _command_payload(
                session.get_command("SystemInfo"),
                "SystemInfo",
            )
            try:
                capabilities = _command_payload(
                    session.get_command("SystemFunction"),
                    "SystemFunction",
                )
            except IcseeFeederProtocolError:
                _LOGGER.debug("SystemFunction is not available from %s", self.host)
                capabilities = {}
            feed_history: list[dict[str, Any]] = []
            feed_book: list[dict[str, Any]] = []
            if include_feed_details:
                feed_history = self._get_feed_history()
                feed_book = self._get_feed_book()
            return IcseeFeederStatus(
                system_info=system_info,
                capabilities=capabilities,
                feed_history=feed_history,
                feed_book=feed_book,
            )

        return self._with_session(action)

    def _get_feed_history(self) -> list[dict[str, Any]]:
        """Fetch feed history using a separate session.

        Some iCSee feeder firmware accepts OPFeedHistory but never replies. Keeping
        this out of the core status path lets setup and control keep working.
        """

        def action(session: _DvripSession) -> list[dict[str, Any]]:
            return _feed_history_from_response(session.get_command("OPFeedHistory"))

        try:
            return self._with_session(action)
        except (IcseeFeederConnectionError, IcseeFeederProtocolError):
            _LOGGER.debug("Feed history is not available from %s", self.host)
            return []

    def _get_feed_book(self) -> list[dict[str, Any]]:
        """Fetch feed schedule using a separate session."""

        def action(session: _DvripSession) -> list[dict[str, Any]]:
            return _feed_book_from_response(session.get_command("OPFeedBook"))

        try:
            return self._with_session(action)
        except (IcseeFeederConnectionError, IcseeFeederProtocolError):
            _LOGGER.debug("Feed schedule is not available from %s", self.host)
            return []

    def test_connection(self) -> IcseeFeederStatus:
        """Connect and verify that the target is probably a feeder."""

        status = self.get_status()
        if status.supports_feeder is False:
            raise IcseeFeederUnsupportedError(
                "Device responded but does not report feeder support"
            )
        return status

    def feed_manual(self, servings: int) -> ManualFeedResult:
        """Dispense food using OPFeedManual."""

        servings = int(servings)
        if servings < 1:
            raise ValueError("servings must be at least 1")

        def action(session: _DvripSession) -> ManualFeedResult:
            response = session.set_command("OPFeedManual", {"Servings": servings})
            feed_response = response.get("OPFeedManual")
            fed_servings = None
            not_feeding = None
            if isinstance(feed_response, Mapping):
                fed_servings = _coerce_int(feed_response.get("Feeded"))
                not_feeding = _coerce_int(feed_response.get("NotFeeding"))

            return ManualFeedResult(
                requested_servings=servings,
                fed_servings=fed_servings,
                not_feeding=not_feeding,
                response=response,
            )

        return self._with_session(action)

    def add_scheduled_feed(
        self,
        feed_time: str,
        servings: int,
        *,
        enabled: bool = True,
    ) -> dict[str, Any]:
        """Add a scheduled feed entry to the feeder."""

        servings = int(servings)
        if servings < 1:
            raise ValueError("servings must be at least 1")

        now = datetime.now()
        entry = {
            "Enable": 1 if enabled else 0,
            "RecDate": now.strftime("%Y-%m-%d"),
            "RecTime": now.strftime("%H:%M:%S"),
            "Servings": servings,
            "Time": _normalize_feed_time(feed_time),
        }

        def action(session: _DvripSession) -> dict[str, Any]:
            return session.set_command(
                "OPFeedBook",
                {"Action": "Add", "FeedBook": [entry]},
            )

        return self._with_session(action)

    def delete_scheduled_feed(
        self,
        feed_time: str,
        servings: int | None = None,
    ) -> int:
        """Delete scheduled feed entries that match the given time."""

        normalized_time = _normalize_feed_time(feed_time)

        def action(session: _DvripSession) -> int:
            current_entries = _feed_book_from_response(session.get_command("OPFeedBook"))
            entries_to_delete = [
                entry
                for entry in current_entries
                if entry.get("Time") == normalized_time
                and (servings is None or _coerce_int(entry.get("Servings")) == servings)
            ]
            if not entries_to_delete:
                return 0

            session.set_command(
                "OPFeedBook",
                {"Action": "Delete", "FeedBook": entries_to_delete},
            )
            return len(entries_to_delete)

        return self._with_session(action)

    def _with_session(self, action: Callable[["_DvripSession"], _T]) -> _T:
        """Run an action within an authenticated session."""

        with _DvripSession(
            self.host,
            self.port,
            self.username,
            self.password,
            self.timeout,
        ) as session:
            session.login()
            return action(session)


class _DvripSession(AbstractContextManager["_DvripSession"]):
    """Authenticated DVRIP socket session."""

    COMMAND_CODES = {
        "SystemInfo": SYSTEM_INFO,
        "SystemFunction": SYSTEM_FUNCTION,
    }

    FEED_CODES = {
        "OPFeedBook": {"GET": OP_FEED_BOOK_GET, "SET": OP_FEED_BOOK_SET},
        "OPFeedManual": {"SET": OP_FEED_MANUAL_SET},
        "OPFeedHistory": {"GET": OP_FEED_HISTORY_GET, "SET": OP_FEED_HISTORY_SET},
    }

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        timeout: float,
    ) -> None:
        """Initialize the session."""

        self.host = host
        self.port = port
        self.username = username
        self.password_hash = sofia_hash(password)
        self.timeout = timeout
        self.session_id = 0
        self.sequence = 0
        self._socket: socket.socket | None = None

    def __enter__(self) -> Self:
        """Open the socket."""

        try:
            self._socket = socket.create_connection(
                (self.host, self.port),
                timeout=self.timeout,
            )
            self._socket.settimeout(self.timeout)
        except OSError as err:
            raise IcseeFeederConnectionError(
                f"Could not connect to {self.host}:{self.port}"
            ) from err

        return self

    def __exit__(self, *exc_info: object) -> None:
        """Close the socket."""

        if self._socket is None:
            return

        try:
            self._socket.close()
        finally:
            self._socket = None

    def login(self) -> None:
        """Authenticate with the device."""

        response = self.send(
            LOGIN,
            {
                "EncryptType": "MD5",
                "LoginType": "DVRIP-Web",
                "PassWord": self.password_hash,
                "UserName": self.username,
            },
        )
        ret = response.get("Ret")
        if ret in AUTH_RET_CODES:
            raise IcseeFeederAuthError(_ret_description(ret))
        if ret not in OK_RET_CODES:
            raise IcseeFeederProtocolError(
                f"Login failed with response code {ret}: {_ret_description(ret)}"
            )

        session_id = response.get("SessionID")
        if not isinstance(session_id, str):
            raise IcseeFeederProtocolError("Login response did not include SessionID")

        try:
            self.session_id = int(session_id, 16)
        except ValueError as err:
            raise IcseeFeederProtocolError(
                f"Login response included invalid SessionID: {session_id}"
            ) from err

    def get_command(self, command: str) -> dict[str, Any]:
        """Send a DVRIP get command."""

        code = self._command_code(command, "GET")
        return self._checked_response(
            self.send(
                code,
                {
                    "Name": command,
                    "SessionID": self._session_id_hex,
                },
            )
        )

    def set_command(self, command: str, data: Mapping[str, Any]) -> dict[str, Any]:
        """Send a DVRIP set command."""

        code = self._command_code(command, "SET")
        return self._checked_response(
            self.send(
                code,
                {
                    "Name": command,
                    "SessionID": self._session_id_hex,
                    command: dict(data),
                },
            )
        )

    def send(self, message_id: int, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Send a DVRIP packet and parse the JSON response."""

        sock = self._require_socket()
        packet = _build_packet(message_id, self.session_id, self.sequence, payload)
        self.sequence += 1
        _LOGGER.debug("Sending DVRIP message %s to %s", message_id, self.host)

        try:
            sock.sendall(packet)
            header = self._recv_exact(20)
            (
                magic,
                _version,
                session_id,
                _sequence,
                response_id,
                payload_length,
            ) = struct.unpack("<BB2xII2xHI", header)
            if magic != 0xFF:
                raise IcseeFeederProtocolError(
                    f"Unexpected DVRIP magic byte {magic!r}"
                )

            raw_payload = self._recv_exact(payload_length)
        except OSError as err:
            raise IcseeFeederConnectionError(
                f"Connection to {self.host}:{self.port} failed: {err}"
            ) from err

        self.session_id = session_id
        _LOGGER.debug(
            "Received DVRIP response %s from %s with %s bytes",
            response_id,
            self.host,
            payload_length,
        )
        return _decode_json_payload(raw_payload)

    @property
    def _session_id_hex(self) -> str:
        return f"0x{self.session_id:08X}"

    def _checked_response(self, response: dict[str, Any]) -> dict[str, Any]:
        ret = response.get("Ret")
        if ret in AUTH_RET_CODES:
            raise IcseeFeederAuthError(_ret_description(ret))
        if ret not in OK_RET_CODES:
            raise IcseeFeederProtocolError(
                f"Command returned response code {ret}: {_ret_description(ret)}"
            )
        return response

    def _command_code(self, command: str, operation: str) -> int:
        feed_codes = self.FEED_CODES.get(command)
        if feed_codes is not None:
            if operation not in feed_codes:
                raise IcseeFeederProtocolError(
                    f"Command {command} does not support {operation}"
                )
            return feed_codes[operation]

        if operation == "GET" and command in self.COMMAND_CODES:
            return self.COMMAND_CODES[command]

        raise IcseeFeederProtocolError(f"Unsupported DVRIP command {command}")

    def _recv_exact(self, length: int) -> bytes:
        sock = self._require_socket()
        buffer = bytearray()
        while len(buffer) < length:
            chunk = sock.recv(length - len(buffer))
            if not chunk:
                raise IcseeFeederConnectionError("Connection closed by device")
            buffer.extend(chunk)
        return bytes(buffer)

    def _require_socket(self) -> socket.socket:
        if self._socket is None:
            raise IcseeFeederConnectionError("Session is not connected")
        return self._socket


def _decode_json_payload(payload: bytes) -> dict[str, Any]:
    cleaned = payload.rstrip(b"\x00\r\n")
    if not cleaned:
        return {}

    for encoding in ("utf-8", "latin1"):
        try:
            return json.loads(cleaned.decode(encoding), strict=False)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue

    printable_payload = bytes(
        byte for byte in cleaned if byte >= 32 or byte in (9, 10, 13)
    )
    try:
        return json.loads(printable_payload.decode("latin1"), strict=False)
    except json.JSONDecodeError as err:
        raise IcseeFeederProtocolError("Device returned non-JSON data") from err


def _command_payload(
    response: Mapping[str, Any],
    command: str | None = None,
) -> dict[str, Any]:
    if command is not None:
        nested = response.get(command)
        if isinstance(nested, Mapping):
            return dict(nested)

    name = response.get("Name")
    if isinstance(name, str):
        nested = response.get(name)
        if isinstance(nested, Mapping):
            return dict(nested)

    return {
        str(key): value
        for key, value in response.items()
        if key not in {"Name", "Ret", "SessionID"}
    }


def _feed_history_from_response(response: Mapping[str, Any]) -> list[dict[str, Any]]:
    history = response.get("FeedHistory")
    if isinstance(history, list):
        return [dict(item) for item in history if isinstance(item, Mapping)]

    nested = response.get("OPFeedHistory")
    if isinstance(nested, Mapping):
        history = nested.get("FeedHistory")
        if isinstance(history, list):
            return [dict(item) for item in history if isinstance(item, Mapping)]

    return []


def _feed_book_from_response(response: Mapping[str, Any]) -> list[dict[str, Any]]:
    feed_book = response.get("FeedBook")
    if isinstance(feed_book, list):
        return [dict(item) for item in feed_book if isinstance(item, Mapping)]

    nested = response.get("OPFeedBook")
    if isinstance(nested, Mapping):
        feed_book = nested.get("FeedBook")
        if isinstance(feed_book, list):
            return [dict(item) for item in feed_book if isinstance(item, Mapping)]

    return []


def _normalize_feed_time(feed_time: str) -> str:
    for time_format in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(feed_time, time_format).strftime("%H:%M:%S")
        except ValueError:
            continue
    raise ValueError("feed_time must be HH:MM or HH:MM:SS")


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_str(source: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _ret_description(ret: Any) -> str:
    if isinstance(ret, int) and ret in RESPONSE_CODE_DESCRIPTIONS:
        return RESPONSE_CODE_DESCRIPTIONS[ret]
    return "Unexpected device response"
