"""Run an audited unit layer or complete deterministic integration shards."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]

# Explicitly reviewed fixture-free classes; unclassified new tests stay integration.
# ASGI/DB/filesystem fixture classes remain integration even if some methods are pure.
UNIT_CLASSES = frozenset({
    "tests.test_auth.AuthSchemaTests", "tests.test_auth.AuthTokenTests",
    "tests.test_profile_validation.ProfileSchemaTests",
    "tests.test_api_contract_gate.ContractGateTests",
    "tests.test_workflows.WorkflowTests",
    "tests.test_cognitive_commons.CognitiveCommonsTests",
    "tests.test_cognitive_infrastructure.CognitiveInfrastructureTests",
    "tests.test_planetary_resilience.PlanetaryResilienceTests",
    "tests.test_provable_autonomy.ProvableAutonomyTests",
    "tests.test_test_suites.TestSuiteGateTests",
})


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def test_class_id(identifier):
    return identifier.rsplit(".", 1)[0]


def partition(cases, shard_count):
    if not 1 <= shard_count <= 16:
        raise ValueError("shard_count must be between 1 and 16")
    identifiers = [case.id() for case in cases]
    duplicates = [key for key, count in Counter(identifiers).items() if count != 1]
    if duplicates or any("_FailedTest" in name for name in identifiers):
        raise ValueError(f"Discovery failed or duplicated cases: {duplicates or identifiers}")
    classes = {test_class_id(name) for name in identifiers}
    if not UNIT_CLASSES <= classes:
        raise ValueError(f"Stale unit classification: {sorted(UNIT_CLASSES - classes)}")
    groups = {"unit": [], **{f"integration-{i}": [] for i in range(1, shard_count + 1)}}
    for case in sorted(cases, key=lambda item: item.id()):
        class_id = test_class_id(case.id())
        if class_id in UNIT_CLASSES:
            key = "unit"
        else:
            # A class stays in one process so its class fixtures and ordering survive.
            index = int.from_bytes(hashlib.sha256(class_id.encode()).digest()[:8], "big") % shard_count + 1
            key = f"integration-{index}"
        groups[key].append(case)
    assigned = [case.id() for group in groups.values() for case in group]
    if Counter(assigned) != Counter(identifiers):
        raise ValueError("Partition does not exactly cover discovery")
    return groups


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executed = []
        self.durations = {}

    def startTest(self, test):
        self.executed.append(test.id())
        self.started_at = time.perf_counter()
        super().startTest(test)

    def stopTest(self, test):
        self.durations[test.id()] = round(time.perf_counter() - self.started_at, 6)
        super().stopTest(test)


def configure(storage):
    from app.config import Settings, get_settings
    Settings.model_config["env_file"] = None
    for key in Settings.model_fields:
        os.environ.pop(key, None)
    os.environ.update(DATABASE_URL="sqlite+aiosqlite:///:memory:", AUTO_CREATE_TABLES="false",
                      KNOWLEDGE_STORAGE_PATH=str(storage), TASK_SCHEDULER_ENABLED="false",
                      RUN_BACKGROUND_WORKERS_IN_API="false", CRAWLER_ENABLED="false",
                      SOURCE_SYNC_ENABLED="false", MEDIA_WORKER_ENABLED="false", ORCHESTRATION_WORKER_ENABLED="false")
    get_settings.cache_clear()


def successful(result, planned):
    return (result.wasSuccessful() and Counter(result.executed) == Counter(planned)
            and not result.skipped and not result.expectedFailures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["unit", "integration", "all"], default="all")
    parser.add_argument("--shard-index", type=int, default=1)
    parser.add_argument("--shard-count", type=int, default=3)
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--environment", default="local")
    args = parser.parse_args()
    if not 1 <= args.shard_index <= args.shard_count or (args.suite != "integration" and args.shard_index != 1):
        parser.error("invalid shard index for selected suite")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    with tempfile.TemporaryDirectory(prefix="infopulse-tests-") as directory:
        configure(Path(directory))
        cases = list(flatten(unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))))
        groups = partition(cases, args.shard_count)
        selected = cases if args.suite == "all" else groups["unit" if args.suite == "unit" else f"integration-{args.shard_index}"]
        report = {"environment": args.environment, "python": sys.version.split()[0],
                  "suite": args.suite, "shard_index": args.shard_index, "shard_count": args.shard_count,
                  "discovered": sorted(case.id() for case in cases),
                  "partitions": {key: [case.id() for case in value] for key, value in groups.items()},
                  "planned": [case.id() for case in selected], "completed": False}
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("Discovery:", len(cases), "; partitions:", {key: len(value) for key, value in groups.items()}, flush=True)
        if args.list_only:
            return 0
        if not selected:
            raise ValueError("Refusing to pass an empty test selection")
        started = time.perf_counter()
        result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(unittest.TestSuite(selected))
        success = successful(result, report["planned"])
        report.update(completed=success, executed=result.executed, seconds=round(time.perf_counter() - started, 6),
                      durations=result.durations, failures=[test.id() for test, _ in result.failures],
                      errors=[test.id() for test, _ in result.errors], skipped=[test.id() for test, _ in result.skipped],
                      expected_failures=[test.id() for test, _ in result.expectedFailures])
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
