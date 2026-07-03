"""Unit tests for message models."""

import pytest
from pydantic import ValidationError

from app.models.messages import DriverResultMessage, FrameMessage, SeatbeltResultMessage


class TestFrameMessage:
    def test_valid_frame_message(self):
        msg = FrameMessage(frame_id=42, timestamp=1234567890.123)
        assert msg.frame_id == 42
        assert msg.timestamp == 1234567890.123

    def test_frame_message_defaults(self):
        msg = FrameMessage(frame_id=0, timestamp=0.0)
        assert msg.frame_id == 0
        assert msg.timestamp == 0.0

    def test_frame_message_missing_fields_raises(self):
        with pytest.raises(ValidationError):
            FrameMessage()

    def test_frame_message_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            FrameMessage(frame_id="abc", timestamp=1.0)


class TestDriverResultMessage:
    def test_valid_sleepy_true(self):
        msg = DriverResultMessage(
            frame_id=100,
            timestamp=1234567890.5,
            sleepy=True,
            confidence=0.95,
        )
        assert msg.sleepy is True
        assert msg.confidence == 0.95

    def test_valid_sleepy_false(self):
        msg = DriverResultMessage(
            frame_id=200,
            timestamp=1234567891.0,
            sleepy=False,
            confidence=0.12,
        )
        assert msg.sleepy is False
        assert msg.confidence == 0.12

    def test_defaults(self):
        msg = DriverResultMessage(
            frame_id=1,
            timestamp=1.0,
        )
        assert msg.sleepy is False
        assert msg.confidence == 0.0

    def test_invalid_json(self):
        with pytest.raises(ValidationError):
            DriverResultMessage(**{"frame_id": "x", "timestamp": 1.0})


class TestSeatbeltResultMessage:
    def test_valid_seatbelt_true(self):
        msg = SeatbeltResultMessage(
            frame_id=300,
            timestamp=1234567892.0,
            seatbelt=True,
            confidence=0.88,
        )
        assert msg.seatbelt is True
        assert msg.confidence == 0.88

    def test_valid_seatbelt_false(self):
        msg = SeatbeltResultMessage(
            frame_id=400,
            timestamp=1234567893.0,
            seatbelt=False,
            confidence=0.05,
        )
        assert msg.seatbelt is False

    def test_defaults(self):
        msg = SeatbeltResultMessage(
            frame_id=1,
            timestamp=1.0,
        )
        assert msg.seatbelt is False
        assert msg.confidence == 0.0
