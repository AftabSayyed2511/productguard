# ProductGuard – Project Demonstration & Defense Guide

This guide provides a structured, step-by-step walkthrough to demonstrate the **ProductGuard** application to project evaluators, faculty members, and technical review panels.

---

## 1. Pre-Demo Preparation

### Ensure Server is Running:
Open PowerShell in the project directory:
```powershell
Set-Location "c:\Users\Asus\Desktop\ekta mobile"
.\venv\Scripts\python.exe run.py
```
Open web browser: **`http://127.0.0.1:5000`**

### Pre-Configured Demo Accounts:
| Role | Email | Password |
|---|---|---|
| **Administrator** | `admin@productguard.ai` | `AdminSecurity2026!` |
| **Standard User** | `demo@productguard.ai` (or register a fresh account) | `UserPass123!` |

---

## 2. Structured 5-Stage Demonstration Script

### Stage 1: Landing Page & Architectural Overview (2 Minutes)
- **What to show**: Open `http://127.0.0.1:5000`.
- **Key points to explain to evaluators**:
  - Point out the branding: **"Detect. Verify. Protect."** with dark navy and electric blue theme.
  - Explain the 3-step pipeline: *Upload Packaging Image* $\to$ *MobileNetV2 Deep Feature Extraction* $\to$ *Cosine Similarity Matching*.
  - Show the **About & Methodology** page (`/about`) explaining why visual similarity is used and how packaging discrepancies help spot counterfeits.

---

### Stage 2: User Registration & Authentication (2 Minutes)
- **What to show**:
  1. Click **Register** (`/auth/register`).
  2. Demonstrate server-side validation: try submitting empty passwords or mismatched passwords.
  3. Register an account with your own name.
  4. Explain password security: Passwords are never stored in plain text; they use Werkzeug PBKDF2/SHA-256 salted hashes.
  5. Demonstrate **Rate Limiting**: Show that rapid registration submissions trigger HTTP 429 protection.

---

### Stage 3: Live Real-Time Product Scanning (4 Minutes - Core Demo)
- **What to show**:
  1. Click **Scan Product** in the navbar (`/scan`).
  2. Select category: **Electronics**.
  3. **Scenario A (Genuine Match)**:
     - Drag-and-drop or select an authentic electronics packaging image (e.g. from `legacy_store/apple-iphone-13-128gb-midnight.jpg` or `seed_products.py`).
     - Click **Run Verification Scan**.
     - Point out the live processing states (*Validating image* $\to$ *Extracting MobileNetV2 embeddings* $\to$ *Computing cosine similarity*).
     - Show the resulting report page:
       - **Assessment Status**: `HIGH VISUAL SIMILARITY` (green pill badge).
       - **Similarity Score**: e.g., `92.4%`.
       - **Processing Latency**: Real-time measurement (typically 100–250ms).
       - **Side-by-side display**: Uploaded packaging vs. Verified Reference packaging standard.
  4. **Scenario B (Low Similarity / Discrepancy)**:
     - Upload an image that does not match (e.g. an arbitrary packaging or different product in the same category).
     - Point out that the system accurately calculates a low similarity score and issues a warning (`LOW VISUAL SIMILARITY`).
  5. **Scenario C (Insufficient Data)**:
     - Choose a category with no reference products yet (e.g., *Clothing* or *Personal Care* before admin adds one).
     - Show that the system honestly reports: *"Insufficient reference data – Unable to assess this product"* rather than fabricating a fake match.

---

### Stage 4: User Dashboard & History Analytics (3 Minutes)
- **What to show**:
  1. Click **Dashboard** (`/dashboard`).
  2. Point out that all data is queried live from the SQLite/PostgreSQL database:
     - Total Scans counter.
     - Status partitioning: High, Moderate, Low, and Insufficient Data counts.
     - Interactive **Chart.js** Donut Chart showing outcome ratios.
     - 30-Day Activity timeline line chart with electric blue glow.
     - Category breakdown bar chart.
  3. Scroll down to **Recent Scan Activity** and click **View** to inspect a past scan report.
  4. Navigate to **History** (`/scan/history`):
     - Filter by category (*Electronics*).
     - Filter by status (*High Similarity*).
     - Search by product name (*iPhone*).
     - Demonstrate personal scan record deletion.

---

