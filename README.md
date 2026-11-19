# ProductGuard – AI-Based Counterfeit Product Detection Platform

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![TensorFlow](https://img.shields.io/badge/TensorFlow_CPU-2.21-FF6F00?logo=tensorflow&logoColor=white)](https://www.tensorflow.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.11-5C3EE8?logo=opencv&logoColor=white)](https://opencv.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Test_Suite-62_Passed_(100%25)-22c55e?logo=pytest&logoColor=white)](https://pytest.org/)

> **"Detect. Verify. Protect."**  
> An enterprise-grade, end-to-end computer vision and visual similarity platform designed to identify counterfeit consumer product packaging by comparing real-time image uploads against verified manufacturer reference standards.

---

## 1. System Overview

ProductGuard is a production-ready web application engineered as a final-year software and AI engineering project. It replaces traditional superficial rule engines with an authentic Deep Learning visual feature extraction pipeline:

1. **User Authentication & RBAC**: Secure credential hashing (PBKDF2/SHA-256), session management, active account validation, and role-based access control (`user` vs. `admin`).
2. **AI Feature Extraction Backbone**: MobileNetV2 pretrained on ImageNet (Global Average Pooling head, 1,280-dimensional feature representations).
3. **Similarity Engine**: L2-normalized cosine distance comparison against category-constrained verified reference packaging embeddings cached on disk (`.npy`).
4. **Interactive Portals**: Real-time drag-and-drop scanner, personal analytics dashboard with Chart.js, and an administrative command center for genuine product catalog management and security audit logging.

---

## 2. Technical Architecture

```
                    ┌──────────────────────────────────────────────┐
                    │               CLIENT BROWSER                 │
                    │   HTML5 / Bootstrap 5 / Chart.js / Vanilla JS │
                    └───────────────────────┬──────────────────────┘
                                            │ HTTP / REST APIs (CSRF & Rate Limited)
                                            ▼
                    ┌──────────────────────────────────────────────┐
                    │            FLASK APPLICATION CORE            │
                    │   Blueprints: Main, Auth, Scan, User, Admin  │
                    │   Middlewares: Limiter, Security Headers, ORM│
                    └───────┬───────────────────────────────┬──────┘
                            │                               │
                Save Image  ▼                   Load Embed  ▼
        ┌─────────────────────────┐             ┌─────────────────────────┐
        │     STORAGE ENGINE      │             │    RELATIONAL DB        │
        │ - uploads/references/   │             │ SQLite (Local Dev) /    │
        │ - uploads/scans/        │             │ PostgreSQL 16 (Docker)  │
        │ - uploads/embeddings/   │             │ Tables: users, products,│
        └───────────┬─────────────┘             │ reference_images, scans,│
                    │                           │ admin_activities        │
                    ▼                           └─────────────────────────┘
        ┌─────────────────────────────────────────┐
        │       AI COMPUTER VISION PIPELINE       │
        │ 1. Pillow: Content & Format Validation  │
        │ 2. OpenCV: RGB conversion & 224x224 res │
        │ 3. MobileNetV2: 1280-D Feature Vector   │
        │ 4. Scikit-Learn: Cosine Similarity      │
        │ 5. Calibrated Threshold Classification  │
        └─────────────────────────────────────────┘
```

---

## 3. Mathematical & AI Methodology

### Image Preprocessing
Input packaging images $I \in \mathbb{R}^{H \times W \times C}$ are validated for genuine MIME content, converted to standard 3-channel RGB, and resized using bilinear interpolation:
$$\tilde{I} = \text{Resize}(I, (224, 224))$$
Pixels are mapped to $[-1, 1]$ matching ImageNet normalization:
$$x = \frac{\tilde{I}}{127.5} - 1.0$$

### Feature Extraction
The image tensor is forwarded through MobileNetV2 without the dense classification head:
$$\mathbf{f} = \text{GAP}(\text{MobileNetV2}(x)) \in \mathbb{R}^{1280}$$
The raw feature vector is normalized to the unit hypersphere ($L_2$ norm):
$$\mathbf{u} = \frac{\mathbf{f}}{\|\mathbf{f}\|_2} = \frac{\mathbf{f}}{\sqrt{\sum_{i=1}^{1280} f_i^2}}$$

### Cosine Similarity & Matching
Given a query vector $\mathbf{u}_q$ and candidate verified reference embeddings $\{\mathbf{u}_{r, 1}, \mathbf{u}_{r, 2}, \dots, \mathbf{u}_{r, K}\}$ in the selected category:
$$S(\mathbf{u}_q, \mathbf{u}_r) = \mathbf{u}_q \cdot \mathbf{u}_r = \sum_{j=1}^{1280} u_{q, j} \cdot u_{r, j}$$
The closest matching genuine product is identified by:
$$S^* = \max_{r \in \text{Category}} S(\mathbf{u}_q, \mathbf{u}_r)$$

### Calibrated Assessment Thresholds
- **High Visual Similarity** ($S^* \ge 0.82$): Packaging aligns closely with manufacturer reference.
- **Moderate Visual Similarity** ($0.65 \le S^* < 0.82$): Partial resemblance detected; packaging revision, lighting variation, or possible counterfeit.
- **Low Visual Similarity** ($0.40 \le S^* < 0.65$): Significant visual packaging discrepancies observed.
- **Insufficient Reference Data** ($S^* < 0.40$ or empty category): No verified standard exists for reliable comparison.

---

## 4. Key Features

- **Real-Time Scanning Portal**: Drag-and-drop file upload, live visual stage feedback, millisecond execution timer, and side-by-side comparison cards.
- **Personal User Dashboard**: Summary cards, 30-day activity trends, assessment donut chart, and complete historical scan logs.
- **Administrator Command Center**:
  - Genuine product catalog CRUD with multi-angle reference image support.
  - Automatic precomputation of reference `.npy` embeddings.
  - User management: account search, suspension toggles, and role promotion with self-modification prevention.
  - Security audit stream logging IP addresses and administrative actions.
- **Security Hardening**:
  - Flask-Limiter rate limiting on logins (20/min), registrations (10/min), and inference scans (30/min).
  - Strict Content-Security-Policy, X-Frame-Options (`SAMEORIGIN`), X-Content-Type-Options (`nosniff`).
  - Corrupted binary validation and file extension disguise prevention.

---

## 5. Local Setup & Execution

### Prerequisites
- Python 3.11 (tested on Windows & Linux)
- Git

### 1. Clone & Environment Setup
```powershell
git clone <repository_url>
cd "ekta mobile"

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Initialization & Seed Data
```powershell
# Create SQLite tables
flask --app run.py init-db

# Create Default Administrator Account
# Username: admin
# Email: admin@productguard.ai
# Password: AdminSecurity2026!
python seed_admin.py

# Seed initial verified reference products and compute embeddings
python seed_products.py
python sync_embeddings.py
```

### 3. Run Development Server
```powershell
python run.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your web browser.

---

## 6. Docker & Production Deployment

ProductGuard is fully containerized and production-ready with PostgreSQL 16 and Gunicorn WSGI.

### Deploying with Docker Compose
```bash
# 1. Copy production environment file
cp .env.production.example .env

# 2. Build and launch services
docker-compose up -d --build

# 3. View logs
docker-compose logs -f web
```
The application will be accessible at `http://localhost:5000`.

---

## 7. Automated Test Suite

ProductGuard includes 62 automated unit, integration, and security tests covering all 11 development phases.

```powershell
# Run the complete test suite
pytest -v
```

### Test Coverage Breakdown:
| Test File | Test Count | Description |
|---|---|---|
| `tests/test_ai_pipeline.py` | 7 | Preprocessing, MobileNetV2 embeddings, cosine math, disk caching |
| `tests/test_auth.py` | 8 | Registration, password hashing, login/logout, RBAC, REST API auth |
| `tests/test_product_management.py` | 8 | Product CRUD, multi-image upload, cascade deletions, admin APIs |
| `tests/test_frontend.py` | 5 | Scan portal UI, history search, result privacy isolation |
| `tests/test_scans.py` | 6 | End-to-end scanning workflow, corrupt file rejection, insufficient data |
| `tests/test_dashboard.py` | 4 | Real database aggregation, KPI counts, category distribution |
| `tests/test_admin_dashboard.py` | 8 | Admin KPIs, user toggle status, self-demotion prevention, audit log |
| `tests/test_security.py` | 6 | Security headers, rate limiting (429), SQL injection, XSS escaping |
| `tests/test_deployment.py` | 4 | Dockerfile, docker-compose, gunicorn.conf.py, ProductionConfig |
| `tests/test_phase2_setup.py` | 6 | Upload dirs, route health, error handlers, AI stack availability |
| **Total** | **62** | **100% Passed** |

---

## 8. REST API Reference

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/scans` | Run real-time AI packaging verification scan | User / Admin |
| `GET` | `/api/scans` | List authenticated user's scan history | User / Admin |
| `GET` | `/api/scans/<id>` | Get detailed verification result report | User (Owner) / Admin |
| `DELETE` | `/api/scans/<id>` | Delete scan record and physical query image | User (Owner) / Admin |
| `GET` | `/api/dashboard/stats` | Get KPI metrics and chart telemetry | User / Admin |
| `GET` | `/admin/api/stats` | Get global platform KPIs & system telemetry | Admin |
| `GET` | `/admin/api/products` | Get list of all verified reference products | Admin |
| `POST` | `/admin/api/users/<id>/toggle-status` | Suspend or activate a user account | Admin |

---

## 9. Academic & Ethical Disclaimer

**Advisory Notice**: ProductGuard is an AI-powered visual packaging comparison platform. A high visual similarity score indicates that the uploaded image resembles the verified packaging standard, but visual inspection alone cannot confirm chemical composition, internal hardware authenticity, or lab purity. Users are advised to combine visual checks with authorized distributor verification.
