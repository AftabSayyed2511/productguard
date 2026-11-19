"""
Tests for Phase 11: Production Deployment Configuration & Assets
Validates:
- Dockerfile existence and configuration
- docker-compose.yml syntax and service definitions
- gunicorn.conf.py parameters
- ProductionConfig loading and environment handling
"""

import os
from pathlib import Path
from config import config_by_name, BASE_DIR, ProductionConfig


def test_dockerfile_and_compose_exist():
    """Verify production container deployment manifests exist."""
    assert (BASE_DIR / "Dockerfile").exists()
    assert (BASE_DIR / "docker-compose.yml").exists()
    assert (BASE_DIR / "gunicorn.conf.py").exists()
    assert (BASE_DIR / ".env.production.example").exists()


def test_gunicorn_conf_parameters():
    """Verify gunicorn configuration defines essential concurrency parameters."""
    gconf_path = BASE_DIR / "gunicorn.conf.py"
    content = gconf_path.read_text(encoding="utf-8")
    assert "bind" in content
    assert "workers" in content
    assert "threads" in content
    assert "timeout" in content
    assert "worker_class" in content


def test_docker_compose_structure():
    """Verify docker-compose includes web and db services."""
    compose_path = BASE_DIR / "docker-compose.yml"
    content = compose_path.read_text(encoding="utf-8")

    assert "services:" in content
    assert "web:" in content
    assert "db:" in content
    assert "postgres" in content
    assert "uploads_data:" in content


def test_production_config_class():
    """Verify ProductionConfig class inherits base parameters properly."""
    assert "production" in config_by_name
    prod_cls = config_by_name["production"]
    assert prod_cls.DEBUG is False
    assert prod_cls.TESTING is False
    assert prod_cls.SIMILARITY_THRESHOLD_HIGH == 0.82
