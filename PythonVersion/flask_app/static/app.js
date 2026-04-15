const state = {
  uploadedSvgName: null,
  capturePollHandle: null,
  statusPollHandle: null,
  lastBulkCopies: 1,
};

function appendLog(message, isError = false) {
  const logBox = document.getElementById("logBox");
  if (!logBox) return;
  const line = document.createElement("div");
  line.className = `log-line${isError ? " error" : ""}`;
  line.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  logBox.prepend(line);
}

function clampPercent(value) {
  const asNumber = Number(value);
  if (!Number.isFinite(asNumber)) return 0;
  return Math.max(0, Math.min(100, asNumber));
}

function buildPrintSettingsPayload() {
  const settings = loadPrintSettings();
  return {
    width: settings.width,
    height: settings.height,
    xPosition: settings.xPosition,
    yPosition: settings.yPosition,
    scale: Number(settings.scale || 1),
    rotation: Number(settings.rotation || 0),
    invertX: Boolean(settings.invertX),
    invertY: Boolean(settings.invertY),
  };
}

function parseQuadPoints(points) {
  if (!Array.isArray(points) || points.length !== 4) {
    throw new Error("Capture config requires exactly 4 points.");
  }

  return points.map((point) => {
    if (!Array.isArray(point) || point.length !== 2) {
      throw new Error("Invalid 4-point data in config.");
    }
    const x = Number(point[0]);
    const y = Number(point[1]);
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      throw new Error("Invalid 4-point values in config.");
    }
    return [x, y];
  });
}

function buildCapturePayload() {
  const capture = loadCaptureSettings();
  return {
    autofocus_enabled: Boolean(capture.autofocusEnabled),
    manual_focus_value: Number(capture.manualFocusValue || 35),
    quad_points: parseQuadPoints(capture.quadPoints),
  };
}

function setBadgeState(elementId, text, className) {
  const node = document.getElementById(elementId);
  if (!node) return;
  node.textContent = text;
  node.className = `badge ${className}`;
}

function formatDistanceMetersFromMm(mmValue) {
  const meters = Number(mmValue) / 1000;
  if (!Number.isFinite(meters)) return "0.000 m";
  return `${meters.toFixed(3)} m`;
}

function renderStatusGui(status) {
  const isConnected = Boolean(status.is_open);
  const isBusy = Boolean(status.is_printing);
  const executionPercent = clampPercent(status.current_execution_percent);
  const remainingPenPercent = clampPercent(status.remaining_pen_percent);
  const hasPenConfig = Number(status.max_pen_distance_m || 0) > 0;

  setBadgeState(
    "statusConnectionBadge",
    isConnected ? "Connected" : "Disconnected",
    isConnected ? "badge-ok" : "badge-neutral"
  );
  setBadgeState(
    "statusBusyBadge",
    isBusy ? "Busy" : "Idle",
    isBusy ? "badge-warn" : "badge-ok"
  );

  const portNode = document.getElementById("statusPort");
  if (portNode) {
    portNode.textContent = status.port_name || "N/A";
  }

  const cumulativeNode = document.getElementById("statusCumulativeDistance");
  if (cumulativeNode) {
    cumulativeNode.textContent = formatDistanceMetersFromMm(status.cumulative_distance_mm);
  }

  const executedNode = document.getElementById("statusExecutedDistance");
  if (executedNode) {
    executedNode.textContent = formatDistanceMetersFromMm(status.current_executed_distance_mm);
  }

  const executionPercentNode = document.getElementById("statusExecutionPercent");
  if (executionPercentNode) {
    executionPercentNode.textContent = `${executionPercent.toFixed(2)}%`;
  }

  const executionFillNode = document.getElementById("statusExecutionFill");
  if (executionFillNode) {
    executionFillNode.style.width = `${executionPercent}%`;
  }

  const penPercentNode = document.getElementById("statusPenRemaining");
  if (penPercentNode) {
    penPercentNode.textContent = hasPenConfig ? `${remainingPenPercent.toFixed(2)}%` : "N/A";
  }

  const penFillNode = document.getElementById("statusPenFill");
  if (penFillNode) {
    penFillNode.style.width = `${hasPenConfig ? remainingPenPercent : 0}%`;
  }
}

async function refreshStatus(options = {}) {
  const silent = Boolean(options.silent);
  try {
    const status = await apiGet("/api/status");
    renderStatusGui(status);
    if (!silent) {
      appendLog("Status refreshed.");
    }
  } catch (error) {
    if (!silent) {
      appendLog(`Status error: ${error.message}`, true);
    }
  }
}

function startAutoStatusRefresh(intervalMs = 3000) {
  if (state.statusPollHandle) {
    clearInterval(state.statusPollHandle);
    state.statusPollHandle = null;
  }
  state.statusPollHandle = setInterval(() => {
    void refreshStatus({ silent: true });
  }, intervalMs);
}

async function uploadSvgFromFile(file) {
  const formData = new FormData();
  formData.append("svg", file);
  try {
    const data = await apiPostForm("/api/upload", formData);
    state.uploadedSvgName = data.fileName;
    document.getElementById("uploadedSvgLabel").textContent = `Uploaded SVG: ${data.fileName}`;
    appendLog(`SVG uploaded (${data.fileName}).`);
  } catch (error) {
    appendLog(`Upload error: ${error.message}`, true);
  }
}

async function printUploadedSvg() {
  const payload = { printRequest: buildPrintSettingsPayload() };
  try {
    const data = await apiPostJson("/api/print", payload);
    appendLog(`Print completed. Commands sent: ${data.result.commands_sent}.`);
    await refreshStatus();
  } catch (error) {
    appendLog(`Print error: ${error.message}`, true);
  }
}

