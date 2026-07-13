"""Singleton instance of CameraManager shared across the application."""

from app.services.camera_manager import CameraManager

camera_manager = CameraManager()
