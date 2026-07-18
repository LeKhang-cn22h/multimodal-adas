"""Voice Alert Service — TTS + audio playback with per-type cooldown.

Uses Facebook/Meta MMS-TTS-VIE for Vietnamese text-to-speech,
sounddevice for audio playback.

TS-gradio-voice-alert:
    Cooldown per alert type prevents repeated playback within
    the configured window.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np

from app.utils.logger import get_logger

logger = get_logger()

# ── Alert messages ────────────────────────────────────────────────────
MSG_FATIGUE = "Cảnh báo! Tài xế đang buồn ngủ, hãy dừng xe nghỉ ngơi!"
MSG_SEATBELT = "Cảnh báo! Vui lòng thắt dây an toàn!"

# ── Singleton ─────────────────────────────────────────────────────────
_voice_alert_instance: Optional[VoiceAlertService] = None


def set_voice_alert(instance: VoiceAlertService) -> None:
    """Register the active VoiceAlertService instance (called in lifespan)."""
    global _voice_alert_instance
    _voice_alert_instance = instance


def get_voice_alert() -> Optional[VoiceAlertService]:
    """Return the current VoiceAlertService singleton (may be None before lifespan)."""
    return _voice_alert_instance


class VoiceAlertService:
    """Text-to-speech engine with cooldown-based alert gating.

    Loads MMS-TTS-VIE once, reuses for all subsequent calls.
    Alerts are gated by type ("fatigue" | "seatbelt") so that
    each type has its own cooldown timer.

    Supports a "pass-through" mode when the TTS model is not
    loaded (process_result returns None silently).
    """

    def __init__(
        self,
        model_name: str = "facebook/mms-tts-vie",
        cooldown_seconds: float = 10.0,
        device: str = "cpu",
    ) -> None:
        self._model_name = model_name
        self._cooldown = cooldown_seconds
        self._device = device

        # Lazy-loaded TTS components
        self._model: object | None = None
        self._tokenizer: object | None = None
        self._sample_rate: int | None = None
        self._loaded = False

        # Per-type cooldown tracking
        self._last_alert_times: dict[str, float] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        """Download/load MMS-TTS-VIE from HuggingFace (one-time)."""
        if self._loaded:
            return

        logger.info("Loading MMS-TTS model: %s ...", self._model_name)
        try:
            from transformers import VitsModel, VitsTokenizer

            self._tokenizer = VitsTokenizer.from_pretrained(self._model_name)
            self._model = VitsModel.from_pretrained(self._model_name)
            self._model.to(self._device)
            self._sample_rate = getattr(
                self._model.config, "sampling_rate", 16000
            )
            self._loaded = True
            logger.info(
                "MMS-TTS loaded (sample_rate=%d Hz)", self._sample_rate,
            )
        except Exception as exc:
            logger.error("Failed to load TTS model: %s", exc)
            raise

    def close(self) -> None:
        """Release model resources."""
        self._model = None
        self._tokenizer = None
        logger.info("VoiceAlertService closed")

    # ------------------------------------------------------------------
    # Public alert API
    # ------------------------------------------------------------------

    def alert_fatigue(self, level: str) -> bool:
        """Trigger fatigue warning if level warrants it and cooldown passed.

        Returns:
            True if audio was actually played.
        """
        if level not in ("Drowsy", "Dangerous"):
            return False
        return self._try_alert("fatigue", MSG_FATIGUE)

    def alert_seatbelt(self, has_seatbelt: bool) -> bool:
        """Trigger seatbelt warning if not worn and cooldown passed.

        Returns:
            True if audio was actually played.
        """
        if has_seatbelt:
            return False
        return self._try_alert("seatbelt", MSG_SEATBELT)

    def process_result(self, result: dict) -> Optional[str]:
        """Check latest pipeline result and fire appropriate alert.

        Returns:
            The alert type string if an alert was played, else None.
        """
        if result is None or not self._loaded:
            return None

        # Fatigue alert
        level = result.get("fatigue_level", "Unknown")
        if self.alert_fatigue(level):
            return "fatigue"

        # Seatbelt alert
        has_sb = result.get("has_seatbelt", True)
        if self.alert_seatbelt(has_sb):
            return "seatbelt"

        return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _try_alert(self, alert_type: str, text: str) -> bool:
        """Gate an alert by cooldown, then speak."""
        now = time.time()
        with self._lock:
            last = self._last_alert_times.get(alert_type, 0.0)
            if now - last < self._cooldown:
                return False
            self._last_alert_times[alert_type] = now

        self._speak_async(text)
        return True

    def _speak_async(self, text: str) -> None:
        """Play alarm + TTS voice in background thread."""
        threading.Thread(
            target=self._speak, args=(text,), daemon=True,
        ).start()

    def _speak(self, text: str) -> None:
        """Play alarm beeps + TTS voice (voice skipped if model not loaded)."""
        try:
            import sounddevice as sd

            # 1. Alarm beeps (always play)
            alarm = self._make_alarm()
            if alarm is not None:
                sd.play(alarm, samplerate=self._sample_rate or 16000)
                sd.wait()

            # 2. TTS voice (only if model loaded)
            if self._loaded:
                waveform = self._synthesize(text)
                if waveform is not None:
                    sd.play(waveform, samplerate=self._sample_rate)
                    sd.wait()
        except Exception as exc:
            logger.error("Playback error: %s", exc)

    def _make_alarm(self) -> Optional[np.ndarray]:
        """Generate alarm beeps: 3 tones at 800Hz, 200ms each, 100ms gap."""
        sr = self._sample_rate or 16000
        duration_beep = 0.2   # 200ms
        duration_gap = 0.1    # 100ms
        freq = 800            # Hz
        num_beeps = 3

        t_beep = np.linspace(0, duration_beep, int(sr * duration_beep), endpoint=False)
        beep = (np.sin(2 * np.pi * freq * t_beep) * 0.5).astype(np.float32)
        gap = np.zeros(int(sr * duration_gap), dtype=np.float32)

        parts = []
        for _ in range(num_beeps):
            parts.append(beep)
            parts.append(gap)
        return np.concatenate(parts)

    def _synthesize(self, text: str) -> Optional[np.ndarray]:
        """Run TTS model, return float32 waveform or None."""
        from transformers import VitsModel, VitsTokenizer

        tokenizer: VitsTokenizer = self._tokenizer
        model: VitsModel = self._model

        inputs = tokenizer(text, return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with _no_grad():
            output = model(**inputs)

        waveform = output.waveform[0].cpu().numpy()
        return waveform.astype(np.float32)


# ----------------------------------------------------------------------
# Helper
# ----------------------------------------------------------------------

def _no_grad():
    """Return torch.no_grad() context manager (lazy import)."""
    import torch
    return torch.no_grad()
