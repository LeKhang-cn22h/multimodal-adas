"""Singleton instance of SeatbeltDetector shared across the application."""

from app.services.seatbelt_detector import SeatbeltDetector

detector = SeatbeltDetector()
