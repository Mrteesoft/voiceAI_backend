from __future__ import annotations

from pgvector.sqlalchemy import VECTOR
from sqlalchemy.types import JSON, TypeDecorator


class EmbeddingVectorType(TypeDecorator):
    impl = JSON
    cache_ok = True
    comparator_factory = VECTOR.comparator_factory

    def __init__(self, dimensions: int) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(VECTOR(self.dimensions))
        return dialect.type_descriptor(JSON())
