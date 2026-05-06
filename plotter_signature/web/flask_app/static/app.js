const state = {
  uploadedSvgName: null,
  lastSvgFile: null,
  capturePollHandle: null,
  statusPollHandle: null,
  lastBulkCopies: 1,
  bulkRunning: false,
  bulkStopRequested: false,
  bulkRequestedTotal: 0,
  bulkPrintedCount: 0,
};

function appendLog(message, isError = false) {
  const logBox = document.getElementById("logBox");
  if (!logBox) return;
  const line = document.createElement("div");
  line.className = `log-line${isError ? " error" : ""}`;
  line.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  logBox.prepend(line);
}

function formatTimestamp(dateValue = new Date()) {
  return dateValue.toLocaleString();
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

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function updateBulkProgressLabel() {
  const node = document.getElementById("bulkProgressLabel");
  if (!node) return;
  node.textContent = `Bulk progress: ${state.bulkPrintedCount} / ${state.bulkRequestedTotal}`;
}

function updateBulkUiState() {
  const stopButton = document.getElementById("stopBulkBtn");
  const bulkButton = document.getElementById("bulkPrintBtn");
  const printButton = document.getElementById("printBtn");
  if (stopButton) {
    stopButton.disabled = !state.bulkRunning;
  }
  if (bulkButton) {
    bulkButton.disabled = state.bulkRunning;
  }
  if (printButton) {
    printButton.disabled = state.bulkRunning;
  }
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
  const isBusy = Boolean(status.is_busy ?? status.is_printing);
  const executionPercent = clampPercent(status.current_execution_percent);
  const remainingPenPercent = clampPercent(status.remaining_pen_percent);
  const hasPenConfig = Number(status.max_pen_distance_m || 0) > 0;

  setBadgeState(
    "statusConnectionBadge",
    "—",
    "badge-neutral"
  );
  setBadgeState(
    "statusBusyBadge",
    isBusy ? "Busy" : "Idle",
    isBusy ? "badge-warn" : "badge-ok"
  );

  const portNode = document.getElementById("statusPort");
  if (portNode) {
    const saved = String(loadConnectionSettings().comPort || "").trim();
    portNode.textContent = saved || "--";
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
    const status = await apiGet("/api/cmd/status");
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

function clearSelectedSvgUi() {
  state.lastSvgFile = null;
  state.uploadedSvgName = null;
  const label = document.getElementById("uploadedSvgLabel");
  if (label) {
    label.textContent = "No SVG selected — choose a file before each print or bulk.";
  }
}

async function selectSvgFromFile(file) {
  if (!file) return;
  try {
    state.uploadedSvgName = file.name || "svg";
    state.lastSvgFile = file;
    const label = document.getElementById("uploadedSvgLabel");
    if (label) {
      label.textContent = `SVG ready: ${state.uploadedSvgName} (picked locally; sent with each print)`;
    }
    appendLog(`SVG selected (${state.uploadedSvgName}).`);
  } catch (error) {
    appendLog(`File error: ${error.message}`, true);
  }
}

function logPrintResponse(data, label) {
  if (data.queued) {
    appendLog(
      `${label} queued | job ${data.jobId} | position ${data.queuePosition} | ${data.svgFileName || state.uploadedSvgName || ""}`
    );
    return;
  }
  const svgName = data.svgFileName || state.uploadedSvgName || "unknown.svg";
  if (data.jobType === "bulk" && data.result) {
    appendLog(
      `${label} | SVG: ${svgName} | copies printed: ${data.result.copies ?? "?"} | commands: ${data.result.total_commands_sent ?? data.commandCount}.`
    );
  } else if (data.result) {
    appendLog(`${label} | SVG: ${svgName} | commands: ${data.result.commands_sent}.`);
  } else {
    appendLog(`${label} completed.`);
  }
}

async function printUploadedSvg() {
  if (!state.lastSvgFile) {
    appendLog("Choose an SVG file first (Choose SVG). Each print sends the file with the request.", true);
    return;
  }
  const formData = new FormData();
  formData.append("svg", state.lastSvgFile);
  formData.append("printRequestJson", JSON.stringify({ printRequest: buildPrintSettingsPayload() }));
  try {
    const startedAt = new Date();
    appendLog(`Print started at ${formatTimestamp(startedAt)}.`);
   
    const data = await apiPostForm("/api/cmd/print", formData);
    const completedAt = new Date();
    logPrintResponse(data, "Print");
    if (!data.queued) {
      appendLog(`Print finished at ${formatTimestamp(completedAt)}.`);
    }
    clearSelectedSvgUi();
    await refreshStatus();
  } catch (error) {
    appendLog(`Print error: ${error.message}`, true);
  }
}

async function bulkPrintUploadedSvg() {
  if (state.bulkRunning) {
    appendLog("Bulk print is already running.", true);
    return;
  }

  if (!state.lastSvgFile) {
    appendLog("Select an SVG file first. One file is used for the entire bulk run.", true);
    return;
  }

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
  state.bulkRunning = true;
  state.bulkStopRequested = false;
  state.bulkRequestedTotal = copies;
  state.bulkPrintedCount = 0;
  updateBulkProgressLabel();
  updateBulkUiState();

  const formData = new FormData();
  formData.append("svg", state.lastSvgFile);
  formData.append("copies", String(copies));
  formData.append("printRequestJson", JSON.stringify({ printRequest: buildPrintSettingsPayload() }));

  try {
    appendLog(`Bulk print started (${copies} copies, one server job).`);
    const data = await apiPostForm("/api/cmd/print/bulk", formData);
    logPrintResponse(data, "Bulk print");
    state.bulkPrintedCount = data.result?.copies ?? copies;
    if (!data.queued) {
      state.bulkRequestedTotal = copies;
      updateBulkProgressLabel();
    }
    clearSelectedSvgUi();
    await refreshStatus();
  } catch (error) {
    appendLog(`Bulk print error: ${error.message}`, true);
  } finally {
    state.bulkRunning = false;
    state.bulkStopRequested = false;
    updateBulkUiState();
  }
}

async function stopBulkPrint() {
  if (!state.bulkRunning) {
    appendLog("No bulk print is currently running in this page session.", true);
    return;
  }
  state.bulkStopRequested = true;
  try {
    await apiPostJson("/api/cmd/bulk/stop");
  } catch (error) {
    appendLog(`Stop request warning: ${error.message}`, true);
  }
  appendLog("Stop bulk requested.");
}

async function runVoid() {
  try {
    await apiPostJson("/api/cmd/void");
    appendLog("Void completed.");
    await refreshStatus();
  } catch (error) {
    appendLog(`Void error: ${error.message}`, true);
  }
}

async function loadLatestCapture() {
  const response = await apiFetch("/api/config/capture/latest", { method: "GET" });
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

async function requestCaptureAndThrow() {
  const capture = loadCaptureSettings();
  const data = await apiPostJson("/api/config/scanner/capture/oneshot", {
    autofocus_enabled: Boolean(capture.autofocusEnabled),
    manual_focus_value: Number(capture.manualFocusValue || 35),
  });
  const imageEl = document.getElementById("capturePreview");
  if (data.dataUri) {
    imageEl.src = String(data.dataUri);
  } else {
    const imageUrl = String(data.imageUrl || "/api/config/capture/latest/image");
    imageEl.src = `${imageUrl}?t=${Date.now()}`;
  }
  imageEl.style.display = "block";
}

async function requestCapture() {
  try {
    await requestCaptureAndThrow();
    appendLog("Capture completed and rectified image loaded.");
  } catch (error) {
    appendLog(`Capture request error: ${error.message}`, true);
  }
}

function registerEvents() {
  document.getElementById("captureBtn").addEventListener("click", requestCapture);
  document.getElementById("printBtn").addEventListener("click", printUploadedSvg);
  document.getElementById("bulkPrintBtn").addEventListener("click", bulkPrintUploadedSvg);
  document.getElementById("stopBulkBtn").addEventListener("click", stopBulkPrint);
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
    await selectSvgFromFile(file);
    event.target.value = "";
  });
}

async function initPage() {
  registerEvents();
  clearSelectedSvgUi();
  updateCaptureFullscreenButtonLabel();
  updateBulkProgressLabel();
  updateBulkUiState();
  await refreshStatus();
  startAutoStatusRefresh();
  try {
    await loadLatestCapture();
  } catch (error) {
    appendLog(`Initial capture check: ${error.message}`, true);
  }
}

initPage();
