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
helm install kubemq-next kubemq-next/kubemq-next -n kubemq --create-namespace --set key=<your-license-key>
```

To keep the license key out of the cluster object and out of Helm's saved values, reference a Secret:

```bash
kubectl -n kubemq create secret generic kubemq-license --from-literal=key=<your-license-key>
helm install kubemq-next kubemq-next/kubemq-next -n kubemq --set keySecretRef=kubemq-license
```

## What gets installed

| Object | Name |
|--------|------|
| CRDs | `kubemqclusters.next.kubemq.io`, `kubemqconnectors.next.kubemq.io` (version `v1`) |
| Operator Deployment and ServiceAccount | `kubemq-operator-next` |
| ClusterRole / ClusterRoleBinding | `kubemq-operator-next` / `kubemq-operator-next-<namespace>-crb` |
| Server ServiceAccount, Role, RoleBinding | `kubemq-cluster-next`, `kubemq-cluster-next-role`, `kubemq-cluster-next-rb` |
| KubemqCluster (when `cluster.enabled=true`) | the release name |

Images come from `europe-docker.pkg.dev/kubemq/images` and need no registry login:
`kubemq-operator-next:latest` and `kubemq-next:latest`. Pin a release with
`--set operator.image=…:v1.0.0` and `--set image.image=…/kubemq-next:v1.0.0`.

## Configuring the cluster

Every top-level value that is not a chart-only key (`key`, `license`, `cluster`, `operator`,
`preDelete`, `imagePullSecrets`, `nameOverride`, `fullnameOverride`) is passed through verbatim into the
`KubemqCluster` spec:

```bash
helm install kubemq-next kubemq-next/kubemq-next -n kubemq --set key=<key> \
  --set replicas=3 --set volume.size=50Gi --set mqtt.enabled=true
```

Kafka (ports 9092/9093) and RabbitMQ / AMQP 0-9-1 (5672/5671) are on by default — a fresh
install serves both with no connector values. Turn one off with `--set kafka.enabled=false` or
`--set amqp.enabled=false`. The other wire-protocol connectors (`mqtt`, `amqp10`, `stomp`, `aws`,
`gcp`) are opt-in via `<name>.enabled=true`.

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
chart. Connector images ship in next v1.1 — until then set `spec.image` on every `KubemqConnector`.

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
2. Bump `version` (and `appVersion`) in `kubemq-next/Chart.yaml`.
3. `scripts/package.sh`, commit `docs/`, push to `main`. GitHub Pages serves `docs/`.