### Stage 5: Administrator Portal & System Telemetry (4 Minutes)
- **What to show**:
  1. Log out and log in with administrator credentials (`admin@productguard.ai` / `AdminSecurity2026!`).
  2. Click **Admin Portal** in the navigation bar (`/admin/dashboard`).
  3. **System Command Center**:
     - Live KPI cards: Total registered users, verified products, reference images, total scans, and average inference latency.
     - Active AI model specification card (MobileNetV2, 1,280 Float32 features, Cosine Distance).
     - **Reference Coverage Alerts**: Highlights products in the database that still need packaging images uploaded.
  4. **Product & Reference Image Repository** (`/admin/products`):
     - Show the product catalog.
     - Click **Add Verified Product** (`/admin/products/new`) and add a genuine reference product with multiple packaging angles.
     - Explain that embeddings are automatically computed and saved as `.npy` vectors for fast $O(1)$ disk retrieval.
  5. **User Management & RBAC** (`/admin/users`):
     - Search for a user.
     - Demonstrate **Account Suspension** (click suspend, then verify that the user is immediately prevented from logging in).
     - Demonstrate **Self-Protection**: Try suspending the active admin account — show that the system actively blocks self-deactivation.
  6. **Telemetry & Security Audit Trail** (`/admin/analytics`):
     - Show the global scan throughput chart and category inventory vs. demand charts.
     - Show the **Administrative Audit Trail** recording admin IDs, actions (`CREATE_PRODUCT`, `DEACTIVATE_USER`), timestamps, and IP addresses.

---

## 3. Anticipated Questions from Evaluators & Answers

### Q1: "Why did you use MobileNetV2 instead of a custom CNN trained from scratch?"
> **Answer**: Training a CNN from scratch requires hundreds of thousands of labeled packaging images per product, which is impractical for real-world retail catalogs. MobileNetV2 pretrained on ImageNet leverages rich low- and high-level visual representations (edges, textures, spatial branding layouts) learned across 1.4 million images. Using transfer learning with 1,280-dimensional embeddings allows ProductGuard to perform zero-shot visual verification on new products without retraining the entire network every time a new product is added.

### Q2: "How fast is the verification scan in real time?"
> **Answer**: The entire pipeline executes in approximately 100 to 250 milliseconds per image. We achieved this by:
> 1. Loading the MobileNetV2 model once into memory as a thread-safe singleton.
> 2. Precomputing and caching verified reference embeddings as `.npy` arrays on disk.
> 3. Computing cosine distance via vector dot-products using Scikit-Learn/NumPy.

### Q3: "What prevents a user from uploading a shell script or malicious executable?"
> **Answer**: ProductGuard uses defense-in-depth security:
> 1. Flask restricts upload payloads to 5 MB (`MAX_CONTENT_LENGTH`).
> 2. We validate file extensions against a strict whitelist (`.jpg`, `.jpeg`, `.png`).
> 3. Filenames are regenerated using random UUIDv4 identifiers to prevent directory traversal (`../`).
> 4. We open every upload with Pillow and verify the image headers — any text file, shell script, or corrupted binary disguised with a `.jpg` extension is rejected immediately.

### Q4: "How does the system ensure user data privacy?"
> **Answer**: All scans, historical records, and uploaded images are bound by foreign keys (`user_id`). Route-level security checks verify that standard users can only view, search, or delete their own scans (`scan.user_id == current_user.id`), returning HTTP 403 Forbidden on unauthorized access attempts.

### Q5: "Is the system tested and production-ready?"
> **Answer**: Yes. ProductGuard includes 62 automated test cases (`pytest -v`) covering all 11 phases with 100% pass rate. It is containerized via Docker and Docker Compose with PostgreSQL 16 and Gunicorn WSGI.

---

## 4. Verification & Defense Checklist
- [x] All 62 automated tests passing (`pytest -v`)
- [x] Flask development server runs with zero errors (`python run.py`)
- [x] MobileNetV2 model weights loaded from local `.keras/models/` cache
- [x] Admin account created (`admin@productguard.ai`)
- [x] Initial reference products seeded with precomputed embeddings
- [x] Real-time scan workflow tested with side-by-side visual reports
- [x] User dashboard rendering live Chart.js analytics
- [x] Admin dashboard displaying system telemetry and audit logs
- [x] Rate limiting and security headers active
- [x] Dockerfile and docker-compose.yml configured for deployment
