# Observability Assets

This folder contains local configuration assets for the observability tools wired into the app.

- `prometheus/prometheus.yml`: Prometheus scrape configuration for the app's `/metrics` endpoint
- `grafana/provisioning/`: Grafana datasource and dashboard provisioning
- `grafana/dashboards/fastapi-observability.json`: starter dashboard for request rate, latency, and queue depth
- `otel-collector/config.yaml`: OpenTelemetry Collector config for receiving OTLP traces
- `filebeat/filebeat.yml`: ELK shipper example for ECS JSON logs
- `fluent-bit/fluent-bit.conf`: EFK shipper example for ECS JSON logs
- `newrelic/newrelic.ini`: New Relic agent configuration template

Use these files as local examples. In production you would usually manage them with Docker Compose, Kubernetes manifests, Helm charts, or your cloud observability platform.
