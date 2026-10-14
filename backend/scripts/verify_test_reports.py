"""Reject missing, failed, skipped or duplicated test coverage across CI environments."""
import argparse
from collections import Counter
import json
from pathlib import Path


def verify(reports, environments, shard_count=3):
    if not reports or len(environments) != len(set(environments)):
        raise ValueError("Missing reports or duplicate environments")
    reference = reports[0]["discovered"]
    if not reference or len(reference) != len(set(reference)):
        raise ValueError("Empty or duplicated discovery inventory")
    partitions = reports[0]["partitions"]
    keys = {"unit", *[f"integration-{i}" for i in range(1, shard_count + 1)]}
    if set(partitions) != keys or Counter(x for group in partitions.values() for x in group) != Counter(reference):
        raise ValueError("Partitions must exactly cover discovery")
    if set(report["environment"] for report in reports) != set(environments):
        raise ValueError("Unexpected or missing test environment")
    summary = {}
    for environment in environments:
        selected = [report for report in reports if report["environment"] == environment]
        seen = []
        executed = []
        for report in selected:
            key = "unit" if report["suite"] == "unit" else f"integration-{report['shard_index']}"
            if (report["suite"] not in {"unit", "integration"} or key not in keys
                    or report["shard_count"] != shard_count or report["discovered"] != reference
                    or report["partitions"] != partitions or report["planned"] != partitions[key]
                    or not report.get("completed") or not report["planned"]
                    or Counter(report.get("executed", [])) != Counter(report["planned"])
                    or any(report.get(field) for field in ("failures", "errors", "skipped", "expected_failures"))):
                raise ValueError(f"Invalid or incomplete report: {environment}/{key}")
            seen.append(key)
            executed.extend(report["executed"])
        if Counter(seen) != Counter(keys) or Counter(executed) != Counter(reference):
            raise ValueError(f"Missing or repeated coverage: {environment}")
        summary[environment] = {"tests": len(executed), "groups": len(selected),
                                "longest_group_seconds": max(report["seconds"] for report in selected)}
    return {"completed": True, "discovered": len(reference), "environments": summary}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--environments", nargs="+", required=True)
    parser.add_argument("--shard-count", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    files = sorted(args.reports.rglob("*.json"))
    result = verify([json.loads(path.read_text(encoding="utf-8")) for path in files], args.environments, args.shard_count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
