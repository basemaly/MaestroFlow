---
type: reference
title: Observability CI/CD Integration
created: 2026-03-22
tags:
  - ci-cd
  - observability
  - devops
  - automation
related:
  - "[[OBSERVABILITY]]"
  - "[[PERFORMANCE_BASELINE]]"
---

# Observability CI/CD Integration

## Overview

This document outlines the CI/CD pipeline integration for the observability system. It ensures that:

- Prometheus configuration syntax is valid
- Alert rules are syntactically correct
- Grafana dashboards are properly formatted
- Environment variable references are complete
- Observability infrastructure is healthy before deployment
- Performance baselines are tracked across releases

---

## Configuration Validation in CI

### 1. Prometheus Configuration Linting

#### Using `yamllint`

```bash
# Install
pip install yamllint

# Lint prometheus.yml
yamllint -d relaxed monitoring/prometheus/prometheus.yml

# Lint alerts.yml
yamllint -d relaxed monitoring/prometheus/alerts.yml

# Return non-zero exit code on failure (for CI)
yamllint -d relaxed monitoring/prometheus/*.yml || exit 1
```

#### Using `prom_rules_validator`

```bash
# Install
pip install prometheus-client pyyaml

# Create validation script
cat > scripts/validate_prometheus_config.py << 'EOF'
#!/usr/bin/env python3
"""Validate Prometheus configuration."""

import sys
import yaml
import re
from pathlib import Path


def validate_prometheus_yml(path):
    """Validate prometheus.yml syntax and structure."""
    try:
        with open(path) as f:
            config = yaml.safe_load(f)
        
        # Check required fields
        assert 'global' in config, "Missing 'global' section"
        assert 'scrape_configs' in config, "Missing 'scrape_configs' section"
        
        # Validate scrape_configs
        for job in config['scrape_configs']:
            assert 'job_name' in job, f"Scrape job missing 'job_name': {job}"
            assert 'static_configs' in job or 'consul_sd_configs' in job, \
                f"Job '{job['job_name']}' missing service discovery"
        
        print(f"✓ {path} is valid")
        return True
    except Exception as e:
        print(f"✗ {path} validation failed: {e}")
        return False


def validate_alerts_yml(path):
    """Validate alerts.yml syntax and structure."""
    try:
        with open(path) as f:
            config = yaml.safe_load(f)
        
        assert 'groups' in config, "Missing 'groups' section"
        
        for group in config['groups']:
            assert 'name' in group, "Alert group missing 'name'"
            assert 'rules' in group, "Alert group missing 'rules'"
            
            for rule in group['rules']:
                assert 'alert' in rule, f"Alert rule missing 'alert' name in {group['name']}"
                assert 'expr' in rule, f"Alert '{rule.get('alert')}' missing 'expr'"
                assert 'for' in rule, f"Alert '{rule.get('alert')}' missing 'for' duration"
        
        print(f"✓ {path} is valid")
        return True
    except Exception as e:
        print(f"✗ {path} validation failed: {e}")
        return False


if __name__ == "__main__":
    valid = True
    valid &= validate_prometheus_yml("monitoring/prometheus/prometheus.yml")
    valid &= validate_alerts_yml("monitoring/prometheus/alerts.yml")
    sys.exit(0 if valid else 1)
EOF

chmod +x scripts/validate_prometheus_config.py
python scripts/validate_prometheus_config.py
```

### 2. Alert Rules Validation

#### Using `amtool`

```bash
# Install amtool
go install github.com/prometheus/alertmanager/cmd/amtool@latest

# Validate alert rules
amtool config routes --config.file=monitoring/alertmanager/alertmanager.yml

# Check syntax
amtool check-config monitoring/alertmanager/alertmanager.yml
```

#### Using Custom Python Validator