async function bulkPrintUploadedSvg() {
  const rawInput = window.prompt("Enter number of copies (1-100):", String(state.lastBulkCopies || 1));
  if (rawInput === null) {
    return;
  }

  const copies = Number.parseInt(String(rawInput).trim(), 10);
  if (!Number.isInteger(copies) || copies < 1 || copies > 100) {
    appendLog("Bulk print error: copies must be an integer between 1 and 100.", true);
    return;
  }

  state.lastBulkCopies = copies;
  const payload = { copies, printRequest: buildPrintSettingsPayload() };
  try {
    const data = await apiPostJson("/api/print/bulk", payload);
    appendLog(`Bulk print completed (${copies} copies). Commands per copy: ${data.commandCount}.`);
    await refreshStatus();
  } catch (error) {
    appendLog(`Bulk print error: ${error.message}`, true);
  }
}

async function runVoid() {
  try {
    await apiPostJson("/api/void");
    appendLog("Void completed.");
    await refreshStatus();
  } catch (error) {
    appendLog(`Void error: ${error.message}`, true);
  }
}

async function loadLatestCapture() {
  const response = await fetch("/api/capture/latest");
  if (response.status === 404) {
    return false;
  }
  const payload = await response.json();
  if (!response.ok || payload.success === false) {
    throw new Error(payload?.message || `Capture load failed (${response.status})`);
  }

  const data = payload.data;
  const imageEl = document.getElementById("capturePreview");
  imageEl.src = `${data.imageUrl}?t=${Date.now()}`;
  imageEl.style.display = "block";
  return true;
}

function startCapturePolling(maxAttempts = 20, intervalMs = 2000) {
  if (state.capturePollHandle) {
    clearInterval(state.capturePollHandle);
    state.capturePollHandle = null;
  }

  let attempts = 0;
  state.capturePollHandle = setInterval(async () => {
    attempts += 1;
    try {
      const loaded = await loadLatestCapture();
      if (loaded) {
        appendLog("Captured photo received.");
        clearInterval(state.capturePollHandle);
        state.capturePollHandle = null;
      } else if (attempts >= maxAttempts) {
        appendLog("Capture polling timed out (no image yet).", true);
        clearInterval(state.capturePollHandle);
        state.capturePollHandle = null;
      }
    } catch (error) {
      appendLog(`Capture polling error: ${error.message}`, true);
      clearInterval(state.capturePollHandle);
      state.capturePollHandle = null;
    }
  }, intervalMs);
}

function isCaptureFullscreenActive() {
  const imageEl = document.getElementById("capturePreview");
  return document.fullscreenElement === imageEl;
}

function updateCaptureFullscreenButtonLabel() {
  const button = document.getElementById("captureFullscreenBtn");
  if (!button) return;
  button.textContent = isCaptureFullscreenActive() ? "Exit Fullscreen" : "Fullscreen";
}

async function toggleCaptureFullscreen() {
  const imageEl = document.getElementById("capturePreview");
  if (!imageEl) return;

  try {
    if (isCaptureFullscreenActive()) {
      await document.exitFullscreen();
      return;
    }
    await imageEl.requestFullscreen();
  } catch (error) {
    appendLog(`Fullscreen error: ${error.message}`, true);
  } finally {
    updateCaptureFullscreenButtonLabel();
  }
}

async function requestCapture() {
  try {
    const startData = await apiPostJson("/api/scanner/capture/start", {
      readability_required: true,
      timeout_seconds: 15,
    });
    const captureId = String(startData.captureId || startData.capture?.capture_id || startData.capture?.job_id || "").trim();
    if (!captureId) {
      throw new Error("Capture id was not returned.");
    }

    const maxAttempts = 50;
    let latestStatus = "";
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const statusData = await apiGet(`/api/scanner/capture/${encodeURIComponent(captureId)}/status`);
      latestStatus = String(statusData.capture?.status || "").toLowerCase();
      if (latestStatus === "succeeded") {
        break;
      }
      if (latestStatus === "failed") {
        const capture = statusData.capture || {};
        throw new Error(`Capture failed: ${capture.error || "unknown_error"} - ${capture.detail || "no detail"}`);
      }
      await new Promise((resolve) => {
        setTimeout(resolve, 400);
      });
    }
    if (latestStatus !== "succeeded") {
      throw new Error("Capture status polling timed out.");
    }

    const imageUrl = `/api/scanner/capture/${encodeURIComponent(captureId)}/result`;
    const imageEl = document.getElementById("capturePreview");
    imageEl.src = `${imageUrl}?t=${Date.now()}`;
    imageEl.style.display = "block";
    appendLog("Capture completed and rectified image loaded.");
  } catch (error) {
    appendLog(`Capture request error: ${error.message}`, true);
  }
}

function registerEvents() {
  document.getElementById("captureBtn").addEventListener("click", requestCapture);
  document.getElementById("printBtn").addEventListener("click", printUploadedSvg);
  document.getElementById("bulkPrintBtn").addEventListener("click", bulkPrintUploadedSvg);
  document.getElementById("captureFullscreenBtn").addEventListener("click", () => {
    void toggleCaptureFullscreen();
  });
  document.getElementById("uploadBtn").addEventListener("click", () => {
    document.getElementById("svgFileInput").click();
  });
  document.getElementById("voidBtn").addEventListener("click", runVoid);
  document.addEventListener("fullscreenchange", updateCaptureFullscreenButtonLabel);

  document.getElementById("svgFileInput").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await uploadSvgFromFile(file);
    event.target.value = "";
  });
}

async function initPage() {
  registerEvents();
  updateCaptureFullscreenButtonLabel();
  await refreshStatus();
  startAutoStatusRefresh();
  try {
    await loadLatestCapture();
  } catch (error) {
    appendLog(`Initial capture check: ${error.message}`, true);
  }
}

initPage();
