{{/*
Expand the name of the chart.
*/}}
{{- define "doctor-ku.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "doctor-ku.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "doctor-ku.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "doctor-ku.labels" -}}
helm.sh/chart: {{ include "doctor-ku.chart" . }}
{{ include "doctor-ku.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "doctor-ku.selectorLabels" -}}
app.kubernetes.io/name: {{ include "doctor-ku.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Variables de entorno comunes del contenedor
*/}}
{{- define "doctor-ku.containerEnv" -}}
- name: CONFIG_PATH
  value: /config/clusters.yaml
- name: SSH_KEYS_DIR
  value: /secrets/ssh
- name: SCRIPTS_DIR
  value: /scripts
- name: LOG_LEVEL
  value: {{ .Values.base.deployment.logLevel | default "INFO" | quote }}
- name: TZ
  value: {{ .Values.config.global.timezone | default "America/Argentina/Buenos_Aires" | quote }}
- name: STATE_PATH
  value: {{ .Values.persistence.stateFile | default "/data/state.json" | quote }}
- name: RUN_TIMEOUT_SECONDS
  value: {{ .Values.cron.runTimeoutSeconds | default 1500 | quote }}
{{- range $key, $value := .Values.base.deployment.env }}
- name: {{ $key }}
  value: {{ $value | quote }}
{{- end }}
{{- end }}

{{/*
Montajes de volumen comunes
*/}}
{{- define "doctor-ku.volumeMounts" -}}
- name: config
  mountPath: /config
  readOnly: true
- name: scripts
  mountPath: /scripts
  readOnly: true
{{- if .Values.secrets.sshKeys }}
- name: secrets
  mountPath: /secrets
  readOnly: true
{{- end }}
{{- if .Values.persistence.enabled }}
- name: data
  mountPath: {{ .Values.persistence.mountPath | default "/data" }}
{{- end }}
{{- end }}

{{/*
Volumenes comunes
*/}}
{{- define "doctor-ku.volumes" -}}
- name: config
  configMap:
    name: {{ include "doctor-ku.fullname" . }}-config
- name: scripts
  configMap:
    name: {{ include "doctor-ku.fullname" . }}-scripts
    defaultMode: 0555
{{- if .Values.secrets.sshKeys }}
- name: secrets
  secret:
    secretName: {{ include "doctor-ku.fullname" . }}-secrets
    items:
    {{- range $name, $_ := .Values.secrets.sshKeys }}
    - key: ssh-{{ $name }}
      path: ssh/{{ $name }}
    {{- end }}
{{- end }}
{{- if .Values.persistence.enabled }}
- name: data
  persistentVolumeClaim:
    claimName: {{ include "doctor-ku.fullname" . }}-data
{{- end }}
{{- end }}
