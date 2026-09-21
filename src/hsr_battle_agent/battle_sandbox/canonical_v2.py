# -*- coding: utf-8 -*-
"""Strict canonical value grammar for Terra semantic identity.

Mappings are key-sorted only for serialization identity.  Lists retain source
order and duplicates.  Every scalar receives an explicit type tag so null,
bool, integer, finite binary float and string cannot collide.  Raw tuples are
rejected; an authorized tuple must already be carried by the explicit F01
tagged envelope in a validated Terra snapshot.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any

__all__ = [
    "CANONICAL_V2_SCHEMA",
    "CanonicalV2Error",
    "canonical_v2_bytes",
    "canonical_v2_text",
]

CANONICAL_V2_SCHEMA = "terra_canonical/2"


class CanonicalV2Error(ValueError):
    """Raised for values outside the unambiguous canonical grammar."""


def _node(value: Any, where: str) -> dict[str, Any]:
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, int):
        return {"type": "int", "value": str(value)}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalV2Error(f"{where} contains a non-finite number")
        return {"type": "float", "value": value.hex()}
    if isinstance(value, str):
        return {"type": "string", "value": value}
    if isinstance(value, tuple):
        raise CanonicalV2Error(
            f"{where} contains an untagged tuple; raw tuple/list coercion is forbidden"
        )
    if isinstance(value, list):
        return {
            "type": "list",
            "items": [
                _node(item, f"{where}[{index}]")
                for index, item in enumerate(value)
            ],
        }
    if isinstance(value, Mapping):
        keys = tuple(value.keys())
        for key in keys:
            if not isinstance(key, str):
                raise CanonicalV2Error(
                    f"{where} has non-string mapping key {key!r}"
                )
        # Sorting establishes only canonical mapping encoding. It never
        # reorders list/queue contents or supplies an unknown semantic order.
        ordered = sorted(keys, key=lambda key: key.encode("utf-8"))
        return {
            "type": "mapping",
            "items": [
                [key, _node(value[key], f"{where}.{key}")]
                for key in ordered
            ],
        }
    raise CanonicalV2Error(
        f"{where} contains unsupported or ambiguous numeric/value type "
        f"{type(value).__name__}"
    )


def canonical_v2_text(value: Any) -> str:
    document = {
        "schema": CANONICAL_V2_SCHEMA,
        "value": _node(value, "value"),
    }
    return json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def canonical_v2_bytes(value: Any) -> bytes:
    return canonical_v2_text(value).encode("utf-8")
