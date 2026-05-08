"""Sender-id parsing for phone and Business-Scoped User ID (BSUID) inputs.

Meta's June 2026 BSUID rollout means `message.from` may be either an E.164
phone or an opaque per-user identifier. `core.sender_id.parse_sender_id`
disambiguates without rejecting BSUIDs as "invalid sender".
"""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "raw,expected_value",
    [
        ("37368826828", "37368826828"),
        ("5219841050808", "529841050808"),  # MX 521-prefix normalization
        ("9841050808", "9841050808"),
    ],
)
def test_parse_phone_returns_normalized_phone(raw: str, expected_value: str) -> None:
    from core.sender_id import parse_sender_id

    sender = parse_sender_id(raw)

    assert sender is not None
    assert sender.id_type == "phone"
    assert sender.is_phone is True
    assert sender.is_bsuid is False
    assert sender.value == expected_value


@pytest.mark.parametrize(
    "raw",
    [
        "abc12345",  # 8 chars, alphanumeric
        "user_2026.0001:meta",
        "BSUID-abcdef-12345-67890",
        "X" * 64,  # within max length
    ],
)
def test_parse_bsuid_returns_bsuid(raw: str) -> None:
    """Non-phone identifiers that look like opaque BSUIDs are accepted as-is."""
    from core.sender_id import parse_sender_id

    sender = parse_sender_id(raw)

    assert sender is not None, f"{raw!r} should parse"
    assert sender.id_type == "bsuid"
    assert sender.is_bsuid is True
    assert sender.value == raw


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "a",  # too short for BSUID
        "ab",
        "abcdefg",  # 7 chars, just under min
        "X" * 200,  # too long
        "https://attacker.invalid",  # contains non-id chars
        "<script>alert(1)</script>",
        "abc def",  # whitespace inside
    ],
)
def test_parse_rejects_unrecognized_input(raw: str) -> None:
    from core.sender_id import parse_sender_id

    assert parse_sender_id(raw) is None, f"{raw!r} must not parse"


def test_is_valid_recipient_accepts_phone_and_bsuid() -> None:
    from core.sender_id import is_valid_recipient

    assert is_valid_recipient("37368826828") is True
    assert is_valid_recipient("user_2026.0001:meta") is True
    assert is_valid_recipient("") is False
    assert is_valid_recipient("a") is False


def test_mask_sender_id_distinguishes_phone_and_bsuid() -> None:
    from core.sender_id import SenderId, mask_sender_id

    phone = SenderId(value="37368826828", id_type="phone")
    bsuid = SenderId(value="abcdef123456", id_type="bsuid")

    phone_masked = mask_sender_id(phone)
    bsuid_masked = mask_sender_id(bsuid)

    # Phone masking keeps the last 4 digits.
    assert phone_masked.endswith("6828")
    # BSUID masking is type-prefixed so logs distinguish the two id flavours.
    assert bsuid_masked.startswith("bsuid:")
    assert "3456" in bsuid_masked
