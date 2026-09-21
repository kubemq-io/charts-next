# KubeMQ Helm chart — next line

One chart, `kubemq-next`, installs everything a new KubeMQ deployment needs on Kubernetes: the
CRDs, the operator, and (by default) one KubeMQ cluster.

> **"next" means two things in KubeMQ.** `-next` artifacts (this chart, the `kubemq-next` image, the
> `next.kubemq.io` API group) are the current product line for new installations. The *next storage
> engine* is the server's storage engine, selected with `store.engine`. They are independent names.

## Install

```bash
helm repo add kubemq-next https://kubemq-io.github.io/charts-next
helm repo update
# online license key
helm install kubemq-next kubemq-next/kubemq-next -n kubemq --create-namespace --set licenseKey=<your-license-key>
# or an offline, signed license file (armored "-----BEGIN KUBEMQ LICENSE-----" text or a bare compact JWS)
helm install kubemq-next kubemq-next/kubemq-next -n kubemq --create-namespace --set-file licenseFile=./kubemq.license
```

## Licensing

A KubeMQ server does not start without a license. The chart takes exactly **one** of four sources
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
helm install kubemq-next kubemq-next/kubemq-next -n kubemq --set licenseKeySecretRef.name=my-kubemq-license
# file
kubectl -n kubemq create secret generic my-kubemq-license --from-file=licenseFile=./kubemq.license
helm install kubemq-next kubemq-next/kubemq-next -n kubemq --set licenseFileSecretRef.name=my-kubemq-license
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
| Server Role / RoleBinding (OpenShift `privileged` SCC) | `kubemq-cluster-next-role` / `kubemq-cluster-next-rb` | `operator.enabled=true` |
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

Images come from `europe-docker.pkg.dev/kubemq/images` and need no registry login. The operator
is `kubemq-operator-next:latest`; pin it with `--set operator.image=…/kubemq-operator-next:<version>`.
The default server image is pinned to `kubemq-next:v1.1.0` (`operator.serverImage`) and moves
together with each operator release: a server release can depend on a newer operator, so the
chart never points the server at `:latest`. Override it for one cluster with
`--set image.image=…/kubemq-next:<version>`, or for every cluster the operator creates with
`--set operator.serverImage=…`.

## Configuring the cluster

Every top-level value that is not a chart-only key (`licenseKey`, `licenseFile`, `licenseKeySecretRef`,
`licenseFileSecretRef`, `cluster`, `operator`, `preDelete`, `imagePullSecrets`, `nameOverride`,
`fullnameOverride`) is passed through verbatim into the `KubemqCluster` spec:

```bash
helm install kubemq-next kubemq-next/kubemq-next -n kubemq --set licenseKey=<key> \
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

Operator only, no cluster: `--set cluster.enabled=false`, then apply your own `next.kubemq.io/v1`
`KubemqCluster` manifests.

## Data warning

Both of these delete the `KubemqCluster` and its pods:

- `helm upgrade … --set cluster.enabled=false` on a live release
- `helm uninstall`

The PersistentVolumeClaims are **kept** in both cases. Delete them yourself when the data is no longer
needed. `helm uninstall` also leaves the two CRDs in place — Helm never removes CRDs.

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