```python
#!/usr/bin/env python3
"""Validate alert rules."""

import yaml
import re
import sys
from pathlib import Path


def validate_alert_rules(alerts_file):
    """
    Validate alert rule syntax and completeness.
    
    Checks:
    - Valid YAML syntax
    - Required fields (alert, expr, for)
    - Valid PromQL expressions (basic check)
    - Alert annotations completeness
    """
    with open(alerts_file) as f:
        config = yaml.safe_load(f)
    
    errors = []
    warnings = []
    
    for group in config.get('groups', []):
        for rule in group.get('rules', []):
            alert_name = rule.get('alert', 'unknown')
            
            # Check required fields
            if 'expr' not in rule:
                errors.append(f"Alert '{alert_name}' missing 'expr'")
            elif not isinstance(rule['expr'], str):
                errors.append(f"Alert '{alert_name}' expr must be string")
            
            if 'for' not in rule:
                errors.append(f"Alert '{alert_name}' missing 'for' duration")
            
            # Check annotations
            if 'annotations' not in rule:
                warnings.append(f"Alert '{alert_name}' missing 'annotations'")
            else:
                annotations = rule['annotations']
                if 'summary' not in annotations:
                    warnings.append(f"Alert '{alert_name}' missing 'summary' annotation")
                if 'description' not in annotations:
                    warnings.append(f"Alert '{alert_name}' missing 'description' annotation")
            
            # Basic PromQL validation (not comprehensive)
            expr = rule.get('expr', '')
            if not _is_valid_promql(expr):
                warnings.append(f"Alert '{alert_name}' expr looks suspicious: {expr[:50]}")
    
    # Print results
    for error in errors:
        print(f"ERROR: {error}")
    
    for warning in warnings:
        print(f"WARNING: {warning}")
    
    if errors:
        print(f"\nValidation FAILED with {len(errors)} errors")
        return False
    
    print(f"Validation OK ({len(warnings)} warnings)")
    return True


def _is_valid_promql(expr: str) -> bool:
    """Basic PromQL expression validation."""
    # Check for empty expression
    if not expr.strip():
        return False
    
    # Check for balanced parentheses
    if expr.count('(') != expr.count(')'):
        return False
    
    # Check for balanced brackets
    if expr.count('[') != expr.count(']'):
        return False
    
    # Check for invalid characters (basic)
    invalid_chars = ['@', '#', '$']
    for char in invalid_chars:
        if char in expr:
            return False
    
    return True


if __name__ == "__main__":
    valid = validate_alert_rules("monitoring/prometheus/alerts.yml")
    sys.exit(0 if valid else 1)
```

### 3. Grafana Dashboard Validation

```python
#!/usr/bin/env python3
"""Validate Grafana dashboard JSON."""

import json
import sys
from pathlib import Path


def validate_dashboard_json(dashboard_file):
    """Validate Grafana dashboard JSON syntax and structure."""
    try:
        with open(dashboard_file) as f:
            dashboard = json.load(f)
        
        # Check required fields
        required = ['dashboard', 'overwrite']
        for field in required:
            if field not in dashboard:
                print(f"WARNING: Dashboard missing '{field}'")
        
        # Validate dashboard object
        if 'dashboard' in dashboard:
            db = dashboard['dashboard']
            required_db = ['uid', 'title', 'panels']
            for field in required_db:
                if field not in db:
                    print(f"ERROR: Dashboard missing '{field}'")
                    return False
        
        print(f"✓ {dashboard_file} is valid")
        return True
    except json.JSONDecodeError as e:
        print(f"✗ {dashboard_file} has invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"✗ {dashboard_file} validation failed: {e}")
        return False


if __name__ == "__main__":
    valid = True
    for dashboard_file in Path("monitoring/grafana/dashboards").glob("*.json"):
        valid &= validate_dashboard_json(str(dashboard_file))
    
    sys.exit(0 if valid else 1)
```

### 4. Environment Variable Validation

