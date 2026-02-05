{{- define "agentic.name" -}}
agentic-system
{{- end -}}

{{- define "agentic.namespace" -}}
{{ .Values.namespace | default "agentic-system" }}
{{- end -}}
