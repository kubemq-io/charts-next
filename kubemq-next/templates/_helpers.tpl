{{/* vim: set filetype=mustache: */}}


{{/*{{- define "kubemq.name" -}}*/}}
{{/*{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}*/}}
{{/*{{- end -}}*/}}

{{- define "kubemq.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "kubemq.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create the name of the service account to use
*/}}
{{- define "mychart.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
    {{ default (include "mychart.fullname" .) .Values.serviceAccount.name }}
{{- else -}}
    {{ default "default" .Values.serviceAccount.name }}
{{- end -}}
{{- end -}}

{{- define "kubemq.operatorRoleName" -}}
{{- printf "kubemq-operator-next-%s" .Release.Namespace -}}
{{- end -}}

{{- /* The binding is renamed together with the ClusterRole it points at: roleRef is immutable,
     so an upgrade that changed only the reference would be rejected by the API server. Under a
     new name Helm creates the new binding and removes the old one. */}}
{{- define "kubemq.crbName" -}}
{{- printf "kubemq-operator-next-%s-binding" .Release.Namespace -}}
{{- end -}}

{{/* Release-namespace-scoped names for the server's license ClusterRole and its binding:
     cluster-scoped objects, so two releases in different namespaces must not collide. */}}
{{- define "kubemq.clusterLicenseRoleName" -}}
{{- printf "kubemq-cluster-next-%s-license" .Release.Namespace -}}
{{- end -}}
{{- define "kubemq.clusterLicenseCrbName" -}}
{{- printf "kubemq-cluster-next-%s-license-crb" .Release.Namespace -}}
{{- end -}}
