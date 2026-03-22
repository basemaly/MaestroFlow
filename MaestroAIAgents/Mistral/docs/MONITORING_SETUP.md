---
type: guide
title: Monitoring Setup & Configuration Guide
created: 2026-03-21
tags:
  - monitoring
  - prometheus
  - grafana
  - setup
  - ops
---

# MaestroFlow Monitoring Setup Guide

This guide walks through setting up Prometheus, Grafana, and Langfuse for complete application observability.

## Table of Contents

1. [Quick Start (5 minutes)](#quick-start)
2. [Docker Compose Stack Setup](#docker-compose-setup)
3. [Grafana Dashboard Configuration](#grafana-dashboards)
4. [AlertManager Integration](#alertmanager-integration)
5. [Langfuse Setup](#langfuse-setup)
6. [Backup & Restore](#backup--restore)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

- Docker & Docker Compose installed
- FastAPI backend running on `localhost:8000`
- Metrics endpoint available at `localhost:8000/metrics`

### Step 1: Start the Monitoring Stack

```bash
cd /Volumes/BA/DEV/MaestroAIAgents/Mistral

# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps
```

Expected output:
```
NAME                      STATUS
maestroflow-prometheus    Up (healthy)
maestroflow-grafana       Up (healthy)
maestroflow-alertmanager  Up (healthy)
maestroflow-redis         Up (healthy)
```

### Step 2: Verify Metrics Collection

```bash
# Check that Prometheus is scraping metrics
curl http://localhost:9090/api/v1/query?query=up

# You should see: maestroflow target is 1 (up)
```

### Step 3: Access Dashboards

- **Prometheus:** http://localhost:9090
- **Grafana:** http://localhost:3000 (login: admin/admin)
- **AlertManager:** http://localhost:9093

---

## Docker Compose Setup

The `docker-compose.yml` starts 5 services:

### 1. Prometheus

**Port:** 9090  
**Purpose:** Metrics time-series database and alerting engine  
**Volume:** `./monitoring/prometheus/prometheus.yml` (configuration)

#### Configuration

Edit `monitoring/prometheus/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: maestroflow
    static_configs:
      - targets: ['host.docker.internal:8000']  # FastAPI app
    metrics_path: '/metrics'
    scrape_interval: 15s
```

#### Common Configuration Changes

**Change scrape interval (default: 15s):**
```yaml
scrape_configs:
  - job_name: maestroflow
    scrape_interval: 30s  # Lower frequency for high-volume apps
```

**Add custom label to all metrics:**
```yaml
scrape_configs:
  - job_name: maestroflow
    static_configs:
      - targets: ['host.docker.internal:8000']
    metric_relabel_configs:
      - source_labels: [__address__]
        target_label: instance
```

### 2. Grafana

**Port:** 3000  
**Purpose:** Visualization and dashboard creation  
**Default Credentials:** admin / admin

#### Configuration

Edit environment variables in `docker-compose.yml`:

```yaml
grafana:
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=your_new_password
    - GF_USERS_ALLOW_SIGN_UP=false  # Disable registration
    - GF_AUTH_ANONYMOUS_ENABLED=false
```

#### Custom Configuration

Create `monitoring/grafana/grafana.ini` and mount it:

```yaml
grafana:
  volumes:
    - ./monitoring/grafana/grafana.ini:/etc/grafana/grafana.ini
```

### 3. AlertManager

**Port:** 9093  
**Purpose:** Alert routing and notification management

#### Configuration

Edit `monitoring/alertmanager/alertmanager.yml`:

```yaml
receivers:
  - name: 'slack'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        channel: '#maestroflow-alerts'
```

To add Slack integration:

1. Create Slack app: https://api.slack.com/apps
2. Add Incoming Webhooks
3. Copy webhook URL
4. Update `alertmanager.yml`:

```bash
# Or set environment variable
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
docker-compose up -d
```

### 4. Redis

**Port:** 6379  
**Purpose:** Caching and queue operations

#### Configuration

No configuration needed for basic usage. For production:

```yaml
redis:
  command: redis-server --requirepass your_password
```

### 5. PostgreSQL (Optional)

Uncomment in `docker-compose.yml` to use PostgreSQL instead of SQLite:

```yaml
postgres:
  image: postgres:15-alpine
  environment:
    POSTGRES_DB: maestroflow
    POSTGRES_USER: maestroflow
    POSTGRES_PASSWORD: your_password
  ports:
    - "5432:5432"
```

Then set in FastAPI `.env`:
```bash
DATABASE_URL=postgresql://maestroflow:your_password@localhost:5432/maestroflow
```

---

## Grafana Dashboards

### Importing Pre-Built Dashboards

1. Open Grafana: http://localhost:3000
2. Click **+** → **Import**
3. Upload JSON file from `monitoring/grafana/dashboards/` or
4. Paste dashboard ID (for community dashboards)

### Common Dashboard IDs

- **1860** — Node Exporter for Prometheus
- **3662** — Prometheus 2.0 Stats
- **8919** — Prometheus Exporter Stats

### Creating Custom Dashboards

#### Dashboard: MaestroFlow Metrics Overview

1. New Dashboard → Add Panel
2. Choose **Prometheus** as data source
3. Add panels:

**Panel 1: HTTP Request Rate**
```
Query: rate(http_requests_total[5m])
Visualization: Graph
Title: Requests Per Minute
```

**Panel 2: Request Latency (p95)**
```
Query: histogram_quantile(0.95, http_request_duration_seconds)
Visualization: Stat
Title: p95 Latency (seconds)
```

**Panel 3: Error Rate**
```
Query: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])
Visualization: Gauge
Title: 5xx Error Rate
```

**Panel 4: Cache Hit Ratio**
```
Query: cache_hit_ratio
Visualization: Gauge
Title: Cache Hit Ratio
```

**Panel 5: Memory Usage**
```
Query: process_memory_usage_bytes / 1024 / 1024
Visualization: Graph
Title: Memory (MB)
```

### Dashboard Best Practices

- **Time Range:** Set to "Last 6 hours" for development
- **Refresh Rate:** Auto-refresh every 10 seconds
- **Alerting:** Add alert thresholds to key panels
- **Organization:** Group related panels in rows

---

## AlertManager Integration

### Step 1: Enable Alerts

Prometheus loads alert rules from `monitoring/prometheus/alerts.yml`.

Verify alerts are loaded:
1. Go to Prometheus: http://localhost:9090
2. Click **Alerts** (top menu)
3. You should see all alert rules listed

### Step 2: Configure Notification Channel

Edit `monitoring/alertmanager/alertmanager.yml`:

#### Slack Notifications

```yaml
receivers:
  - name: 'slack'
    slack_configs:
      - api_url: 'YOUR_WEBHOOK_URL'
        channel: '#maestroflow-alerts'
        title: 'Alert: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
```

#### PagerDuty Integration

```yaml
receivers:
  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: 'YOUR_SERVICE_KEY'
        description: '{{ .GroupLabels.alertname }}'
```

#### Email Notifications

```yaml
receivers:
  - name: 'email'
    email_configs:
      - to: 'alerts@example.com'
        from: 'alertmanager@example.com'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'your_email@gmail.com'
        auth_password: 'your_app_password'
```

### Step 3: Reload AlertManager Configuration

```bash
# After editing alertmanager.yml
docker-compose restart alertmanager
```

### Step 4: Test Alert Routing

To test if alerts reach your notification channel:

```bash
# Make a request to trigger an error
for i in {1..100}; do
  curl http://localhost:8000/invalid-endpoint 2>/dev/null &
done
wait

# Check AlertManager UI for active alerts
# http://localhost:9093
```

### Alert Severity Levels

| Severity | Response Time | Channel |
|----------|---------------|---------|
| **info** | None | Logging only |
| **warning** | 4 hours | Slack |
| **critical** | 15 minutes | PagerDuty |

---

## Langfuse Setup

### Option 1: Cloud (Langfuse.com)

1. Sign up: https://cloud.langfuse.io
2. Create project
3. Copy API keys
4. Add to `.env`:

```bash
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk_xxxxx
LANGFUSE_SECRET_KEY=sk_xxxxx
LANGFUSE_HOST=https://cloud.langfuse.io
```

5. Restart FastAPI:

```bash
python3 backend/main.py
```

6. View traces: https://cloud.langfuse.io

### Option 2: Self-Hosted Langfuse

Add to `docker-compose.yml`:

```yaml
langfuse:
  image: langfuse/langfuse:latest
  container_name: maestroflow-langfuse
  ports:
    - "3000:3000"
  environment:
    DATABASE_URL: postgresql://user:pass@postgres:5432/langfuse
    NODE_ENV: production
    NEXTAUTH_SECRET: your_secret_here
  depends_on:
    - postgres
  networks:
    - observability
```

Then update `.env`:

```bash
LANGFUSE_HOST=http://localhost:3000
```

### Option 3: Development (Mock Client)

For local development without Langfuse:

```bash
LANGFUSE_ENABLED=false
```

The mock client logs traces to console but doesn't send them.

### Viewing Traces

1. Open Langfuse UI
2. Click **Traces**
3. Filter by:
   - **trace_id** — Request unique ID
   - **user_id** — User who made request
   - **session_id** — Conversation session
4. Click trace to see:
   - Full request/response
   - LLM model and tokens
   - Cost calculation
   - Nested spans (DB queries, cache, etc.)

---

## Backup & Restore

### Backup Prometheus Data

```bash
# Stop Prometheus
docker-compose stop prometheus

# Backup volume
docker run --rm -v maestroflow_prometheus_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/prometheus-backup.tar.gz -C /data .

# Restart
docker-compose start prometheus
```

### Restore Prometheus Data

```bash
# Stop Prometheus
docker-compose stop prometheus

# Restore from backup
docker run --rm -v maestroflow_prometheus_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/prometheus-backup.tar.gz -C /data

# Restart
docker-compose start prometheus
```

### Backup Grafana Dashboards

```bash
# Export all dashboards
curl -H "Authorization: Bearer $GRAFANA_API_TOKEN" \
  http://localhost:3000/api/dashboards/db > grafana-dashboards.json

# Or export individual dashboard
curl -H "Authorization: Bearer $GRAFANA_API_TOKEN" \
  "http://localhost:3000/api/dashboards/db/dashboard-name" > dashboard.json
```

### Restore Grafana Dashboards

```bash
# Import dashboard JSON
curl -X POST -H "Authorization: Bearer $GRAFANA_API_TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:3000/api/dashboards/db \
  -d @dashboard.json
```

---

## Troubleshooting

### Prometheus Can't Reach FastAPI

**Problem:** Prometheus shows maestroflow target as "DOWN"

**Solution:**
1. Check if FastAPI is running:
   ```bash
   curl http://localhost:8000/health
   ```

2. Check Prometheus configuration:
   ```bash
   cat monitoring/prometheus/prometheus.yml
   # Verify target is correct
   ```

3. On macOS, use `host.docker.internal`:
   ```yaml
   # In prometheus.yml
   targets: ['host.docker.internal:8000']
   ```

4. Reload Prometheus:
   ```bash
   docker-compose restart prometheus
   ```

### Metrics Endpoint Returns 500

**Problem:** `GET /metrics` returns error

**Solution:**
1. Check metrics module is initialized:
   ```python
   python3 -c "from src.observability import get_metrics; print(get_metrics())"
   ```

2. Check for metric cardinality explosion:
   - Too many unique label combinations
   - Fix: Normalize labels (e.g., group unknown endpoints)

3. Restart FastAPI:
   ```bash
   pkill -f "python3 backend/main.py"
   python3 backend/main.py
   ```

### Grafana Can't Connect to Prometheus

**Problem:** "Unable to connect to Prometheus"

**Solution:**
1. Check service connectivity:
   ```bash
   docker-compose exec grafana curl http://prometheus:9090
   ```

2. Verify data source configuration:
   - Grafana → Configuration → Data Sources
   - Edit Prometheus data source
   - URL should be `http://prometheus:9090` (not localhost)

3. Test connection:
   - Click "Save & Test"
   - Should show "Data source is working"

### Alerts Not Firing

**Problem:** Alert rules are configured but not triggering

**Solution:**
1. Check alert rules syntax:
   ```bash
   docker-compose logs prometheus | grep -i alert
   ```

2. Verify metric exists:
   ```bash
   # Go to Prometheus → Graph
   # Query: db_query_duration_seconds
   # Should return data points
   ```

3. Check AlertManager configuration:
   ```bash
   curl http://localhost:9093/api/v1/status
   ```

4. View alerts:
   ```bash
   # Prometheus UI → Alerts tab
   # Should show green (OK) or red (FIRING)
   ```

---

## Performance Tuning

### Reduce Prometheus Disk Usage

By default, Prometheus keeps 30 days of data. To reduce:

```yaml
command:
  - "--storage.tsdb.retention.time=7d"  # Keep 7 days instead of 30
```

### Reduce Scrape Frequency

Scrape every 30 seconds instead of 15:

```yaml
prometheus:
  volumes:
    - ./monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
  # In prometheus.yml:
  # global:
  #   scrape_interval: 30s
```

### Optimize Grafana Performance

- Limit dashboard refresh rate to 30 seconds
- Reduce data point resolution in panels
- Use Prometheus query recording rules for expensive queries

---

## Next Steps

1. **Import Grafana Dashboards** — Use community dashboards or create custom ones
2. **Configure Alerts** — Wire AlertManager to Slack/PagerDuty
3. **Define SLOs** — Set Service Level Objectives based on metrics
4. **Capacity Planning** — Use trends to forecast resource needs
5. **Cost Optimization** — Analyze metrics to find inefficiencies

---

## Reference

- Prometheus Docs: https://prometheus.io/docs/
- Grafana Docs: https://grafana.com/docs/
- AlertManager Docs: https://prometheus.io/docs/alerting/alertmanager/
- Langfuse Docs: https://langfuse.com/docs/
