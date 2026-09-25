# KubeMQ Helm chart — next line

The `kubemq-next` chart uses independent releases: one operator release per namespace, then
one release per KubeMQ cluster. The default installs only the operator and shared permissions.
Combined operator/cluster releases are refused.

> **"next" means two things in KubeMQ.** `-next` artifacts (this chart, the `kubemq-next` image, the
> `next.kubemq.io` API group) are the current product line for new installations. The *next storage
> engine* is the server's storage engine, selected with `store.engine`. They are independent names.

## Install

```bash
helm repo add kubemq-next https://kubemq-io.github.io/charts-next
helm repo update
helm install kubemq-operator kubemq-next/kubemq-next -n kubemq --create-namespace
kubectl rollout status deployment/kubemq-operator-next -n kubemq --timeout=120s
# Create my-kubemq-license separately, then install one independent cluster release.
helm install messaging kubemq-next/kubemq-next -n kubemq --set cluster.enabled=true --set operator.enabled=false --set fullnameOverride=messaging --set licenseKeySecretRef.name=my-kubemq-license
```

The operator release owns the shared ServiceAccounts and permissions. Reuse it for every cluster
in that namespace. Inspect existing ownership and compatibility before installing; do not adopt
another release's resources. Authentication and private management access must be configured in
your cluster values; see `examples/cluster-values.yaml`. Helm success alone does not prove readiness.
Require the `Ready` condition at the current custom-resource generation, current StatefulSet
revision, and the intended durable license adoption on every server, then verify an actual message.


The default requests **3 server nodes, each with a 5 GiB volume** (15 GiB total).
Set `replicas` before first install. The license can cap the initial count. Once established,
the member count is permanent: Kubernetes rejects changes to `replicas` for the next storage
engine. If a changed count reaches the operator through an older schema, it reports
`ReplicasFrozen` and keeps the established count.

## Private encrypted management

Create a customer-owned TLS Secret before applying the example cluster values:

```text
kubectl --context YOUR_CONTEXT -n kubemq create secret tls messaging-management-tls --cert=management.crt --key=management.key
```

The certificate must be valid for `messaging-api.kubemq.svc`. Include `localhost` and IP address
`127.0.0.1` if the client verifies a local port-forward URL. Trust the issuing authority or the
pinned certificate in the client; never disable verification. The operator validates the Secret
before rolling workloads and uses the public certificate to verify each management request.
Updating its certificate rolls the pods. Kubernetes HTTPS probes check listener health only;
certificate-verified authenticated management and a real message remain separate acceptance checks.

Apply the current chart CRDs explicitly before an upgrade (`kubectl apply -f kubemq-next/crds/`
from the reviewed local chart), because Helm does not upgrade CRDs. Upgrade the compatible operator
before enabling `api.tlsSecret` and the server version that supports native management TLS.
On a disconnected installation, stage the pinned chart, operator/server images, native executables,
kubectl, Helm, certificates and offline license beforehand. There is no hook image requirement.

## Licensing

A KubeMQ deployment on Kubernetes requires a license key or signed file. The signup-free
standalone-container evaluation does not apply to Kubernetes. The chart takes exactly **one** of four sources
(rendering fails when none or more than one is set):

| Value | What it is | Reaches the pod as |
|-------|------------|--------------------|
| `licenseKey` | the online license key; the server activates it and keeps a lease | env `KUBEMQ_LICENSE_KEY` |
| `licenseFile` | an offline signed license file, verified locally, no network needed | env `KUBEMQ_LICENSE_DATA` |
| `licenseKeySecretRef` | `{name, key}` — an existing Secret holding the key (`key` defaults to `licenseKey`) | env `KUBEMQ_LICENSE_KEY` |
| `licenseFileSecretRef` | `{name, key}` — an existing Secret holding the file (`key` defaults to `licenseFile`) | env `KUBEMQ_LICENSE_DATA` |

To keep the license out of the `KubemqCluster` object and out of Helm's saved values, reference a Secret:

```bash
# key
kubectl -n kubemq create secret generic my-kubemq-license --from-literal=licenseKey=<your-license-key>
helm install messaging kubemq-next/kubemq-next -n kubemq --set cluster.enabled=true --set operator.enabled=false --set fullnameOverride=messaging --set licenseKeySecretRef.name=my-kubemq-license
# file
kubectl -n kubemq create secret generic my-kubemq-license --from-file=licenseFile=./kubemq.license
helm install messaging kubemq-next/kubemq-next -n kubemq --set cluster.enabled=true --set operator.enabled=false --set fullnameOverride=messaging --set licenseFileSecretRef.name=my-kubemq-license
# a different data key
helm install … --set licenseFileSecretRef.name=my-kubemq-license --set licenseFileSecretRef.key=lic
```

