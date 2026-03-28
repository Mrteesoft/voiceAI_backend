from __future__ import annotations

import hashlib
import math
import re

from app.core.config import get_settings

TOKEN_PATTERN = re.compile(r"\w+")


class EmbeddingService:
    def __init__(self) -> None:
        settings = get_settings()
        self.backend = settings.embedding_backend
        self.dimensions = settings.embedding_dimensions

    def embed_text(self, text: str) -> list[float]:
        if self.backend != "hash":
            raise ValueError(
                f"Unsupported EMBEDDING_BACKEND '{self.backend}'. "
                "Add a real embedding provider in app/services/embeddings.py."
            )

        vector = [0.0] * self.dimensions
        tokens = TOKEN_PATTERN.findall(text.lower())
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], byteorder="big") % self.dimensions
            sign = -1.0 if digest[4] % 2 else 1.0
            magnitude = 1.0 + (digest[5] / 255.0)
            vector[index] += sign * magnitude

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]
