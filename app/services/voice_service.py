from __future__ import annotations

import base64
import binascii


class VoiceService:
    def normalize_input(
        self,
        *,
        channel: str,
        message: str,
        platform: str,
        audio_reference: str | None = None,
        audio_input: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, str | int | None]:
        normalized_metadata = metadata or {}
        if channel != "voice":
            return {
                "normalized_text": message.strip(),
                "transcript": None,
                "input_transport": "text-request",
                "audio_format": None,
                "audio_size_bytes": None,
            }

        transcript_hint = self._safe_string(normalized_metadata.get("transcript"))
        audio_payload = audio_input or {}
        audio_base64 = self._safe_string(audio_payload.get("audio_base64"))
        audio_format = self._safe_string(audio_payload.get("audio_format")) or "wav"

        transcript = transcript_hint or message.strip()
        input_transport = "websocket-audio" if audio_reference else "voice-transcript"
        audio_size_bytes: int | None = None

        if audio_base64:
            transcription_result = self.transcribe_audio(
                audio_base64=audio_base64,
                audio_format=audio_format,
                transcript_hint=self._safe_string(audio_payload.get("transcript_hint")) or transcript_hint,
            )
            transcript = transcription_result["transcript"]
            audio_size_bytes = transcription_result["audio_size_bytes"]
            input_transport = "inline-audio-payload"

        if platform == "ivr":
            input_transport = "telephony-bridge"

        return {
            "normalized_text": transcript,
            "transcript": transcript,
            "input_transport": input_transport,
            "audio_format": audio_format if audio_base64 else None,
            "audio_size_bytes": audio_size_bytes,
        }

    def build_voice_response(
        self,
        *,
        channel: str,
        platform: str,
        reply: str,
        preferred_format: str | None = None,
    ) -> dict[str, object] | None:
        if channel != "voice":
            return None

        transport = "websocket-stream"
        audio_format = preferred_format or "pcm16"
        sample_rate_hz = 16000
        if platform == "ivr":
            transport = "sip-bridge"
            audio_format = "pcm16"
            sample_rate_hz = 8000
        elif platform == "whatsapp":
            transport = "voice-note-webhook"
            audio_format = "ogg-opus"
            sample_rate_hz = 16000

        return {
            "transport": transport,
            "audio_format": audio_format,
            "sample_rate_hz": sample_rate_hz,
            "voice_prompt": reply,
            "audio_base64": self.synthesize_audio(reply=reply, audio_format=audio_format),
        }

    def transcribe_audio(
        self,
        *,
        audio_base64: str,
        audio_format: str,
        transcript_hint: str | None = None,
    ) -> dict[str, str | int]:
        raw_bytes = self._decode_audio_payload(audio_base64)
        transcript = transcript_hint or self._decode_text_like_audio(raw_bytes)
        if not transcript:
            transcript = f"Mock transcript from {audio_format} audio ({len(raw_bytes)} bytes)."

        return {
            "transcript": transcript,
            "audio_size_bytes": len(raw_bytes),
        }

    def synthesize_audio(self, *, reply: str, audio_format: str) -> str:
        synthetic_audio = f"MOCK-{audio_format.upper()}::{reply}".encode("utf-8")
        return base64.b64encode(synthetic_audio).decode("utf-8")

    def _decode_audio_payload(self, audio_base64: str) -> bytes:
        try:
            return base64.b64decode(audio_base64, validate=True)
        except (ValueError, binascii.Error):
            return audio_base64.encode("utf-8")

    def _decode_text_like_audio(self, raw_bytes: bytes) -> str | None:
        try:
            decoded = raw_bytes.decode("utf-8").strip()
        except UnicodeDecodeError:
            return None

        if not decoded:
            return None

        if any((not char.isprintable()) and (not char.isspace()) for char in decoded):
            return None

        return " ".join(decoded.split())

    def _safe_string(self, value: object | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