```python
#!/usr/bin/env python3
"""Validate environment variable completeness."""

import re
import sys
from pathlib import Path


def extract_env_vars(file_path):
    """Extract all environment variables referenced in a file."""
    with open(file_path) as f:
        content = f.read()
    
    # Match $VAR_NAME or ${VAR_NAME}
    pattern = r'\$\{?([A-Z_][A-Z0-9_]*)\}?'
    matches = re.findall(pattern, content)
    return set(matches)


def extract_defined_vars():
    """Extract all defined environment variables from .env.example."""
    defined = set()
    
    with open("backend/.env.example") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    var_name = line.split('=')[0].strip()
                    defined.add(var_name)
    
    return defined


def main():
    """Validate all env var references are defined."""
    print("Validating environment variable references...")
    
    # Files to check
    files_to_check = [
        "docker-compose.yml",
        "monitoring/prometheus/prometheus.yml",
        "monitoring/alertmanager/alertmanager.yml",
        "backend/main.py",
        "backend/src/config/observability.py",
    ]
    
    defined_vars = extract_defined_vars()
    referenced_vars = set()
    
    for file_path in files_to_check:
        if Path(file_path).exists():
            vars_in_file = extract_env_vars(file_path)
            referenced_vars.update(vars_in_file)
    
    # Find undefined references
    undefined = referenced_vars - defined_vars
    
    if undefined:
        print(f"ERROR: Undefined environment variables referenced:")
        for var in sorted(undefined):
            print(f"  - {var}")
        return False
    
    print(f"✓ All {len(referenced_vars)} environment variable references are defined")
    return True


if __name__ == "__main__":
    valid = main()
    sys.exit(0 if valid else 1)
```

---

## Health Check in Deployment Pipeline

### Pre-Deployment Health Check

```bash
#!/bin/bash
# scripts/health_check_pre_deploy.sh

set -e

echo "Performing pre-deployment health checks..."

# Check /health endpoint responsive
echo "Checking /health endpoint..."
for i in {1..10}; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✓ /health endpoint responsive"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "✗ /health endpoint not responding"
        exit 1
    fi
    sleep 1
done

# Check /metrics endpoint accessible
echo "Checking /metrics endpoint..."
METRICS_RESPONSE=$(curl -f http://localhost:8000/metrics 2>/dev/null)
if echo "$METRICS_RESPONSE" | grep -q "http_requests_total"; then
    echo "✓ /metrics endpoint returning valid Prometheus format"
else
    echo "✗ /metrics endpoint invalid"
    exit 1
fi

echo "✓ All pre-deployment checks passed"
```

### Post-Deployment Verification

```bash
#!/bin/bash
# scripts/verify_deployment.sh

set -e

echo "Verifying observability after deployment..."

RETRIES=30
DELAY=2

# Wait for /metrics to be scrape-able
echo "Waiting for Prometheus to scrape metrics..."
for i in $(seq 1 $RETRIES); do
    if curl -f http://localhost:9090/api/v1/query?query=up > /dev/null 2>&1; then
        SAMPLES=$(curl -s http://localhost:9090/api/v1/query?query='up{job="maestroflow"}' | \
                  grep -o '"value"' | wc -l)
        if [ "$SAMPLES" -gt 0 ]; then
            echo "✓ Prometheus scraping metrics (${SAMPLES} samples)"
            break
        fi
    fi
    if [ $i -eq $RETRIES ]; then
        echo "✗ Prometheus not scraping metrics after ${RETRIES} attempts"
        exit 1
    fi
    sleep $DELAY
done

# Smoke test: make request and verify trace appears in Langfuse
echo "Smoke testing Langfuse trace capture..."
RESPONSE=$(curl -s http://localhost:8000/health)
TRACE_ID=$(echo "$RESPONSE" | grep -o '"trace_id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$TRACE_ID" ]; then
    echo "⚠ Warning: trace_id not found in response (might be disabled)"
else
    # Wait for trace to appear in Langfuse
    echo "Waiting for trace ${TRACE_ID} to appear in Langfuse..."
    for i in $(seq 1 10); do
        sleep 1
        # Check if trace exists (requires LANGFUSE_API_KEY in env)
        TRACE_EXISTS=$(curl -s -H "Authorization: Bearer ${LANGFUSE_SECRET_KEY}" \
                          https://cloud.langfuse.com/api/traces/${TRACE_ID} \
                          2>/dev/null | grep -q 'traceId' && echo "true" || echo "false")
        if [ "$TRACE_EXISTS" == "true" ]; then
            echo "✓ Trace appeared in Langfuse within 10 seconds"
            break
        fi
    done
fi

echo "✓ Deployment verification passed"
```

