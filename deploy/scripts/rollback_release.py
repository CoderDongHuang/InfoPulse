"""Restore release resources and remove resources introduced by a failed release.

Does not roll back schema or secrets. Requires backward-compatible migrations.
"""
import argparse
import json
from pathlib import Path
import subprocess

RESOURCE_TYPES = "deployment,service,ingress,networkpolicy,hpa,pdb"
MANAGED = {
    "Deployment": {"api-stable", "api-canary", "web", "scheduler", "knowledge-worker", "orchestration-worker", "media-worker", "sources-worker", "actions-worker"},
    "Service": {"backend", "api-canary", "web"},
    "Ingress": {"api-stable", "api-canary", "web"},
    "NetworkPolicy": {"default-deny-ingress", "allow-ingress-controller", "allow-web-to-api"},
    "HorizontalPodAutoscaler": {"api-stable", "orchestration-worker", "media-worker"},
    "PodDisruptionBudget": {"api-stable"},
}


def managed(item):
    return item["metadata"]["name"] in MANAGED.get(item["kind"], set())


def clean(item):
    item = json.loads(json.dumps(item))
    item.pop("status", None)
    for field in ("resourceVersion", "uid", "creationTimestamp", "generation", "managedFields"):
        item["metadata"].pop(field, None)
    item["metadata"].get("annotations", {}).pop("kubectl.kubernetes.io/last-applied-configuration", None)
    return item


def identity(item):
    return item["kind"], item["metadata"]["name"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--namespace", default="infopulse")
    args = parser.parse_args()
    prior = [item for item in json.loads(Path(args.snapshot).read_text())["items"] if managed(item)]
    old = {identity(item): item for item in prior}
    live = json.loads(subprocess.check_output(["kubectl", "-n", args.namespace, "get", RESOURCE_TYPES, "-o", "json"]))["items"]
    for item in live:
        if managed(item) and identity(item) not in old:
            subprocess.run(["kubectl", "-n", args.namespace, "delete", item["kind"], item["metadata"]["name"], "--ignore-not-found"], check=True)
    if prior:
        payload = json.dumps({"apiVersion": "v1", "kind": "List", "items": [clean(item) for item in prior]})
        subprocess.run(["kubectl", "apply", "-f", "-"], input=payload, text=True, check=True)
    for item in prior:
        if item["kind"] == "Deployment":
            subprocess.run(["kubectl", "-n", args.namespace, "rollout", "status", "deployment/" + item["metadata"]["name"], "--timeout=300s"], check=True)


if __name__ == "__main__": main()
