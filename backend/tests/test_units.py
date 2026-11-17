"""Plain unit tests for small pure functions (no database, no HTTP)."""

from dataclasses import dataclass

import pytest

from app.core.config import Settings
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.models import Role
from app.services.attachments import check_signature
from app.services.notifications import extract_mentions
from app.services.ordering import move_item, renumber


@dataclass(eq=False)
class Card:
    name: str
    position: int


def names(cards: list[Card]) -> list[str]:
    return [c.name for c in cards]


def test_move_item_within_list() -> None:
    a, b, c = Card("a", 0), Card("b", 1), Card("c", 2)
    ordered = move_item([a, b, c], c, 0)
    renumber(ordered)
    assert names(ordered) == ["c", "a", "b"]
    assert [x.position for x in ordered] == [0, 1, 2]


def test_move_item_into_other_list_and_clamp() -> None:
    x, new = Card("x", 0), Card("new", 7)
    assert names(move_item([x], new, 50)) == ["x", "new"]
    assert names(move_item([x], new, -3)) == ["new", "x"]


def test_role_ranking() -> None:
    assert Role.OWNER.at_least(Role.ADMIN)
    assert Role.MEMBER.at_least(Role.VIEWER)
    assert not Role.VIEWER.at_least(Role.MEMBER)


def test_extract_mentions() -> None:
    text = "Hi @Sara and @bob_2, mail me at me@example.com, @ab is too short, @@x"
    assert extract_mentions(text) == {"sara", "bob_2"}


@pytest.mark.parametrize(
    ("ext", "head", "ok"),
    [
        (".png", b"\x89PNG\r\n\x1a\nrest", True),
        (".png", b"GIF89a", False),
        (".webp", b"RIFF1234WEBPVP8", True),
        (".webp", b"RIFF1234WAVE", False),
        (".txt", "naïve".encode(), True),
        (".txt", "é".encode()[:1], True),  # chunk cut inside a multi-byte character
        (".txt", b"\xff\xfe\xfa" + b"a" * 10, False),
    ],
)
def test_check_signature(ext: str, head: bytes, ok: bool) -> None:
    assert check_signature(ext, head) is ok


def test_password_hashing() -> None:
    hashed = hash_password("Secret123")
    assert hashed != "Secret123"
    assert verify_password("Secret123", hashed)
    assert not verify_password("secret123", hashed)
    assert not verify_password("Secret123", "not-a-bcrypt-hash")


def test_token_round_trip() -> None:
    assert decode_token(create_token(42, "access"), "access") == 42


def test_cors_origins_from_comma_string() -> None:
    s = Settings(cors_origins="http://a.com, http://b.com")  # type: ignore[arg-type]
    assert s.cors_origins == ["http://a.com", "http://b.com"]


def test_json_log_formatter() -> None:
    import json
    import logging

    from app.core.logging import JsonFormatter, TextFormatter

    record = logging.LogRecord("app", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    record.fields = {"status": 200}
    line = json.loads(JsonFormatter().format(record))
    assert (line["msg"], line["level"], line["status"]) == ("hello world", "INFO", 200)
    assert TextFormatter().format(record) == "INFO    app: hello world status=200"
