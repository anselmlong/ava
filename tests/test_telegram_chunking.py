"""Tests for Telegram message chunking."""

from src.bot.handlers.message import (
    _split_text_for_telegram,
    TELEGRAM_SAFE_MESSAGE_LENGTH,
)


def test_split_text_for_telegram_short() -> None:
    assert _split_text_for_telegram("hello") == ["hello"]


def test_split_text_for_telegram_hard_splits_long_paragraph() -> None:
    text = "a" * (TELEGRAM_SAFE_MESSAGE_LENGTH * 2 + 10)
    chunks = _split_text_for_telegram(text)

    assert len(chunks) >= 3
    assert all(len(c) <= TELEGRAM_SAFE_MESSAGE_LENGTH for c in chunks)
    assert "".join(chunks) == text


def test_split_text_for_telegram_prefers_paragraph_boundaries() -> None:
    long_paragraph = "b" * (TELEGRAM_SAFE_MESSAGE_LENGTH + 20)
    text = "para1\n\n" + long_paragraph + "\n\npara3"

    chunks = _split_text_for_telegram(text)

    assert len(chunks) >= 2
    assert all(len(c) <= TELEGRAM_SAFE_MESSAGE_LENGTH for c in chunks)
    assert chunks[0].startswith("para1")
    assert chunks[-1].endswith("para3")
