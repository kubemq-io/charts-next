#!/usr/bin/env python3
"""Request deletion of one recorded KubemqCluster; retain all persistent volumes.

Requires Python 3 and kubectl on Linux, macOS, or Windows. No shell is used.
"""
import argparse
import json
import subprocess
import sys
from urllib.parse import quote


def remove(args, run=subprocess.run):
    command = ["kubectl", "--context", args.context, "--request-timeout=30s"]

    def kubectl(*parts, body=None):
        result = run(command + list(parts), input=body, text=True,
                     capture_output=True, check=False)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "kubectl request failed")
        return json.loads(result.stdout)

    # Pin the API endpoint's installation identity as well as the namespaced object.
    identity = kubectl("get", "--raw", "/api/v1/namespaces/kube-system")
    if identity["metadata"]["uid"] != args.cluster_uid:
        raise RuntimeError("Kubernetes cluster identity changed; nothing deleted")
    path = ("/apis/next.kubemq.io/v1/namespaces/" + quote(args.namespace, safe="")
            + "/kubemqclusters/" + quote(args.name, safe=""))
    current = kubectl("get", "--raw", path)
    metadata = current["metadata"]
    if (metadata["uid"] != args.uid
            or metadata["resourceVersion"] != args.resource_version):
        raise RuntimeError("cluster UID or resource version changed; inspect and record a fresh deletion plan")
    options = {"apiVersion": "v1", "kind": "DeleteOptions",
               "preconditions": {"uid": args.uid, "resourceVersion": args.resource_version},
               "propagationPolicy": "Foreground"}
    # The API server checks both preconditions at the actual mutation, including
    # replacement or concurrent updates after the GET above.
    kubectl("delete", "--raw", path, "-f", "-", body=json.dumps(options))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("context", "namespace", "name", "cluster-uid", "uid", "resource-version"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    try:
        remove(args)
    except (RuntimeError, OSError, KeyError, ValueError) as exc:
        print("Deletion not confirmed: " + str(exc), file=sys.stderr)
        return 1
    print("Deletion accepted for recorded UID " + args.uid
          + ". Wait for finalization before uninstalling the cluster release. Volumes are retained.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
