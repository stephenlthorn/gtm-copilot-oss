from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.types import TypeDecorator, Text


class TiDBVector(TypeDecorator):
    """SQLAlchemy type for TiDB VECTOR(n) columns.

    Stores vectors as JSON strings internally for TiDB's native VECTOR type.
    TiDB uses VEC_COSINE_DISTANCE() and VEC_L2_DISTANCE() for similarity search.
    """

    impl = Text
    cache_ok = True

    def __init__(self, dimensions: int = 1536) -> None:
        super().__init__()
        self.dimensions = dimensions

    def get_col_spec(self) -> str:
        return f"VECTOR({self.dimensions})"

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if not isinstance(parsed, list) or not all(isinstance(x, (int, float)) for x in parsed):
                    raise ValueError(f"Invalid vector string: expected JSON array of numbers")
            except (json.JSONDecodeError, ValueError):
                raise ValueError(f"Invalid vector string: not valid JSON")
            return value
        if isinstance(value, list):
            if value and not all(isinstance(x, (int, float)) for x in value):
                raise ValueError("Vector must contain only numbers")
            return json.dumps(value)
        raise TypeError(f"Cannot store {type(value).__name__} as vector")

    def process_result_value(self, value: Any, dialect: Any) -> list[float] | None:
        if value is None:
            return None
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return None
        return None


def vec_cosine_distance(col: Any, vec: Any) -> Any:
    return func.VEC_COSINE_DISTANCE(col, vec)


def vec_l2_distance(col: Any, vec: Any) -> Any:
    return func.VEC_L2_DISTANCE(col, vec)
