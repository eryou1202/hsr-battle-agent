"""Deterministic reference semantics for DynamicValue storage and formulas.

This is the COMPILER-DYNAMIC-VALUE-001 semantics companion, not a production
battle runtime.  It reconstructs two layers:

1. ``PostfixExpr`` serialization.  TurnBasedGameData emits formula bytecode
   as a base64 ``OpCodes`` string plus ordered ``FixedValues`` and
   ``DynamicHashes`` arrays.  The selected decoder treats ``0x00``/``0x01``
   as two-byte operand tokens (fixed value / dynamic value plus index),
   ``0x02..0x0f`` as operations, and ``0x11`` as END.  Operation semantics
   are selected as: ADD=0x02, SUB=0x03, MUL=0x04, DIV=0x05, NEG=0x0e.
   This is an R2/R3 cross-source selected model anchored by the 1347 formula
   instances in the reviewed corpus; it is explicit whenever an operation is
   unsupported or an operand cannot be resolved.

2. DynamicValue store semantics.  ``DefineDynamicValue`` creates a key on
   the selected scope owner when absent (optionally with ``ResetValue``);
   ``SetDynamicValue`` evaluates the value expression and overwrites the key.
   The default scope when ``ContextScope`` is absent is selected as the
   caster context and remains an explicit ambiguity.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, replace
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext
from typing import Any, Callable, Mapping, Sequence

DynamicResolver = Callable[[int], Decimal | int | float | str]


class DynamicValueSemanticError(ValueError):
    """A formula or store transition cannot be reconstructed safely."""


class UnsupportedFormulaOperation(DynamicValueSemanticError):
    """The bytecode uses an operation outside the selected model."""


END = 0x11
OPERAND_FIXED = 0x00
OPERAND_DYNAMIC = 0x01
ADD = 0x02
SUB = 0x03
MUL = 0x04
DIV = 0x05
NEG = 0x0E

BINARY_OPERATIONS = {ADD: "ADD", SUB: "SUB", MUL: "MUL", DIV: "DIV"}
UNARY_OPERATIONS = {NEG: "NEG"}
ALL_OPERATIONS = {**BINARY_OPERATIONS, **UNARY_OPERATIONS}


def _decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise DynamicValueSemanticError("boolean is not a numeric formula operand")
    if isinstance(value, (int, float, str)):
        try:
            return Decimal(str(value))
        except InvalidOperation as error:
            raise DynamicValueSemanticError(f"non-numeric formula operand: {value!r}") from error
    raise DynamicValueSemanticError(f"non-numeric formula operand: {value!r}")


@dataclass(frozen=True)
class FormulaOperand:
    kind: str
    index: int
    token_start: int


@dataclass(frozen=True)
class FormulaToken:
    offset: int
    op: int | None
    operand: FormulaOperand | None

    def describe(self) -> str:
        if self.operand is not None:
            return f"{self.operand.kind}[{self.operand.index}]"
        if self.op in ALL_OPERATIONS:
            return ALL_OPERATIONS[self.op]
        if self.op == END:
            return "END"
        return f"OP_0x{self.op:02X}"


@dataclass(frozen=True)
class PostfixProgram:
    """Decoded and validated PostfixExpr bytecode."""

    tokens: tuple[FormulaToken, ...]
    opcode_source: str
    fixed_values: tuple[Decimal, ...]
    dynamic_hashes: tuple[int, ...]

    @property
    def operations(self) -> tuple[int, ...]:
        return tuple(token.op for token in self.tokens if token.op is not None and token.op != END)

    @property
    def operand_count(self) -> int:
        return sum(token.operand is not None for token in self.tokens)

    def to_infix(self) -> str:
        stack: list[str] = []
        for token in self.tokens:
            if token.operand is not None:
                stack.append(token.describe())
            elif token.op == END:
                continue
            elif token.op in BINARY_OPERATIONS:
                if len(stack) < 2:
                    raise DynamicValueSemanticError("malformed binary formula")
                right, left = stack.pop(), stack.pop()
                stack.append(f"({left} {ALL_OPERATIONS[token.op]} {right})")
            elif token.op in UNARY_OPERATIONS:
                if not stack:
                    raise DynamicValueSemanticError("malformed unary formula")
                stack.append(f"({ALL_OPERATIONS[token.op]} {stack.pop()})")
            else:
                stack.append(f"OP_0x{token.op:02X}({', '.join(stack[-2:]) if len(stack) >= 2 else stack})")
        if len(stack) != 1:
            raise DynamicValueSemanticError("formula stack did not reduce to one value")
        return stack[0]

    def evaluate(self, dynamic_resolver: DynamicResolver) -> Decimal:
        """Evaluate the selected-operation formula with Decimal arithmetic.

        The resolver maps a signed 32-bit DynamicHash to a numeric value.
        Division uses 38 significant digits and raises on division by zero;
        the caller records rounding provenance.
        """
        stack: list[Decimal] = []
        for token in self.tokens:
            if token.operand is not None:
                operand = token.operand
                if operand.kind == "FIXED":
                    if not 0 <= operand.index < len(self.fixed_values):
                        raise DynamicValueSemanticError(f"fixed operand index {operand.index} out of range")
                    stack.append(self.fixed_values[operand.index])
                elif operand.kind == "DYNAMIC":
                    if not 0 <= operand.index < len(self.dynamic_hashes):
                        raise DynamicValueSemanticError(f"dynamic operand index {operand.index} out of range")
                    key = self.dynamic_hashes[operand.index]
                    stack.append(_decimal(dynamic_resolver(key)))
                else:
                    raise DynamicValueSemanticError(f"unknown operand kind {operand.kind}")
            elif token.op == END:
                continue
            elif token.op in BINARY_OPERATIONS:
                if len(stack) < 2:
                    raise DynamicValueSemanticError("malformed binary formula")
                right, left = stack.pop(), stack.pop()
                with localcontext() as context:
                    context.prec = 38
                    try:
                        if token.op == ADD:
                            result = left + right
                        elif token.op == SUB:
                            result = left - right
                        elif token.op == MUL:
                            result = left * right
                        elif token.op == DIV:
                            if right == 0:
                                raise DivisionByZero
                            result = left / right
                    except DivisionByZero as error:
                        raise DynamicValueSemanticError("formula division by zero") from error
                stack.append(result)
            elif token.op in UNARY_OPERATIONS:
                if not stack:
                    raise DynamicValueSemanticError("malformed unary formula")
                if token.op == NEG:
                    stack.append(-stack.pop())
            else:
                raise UnsupportedFormulaOperation(f"unsupported formula operation 0x{token.op:02X}")
        if len(stack) != 1:
            raise DynamicValueSemanticError("formula stack did not reduce to one value")
        return stack[0]


def decode_postfix_program(opcodes: str, fixed_values: Sequence[Any], dynamic_hashes: Sequence[int]) -> PostfixProgram:
    """Decode a TurnBasedGameData PostfixExpr into a validated program."""
    if not isinstance(opcodes, str) or not opcodes:
        raise DynamicValueSemanticError("PostfixExpr OpCodes must be a non-empty base64 string")
    try:
        raw = base64.b64decode(opcodes, validate=True)
    except Exception as error:  # noqa: BLE001 - normalize malformed base64
        raise DynamicValueSemanticError(f"invalid PostfixExpr OpCodes: {opcodes!r}") from error
    if not raw:
        raise DynamicValueSemanticError("PostfixExpr OpCodes decoded to empty bytes")
    tokens: list[FormulaToken] = []
    offset = 0
    while offset < len(raw):
        byte = raw[offset]
        if byte in {OPERAND_FIXED, OPERAND_DYNAMIC}:
            if offset + 1 >= len(raw):
                raise DynamicValueSemanticError("truncated formula operand token")
            index = raw[offset + 1]
            kind = "FIXED" if byte == OPERAND_FIXED else "DYNAMIC"
            tokens.append(FormulaToken(offset=offset, op=None, operand=FormulaOperand(kind=kind, index=index, token_start=offset)))
            offset += 2
            continue
        if byte == END:
            tokens.append(FormulaToken(offset=offset, op=END, operand=None))
            if offset != len(raw) - 1:
                raise DynamicValueSemanticError("formula has bytes after END")
            offset += 1
            continue
        if byte in ALL_OPERATIONS:
            tokens.append(FormulaToken(offset=offset, op=byte, operand=None))
            offset += 1
            continue
        raise UnsupportedFormulaOperation(f"unsupported formula token 0x{byte:02X} at offset {offset}")
    if not tokens or tokens[-1].op != END:
        raise DynamicValueSemanticError("formula does not end with END")
    if not any(token.operand is not None for token in tokens):
        raise DynamicValueSemanticError("formula has no operands")
    program = PostfixProgram(
        tokens=tuple(tokens),
        opcode_source=opcodes,
        fixed_values=tuple(_decimal(value.get("Value") if isinstance(value, Mapping) else value) for value in fixed_values),
        dynamic_hashes=tuple(int(value) for value in dynamic_hashes),
    )
    # Validate operand ranges eagerly.
    for token in tokens:
        if token.operand is None:
            continue
        operand = token.operand
        if operand.kind == "FIXED" and not 0 <= operand.index < len(program.fixed_values):
            raise DynamicValueSemanticError(f"fixed operand index {operand.index} out of range")
        if operand.kind == "DYNAMIC" and not 0 <= operand.index < len(program.dynamic_hashes):
            raise DynamicValueSemanticError(f"dynamic operand index {operand.index} out of range")
    return program


@dataclass(frozen=True)
class DynamicValueSpec:
    """Canonical value expression: fixed value or formula program."""

    is_dynamic: bool
    fixed_value: Decimal | None
    program: PostfixProgram | None

    def evaluate(self, dynamic_resolver: DynamicResolver) -> Decimal:
        if not self.is_dynamic:
            if self.fixed_value is None:
                raise DynamicValueSemanticError("non-dynamic spec has no fixed value")
            return self.fixed_value
        if self.program is None:
            raise DynamicValueSemanticError("dynamic spec has no program")
        return self.program.evaluate(dynamic_resolver)


def value_spec_from_payload(value: Any) -> DynamicValueSpec:
    """Canonicalize ``{IsDynamic, FixedValue|PostfixExpr}`` payloads."""
    if not isinstance(value, Mapping):
        raise DynamicValueSemanticError("value expression must be a mapping")
    is_dynamic = bool(value.get("IsDynamic", False))
    if not is_dynamic:
        fixed = value.get("FixedValue")
        if isinstance(fixed, Mapping):
            fixed = fixed.get("Value")
        if fixed is None:
            raise DynamicValueSemanticError("non-dynamic value expression has no FixedValue")
        return DynamicValueSpec(is_dynamic=False, fixed_value=_decimal(fixed), program=None)
    postfix = value.get("PostfixExpr")
    if not isinstance(postfix, Mapping):
        raise DynamicValueSemanticError("dynamic value expression has no PostfixExpr")
    program = decode_postfix_program(
        str(postfix.get("OpCodes", "")),
        postfix.get("FixedValues", []),
        [int(item) for item in postfix.get("DynamicHashes", [])],
    )
    return DynamicValueSpec(is_dynamic=True, fixed_value=None, program=program)


def dynamic_key_from_payload(value: Any) -> str:
    """Extract the stable DynamicKey string from ``"x"`` or ``{"Value": "x"}``."""
    if isinstance(value, str) and value:
        return value
    if isinstance(value, Mapping):
        nested = value.get("Value")
        if isinstance(nested, str) and nested:
            return nested
    raise DynamicValueSemanticError(f"DynamicKey payload is not a non-empty string: {value!r}")


@dataclass(frozen=True)
class DynamicValueTransition:
    store: "DynamicValueStore"
    action: str
    owner_id: str
    key: str
    value: Decimal | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "owner_id": self.owner_id,
            "key": self.key,
            "value": None if self.value is None else str(self.value),
        }


@dataclass(frozen=True)
class DynamicValueStore:
    """Immutable owner -> key -> Decimal store with deterministic transitions."""

    values: Mapping[str, Mapping[str, str]] = ()

    @staticmethod
    def empty() -> "DynamicValueStore":
        return DynamicValueStore(values={})

    def _owner_buckets(self) -> dict[str, Mapping[str, str]]:
        return {str(owner): dict(bucket) for owner, bucket in self.values.items()} if isinstance(self.values, Mapping) else {}

    def read(self, owner_id: str, key: str) -> Decimal:
        bucket = self._owner_buckets().get(owner_id, {})
        if key not in bucket:
            raise KeyError((owner_id, key))
        return Decimal(bucket[key])

    def define(self, owner_id: str, key: str, reset_value: Any | None = None) -> DynamicValueTransition:
        buckets = self._owner_buckets()
        bucket = buckets.setdefault(owner_id, {})
        if key in bucket:
            return DynamicValueTransition(self, "DEFINE_ALREADY_PRESENT", owner_id, key)
        reset = None
        if isinstance(reset_value, Mapping) and ("IsDynamic" in reset_value or "FixedValue" in reset_value or "PostfixExpr" in reset_value):
            reset_spec = value_spec_from_payload(reset_value)
            if reset_spec.is_dynamic:
                raise DynamicValueSemanticError("DefineDynamicValue ResetValue must be fixed in the selected model")
            reset = reset_spec.fixed_value
        elif isinstance(reset_value, Mapping) and "Value" in reset_value:
            reset = _decimal(reset_value.get("Value"))
        elif reset_value is not None:
            reset = _decimal(reset_value)
        if reset is None:
            reset = Decimal("0")
        bucket[key] = str(reset)
        return DynamicValueTransition(DynamicValueStore(values=buckets), "DEFINE_INITIALIZED", owner_id, key, reset)

    def set_value(self, owner_id: str, key: str, value: Decimal) -> DynamicValueTransition:
        buckets = self._owner_buckets()
        bucket = buckets.setdefault(owner_id, {})
        bucket[key] = str(value)
        return DynamicValueTransition(DynamicValueStore(values=buckets), "SET_VALUE", owner_id, key, value)

    def snapshot(self) -> dict[str, dict[str, str]]:
        return {owner: dict(bucket) for owner, bucket in sorted(self._owner_buckets().items())}


# Selected scope-resolution defaults.  The scope itself remains an R3 choice
# whenever the source does not record a target context.
SCOPE_CONTEXT_CASTER = "ContextCaster"
SCOPE_CONTEXT_OWNER = "ContextOwner"
SCOPE_CONTEXT_MODIFIER = "ContextModifier"
SCOPE_TARGET_ENTITY = "TargetEntity"
SCOPE_CONTEXT_ABILITY = "ContextAbility"
DEFAULT_SCOPE = SCOPE_CONTEXT_CASTER


def context_scope_from_payload(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    return DEFAULT_SCOPE
