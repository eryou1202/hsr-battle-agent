# -*- coding: utf-8 -*-
"""Owned Terra state stores.

TERRA F02-006 introduces the store classification and ownership catalog.
F02-007 adds the concrete stores under ``stores/core.py`` and
``battle_sandbox/opaque.py``.

Every state field family has exactly one owner, and that owner declares which
store class it belongs to.  Nothing may be written through a class that does not
own it, and the generic ``extensions`` bag is explicitly not writable on the
Terra path.
"""
from __future__ import annotations

from hsr_battle_agent.battle_sandbox.stores.protocols import (
    FROZEN_FIELD_FAMILIES,
    OWNERSHIP_CATALOG,
    STORE_CLASSES,
    StoreClass,
    StoreOwnershipError,
    StoreOwner,
    frozen_field_families,
    owner_for,
    require_writable,
    validate_catalog,
)

__all__ = [
    "FROZEN_FIELD_FAMILIES",
    "OWNERSHIP_CATALOG",
    "STORE_CLASSES",
    "StoreClass",
    "StoreOwnershipError",
    "StoreOwner",
    "frozen_field_families",
    "owner_for",
    "require_writable",
    "validate_catalog",
]
