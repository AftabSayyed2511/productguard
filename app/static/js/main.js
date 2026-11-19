/**
 * ProductGuard - Global Frontend Script
 * Includes Auto-dismiss alerts, Bootstrap tooltips, and 3D Interactive Tilt Engine
 */

document.addEventListener("DOMContentLoaded", function () {
    // Auto-dismiss standard alerts after 6 seconds
    const alerts = document.querySelectorAll(".alert-dismissible:not(.alert-important)");
    alerts.forEach((alert) => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 6000);
    });

    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(
        document.querySelectorAll('[data-bs-toggle="tooltip"]')
    );
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // -----------------------------------------------------------------------
    // Interactive 3D Card Tilt Engine
    // -----------------------------------------------------------------------
    const tiltCards = document.querySelectorAll(".card-custom, .card-3d");

    tiltCards.forEach((card) => {
        card.addEventListener("mousemove", (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left; // x position within card
            const y = e.clientY - rect.top;  // y position within card

            const centerX = rect.width / 2;
            const centerY = rect.height / 2;

            const rotateX = ((y - centerY) / centerY) * -8; // Max 8 deg
            const rotateY = ((x - centerX) / centerX) * 8;  // Max 8 deg

            card.style.transform = `perspective(1000px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateY(-4px)`;
        });

        card.addEventListener("mouseleave", () => {
            card.style.transform = "perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0px)";
            card.style.transition = "transform 0.5s cubic-bezier(0.16, 1, 0.3, 1)";
        });

        card.addEventListener("mouseenter", () => {
            card.style.transition = "none";
        });
    });
});
