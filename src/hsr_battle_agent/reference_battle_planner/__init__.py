"""Deterministic caller-objective planning over M10 local reference battles."""

from .adapter import ReferenceBattleAdapter, ResourceV1Boundary, TransitionAdapter
from .contract import (
    HORIZON_ENTITY, HORIZON_RESOURCE, MIN_ENTITY, MIN_RESOURCE, REACH_ENTITY,
    REACH_RESOURCE, BattlePlannerContractError, ReferenceBattleObjective,
    ReferenceBattleSearchPolicy,
)
from .replay import BattlePlanReplayError, BattlePlanValidation, validate_plan, validate_result
from .search import BattlePlan, BattlePlannerError, BattlePlannerResult, search_battle_plans

__all__ = [
    "HORIZON_ENTITY", "HORIZON_RESOURCE", "MIN_ENTITY", "MIN_RESOURCE",
    "REACH_ENTITY", "REACH_RESOURCE", "BattlePlannerContractError",
    "ReferenceBattleObjective", "ReferenceBattleSearchPolicy", "ReferenceBattleAdapter",
    "ResourceV1Boundary", "TransitionAdapter", "BattlePlan", "BattlePlannerError",
    "BattlePlannerResult", "search_battle_plans", "BattlePlanReplayError",
    "BattlePlanValidation", "validate_plan", "validate_result",
]
