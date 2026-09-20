# -*- coding: utf-8 -*-
"""Reference-quarantine guard-rail tests.

These tests enforce ``REFERENCE_QUARANTINE_DECISION``:

* ``ReferenceProfile`` / ``ReferenceDescriptor`` / ``ReferenceResult`` and
  ``ReferenceRegistry`` can never satisfy ``NativeContract`` or
  ``GateCertificate`` APIs;
* native and reference registries are separate types;
* only ``reference_boundary`` is a crossing point, and crossing preserves the
  evidence mode;
* no strict-path module imports a quarantined reference module.

They are guard-rail tests only: they assert type separation and import
boundaries, and deliberately exercise no battle behaviour.
"""
from __future__ import annotations

import ast
import importlib
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_sandbox import evidence_boundary as eb  # noqa: E402
from hsr_battle_agent.battle_sandbox import reference_boundary as rb  # noqa: E402

SRC = REPO / "src"
STRICT_PATH_DIR = SRC / "hsr_battle_agent" / "battle_sandbox"


def strict_path_files() -> list[Path]:
    return sorted(STRICT_PATH_DIR.rglob("*.py"))


def module_name_for(path: Path) -> str:
    return ".".join(path.relative_to(SRC).with_suffix("").parts)


def imported_modules(path: Path) -> set[str]:
    """Every dotted module path named by an import statement in ``path``.

    Relative imports are resolved against the file's own package, and
    ``from package import symbol`` records both ``package`` and
    ``package.symbol`` so that a submodule pulled in as a symbol is caught.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = module_name_for(path).rpartition(".")[0]
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package
                for _ in range(node.level - 1):
                    base = base.rpartition(".")[0]
                target = f"{base}.{node.module}" if node.module else base
            else:
                target = node.module or ""
            if target:
                found.add(target)
                for alias in node.names:
                    found.add(f"{target}.{alias.name}")
    return found


def string_literals(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


class TestEvidenceModes(unittest.TestCase):
    def test_frozen_evidence_mode_spellings(self):
        # The four modes are exactly the Astra freeze spellings.
        self.assertEqual(
            eb.EVIDENCE_MODE_NAMES,
            (
                "NATIVE_EVIDENCED",
                "REFERENCE_MODEL",
                "SANDBOX_EXTENSION",
                "UNSUPPORTED",
            ),
        )
        self.assertIs(eb.NATIVE_EVIDENCE_MODE, eb.EvidenceMode.NATIVE_EVIDENCED)
        self.assertNotIn(eb.NATIVE_EVIDENCE_MODE, eb.NON_NATIVE_EVIDENCE_MODES)
        self.assertEqual(
            eb.NON_NATIVE_EVIDENCE_MODES,
            frozenset(
                {
                    eb.EvidenceMode.REFERENCE_MODEL,
                    eb.EvidenceMode.SANDBOX_EXTENSION,
                    eb.EvidenceMode.UNSUPPORTED,
                }
            ),
        )


class TestReferenceCannotSatisfyNativeApis(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = eb.ReferenceProfile(
            "reference.packet.example",
            assumptions=("explicit caller selection",),
            exclusions=("native arithmetic",),
        )
        self.descriptor = eb.ReferenceDescriptor("descriptor.example", self.profile)
        self.result = eb.ReferenceResult(self.profile, payload={"ok": True})
        self.reference_registry = eb.ReferenceRegistry()
        self.wrappers = (
            self.profile,
            self.descriptor,
            self.result,
            self.reference_registry,
        )

    def test_reference_profile_cannot_claim_native_evidence(self):
        with self.assertRaises(eb.EvidenceBoundaryError):
            eb.ReferenceProfile(
                "reference.illegal", evidence_mode=eb.EvidenceMode.NATIVE_EVIDENCED
            )
        with self.assertRaises(eb.EvidenceBoundaryError):
            eb.ReferenceProfile("reference.illegal", evidence_mode="NATIVE_EVIDENCED")

    def test_reference_descriptor_and_result_inherit_profile_mode(self):
        self.assertIs(self.descriptor.evidence_mode, self.profile.evidence_mode)
        self.assertIs(self.result.evidence_mode, self.profile.evidence_mode)

    def test_gate_certificate_rejects_every_reference_wrapper(self):
        for wrapper in self.wrappers:
            with self.subTest(wrapper=type(wrapper).__name__):
                with self.assertRaises(eb.EvidenceBoundaryError):
                    eb.issue_gate_certificate("gate.example", wrapper)

    def test_require_native_contract_rejects_every_reference_wrapper(self):
        for wrapper in self.wrappers:
            with self.subTest(wrapper=type(wrapper).__name__):
                with self.assertRaises(eb.EvidenceBoundaryError):
                    eb.require_native_contract(wrapper)

    def test_is_native_evidenced_is_false_for_reference_wrappers(self):
        for wrapper in self.wrappers:
            with self.subTest(wrapper=type(wrapper).__name__):
                self.assertFalse(eb.is_native_evidenced(wrapper))
                self.assertTrue(eb.is_reference_wrapper(wrapper))

    def test_reference_wrappers_are_not_native_contracts(self):
        for wrapper in self.wrappers:
            with self.subTest(wrapper=type(wrapper).__name__):
                self.assertNotIsInstance(wrapper, eb.NativeContract)
                self.assertNotIsInstance(wrapper, eb.GateCertificate)


class TestNativeContractSeal(unittest.TestCase):
    def test_certified_contract_issues_a_native_certificate(self):
        contract = eb.certify_native_contract("contract.example")
        self.assertTrue(eb.is_native_evidenced(contract))
        self.assertTrue(contract.is_native_evidenced)
        certificate = eb.issue_gate_certificate("gate.example", contract)
        self.assertIs(certificate.evidence_mode, eb.NATIVE_EVIDENCE_MODE)
        self.assertEqual(certificate.contract_id, "contract.example")

    def test_certify_refuses_a_non_native_mode(self):
        with self.assertRaises(eb.EvidenceBoundaryError):
            eb.certify_native_contract(
                "contract.illegal", evidence_mode=eb.EvidenceMode.REFERENCE_MODEL
            )

    def test_uncertified_contract_is_rejected(self):
        # A hand-rolled instance without the module seal must not pass.
        with self.assertRaises(eb.EvidenceBoundaryError):
            eb.NativeContract(
                contract_id="contract.forged",
                evidence_mode=eb.EvidenceMode.NATIVE_EVIDENCED,
                _seal=object(),
            )

    def test_gate_certificate_requires_the_seal(self):
        with self.assertRaises(eb.EvidenceBoundaryError):
            eb.GateCertificate(
                gate_id="gate.forged",
                contract_id="contract.forged",
                evidence_mode=eb.EvidenceMode.NATIVE_EVIDENCED,
                _seal=object(),
            )

    def test_gate_certificate_refuses_non_native_mode(self):
        with self.assertRaises(eb.EvidenceBoundaryError):
            eb.GateCertificate(
                gate_id="gate.illegal",
                contract_id="contract.example",
                evidence_mode=eb.EvidenceMode.REFERENCE_MODEL,
                _seal=object(),
            )

    def test_require_native_contract_rejects_plain_values(self):
        for value in (None, "contract.example", 1, object()):
            with self.subTest(value=repr(value)):
                with self.assertRaises(eb.EvidenceBoundaryError):
                    eb.require_native_contract(value)


class TestRegistrySeparation(unittest.TestCase):
    def test_registries_are_separate_types(self):
        reference_registry = eb.ReferenceRegistry()
        native_registry = eb.NativeContractRegistry()
        self.assertNotIsInstance(reference_registry, eb.NativeContractRegistry)
        self.assertNotIsInstance(native_registry, eb.ReferenceRegistry)
        self.assertFalse(
            issubclass(eb.ReferenceRegistry, eb.NativeContractRegistry)
        )
        self.assertFalse(
            issubclass(eb.NativeContractRegistry, eb.ReferenceRegistry)
        )

    def test_reference_registry_cannot_yield_native_contracts(self):
        reference_registry = eb.ReferenceRegistry()
        with self.assertRaises(eb.EvidenceBoundaryError):
            reference_registry.native_contracts()

    def test_native_registry_rejects_reference_profiles(self):
        native_registry = eb.NativeContractRegistry()
        profile = eb.ReferenceProfile("reference.packet.example")
        with self.assertRaises(eb.EvidenceBoundaryError):
            native_registry.register(profile)
        self.assertEqual(len(native_registry), 0)

    def test_reference_registry_is_reference_model_only(self):
        reference_registry = eb.ReferenceRegistry()
        contract = eb.certify_native_contract("contract.example")
        with self.assertRaises(eb.EvidenceBoundaryError):
            reference_registry.register(contract)
        self.assertEqual(len(reference_registry), 0)
        accepted = eb.ReferenceProfile(
            "reference.packet.example",
            evidence_mode=eb.EvidenceMode.REFERENCE_MODEL,
        )
        reference_registry.register(accepted)
        self.assertIs(
            eb.evidence_mode_of(reference_registry),
            eb.EvidenceMode.REFERENCE_MODEL,
        )
        self.assertEqual(reference_registry.profiles, (accepted,))

        for mode in (
            eb.EvidenceMode.SANDBOX_EXTENSION,
            eb.EvidenceMode.UNSUPPORTED,
        ):
            with self.subTest(mode=mode):
                with self.assertRaises(eb.EvidenceBoundaryError):
                    reference_registry.register(
                        eb.ReferenceProfile(
                            f"reference.{mode.value.lower()}",
                            evidence_mode=mode,
                        )
                    )
        self.assertEqual(reference_registry.profiles, (accepted,))

    def test_registries_are_inert_labels_not_executors(self):
        for registry in (eb.ReferenceRegistry(), eb.NativeContractRegistry()):
            with self.subTest(registry=type(registry).__name__):
                for attribute in ("execute", "run", "step", "apply"):
                    self.assertFalse(
                        hasattr(registry, attribute),
                        f"{type(registry).__name__} must not route execution "
                        f"(found {attribute!r})",
                    )

    def test_native_registry_certifies_registered_contracts(self):
        native_registry = eb.NativeContractRegistry()
        contract = eb.certify_native_contract("contract.example")
        native_registry.register(contract)
        certificate = native_registry.issue("gate.example", contract)
        self.assertIs(certificate.evidence_mode, eb.NATIVE_EVIDENCE_MODE)
        self.assertEqual(len(native_registry), 1)
        self.assertIn(contract, native_registry)


class TestReferenceBoundary(unittest.TestCase):
    def setUp(self) -> None:
        self.source_module = rb.QUARANTINED_MODULES[0]
        self.profile = eb.ReferenceProfile("reference.packet.example")
        self.envelope = rb.envelope(
            self.profile, {"payload": 1}, source_module=self.source_module
        )

    def test_envelope_preserves_the_profile_mode(self):
        self.assertIs(self.envelope.evidence_mode, self.profile.evidence_mode)
        self.assertEqual(self.envelope.source_module, self.source_module)
        self.assertEqual(self.envelope.reference_id, self.profile.reference_id)

    def test_envelope_rejects_non_quarantined_source(self):
        with self.assertRaises(rb.BoundaryCrossingError):
            rb.envelope(
                self.profile,
                payload=None,
                source_module="hsr_battle_agent.battle_sandbox.state",
            )

    def test_envelope_cannot_carry_native_evidence(self):
        with self.assertRaises(rb.BoundaryCrossingError):
            rb.ReferenceEnvelope(
                source_module=self.source_module,
                reference_id="reference.packet.example",
                evidence_mode=eb.EvidenceMode.NATIVE_EVIDENCED,
            )

    def test_envelope_requires_a_reference_profile(self):
        with self.assertRaises(rb.BoundaryCrossingError):
            rb.envelope("not-a-profile", None, source_module=self.source_module)

    def test_preserve_evidence_mode_accepts_matching_output(self):
        output = eb.ReferenceResult(self.profile, payload={"ok": True})
        self.assertIs(rb.preserve_evidence_mode(self.envelope, output), output)

    def test_preserve_evidence_mode_rejects_a_promoted_output(self):
        contract = eb.certify_native_contract("contract.example")
        with self.assertRaises(rb.BoundaryCrossingError):
            rb.preserve_evidence_mode(self.envelope, contract)

    def test_preserve_evidence_mode_rejects_unlabelled_output(self):
        with self.assertRaises(rb.BoundaryCrossingError):
            rb.preserve_evidence_mode(self.envelope, {"unlabelled": True})

    def test_preserve_evidence_mode_requires_an_envelope_source(self):
        with self.assertRaises(rb.BoundaryCrossingError):
            rb.preserve_evidence_mode(self.profile, self.envelope)

    def test_promote_to_native_always_refuses(self):
        with self.assertRaises(rb.BoundaryCrossingError):
            rb.promote_to_native(self.profile)
        with self.assertRaises(rb.BoundaryCrossingError):
            rb.promote_to_native(self.envelope, payload={})

    def test_assert_reference_only_accepts_reference_objects(self):
        self.assertIs(rb.assert_reference_only(self.profile), self.profile)
        self.assertIs(rb.assert_reference_only(self.envelope), self.envelope)

    def test_assert_reference_only_refuses_native_evidence(self):
        contract = eb.certify_native_contract("contract.example")
        with self.assertRaises(rb.BoundaryCrossingError):
            rb.assert_reference_only(contract)

    def test_assert_reference_only_refuses_untagged_values(self):
        with self.assertRaises(rb.BoundaryCrossingError):
            rb.assert_reference_only({"untagged": True})

    def test_boundary_module_constant_points_at_this_module(self):
        self.assertEqual(
            rb.REFERENCE_BOUNDARY_MODULE,
            "hsr_battle_agent.battle_sandbox.reference_boundary",
        )
        self.assertTrue(rb.REFERENCE_BOUNDARY_MODULE.endswith(".reference_boundary"))
        self.assertIn("hsr_battle_agent.battle_sandbox", rb.STRICT_PATH_PACKAGES)


class TestQuarantineDeclaration(unittest.TestCase):
    def test_quarantine_list_is_the_declared_set(self):
        self.assertEqual(
            rb.quarantined_module_names(),
            (
                "hsr_battle_agent.game_data.target_semantics_reference",
                "hsr_battle_agent.game_data.modifier_lifecycle_reference",
                "hsr_battle_agent.game_data.scenario_compiler",
                "hsr_battle_agent.game_data.reference_execution",
                "hsr_battle_agent.game_data.cross_family_execution_reference",
            ),
        )
        self.assertEqual(len(rb.QUARANTINED_SUBMODULES), len(rb.QUARANTINED_MODULES))

    def test_is_quarantined_module_matching(self):
        for module_name in rb.QUARANTINED_MODULES:
            with self.subTest(module_name=module_name):
                self.assertTrue(rb.is_quarantined_module(module_name))
                self.assertTrue(rb.is_quarantined_module(module_name + ".helper"))
        for module_name in (
            "hsr_battle_agent.battle_sandbox.reference_boundary",
            "hsr_battle_agent.game_data.modifier_catalog",
            "hsr_battle_agent.game_data.reference_execution_extra",
            "",
        ):
            with self.subTest(module_name=module_name):
                self.assertFalse(rb.is_quarantined_module(module_name))
        self.assertFalse(rb.is_quarantined_module(None))


class TestStrictPathImportBoundary(unittest.TestCase):
    def test_strict_path_never_imports_a_quarantined_module(self):
        violations: list[str] = []
        for path in strict_path_files():
            for imported in imported_modules(path):
                if rb.is_quarantined_module(imported):
                    violations.append(
                        f"{path.relative_to(REPO)} imports {imported}"
                    )
        self.assertEqual(
            violations,
            [],
            "strict-path modules must reach reference material only through "
            "reference_boundary, never by importing a quarantined module",
        )

    def test_strict_path_scan_actually_covers_the_package(self):
        files = strict_path_files()
        self.assertIn(
            STRICT_PATH_DIR / "reference_boundary.py",
            files,
            "the AST scan must cover the declared crossing point",
        )
        self.assertIn(STRICT_PATH_DIR / "registry.py", files)
        self.assertGreaterEqual(
            len(files), 10, "the strict-path scan should cover the whole package"
        )

    def test_only_reference_boundary_names_a_quarantined_module(self):
        allowed = {STRICT_PATH_DIR / "reference_boundary.py"}
        offenders: list[str] = []
        for path in strict_path_files():
            if path in allowed:
                continue
            for literal in string_literals(path):
                if rb.is_quarantined_module(literal):
                    offenders.append(
                        f"{path.relative_to(REPO)} names {literal!r}"
                    )
        self.assertEqual(
            offenders,
            [],
            "only reference_boundary may name a quarantined module",
        )


class TestQuarantinedModulesRemainImportable(unittest.TestCase):
    def test_existing_reference_fixtures_remain_importable(self):
        # The guard rails must label the quarantine, not break the modules.
        for module_name in rb.QUARANTINED_MODULES:
            with self.subTest(module_name=module_name):
                module = importlib.import_module(module_name)
                self.assertIsNotNone(module)
                self.assertEqual(module.__name__, module_name)


class TestCanonicalEvidenceMode(unittest.TestCase):
    """F01-001: the sandbox must consume the canonical battle-IR class object.

    Two equal-valued but identity-unequal ``EvidenceMode`` classes are forbidden
    by ``REFERENCE_QUARANTINE_DECISION``.  These tests prove that
    ``battle_sandbox.evidence_boundary`` no longer defines its own enum and that
    every sandbox path resolves to the single canonical class.
    """

    def test_three_way_identity_of_the_canonical_class(self):
        from hsr_battle_agent.battle_ir.evidence import (
            EvidenceMode as canonical,
        )

        self.assertIs(canonical, eb.EvidenceMode)
        self.assertIs(canonical, rb.EvidenceMode)
        self.assertIs(canonical, eb.EvidenceMode)
        # The class objects are the same object, not merely equal.
        self.assertIs(eb.EvidenceMode, rb.EvidenceMode)

    def test_members_resolve_to_the_canonical_class(self):
        from hsr_battle_agent.battle_ir.evidence import (
            EvidenceMode as canonical,
        )

        for name, member in (
            ("NATIVE_EVIDENCED", eb.NATIVE_EVIDENCE_MODE),
            ("NATIVE_EVIDENCED", canonical.NATIVE_EVIDENCED),
        ):
            self.assertEqual(member.name, name)
            self.assertIs(member.__class__, canonical)
        for member in eb.NON_NATIVE_EVIDENCE_MODES:
            self.assertIs(member.__class__, canonical)

    def test_evidence_boundary_has_no_local_evidence_mode_class(self):
        source = (STRICT_PATH_DIR / "evidence_boundary.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        local = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "EvidenceMode"
        ]
        self.assertEqual(
            local,
            [],
            "evidence_boundary.py must not define a local EvidenceMode class",
        )

    def test_evidence_boundary_imports_the_canonical_class(self):
        imported = imported_modules(STRICT_PATH_DIR / "evidence_boundary.py")
        self.assertIn("hsr_battle_agent.battle_ir.evidence", imported)
        self.assertIn(
            "hsr_battle_agent.battle_ir.evidence.EvidenceMode", imported
        )

    def test_frozen_spellings_are_unchanged_after_migration(self):
        from hsr_battle_agent.battle_ir.evidence import (
            EVIDENCE_MODE_SPELLINGS,
        )

        self.assertEqual(
            eb.EVIDENCE_MODE_NAMES,
            (
                "NATIVE_EVIDENCED",
                "REFERENCE_MODEL",
                "SANDBOX_EXTENSION",
                "UNSUPPORTED",
            ),
        )
        self.assertEqual(eb.EVIDENCE_MODE_NAMES, EVIDENCE_MODE_SPELLINGS)

    def test_boundary_behaviour_is_unchanged_for_string_inputs(self):
        # The migration must not change accepted inputs or error types.
        profile = eb.ReferenceProfile(
            "reference.packet.example", evidence_mode="REFERENCE_MODEL"
        )
        self.assertIs(profile.evidence_mode.__class__, eb.EvidenceMode)
        with self.assertRaises(eb.EvidenceBoundaryError):
            eb.ReferenceProfile(
                "reference.packet.illegal",
                evidence_mode="NATIVE_EVIDENCED",
            )
        with self.assertRaises(eb.EvidenceBoundaryError):
            eb.ReferenceProfile(
                "reference.packet.illegal", evidence_mode="NOT_A_MODE"
            )

    def test_canonical_class_exposes_no_executability_helper(self):
        for name in (
            "executable",
            "is_executable",
            "can_execute",
            "implies_execution",
            "as_bool",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(eb.EvidenceMode, name))
        # API_DESIGN_LOCAL: ordinary Enum truthiness is not an execution gate.
        self.assertTrue(bool(eb.EvidenceMode.NATIVE_EVIDENCED))


if __name__ == "__main__":
    unittest.main()