The server enforces the license in every deployment mode; the operator is a convenience
(offline-file signature check before the StatefulSet is created, replica clamp to the license's
`max_instances` on first create, and a lease cache in the operator-owned Secret
`<cluster>-license-cache`).

### Upgrading from chart 1.x (breaking)

The license values were renamed with no compatibility layer. `key`, `license`, `keySecretRef`,
`keySecretKey`, `licenseSecretRef` and `licenseSecretKey` no longer exist. The CRD schema does not
reject the old fields — unknown spec fields are **pruned/ignored** by the API server (kubectl's
strict validation reports them; server-side apply only warns) — so the chart template **fails the
render** when none of the four new values is set, and the CRD's CEL rule refuses a `KubemqCluster`
spec without exactly one of them. Rename them in your values before `helm upgrade`:

| 1.x | 2.x |
|-----|-----|
| `key` | `licenseKey` |
| `license` | `licenseFile` |
| `keySecretRef` + `keySecretKey` | `licenseKeySecretRef.name` + `licenseKeySecretRef.key` |
| `licenseSecretRef` + `licenseSecretKey` | `licenseFileSecretRef.name` + `licenseFileSecretRef.key` |

A HorizontalPodAutoscaler on the KubeMQ StatefulSet is unsupported: the replica count is bound to
the license and managed by the operator.

## What gets installed

| Object | Name |
|--------|------|
| CRDs | `kubemqclusters.next.kubemq.io`, `kubemqconnectors.next.kubemq.io` (version `v1`) |
| Operator Deployment | `kubemq-operator-next` |
| KubemqCluster (when `cluster.enabled=true`) | the release name |

### RBAC objects the chart creates

| Object | Name | When |
|--------|------|------|
| Operator ServiceAccount | `kubemq-operator-next` | `operator.enabled=true` |
| Operator ClusterRole / ClusterRoleBinding | `kubemq-operator-next-<namespace>` / `kubemq-operator-next-<namespace>-binding` | `operator.enabled=true` |
| Server ServiceAccount | `kubemq-cluster-next` | `operator.enabled=true` |
| Server license ClusterRole / ClusterRoleBinding | `kubemq-cluster-next-<namespace>-license` / `kubemq-cluster-next-<namespace>-license-crb` | `operator.enabled=true` |

Every cluster-scoped name carries the release namespace, so the chart installs once per
namespace side by side. The operator watches only its own namespace, and it puts the server
ServiceAccount `kubemq-cluster-next` on every server pod, so the server objects belong to the
release that installs the namespace's operator. A second release in the same namespace with
`operator.enabled=false` (a cluster only) reuses them.

The operator's ClusterRole lists its `next.kubemq.io` resources explicitly (`kubemqclusters`,
`kubemqconnectors` and their `status`); there is no wildcard.

Upgrading from chart 2.1.0 or earlier renames the operator's ClusterRole (it did not carry the
namespace) and, with it, the binding: a ClusterRoleBinding's `roleRef` cannot be changed in place,
so the binding is created under a new name and Helm removes the old pair. Nothing else moves.

The license ClusterRole grants the server `get` on the `kube-system` namespace only: the server
reads that namespace's UID as its installation fingerprint. Without it the server logs a boot
warning and falls back to a persisted random id, and an offline license file bound to a
fingerprint list refuses to start. Non-Helm installs get the same server ServiceAccount,
ClusterRole and ClusterRoleBinding from the operator repo file `deploy/next/rbac.yaml`.

Images come from `europe-docker.pkg.dev/kubemq/images` and need no registry login. The operator image is pinned in `operator.image` with `IfNotPresent` pull policy.
The default server image is pinned in `operator.serverImage` and moves
together with each operator release: a server release can depend on a newer operator, so the
chart never points the server at `:latest`. Override it for one cluster with
`--set image.image=…/kubemq-next:<version>`, or for every cluster the operator creates with
`--set operator.serverImage=…`.

## Upgrade order

Upgrade CRDs explicitly, then the independent operator release, then cluster server images.
Keep the current server image pinned while upgrading the operator. Confirm the operator's rollout
and reconciliation before selecting the compatible newer server image in each cluster release:

