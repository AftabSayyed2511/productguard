/**
 * ProductGuard - Real-Time Scanner Client
 * Handles drag-and-drop, client-side validation, live image preview, and async scan workflow.
 */

document.addEventListener("DOMContentLoaded", function () {
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("fileInput");
    const dropzonePrompt = document.getElementById("dropzonePrompt");
    const previewContainer = document.getElementById("previewContainer");
    const imagePreview = document.getElementById("imagePreview");
    const fileNameSpan = document.getElementById("fileName");
    const fileSizeSpan = document.getElementById("fileSize");
    const removeImageBtn = document.getElementById("removeImageBtn");
    const fileError = document.getElementById("fileError");
    const categorySelect = document.getElementById("categorySelect");
    const submitScanBtn = document.getElementById("submitScanBtn");
    const scanForm = document.getElementById("scanForm");
    const scanStatus = document.getElementById("scanStatus");
    const statusTitle = document.getElementById("statusTitle");
    const statusDetail = document.getElementById("statusDetail");

    const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB
    const ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/jpg"];

    if (!dropzone || !fileInput) return;

    // Trigger file dialog on dropzone click
    dropzone.addEventListener("click", function (e) {
        if (e.target !== removeImageBtn && !removeImageBtn.contains(e.target)) {
            fileInput.click();
        }
    });

    // Drag-and-drop hover effects
    ["dragenter", "dragover"].forEach((eventName) => {
        dropzone.addEventListener(eventName, function (e) {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add("dragover");
        });
    });

    ["dragleave", "drop"].forEach((eventName) => {
        dropzone.addEventListener(eventName, function (e) {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove("dragover");
        });
    });

    // Handle dropped files
    dropzone.addEventListener("drop", function (e) {
        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            handleSelectedFile(files[0]);
        }
    });

    // Handle standard file selection
    fileInput.addEventListener("change", function () {
        if (fileInput.files && fileInput.files.length > 0) {
            handleSelectedFile(fileInput.files[0]);
        }
    });

    // Category change handler
    categorySelect.addEventListener("change", checkSubmitReadiness);

    function handleSelectedFile(file) {
        clearError();

        // Validate MIME type
        const isValidType =
            ALLOWED_MIME_TYPES.includes(file.type) ||
            file.name.match(/\.(jpg|jpeg|png)$/i);

        if (!isValidType) {
            showError("Invalid file type. Only JPEG, JPG, and PNG images are supported.");
            resetFileSelection();
            return;
        }

        // Validate file size
        if (file.size > MAX_FILE_SIZE) {
            showError("File size exceeds 5 MB. Please select a compressed packaging image.");
            resetFileSelection();
            return;
        }

        // Read and preview file
        const reader = new FileReader();
        reader.onload = function (e) {
            imagePreview.src = e.target.result;
            fileNameSpan.textContent = file.name;
            fileSizeSpan.textContent = formatBytes(file.size);

            dropzonePrompt.classList.add("d-none");
            previewContainer.classList.remove("d-none");
            checkSubmitReadiness();
        };
        reader.readAsDataURL(file);
    }

    // Remove file handler
    removeImageBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        resetFileSelection();
    });

    function resetFileSelection() {
        fileInput.value = "";
        imagePreview.src = "";
        fileNameSpan.textContent = "";
        fileSizeSpan.textContent = "";
        previewContainer.classList.add("d-none");
        dropzonePrompt.classList.remove("d-none");
        checkSubmitReadiness();
    }

    function checkSubmitReadiness() {
        const hasFile = fileInput.files && fileInput.files.length > 0;
        const hasCategory = categorySelect.value !== "";
        submitScanBtn.disabled = !(hasFile && hasCategory);
    }

    function showError(msg) {
        fileError.textContent = msg;
        fileError.classList.remove("d-none");
    }

    function clearError() {
        fileError.textContent = "";
        fileError.classList.add("d-none");
    }

    function formatBytes(bytes) {
        if (bytes === 0) return "0 Bytes";
        const k = 1024;
        const sizes = ["Bytes", "KB", "MB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    }

    // Async Scan Submission
    scanForm.addEventListener("submit", async function (e) {
        e.preventDefault();

        if (submitScanBtn.disabled) return;

        const formData = new FormData(scanForm);

        // Update UI state to processing
        submitScanBtn.disabled = true;
        scanStatus.classList.remove("d-none");
        statusTitle.textContent = "Processing Packaging Image...";
        statusDetail.textContent = "Uploading image and validating MIME content...";

        try {
            // Stage 1 feedback
            setTimeout(() => {
                if (!submitScanBtn.disabled) return;
                statusTitle.textContent = "Running MobileNetV2 Inference...";
                statusDetail.textContent = "Extracting 1280-dimensional feature embedding...";
            }, 700);

            // Stage 2 feedback
            setTimeout(() => {
                if (!submitScanBtn.disabled) return;
                statusTitle.textContent = "Calculating Vector Similarity...";
                statusDetail.textContent = "Comparing against verified reference database...";
            }, 1400);

            const response = await fetch("/api/scans", {
                method: "POST",
                body: formData,
            });

            const data = await response.json();

            if (response.ok && data.status === "success") {
                statusTitle.textContent = "Assessment Complete!";
                statusDetail.textContent = "Redirecting to detailed comparison report...";
                window.location.href = `/scan/${data.scan_id}`;
            } else {
                showError(data.message || data.error || "Failed to process scan.");
                scanStatus.classList.add("d-none");
                submitScanBtn.disabled = false;
            }
        } catch (err) {
            showError("Network or server communication error. Please try again.");
            scanStatus.classList.add("d-none");
            submitScanBtn.disabled = false;
        }
    });
});
