"""Ensure parallelization cannot silently turn missing coverage into a pass."""
import copy
from collections import Counter
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import test_suites
from scripts.verify_test_reports import verify


class Case:
    def __init__(self, identifier):
        self.identifier = identifier

    def id(self):
        return self.identifier


class TestSuiteGateTests(unittest.TestCase):
    def inventory(self):
        return [Case("tests.unit.Pure.test_a"), Case("tests.db.Database.test_b"),
                Case("tests.db.Database.test_a"), Case("tests.http.NewHTTP.test_a")]

    def groups(self):
        with patch.object(test_suites, "UNIT_CLASSES", {"tests.unit.Pure"}):
            return test_suites.partition(self.inventory(), 3)

    def reports(self):
        # One synthetic case per group: inventory validation is independent of SQL.
        parts = {key: [f"tests.{key}.Case.test_a"] for key in ("unit", "integration-1", "integration-2", "integration-3")}
        discovery = sorted(x for values in parts.values() for x in values)
        return [{"environment": "local", "suite": "unit" if key == "unit" else "integration",
                 "shard_index": 1 if key == "unit" else int(key[-1]), "shard_count": 3,
                 "discovered": discovery, "partitions": parts, "planned": values,
                 "executed": values, "completed": True, "seconds": 1,
                 "failures": [], "errors": [], "skipped": [], "expected_failures": []}
                for key, values in parts.items()]

    def test_deterministic_exact_coverage_and_whole_class_affinity(self):
        groups = self.groups()
        self.assertEqual(Counter(x.id() for values in groups.values() for x in values), Counter(x.id() for x in self.inventory()))
        self.assertEqual([x.id() for x in groups["unit"]], ["tests.unit.Pure.test_a"])
        locations = [key for key, values in groups.items() for x in values if x.id().startswith("tests.db.")]
        self.assertEqual(len(set(locations)), 1)
        with patch.object(test_suites, "UNIT_CLASSES", {"tests.unit.Pure"}):
            reversed_groups = test_suites.partition(list(reversed(self.inventory())), 3)
        self.assertEqual({k: [x.id() for x in v] for k, v in groups.items()},
                         {k: [x.id() for x in v] for k, v in reversed_groups.items()})

    def test_unknown_classes_default_to_integration(self):
        self.assertTrue(any(x.id().startswith("tests.http.") for key, values in self.groups().items() if key != "unit" for x in values))

    def test_invalid_discovery_and_stale_classification_fail(self):
        with patch.object(test_suites, "UNIT_CLASSES", {"tests.unit.Pure"}):
            for cases in (self.inventory() * 2, [Case("unittest.loader._FailedTest.broken")], []):
                with self.assertRaises(ValueError):
                    test_suites.partition(cases, 3)
            for count in (0, 17):
                with self.assertRaises(ValueError):
                    test_suites.partition(self.inventory(), count)

    def test_missing_executions_skips_and_expected_failures_fail(self):
        result = SimpleNamespace(wasSuccessful=lambda: True, executed=["a"], skipped=[], expectedFailures=[])
        self.assertTrue(test_suites.successful(result, ["a"]))
        self.assertFalse(test_suites.successful(result, ["a", "b"]))
        result.skipped = [("a", "reason")]
        self.assertFalse(test_suites.successful(result, ["a"]))
        result.skipped = []
        result.expectedFailures = [("a", "trace")]
        self.assertFalse(test_suites.successful(result, ["a"]))

    def test_aggregate_requires_each_group_and_environment(self):
        self.assertEqual(verify(self.reports(), ["local"])["discovered"], 4)
        for reports, environments in (([], ["local"]), (self.reports()[:-1], ["local"]),
                                      (self.reports() * 2, ["local"]), (self.reports(), ["local", "missing"])):
            with self.assertRaises(ValueError):
                verify(reports, environments)

    def test_aggregate_rejects_failure_and_false_coverage(self):
        for field, value in (("completed", False), ("executed", []), ("skipped", ["skip"]),
                             ("failures", ["fail"]), ("errors", ["error"]),
                             ("expected_failures", ["expected"]), ("planned", ["wrong"]),
                             ("discovered", ["different"]), ("shard_count", 2)):
            reports = copy.deepcopy(self.reports())
            reports[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify(reports, ["local"])
