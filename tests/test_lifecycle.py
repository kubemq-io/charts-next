"""Chart separation and the real kubectl deletion transport contract."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.parse import urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import yaml

ROOT = Path(__file__).resolve().parents[1]


class ChartLifecycle(unittest.TestCase):
    def render(self, *values, success=True):
        result = subprocess.run(["helm", "template", "messaging", str(ROOT / "kubemq-next"),
                                 "-n", "kubemq", *values], text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return [obj for obj in yaml.safe_load_all(result.stdout) if obj] if success else []

    def test_operator_default_owns_shared_permissions_only(self):
        objects = self.render()
        self.assertNotIn("KubemqCluster", [obj["kind"] for obj in objects])
        self.assertEqual(1, sum(obj["kind"] == "Deployment" for obj in objects))
        server_account = [obj for obj in objects if obj["kind"] == "ServiceAccount"
                          and obj["metadata"]["name"] == "kubemq-cluster-next"]
        self.assertEqual(1, len(server_account))
        role = next(obj for obj in objects if obj["metadata"]["name"] == "kubemq-cluster-next-kubemq-license")
        self.assertEqual(role["rules"], [{"apiGroups": [""], "resources": ["namespaces"],
                                        "resourceNames": ["kube-system"], "verbs": ["get"]}])
        self.assertFalse(any("helm.sh/hook" in obj["metadata"].get("annotations", {}) for obj in objects))

    def test_cluster_release_owns_only_retained_cluster(self):
        objects = self.render("-f", str(ROOT / "examples/cluster-values.yaml"),
                              "--set", "cluster.installationID=operation-id")
        self.assertEqual(["KubemqCluster"], [obj["kind"] for obj in objects])
        cluster = objects[0]
        self.assertEqual("keep", cluster["metadata"]["annotations"]["helm.sh/resource-policy"])
        self.assertEqual("operation-id", cluster["metadata"]["annotations"]["kmq.io/installation-id"])
        self.assertNotIn("cluster", cluster["spec"])
        self.assertNotIn("operator", cluster["spec"])
        self.assertEqual(3, cluster["spec"]["replicas"])
        self.assertEqual("my-kubemq-license", cluster["spec"]["licenseKeySecretRef"]["name"])
        self.assertTrue(cluster["spec"]["api"]["auth"]["enable"])

    def test_unsafe_or_unlicensed_shapes_refused(self):
        self.render("--set", "cluster.enabled=true,licenseKey=test", success=False)
        self.render("--set", "preDelete.enabled=true", success=False)
        self.render("--set", "operator.enabled=false,cluster.enabled=true", success=False)
        for size in (1, 2):
            self.render("-f", str(ROOT / "examples/cluster-values.yaml"),
                        "--set", "replicas=" + str(size), success=False)


class ProtectedRemoval(unittest.TestCase):
    def exercise(self, scenario):
        requests = []
        testcase = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, code, body):
                raw = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                if scenario == "denied":
                    self.reply(403, {"kind": "Status", "apiVersion": "v1", "status": "Failure",
                                     "reason": "Forbidden", "message": "read denied", "code": 403})
                    return
                if urlsplit(self.path).path == "/api/v1/namespaces/kube-system":
                    self.reply(200, {"metadata": {"uid": "wrong-cluster" if scenario == "wrong-context" else "kubernetes-uid"}})
                else:
                    testcase.assertEqual("/apis/next.kubemq.io/v1/namespaces/kubemq/kubemqclusters/messaging", urlsplit(self.path).path)
                    self.reply(200, {"metadata": {"uid": "replacement" if scenario == "replaced-before-get" else "original",
                                                  "resourceVersion": "43" if scenario == "changed" else "42"}})

            def do_DELETE(self):
                if self.headers.get("Transfer-Encoding") == "chunked":
                    chunks = []
                    while True:
                        size = int(self.rfile.readline().strip(), 16)
                        if size == 0:
                            self.rfile.readline()
                            break
                        chunks.append(self.rfile.read(size))
                        self.rfile.read(2)
                    raw = b"".join(chunks)
                else:
                    raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                body = json.loads(raw)
                requests.append((self.path, body))
                if scenario == "replaced-before-delete":
                    self.reply(409, {"kind": "Status", "apiVersion": "v1", "status": "Failure",
                                     "reason": "Conflict", "message": "UID precondition failed", "code": 409})
                else:
                    self.reply(200, {"kind": "Status", "apiVersion": "v1", "status": "Success"})

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                config = Path(directory) / "config"
                config.write_text(json.dumps({"apiVersion": "v1", "kind": "Config", "clusters": [
                    {"name": "target", "cluster": {"server": "http://127.0.0.1:" + str(server.server_port)}}],
                    "contexts": [{"name": "target", "context": {"cluster": "target"}}], "users": []}))
                result = subprocess.run([sys.executable, str(ROOT / "scripts/remove-cluster.py"),
                    "--context", "target", "--namespace", "kubemq", "--name", "messaging",
                    "--cluster-uid", "kubernetes-uid", "--uid", "original", "--resource-version", "42"],
                    env={**os.environ, "KUBECONFIG": str(config)}, capture_output=True, text=True, timeout=20)
        finally:
            server.shutdown()
            server.server_close()
            worker.join()
        if scenario in ("accepted", "replaced-before-delete"):
            self.assertEqual(1, len(requests), result.stderr)
            self.assertEqual({"uid": "original", "resourceVersion": "42"}, requests[0][1]["preconditions"])
            self.assertEqual("Foreground", requests[0][1]["propagationPolicy"])
        else:
            self.assertEqual([], requests, "preflight refusal must not issue a delete")
        self.assertEqual(scenario == "accepted", result.returncode == 0, result.stderr)

    def test_actual_kubectl_transport(self):
        for scenario in ("accepted", "wrong-context", "replaced-before-get", "changed", "denied", "replaced-before-delete"):
            with self.subTest(scenario=scenario):
                self.exercise(scenario)


if __name__ == "__main__":
    unittest.main()
