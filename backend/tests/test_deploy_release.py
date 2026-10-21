"""Deployment phase, ingress, worker and rollback regression checks."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json
import sys
import yaml

ROOT=Path(__file__).resolve().parents[2]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"deploy/scripts"/(name+".py"));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class DeploymentTests(unittest.TestCase):
    def manifests(self,phase):
        renderer=load("render_manifests")
        text=(ROOT/"deploy/k8s/production.yaml").read_text().replace("CANARY_VERSION","new").replace("VERSION","new")
        return list(yaml.safe_load_all(renderer.select_phase(text,phase)))

    def test_no_deployment_applied_before_preflight_and_migration_gates(self):
        for phase in ("bootstrap","preflight","migrate"):
            self.assertFalse(any(x["kind"]=="Deployment" for x in self.manifests(phase)))
        canary=[x["metadata"]["name"] for x in self.manifests("canary") if x["kind"]=="Deployment"]
        self.assertEqual(canary,["api-canary"])
        promoted=[x["metadata"]["name"] for x in self.manifests("promote") if x["kind"]=="Deployment"]
        self.assertEqual(set(promoted),{"api-stable","web","scheduler","knowledge-worker","orchestration-worker","media-worker","sources-worker","actions-worker"})
        all_ids=[(x["kind"],x["metadata"]["name"]) for phase in ("bootstrap","preflight","migrate","canary","promote") for x in self.manifests(phase)]
        self.assertEqual(len(all_ids),len(set(all_ids)))

    def test_renderer_replaces_registry_and_uses_immutable_config(self):
        renderer=load("render_manifests")
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/"release.yaml"
            args=["render","--source",str(ROOT/"deploy/k8s/production.yaml"),"--output",str(out),"--version","abc123","--canary-version","abc123","--api-host","api.test.com","--app-host","app.test.com","--repository","owner/repo","--phase","canary"]
            with patch.object(sys,"argv",args):renderer.main()
            content=out.read_text();self.assertIn("ghcr.io/owner/repo:abc123",content);self.assertIn("infopulse-config-abc123",content)
            self.assertNotIn("VERSION",content);self.assertNotIn("name: api-stable",content)

    def test_web_ingress_upload_limit_and_web_to_api_policy(self):
        docs=self.manifests("all")
        web=next(x for x in docs if x["kind"]=="Ingress" and x["metadata"]["name"]=="web")
        self.assertEqual(web["metadata"]["annotations"]["nginx.ingress.kubernetes.io/proxy-body-size"],"260m")
        policy=next(x for x in docs if x["kind"]=="NetworkPolicy" and x["metadata"]["name"]=="allow-web-to-api")
        rule=policy["spec"]["ingress"][0]
        self.assertEqual(rule["from"][0]["podSelector"]["matchLabels"]["app"],"infopulse-web")
        self.assertEqual(rule["ports"],[{"protocol":"TCP","port":8000}])
        compose=yaml.safe_load((ROOT/"deploy/staging.compose.yml").read_text())
        for role in ("sources","actions"):
            self.assertEqual(compose["services"][role+"-worker"]["command"][-1],role)

    def test_workflow_checks_direct_canary_and_promotes_after_migration(self):
        workflow=yaml.safe_load((ROOT/".github/workflows/deploy.yml").read_text())
        steps=workflow["jobs"]["deploy"]["steps"];names=[step.get("name") for step in steps]
        self.assertLess(names.index("Preflight gate"),names.index("Migration gate"))
        self.assertLess(names.index("Migration gate"),names.index("Deploy isolated canary"))
        self.assertLess(names.index("Verify exact canary deployment"),names.index("Promote application and all workers"))
        verify=next(x["run"] for x in steps if x.get("name")=="Verify exact canary deployment")
        self.assertIn("port-forward service/api-canary",verify);self.assertIn("test \"$actual\" = \"$expected\"",verify)

    def test_exports_are_shared_by_api_replicas_and_cleanup_worker(self):
        docs=self.manifests("all")
        for name in ("api-stable","api-canary","knowledge-worker"):
            pod=next(x for x in docs if x["kind"]=="Deployment" and x["metadata"]["name"]==name)["spec"]["template"]["spec"]
            volume=next(x for x in pod["volumes"] if x.get("persistentVolumeClaim",{}).get("claimName")=="infopulse-exports")
            self.assertTrue(any(x["name"]==volume["name"] and x["mountPath"]=="/shared/exports" for x in pod["containers"][0]["volumeMounts"]))
        compose=yaml.safe_load((ROOT/"deploy/staging.compose.yml").read_text())
        for name in ("api","knowledge-worker"):
            self.assertIn("staging_exports:/shared/exports",compose["services"][name]["volumes"])

    def test_rollback_restores_web_workers_and_ignores_unrelated_resources(self):
        rollback=load("rollback_release")
        prior=[{"apiVersion":"apps/v1","kind":"Deployment","metadata":{"name":name,"namespace":"infopulse","resourceVersion":"old"},"spec":{"template":{"spec":{"containers":[{"name":"worker","image":"old"}]}}}} for name in ("api-stable","web","scheduler")]
        live=prior+[{"kind":"Deployment","metadata":{"name":"actions-worker"}},{"kind":"Deployment","metadata":{"name":"unrelated-new"}}]
        with tempfile.TemporaryDirectory() as temp:
            snapshot=Path(temp)/"previous.json";snapshot.write_text(json.dumps({"items":prior}))
            with patch.object(sys,"argv",["rollback","--snapshot",str(snapshot)]),patch.object(rollback.subprocess,"check_output",return_value=json.dumps({"items":live}).encode()),patch.object(rollback.subprocess,"run") as run:
                rollback.main()
                calls=run.call_args_list
                self.assertTrue(any("actions-worker" in call.args[0] and "delete" in call.args[0] for call in calls))
                self.assertFalse(any("unrelated-new" in call.args[0] for call in calls))
                payload=next(json.loads(call.kwargs["input"]) for call in calls if "input" in call.kwargs)
                self.assertEqual(len(payload["items"]),3);self.assertNotIn("resourceVersion",payload["items"][0]["metadata"])
