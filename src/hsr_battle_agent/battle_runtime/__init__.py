# -*- coding: utf-8 -*-
"""Battle runtime implementations over canonical Battle IR values.

Dependency direction:

    IR primitive -> executor dispatch -> battle_runtime implementation

Runtime functions must not import battle_sandbox or provenance decision logic.
"""
from __future__ import annotations

from hsr_battle_agent.battle_runtime.values import dynamic_value_equals

__all__ = ["dynamic_value_equals"]
