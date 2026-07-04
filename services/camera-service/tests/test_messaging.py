"""Unit tests for FramePublisher and ResultConsumer."""

import json
import threading
from unittest.mock import MagicMock

import numpy as np
import pika
import pytest

from app.messaging.consumer import ResultConsumer
from app.messaging.publisher import FramePublisher
from app.models.messages import (
    DriverResultMessage,
    FrameMessage,
    SeatbeltResultMessage,
)


class TestFramePublisher:
    @pytest.fixture
    def mock_connection_manager(self, mocker):
        mgr = mocker.MagicMock()
        mgr.is_connected = True
        mgr.stop_event = threading.Event()
        channel = mocker.MagicMock()
        channel.is_closed = False
        channel.is_open = True
        mgr.create_channel.return_value = channel
        return mgr

    @pytest.fixture
    def publisher(self, mock_connection_manager):
        return FramePublisher(mock_connection_manager, routing_key="test.frame")

    def test_start_declares_exchange(self, publisher):
        publisher.start()
        publisher._channel.exchange_declare.assert_called_once_with(
            exchange="adas.exchange",
            exchange_type="topic",
            durable=True,
        )

    def test_publish_success(self, publisher):
        publisher.start()
        jpeg = b"fake_jpeg_bytes"
        metadata = FrameMessage(frame_id=1, timestamp=100.0)
        result = publisher.publish(jpeg, metadata)
        assert result is True
        publisher._channel.basic_publish.assert_called_once()

    def test_publish_not_started_returns_false(self, publisher):
        jpeg = b"fake_jpeg_bytes"
        metadata = FrameMessage(frame_id=1, timestamp=100.0)
        result = publisher.publish(jpeg, metadata)
        assert result is False

    def test_publish_retry_on_closed_channel(self, publisher, mock_connection_manager):
        publisher.start()
        publisher._channel.is_closed = True
        new_channel = MagicMock()
        new_channel.is_closed = False
        new_channel.is_open = True
        mock_connection_manager.create_channel.return_value = new_channel

        jpeg = b"fake_jpeg_bytes"
        metadata = FrameMessage(frame_id=1, timestamp=100.0)
        result = publisher.publish(jpeg, metadata)
        assert result is True

    def test_stop(self, publisher):
        publisher.start()
        publisher.stop()
        publisher._channel.close.assert_called_once()


class TestResultConsumer:
    @pytest.fixture
    def mock_connection_manager(self, mocker):
        mgr = mocker.MagicMock()
        mgr.is_connected = True
        mgr.stop_event = threading.Event()
        return mgr

    @pytest.fixture
    def consumer(self, mock_connection_manager):
        return ResultConsumer(mock_connection_manager)

    def test_driver_result_initially_none(self, consumer):
        assert consumer.latest_driver_result is None

    def test_seatbelt_result_initially_none(self, consumer):
        assert consumer.latest_seatbelt_result is None

    def test_on_driver_message_parses_json(self, consumer):
        body = json.dumps({
            "frame_id": 42,
            "timestamp": 100.0,
            "sleepy": True,
            "confidence": 0.95,
        }).encode("utf-8")
        channel = MagicMock()
        method = MagicMock()
        properties = MagicMock()
        properties.headers = {}

        consumer._on_driver_message(channel, method, properties, body)
        result = consumer.latest_driver_result
        assert result is not None
        assert result.frame_id == 42
        assert result.sleepy is True
        assert result.confidence == 0.95

    def test_on_driver_message_invalid_json(self, consumer):
        body = b"not valid json"
        channel = MagicMock()
        method = MagicMock()
        properties = MagicMock()
        properties.headers = {}

        consumer._on_driver_message(channel, method, properties, body)
        assert consumer.latest_driver_result is None

    def test_on_seatbelt_message_parses_json(self, consumer):
        body = json.dumps({
            "frame_id": 100,
            "timestamp": 200.0,
            "seatbelt": True,
            "confidence": 0.88,
        }).encode("utf-8")
        channel = MagicMock()
        method = MagicMock()
        properties = MagicMock()
        properties.headers = {}

        consumer._on_seatbelt_message(channel, method, properties, body)
        result = consumer.latest_seatbelt_result
        assert result is not None
        assert result.frame_id == 100
        assert result.seatbelt is True
        assert result.confidence == 0.88

    def test_callback_invocation(self, consumer):
        callback_called = []

        def callback(result):
            callback_called.append(result)

        consumer.on_driver_result(callback)
        body = json.dumps({
            "frame_id": 1,
            "timestamp": 1.0,
            "sleepy": False,
            "confidence": 0.1,
        }).encode("utf-8")
        consumer._on_driver_message(MagicMock(), MagicMock(), MagicMock(), body)
        assert len(callback_called) == 1
        assert callback_called[0].sleepy is False

    def test_thread_safety_multiple_updates(self, consumer):
        import concurrent.futures

        def update_driver(frame_id):
            body = json.dumps({
                "frame_id": frame_id,
                "timestamp": float(frame_id),
                "sleepy": frame_id % 2 == 0,
                "confidence": 0.5,
            }).encode("utf-8")
            consumer._on_driver_message(MagicMock(), MagicMock(), MagicMock(), body)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(update_driver, i) for i in range(100)]
            concurrent.futures.wait(futures)

        result = consumer.latest_driver_result
        assert result is not None