```text
helm upgrade kubemq-operator kubemq-next/kubemq-next -n kubemq --reuse-values --set operator.image=PINNED_COMPATIBLE_OPERATOR_IMAGE --set operator.serverImage=CURRENT_SERVER_IMAGE
kubectl rollout status deployment/kubemq-operator-next -n kubemq --timeout=120s
helm upgrade messaging kubemq-next/kubemq-next -n kubemq --reuse-values --set image.image=PINNED_COMPATIBLE_SERVER_IMAGE
```

Record exact chart and image versions before running these commands; placeholders are deliberate.
Inspect all dependent clusters and connectors before changing their shared operator. A chart render
cannot discover runtime compatibility or authorize ownership transfer. Existing combined releases
must follow the separate migration requirements below.

## Configuring the cluster

Every top-level value that is not a chart-only key (`licenseKey`, `licenseFile`, `licenseKeySecretRef`,
`licenseFileSecretRef`, `cluster`, `operator`, `preDelete`, `imagePullSecrets`, `nameOverride`,
`fullnameOverride`) is passed through verbatim into the `KubemqCluster` spec:

```bash
helm install messaging kubemq-next/kubemq-next -n kubemq --set cluster.enabled=true --set operator.enabled=false --set fullnameOverride=messaging --set licenseKey=<key> \
  --set replicas=3 --set volume.size=50Gi --set mqtt.enabled=true
```

Kafka (ports 9092/9093) and RabbitMQ / AMQP 0-9-1 (5672/5671) are on by default — a fresh
install serves both with no connector values. Turn one off with `--set kafka.enabled=false` or
`--set amqp.enabled=false`. The other wire-protocol connectors (`mqtt`, `amqp10`, `stomp`, `aws`,
`gcp`) are opt-in via `<name>.enabled=true`.

The RabbitMQ-compatible management API (`amqp.management.enabled=true`, port 15672) gets its own
Service, `<cluster>-amqp-mgmt`, which is `ClusterIP` (in-cluster only) whatever the AMQP listeners
use. Publish it deliberately with `--set amqp.management.expose=NodePort` or `LoadBalancer`, and
only with authentication configured: without it the management API admits any credentials.

Operator-only is the default. Cluster releases require `--set cluster.enabled=true --set operator.enabled=false`.

## External Kafka access

Kafka returns an address for each broker. A shared Service or `kubectl port-forward` cannot route
those subsequent connections to the right broker. In-cluster clients use the automatically generated
pod addresses. External clients need one reachable address and one Service per server.

For a three-node release named `kubemq-next` in namespace `kubemq`, provision a Service for each
pod. This example uses a fixed NodePort per pod; allow the ports through your firewall and replace
`kafka.example.com` with an address clients can reach on your Kubernetes nodes:

```bash
for ordinal in 0 1 2; do
  kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: kubemq-next-kafka-external-${ordinal}
  namespace: kubemq
spec:
  type: NodePort
  selector:
    statefulset.kubernetes.io/pod-name: kubemq-next-${ordinal}
  ports:
    - name: kafka
      port: 9092
      targetPort: 9092
      nodePort: $((31092 + ordinal))
EOF
done
```

Put the corresponding broker addresses into a values file. Helm passes `kafka.peers` to
`spec.kafka.peers` on the cluster. Broker identifiers are pod ordinals plus one:

```yaml
kafka:
  peers: "1@kafka.example.com:31092,2@kafka.example.com:31093,3@kafka.example.com:31094"
```

