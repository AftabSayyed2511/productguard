"""
Gunicorn WSGI Configuration for ProductGuard Commercial Deployment
Configured for AI/ML inference workloads on containerized Linux hosts.
"""

import os
import multiprocessing

# Server Socket Binding
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:5000")
backlog = 2048

# Worker Processes & Concurrency
# For ML models (MobileNetV2 in RAM), use 2-4 workers with thread concurrency
# to avoid OOM while maintaining high throughput.
workers = int(os.getenv("GUNICORN_WORKERS", 2))
threads = int(os.getenv("GUNICORN_THREADS", 2))
worker_class = "gthread"
worker_connections = 1000

# Timeout Management
# MobileNetV2 image inference typically executes in 80-250ms, but allowing 120s
# prevents premature connection termination during heavy multi-user batch uploads.
timeout = int(os.getenv("GUNICORN_TIMEOUT", 120))
keepalive = 5
graceful_timeout = 30

# Memory & Process Recycling
max_requests = 1000
max_requests_jitter = 50

# Logging
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sµs'

# Process Identification
proc_name = "productguard_wsgi"
preload_app = False
