# -*- coding: utf-8 -*-
"""The single authorised crossing point for quarantined reference material.

``REFERENCE_QUARANTINE_DECISION`` allows exactly one crossing point and requires
it to preserve the evidence mode in every output.  This module is that point.
It *labels* and *checks*; it never promotes.

Two rules are enforced here:

1. Strict-path modules must not import a quarantined module.  They may accept
   reference material only as an already-constructed object passed across this
   boundary, wrapped in a ``ReferenceEnvelope``.
2. Crossing must not change the evidence class.  ``preserve_evidence_mode``
   refuses any output whose mode differs from the source envelope, and
   ``promote_to_native`` refuses unconditionally.

The quarantine list and the strict-path package list are declared here so the
AST/import guard in ``tests/battle_sandbox/test_reference_quarantine.py`` has a
single source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NoReturn

from hsr_battle_agent.battle_sandbox.evidence_boundary import (
    EvidenceBoundaryError,
    EvidenceMode,
    ReferenceProfile,
    evidence_mode_of,
    is_reference_wrapper,
)

__all__ = [
    "QUARANTINED_MODULES",
    "QUARANTINED_SUBMODULES",
    "REFERENCE_BOUNDARY_MODULE",
    "STRICT_PATH_PACKAGES",
    "BoundaryCrossingError",
    "ReferenceEnvelope",
    "assert_reference_only",
    "envelope",
    "is_quarantined_module",
    "preserve_evidence_mode",
    "promote_to_native",
    "quarantined_module_names",
]


class BoundaryCrossingError(EvidenceBoundaryError):
    """Raised on an illegal or evidence-losing crossing of the boundary."""


#: The module that is permitted to be the crossing point.
REFERENCE_BOUNDARY_MODULE = "hsr_battle_agent.battle_sandbox.reference_boundary"

#: Packages that form the strict, native-evidenced path.
STRICT_PATH_PACKAGES = ("hsr_battle_agent.battle_sandbox",)

#: Quarantined reference modules, exactly as the master decision records them.
#: ``scenario_compiler`` is quarantined for its wave behaviour; the module is
#: listed whole because the strict path must not import any of it.
QUARANTINED_MODULES = (
    "hsr_battle_agent.game_data.target_semantics_reference",
    "hsr_battle_agent.game_data.modifier_lifecycle_reference",
    "hsr_battle_agent.game_data.scenario_compiler",
    "hsr_battle_agent.game_data.reference_execution",
    "hsr_battle_agent.game_data.cross_family_execution_reference",
)

#: Bare submodule names, for source-level scans that do not resolve packages.
QUARANTINED_SUBMODULES = tuple(
    name.rsplit(".", 1)[-1] for name in QUARANTINED_MODULES
)


def quarantined_module_names() -> tuple[str, ...]:
    """Return the quarantined module list (the declaration itself)."""
    return QUARANTINED_MODULES


def is_quarantined_module(module_name: str) -> bool:
    """True when ``module_name`` is, or is a submodule of, a quarantined module."""
    if not isinstance(module_name, str):
        return False
    return any(
        module_name == quarantined or module_name.startswith(quarantined + ".")
        for quarantined in QUARANTINED_MODULES
    )


@dataclass(frozen=True)
class ReferenceEnvelope:
    """The only shape reference material may take when it crosses.

    The envelope carries the originating module and the evidence mode so that
    downstream consumers, snapshots and hashes can see the class explicitly.
    """

    source_module: str
    reference_id: str
    evidence_mode: EvidenceMode
    payload: Any = None

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_mode, EvidenceMode):
            raise BoundaryCrossingError(
                f"ReferenceEnvelope.evidence_mode must be an EvidenceMode; got "
                f"{type(self.evidence_mode).__name__}"
            )
        if self.evidence_mode is EvidenceMode.NATIVE_EVIDENCED:
            raise BoundaryCrossingError(
                "ReferenceEnvelope cannot carry NATIVE_EVIDENCED: crossing must "
                "not change the evidence class"
            )
        if not is_quarantined_module(self.source_module):
            raise BoundaryCrossingError(
                "ReferenceEnvelope.source_module must be a quarantined module; "
                f"got {self.source_module!r}"
            )


def envelope(
    profile: ReferenceProfile,
    payload: Any = None,
    *,
    source_module: str,
) -> ReferenceEnvelope:
    """Wrap reference material for a single crossing.

    ``source_module`` must be one of the quarantined modules, and the envelope
    inherits the profile's evidence mode verbatim.
    """
    if not isinstance(profile, ReferenceProfile):
        raise BoundaryCrossingError(
            "envelope() accepts a ReferenceProfile; got "
            f"{type(profile).__name__}"
        )
    return ReferenceEnvelope(
        source_module=source_module,
        reference_id=profile.reference_id,
        evidence_mode=profile.evidence_mode,
        payload=payload,
    )


def assert_reference_only(value: Any) -> Any:
    """Refuse any value that is already native evidence.

    A crossing point deals in reference material only; receiving native
    evidence here means the caller has confused the two paths.
    """
    mode = evidence_mode_of(value)
    if mode is EvidenceMode.NATIVE_EVIDENCED:
        raise BoundaryCrossingError(
            f"{type(value).__name__} is already NATIVE_EVIDENCED; the reference "
            "boundary handles quarantined reference material only"
        )
    if not is_reference_wrapper(value) and not isinstance(
        value, (ReferenceEnvelope, ReferenceProfile)
    ):
        raise BoundaryCrossingError(
            f"{type(value).__name__} is not a boundary-tagged reference object; "
            "wrap it in a ReferenceEnvelope before crossing"
        )
    return value


def preserve_evidence_mode(source: ReferenceEnvelope, output: Any) -> Any:
    """Return ``output`` only if it still carries the source evidence mode.

    This is the rule that makes the crossing point safe for snapshots, hashes
    and traces: an output that lost, upgraded or omitted its evidence mode is a
    hard error rather than a silent promotion.
    """
    if not isinstance(source, ReferenceEnvelope):
        raise BoundaryCrossingError(
            "preserve_evidence_mode expects a ReferenceEnvelope source; got "
            f"{type(source).__name__}"
        )
    output_mode = evidence_mode_of(output)
    if output_mode is None:
        raise BoundaryCrossingError(
            f"output {type(output).__name__} carries no evidence mode; every "
            "object leaving the reference boundary must be labelled"
        )
    if output_mode is not source.evidence_mode:
        raise BoundaryCrossingError(
            "evidence mode changed across the reference boundary: "
            f"{source.evidence_mode.value} -> {output_mode.value} "
            "(reuse never changes evidence class)"
        )
    return output


def promote_to_native(*_args: Any, **_kwargs: Any) -> NoReturn:
    """Refuse reference-to-native promotion unconditionally.

    Present as an explicit guard rail so that any future call site attempting
    promotion fails loudly instead of inventing a native claim.
    """
    raise BoundaryCrossingError(
        "reference material cannot be promoted to native evidence; a native "
        "claim requires its own version/hash-qualified evidence"
    )