Apply that file with `helm upgrade ... --reuse-values -f kafka-external.yaml`. Leave the shared
Kafka Service at `ClusterIP`; the per-pod Services above carry external traffic. Alternatively,
provision a LoadBalancer for each pod and put its assigned address and Kafka port in `peers`.
Every client must be able to reach every advertised address, including clients inside Kubernetes.
Configure authentication and encryption before exposing Kafka to an untrusted network; this example
shows address routing for the plaintext listener. See the
[Kafka Kubernetes access guide](https://docs.kubemq.io/connectors/kafka/how-to/kubernetes-access).

## Removal and retained data

The cluster object always has `helm.sh/resource-policy: keep`. Uninstalling or disabling a cluster
release leaves the cluster running. There is no deletion hook and no hook image to download.
Delete the recorded cluster explicitly, allow the independent operator to finalize it, then uninstall
only its cluster release. Neither Helm nor a hook can delete a same-named replacement cluster.

Before deletion, securely export the customer admin credentials and record the namespace, cluster
UID, member count, engine, volume identities, and Helm release ownership. The generated admin
Secret is owned by the cluster and disappears with it; retained server account data is not reset by
a newly generated Secret. Never use the operator's internal token as a customer credential.

Record and inspect the intended Kubernetes installation and custom resource:

```text
kubectl --context YOUR_CONTEXT get namespace kube-system -o json
kubectl --context YOUR_CONTEXT -n kubemq get kubemqclusters.next.kubemq.io messaging -o json
```

Run the checked-in helper with the recorded `metadata.uid` values and the custom resource's
`metadata.resourceVersion`. It requires Python 3 and kubectl and works without a shell on macOS,
Linux and Windows (use `py -3` instead of `python3` on Windows):

```text
python3 scripts/remove-cluster.py --context YOUR_CONTEXT --namespace kubemq --name messaging --cluster-uid RECORDED_KUBE_SYSTEM_UID --uid RECORDED_CLUSTER_UID --resource-version RECORDED_RESOURCE_VERSION
kubectl --context YOUR_CONTEXT -n kubemq wait --for=delete kubemqclusters.next.kubemq.io/messaging --timeout=180s
helm uninstall messaging --kube-context YOUR_CONTEXT -n kubemq
```

The helper sends Kubernetes `DeleteOptions` with UID and resourceVersion preconditions at the
actual delete. A concurrent update, replacement, denied permission, or unavailable API fails safely;
inspect current state before retrying. A lost response is not proof of deletion. If finalization times
out, restore the operator and permissions and retry observation; never strip finalizers or delete
volumes as a repair. Retain the operator release while any cluster or connector depends on it.
The final uninstall above is permitted only after confirming that release owns the retained cluster
and no shared operator resources. An absent original object with a replacement present requires
inspection, not deletion of the replacement.

Persistent volumes and custom-resource definitions are retained. Reusing volumes requires the
same supported membership and engine, preserved identity, and the existing server credentials.
Destroying data is a separate deliberate operation; no label-wide volume deletion is part of removal.

### Migrating an existing combined release

This is a pre-GA breaking lifecycle change. Do not upgrade a combined release by merely flipping
`operator.enabled` or `cluster.enabled`: its old stored manifest and deletion hook can still remove
shared resources or a same-named replacement. Keep the old chart pinned until a reviewed migration
has recorded every dependent object and retained credential. Before any removal, apply a prepared
chart revision to that same release that removes its hook and marks its cluster as retained while
preserving all its existing operator resources. Verify the saved release manifest and hooks. Then
explicitly delete only the recorded cluster using the helper above and wait for finalization.
Only when no other clusters/connectors use that operator may the old release be uninstalled.
Install the new independent releases afterward. Ownership transfer, volume reattachment, and
retained-account recovery require a separate explicit migration; this chart does not automate them.

Online servers with an old unbound cached lease require one successful activation after upgrading
to input-bound licensing. This includes the operator's injected lease on a fresh store. Once accepted
on the same persistent store, the same configured input retains ordinary signed-lease outage behavior.
Do not delete enforcement or identity records to work around activation refusal.

## Connectors

`KubemqConnector` objects are installed by applying a `next.kubemq.io/v1` manifest; there is no connector
chart. No `-next` connector image is published yet, so the chart sets no default connector image
(`operator.connectorImages.*` are empty): set `spec.image` on every `KubemqConnector`. A connector
without one fails its reconcile with a "no image configured" error in its status and a Warning
event. Once the images ship, set `operator.connectorImages.targets` / `sources` / `bridges`.

## Running beside a legacy v2 installation

The legacy charts (`kubemq-io/charts`) use the API group `core.k8s.kubemq.io` and different object names,
so both lines can run in one Kubernetes cluster. Give the two clusters different
names, and always name the group when using kubectl:

```bash
kubectl get kubemqclusters.next.kubemq.io -A
kubectl get kubemqclusters.core.k8s.kubemq.io -A
```

## Releasing this chart (maintainers)

1. In the operator repo run `task crds:sync` so `kubemq-next/crds/` matches the operator.
2. Bump `version` (and `appVersion`) in `kubemq-next/Chart.yaml`, and bump
   `operator.serverImage` in `kubemq-next/values.yaml` to the server version released with that operator.
3. `scripts/package.sh`, commit `docs/`, push to `main`. GitHub Pages serves `docs/`.

## Supported deployments

This chart installs operator-managed Kubernetes clusters with at least three servers.
`standalone=true` and replica counts of one or two are rejected. Use single-node Docker
for local evaluation. Existing unsupported installations must migrate before upgrading;
do not change an established cluster membership or reuse its member volumes as a new cluster.
Keep the previous chart, operator and server versions pinned until migration is verified.
