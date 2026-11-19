/**
 * ProductGuard – User Dashboard Charts & Live Stats
 * Fetches real data from /api/dashboard/stats and renders Chart.js visuals.
 * Phase 8 — dashboard.js
 */

"use strict";

// ── Colour palette (matches custom.css) ──────────────────────────────────────
const COLORS = {
  high:        "#22c55e",   // green-500
  moderate:    "#f59e0b",   // amber-500
  low:         "#ef4444",   // red-500
  insufficient:"#64748b",   // slate-500
  electric:    "#00D2FF",
  navy:        "#0B1528",
  muted:       "#94a3b8",
};

// Status label map
const STATUS_LABELS = {
  HIGH_SIMILARITY:       "High Similarity",
  MODERATE_SIMILARITY:   "Moderate Similarity",
  LOW_SIMILARITY:        "Low Similarity",
  INSUFFICIENT_DATA:     "Insufficient Data",
};

// ── Chart instances (kept for potential future destroy/recreate) ─────────────
let donutChart   = null;
let activityChart = null;
let categoryChart = null;

// ── Utilities ────────────────────────────────────────────────────────────────
function el(id) { return document.getElementById(id); }

function animateCount(element, target, duration = 800) {
  if (!element) return;
  const start = parseInt(element.textContent, 10) || 0;
  const range = target - start;
  const startTime = performance.now();
  function step(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);  // ease-out cubic
    element.textContent = Math.round(start + range * eased).toLocaleString();
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ── KPI card updater ─────────────────────────────────────────────────────────
function updateKPIs(data) {
  animateCount(el("kpi-total"),        data.total_scans);
  animateCount(el("kpi-high"),         data.high_similarity);
  animateCount(el("kpi-moderate"),     data.moderate_similarity);
  animateCount(el("kpi-low"),          data.low_similarity);
  animateCount(el("kpi-insufficient"), data.insufficient_data);
}

// ── Assessment Status Donut Chart ────────────────────────────────────────────
function renderDonutChart(data) {
  const ctx = el("donutChart");
  if (!ctx) return;

  const values = [
    data.high_similarity,
    data.moderate_similarity,
    data.low_similarity,
    data.insufficient_data,
  ];
  const total = values.reduce((a, b) => a + b, 0);

  if (donutChart) donutChart.destroy();

  donutChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: [
        STATUS_LABELS.HIGH_SIMILARITY,
        STATUS_LABELS.MODERATE_SIMILARITY,
        STATUS_LABELS.LOW_SIMILARITY,
        STATUS_LABELS.INSUFFICIENT_DATA,
      ],
      datasets: [{
        data: values,
        backgroundColor: [
          COLORS.high, COLORS.moderate, COLORS.low, COLORS.insufficient
        ],
        borderColor: COLORS.navy,
        borderWidth: 3,
        hoverOffset: 8,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "68%",
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: COLORS.muted, padding: 16, font: { size: 12 } },
        },
        tooltip: {
          callbacks: {
            label(ctx) {
              const val = ctx.raw;
              const pct = total > 0 ? ((val / total) * 100).toFixed(1) : "0.0";
              return ` ${ctx.label}: ${val} (${pct}%)`;
            },
          },
        },
      },
    },
  });

  // Centre label: total scans
  if (total === 0) {
    const noDataLabel = el("donut-centre-label");
    if (noDataLabel) noDataLabel.textContent = "No scans yet";
  }
}

// ── 30-Day Daily Activity Line Chart ─────────────────────────────────────────
function renderActivityChart(daily_activity_30d) {
  const ctx = el("activityChart");
  if (!ctx) return;

  // Build a full 30-day label array
  const labels = [];
  const values = [];
  for (let i = 29; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const key = d.toISOString().split("T")[0];   // "YYYY-MM-DD"
    const shortLabel = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    labels.push(shortLabel);
    values.push(daily_activity_30d[key] || 0);
  }

  if (activityChart) activityChart.destroy();

  activityChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Scans",
        data: values,
        fill: true,
        tension: 0.4,
        borderColor: COLORS.electric,
        backgroundColor: "rgba(0,210,255,0.08)",
        pointBackgroundColor: COLORS.electric,
        pointRadius: 3,
        pointHoverRadius: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          ticks: {
            color: COLORS.muted,
            maxTicksLimit: 10,
            font: { size: 11 },
          },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
        y: {
          beginAtZero: true,
          ticks: {
            color: COLORS.muted,
            stepSize: 1,
            font: { size: 11 },
          },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title(ctx) { return ctx[0].label; },
            label(ctx) { return ` ${ctx.raw} scan${ctx.raw !== 1 ? "s" : ""}`; },
          },
        },
      },
    },
  });
}

// ── Category Distribution Bar Chart ──────────────────────────────────────────
function renderCategoryChart(category_distribution) {
  const ctx = el("categoryChart");
  if (!ctx) return;

  const labels = Object.keys(category_distribution);
  const values = Object.values(category_distribution);

  if (labels.length === 0) {
    const wrap = ctx.closest(".chart-container");
    if (wrap) {
      wrap.innerHTML = `<p class="text-muted text-center py-4 small">
        No category data yet. Run a scan to populate this chart.
      </p>`;
    }
    return;
  }

  if (categoryChart) categoryChart.destroy();

  categoryChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Scans",
        data: values,
        backgroundColor: "rgba(0,210,255,0.6)",
        borderColor: COLORS.electric,
        borderWidth: 1,
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          ticks: { color: COLORS.muted, font: { size: 11 } },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
        y: {
          beginAtZero: true,
          ticks: { color: COLORS.muted, stepSize: 1, font: { size: 11 } },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
      },
      plugins: { legend: { display: false } },
    },
  });
}

// ── Main bootstrap ────────────────────────────────────────────────────────────
async function initDashboard() {
  const loadingEl    = el("dashboard-loading");
  const contentEl    = el("dashboard-content");
  const errorBannerEl = el("dashboard-error");

  try {
    const response = await fetch("/api/dashboard/stats", {
      headers: { "Accept": "application/json" },
      credentials: "same-origin",
    });

    if (!response.ok) {
      throw new Error(`Server returned HTTP ${response.status}`);
    }

    const json = await response.json();
    if (json.status !== "success") throw new Error(json.message || "API error");

    const data = json.data;

    // Update KPI counters
    updateKPIs(data);

    // Render all charts
    renderDonutChart(data);
    renderActivityChart(data.daily_activity_30d || {});
    renderCategoryChart(data.category_distribution || {});

    // Show content
    if (loadingEl) loadingEl.classList.add("d-none");
    if (contentEl) contentEl.classList.remove("d-none");

  } catch (err) {
    console.error("[Dashboard] Stats fetch failed:", err);
    if (loadingEl) loadingEl.classList.add("d-none");
    if (errorBannerEl) {
      errorBannerEl.textContent = `Failed to load dashboard data: ${err.message}`;
      errorBannerEl.classList.remove("d-none");
    }
  }
}

// ── Entry point ───────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", initDashboard);
