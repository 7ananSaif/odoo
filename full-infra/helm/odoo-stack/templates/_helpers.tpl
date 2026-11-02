{{/*
Expand the name of the chart.
*/}}
{{- define "odoo-stack.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "odoo-stack.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Chart label.
*/}}
{{- define "odoo-stack.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "odoo-stack.labels" -}}
helm.sh/chart: {{ include "odoo-stack.chart" . }}
{{ include "odoo-stack.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "odoo-stack.selectorLabels" -}}
app.kubernetes.io/name: {{ include "odoo-stack.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Postgres component selector labels.
*/}}
{{- define "odoo-stack.postgresSelectorLabels" -}}
app.kubernetes.io/name: {{ include "odoo-stack.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: postgres
{{- end }}

{{/*
Odoo component selector labels.
*/}}
{{- define "odoo-stack.odooSelectorLabels" -}}
app.kubernetes.io/name: {{ include "odoo-stack.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: odoo
{{- end }}

{{/*
Postgres probe body shared by the startup, readiness and liveness probes.

Postgres has no HTTP endpoint, so `pg_isready` is the Postgres-native check:
it opens a TCP connection and asks the server whether it is accepting
connections. Exit 0 = accepting, 1 = rejecting (starting up / shutting down),
2 = no response, 3 = no attempt.

Usage - pass the root `$` and the probe name, so the command can still read
postgres.user / postgres.database while the timings come from the named probe:
  readinessProbe:
    {{- include "odoo-stack.postgresProbe" (dict "root" $ "probe" "readiness") | nindent 12 }}
Keeping the command in one place means the three probes can never drift onto
different checks.
*/}}
{{- define "odoo-stack.postgresProbe" -}}
{{- $postgres := .root.Values.postgres -}}
{{- $probe := index $postgres.probes .probe -}}
exec:
  command: ["sh", "-c", "pg_isready -U {{ $postgres.user }} -d {{ $postgres.database }}"]
periodSeconds: {{ $probe.periodSeconds }}
timeoutSeconds: {{ $probe.timeoutSeconds }}
failureThreshold: {{ $probe.failureThreshold }}
successThreshold: {{ $probe.successThreshold }}
{{- end }}
