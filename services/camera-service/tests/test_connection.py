"""Unit tests for RabbitMQ connection manager."""

import threading
import time

import pika
import pytest
from pika.exceptions import AMQPConnectionError

from app.messaging.connection import RabbitMQConnectionManager


class TestRabbitMQConnectionManager:
    def test_init_defaults(self):
        mgr = RabbitMQConnectionManager()
        assert mgr._host == "localhost"
        assert mgr._port == 5672
        assert mgr.is_connected is False

    def test_init_custom(self):
        mgr = RabbitMQConnectionManager(
            host="rabbitmq",
            port=5673,
            virtual_host="adas",
            username="admin",
            password="secret",
        )
        assert mgr._host == "rabbitmq"
        assert mgr._port == 5673
        assert mgr._virtual_host == "adas"
        assert mgr._username == "admin"
        assert mgr._password == "secret"

    def test_stop_event_initially_not_set(self):
        mgr = RabbitMQConnectionManager()
        assert not mgr.stop_event.is_set()

    def test_close_sets_stop_event(self):
        mgr = RabbitMQConnectionManager()
        mgr._connection = None
        mgr.close()
        assert mgr.stop_event.is_set()

    def test_create_channel_without_connection_raises(self):
        mgr = RabbitMQConnectionManager()
        with pytest.raises(RuntimeError, match="not connected"):
            mgr.create_channel()

    def test_connect_stops_on_stop_event(self, mocker):
        mgr = RabbitMQConnectionManager()
        mgr.stop_event.set()
        mock_params = mocker.patch("pika.ConnectionParameters")
        mock_connection = mocker.patch("pika.BlockingConnection")

        mgr.connect()
        mock_connection.assert_not_called()

    def test_connect_retry_on_failure(self, mocker):
        mgr = RabbitMQConnectionManager()
        mgr._stop_event = threading.Event()

        call_count = [0]

        def mock_connect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise AMQPConnectionError("test error")
            mock_conn = mocker.MagicMock()
            mock_conn.is_open = True
            return mock_conn

        mocker.patch("pika.ConnectionParameters")
        mocker.patch("pika.BlockingConnection", side_effect=mock_connect)
        mocker.patch("time.sleep")

        mgr.connect()
        assert call_count[0] >= 3

    def test_is_connected_false_when_no_connection(self):
        mgr = RabbitMQConnectionManager()
        assert mgr.is_connected is False

    def test_is_connected_true_after_successful_connect(self, mocker):
        mgr = RabbitMQConnectionManager()
        mock_conn = mocker.MagicMock()
        mock_conn.is_open = True
        mocker.patch("pika.ConnectionParameters")
        mocker.patch("pika.BlockingConnection", return_value=mock_conn)
        mgr.connect()
        assert mgr.is_connected is True