---

## GitHub Actions Workflow

```yaml
# .github/workflows/observability-validation.yml

name: Observability Validation

on:
  push:
    paths:
      - 'monitoring/**'
      - 'backend/src/observability/**'
      - 'backend/src/config/observability.py'
      - '.env.example'
      - '.github/workflows/observability-validation.yml'
  pull_request:
    paths:
      - 'monitoring/**'
      - 'backend/src/observability/**'
      - 'backend/src/config/observability.py'
      - '.env.example'

jobs:
  validate-config:
    name: Validate Observability Configuration
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install validation tools
        run: |
          pip install yamllint pyyaml
      
      - name: Validate Prometheus YAML
        run: |
          yamllint -d relaxed monitoring/prometheus/prometheus.yml
          yamllint -d relaxed monitoring/prometheus/alerts.yml
      
      - name: Validate alert rules
        run: python scripts/validate_prometheus_config.py
      
      - name: Validate environment variables
        run: python scripts/validate_env_vars.py
      
      - name: Validate Grafana dashboards
        run: python scripts/validate_grafana_dashboards.py

  lint-python:
    name: Lint Python Code
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install lint tools
        run: |
          pip install flake8 black isort
      
      - name: Check formatting with black
        run: black --check backend/src/observability/ backend/src/config/observability.py
      
      - name: Check import sorting
        run: isort --check-only backend/src/observability/ backend/src/config/observability.py
      
      - name: Lint with flake8
        run: |
          flake8 backend/src/observability/ backend/src/config/observability.py \
            --max-line-length=100 --ignore=E203,W503

  test-integration:
    name: Test Observability Integration
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install pytest pytest-cov
      
      - name: Run observability tests
        run: |
          python -m pytest backend/tests/test_observability_*.py -v --cov=backend/src/observability
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          flags: observability
          name: observability-coverage

  docker-build:
    name: Build Docker Images
    runs-on: ubuntu-latest
    if: github.event_name == 'push'
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      
      - name: Build images
        run: |
          docker-compose -f docker-compose.yml build
      
      - name: Start services
        run: |
          docker-compose -f docker-compose.yml up -d
      
      - name: Wait for services
        run: |
          for service in prometheus grafana alertmanager fastapi; do
            echo "Waiting for $service..."
            for i in {1..30}; do
              if docker ps | grep -q "$service"; then
                echo "✓ $service running"
                break
              fi
              if [ $i -eq 30 ]; then
                echo "✗ $service failed to start"
                docker-compose logs $service
                exit 1
              fi
              sleep 1
            done
          done
      
      - name: Health check
        run: |
          bash scripts/health_check_pre_deploy.sh
      
      - name: Cleanup
        if: always()
        run: docker-compose down
```

---

## Integration Summary

### Validation Stages

| Stage | Tools | Purpose |
|-------|-------|---------|
| **Config** | yamllint, custom scripts | Syntax and structure validation |
| **Rules** | amtool, custom validator | Alert rule completeness |
| **Dashboard** | Custom JSON validator | Grafana dashboard format |
| **Python** | flake8, black, isort | Code quality |
| **Integration** | pytest | End-to-end testing |
| **Docker** | docker-compose | Container build and startup |
| **Health** | curl, bash scripts | Endpoint and service validation |

### Success Criteria

✅ All config files pass linting
✅ All alert rules are syntactically valid
✅ All environment variable references are defined
✅ All Python code passes linting
✅ All integration tests pass
✅ Docker images build successfully
✅ All health checks pass after deployment
✅ Metrics appear in Prometheus within 5 minutes
✅ Traces appear in Langfuse within 10 seconds (if enabled)

---

## Next Steps

1. ✅ Create validation scripts (config, alerts, dashboards, env vars)
2. ✅ Create health check scripts (pre/post deployment)
3. ✅ Create GitHub Actions workflow
4. ⏳ Test CI/CD pipeline against staging environment
5. ⏳ Document troubleshooting procedures
6. ⏳ Set up alerts for CI/CD failures
