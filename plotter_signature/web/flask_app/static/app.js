const state = {
  uploadedSvgName: null,
  lastSvgFile: null,
  capturePollHandle: null,
  statusPollHandle: null,
  jobPollHandle: null,
  queuePollHandle: null,
  lastBulkCopies: 1,
  bulkRunning: false,
  bulkStopRequested: false,
  bulkRequestedTotal: 0,
  bulkPrintedCount: 0,
  systemInitialized: false,
  trackedJobs: new Map(),
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

function jobTypeLabel(jobType, job) {
  if (jobType === "bulk") {
    const name = job?.svgFileName ? ` — ${job.svgFileName}` : "";
    return `Bulk${name}`;
  }
  if (jobType === "bulk_stop") return "Bulk stop";
  if (jobType === "void") return "Void";
  return "Print";
}

function isTerminalJobStatus(status) {
  return status === "completed" || status === "failed" || status === "stopped";
}

function statusLabel(job) {
  if (job.status === "running") return "running";
  if (job.status === "pending") return "pending";
  return job.status || "unknown";
}

function trackJob(jobId, jobType, extra = {}) {
  if (!jobId) return;
  state.trackedJobs.set(String(jobId), {
    jobId: String(jobId),
    jobType,
    status: "pending",
    ...extra,
  });
  ensureJobPolling();
}

function untrackFinishedJobs() {
  for (const [jobId, job] of state.trackedJobs.entries()) {
    if (isTerminalJobStatus(job.status)) {
      state.trackedJobs.delete(jobId);
    }
  }
}

function renderErrorPanel(status) {
  const codeNode = document.getElementById("errorCodeValue");
  const messageNode = document.getElementById("errorMessageValue");
  const code = status?.lastApiErrorCode;
  const message = status?.lastApiErrorMessage;
  if (codeNode) {
    codeNode.textContent = code == null || code === "" ? "—" : String(code);
    codeNode.className = code == null || code === "" ? "" : "error-message-value";
  }
  if (messageNode) {
    messageNode.textContent = message == null || message === "" ? "—" : String(message);
    messageNode.className = message == null || message === "" ? "" : "error-message-value";
  }
}

function renderQueuePanel(queueData, errorMessage = "") {
  const container = document.getElementById("jobQueueList");
  if (!container) return;

  container.innerHTML = "";
  if (errorMessage) {
    const err = document.createElement("div");
    err.className = "job-queue-empty finished-bad";
    err.textContent = errorMessage;
    container.appendChild(err);
    return;
  }

  const items = [];
  if (queueData?.active) {
    items.push({ ...queueData.active, displayStatus: "running" });
  }
  if (Array.isArray(queueData?.pending)) {
    for (const job of queueData.pending) {
      items.push({ ...job, displayStatus: "pending" });
    }
  }

  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "job-queue-empty muted";
    empty.textContent = "No active or pending jobs.";
    container.appendChild(empty);
    return;
  }

  for (const job of items) {
    const row = document.createElement("div");
    const displayStatus = job.displayStatus || job.status;
    let rowClass = "job-queue-item";
    if (displayStatus === "running") rowClass += " running";
    else if (displayStatus === "pending") rowClass += " pending";
    row.className = rowClass;

    const label = document.createElement("span");
    label.textContent = jobTypeLabel(job.jobType, job);

    const statusNode = document.createElement("span");
    statusNode.textContent = statusLabel({ ...job, status: displayStatus });

    row.append(label, statusNode);
    container.appendChild(row);
  }
}

function syncBulkStateFromQueue(queueData) {
  const active = queueData?.active;
  state.bulkRunning = active?.jobType === "bulk" && active?.status === "running";
  if (!state.bulkRunning && !state.trackedJobs.size) {
    state.bulkStopRequested = false;
  }
  updateBulkUiState();
  updatePrintCaptureUiState();
}

function syncBulkStateFromStatus(status) {
  const requested = Number(status?.bulk_requested_total || 0);
  const printed = Number(status?.bulk_printed_count || 0);
  if (requested > 0 || printed > 0 || state.bulkRunning) {
    state.bulkRequestedTotal = requested;
    state.bulkPrintedCount = printed;
    updateBulkProgressLabel();
  }
}

function queueHasOpenJobs(queueData) {
  return Boolean(queueData?.active) || (Array.isArray(queueData?.pending) && queueData.pending.length > 0);
}

async function refreshJobQueue() {
  try {
    const queueData = await apiGet("/api/cmd/jobs/queue");
    renderQueuePanel(queueData);
    syncBulkStateFromQueue(queueData);
    if (queueHasOpenJobs(queueData)) {
      ensureQueuePolling();
    }
    return queueData;
  } catch (error) {
    const message = String(error.message || "Queue unavailable");
    renderQueuePanel(null, message);
    return null;
  }
}

function ensureQueuePolling(intervalMs = 1500) {
  if (state.queuePollHandle) return;
  state.queuePollHandle = setInterval(() => {
    void refreshJobQueue();
  }, intervalMs);
}

function stopQueuePollingIfIdle(queueData) {
  if (queueHasOpenJobs(queueData)) return;
  if (state.trackedJobs.size > 0) return;
  if (state.queuePollHandle) {
    clearInterval(state.queuePollHandle);
    state.queuePollHandle = null;
  }
}

async function pollTrackedJobs() {
  const pendingIds = [...state.trackedJobs.values()]
    .filter((job) => !isTerminalJobStatus(job.status))
    .map((job) => job.jobId);

  for (const jobId of pendingIds) {
    try {
      const polled = await apiGetJobStatus(`/api/cmd/jobs/${encodeURIComponent(jobId)}`);
      const snapshot = polled.data;
      const existing = state.trackedJobs.get(jobId) || { jobId };
      const merged = { ...existing, ...snapshot };
      state.trackedJobs.set(jobId, merged);

      if (isTerminalJobStatus(snapshot.status)) {
        const label = jobTypeLabel(snapshot.jobType, snapshot);
        if (snapshot.status === "completed") {
          appendLog(`${label} finished (${snapshot.jobId.slice(0, 8)}…).`);
        } else if (snapshot.status === "failed") {
          appendLog(`${label} failed: ${polled.message || "No details."}`, true);
        } else if (snapshot.status === "stopped") {
          appendLog(`${label} stopped (${snapshot.jobId.slice(0, 8)}…).`);
        }
      }
    } catch (error) {
      appendLog(`Job ${jobId.slice(0, 8)}… poll error: ${error.message}`, true);
    }
  }

  untrackFinishedJobs();
  const queueData = await refreshJobQueue();

  const stillTracked = [...state.trackedJobs.values()].some((job) => !isTerminalJobStatus(job.status));
  const stillQueued = queueHasOpenJobs(queueData);
  if (!stillTracked && !stillQueued && state.jobPollHandle) {
    clearInterval(state.jobPollHandle);
    state.jobPollHandle = null;
  }
  stopQueuePollingIfIdle(queueData);
}

function ensureJobPolling(intervalMs = 1500) {
  if (state.jobPollHandle) return;
  state.jobPollHandle = setInterval(() => {
    void pollTrackedJobs();
  }, intervalMs);
  void pollTrackedJobs();
}

function updatePrintCaptureUiState() {
  const disabled = !state.systemInitialized || state.bulkRunning;
  const printBtn = document.getElementById("printBtn");
  const bulkPrintBtn = document.getElementById("bulkPrintBtn");
  const captureBtn = document.getElementById("captureBtn");
  if (printBtn) printBtn.disabled = !state.systemInitialized;
  if (bulkPrintBtn) bulkPrintBtn.disabled = disabled;
  if (captureBtn) captureBtn.disabled = !state.systemInitialized;
}

async function refreshSystemInitStatus() {
  try {
    const profile = await apiGet("/api/config/ui-profile");
    state.systemInitialized = Boolean(profile.initialized);
    if (!state.systemInitialized) {
      appendLog("System not initialized. Configure on /configuration and press Send scanner config.", true);
    }
  } catch (error) {
    state.systemInitialized = false;
    appendLog(`Could not load system configuration status: ${error.message}`, true);
  }
  updatePrintCaptureUiState();
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
  const isConnected = Boolean(status.printer_connected ?? status.is_open);
  const isBusy = Boolean(status.is_busy ?? status.is_printing);
  const executionPercent = clampPercent(status.current_execution_percent);
  const remainingPenPercent = clampPercent(status.remaining_pen_percent);
  const hasPenConfig = Number(status.max_pen_distance_m || 0) > 0;

  renderErrorPanel(status);
  syncBulkStateFromStatus(status);

  setBadgeState(
    "statusConnectionBadge",
    isConnected ? "Connected" : "Disconnected",
    isConnected ? "badge-ok" : "badge-warn"
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
  } finally {
    await refreshJobQueue();
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
  ensureQueuePolling(intervalMs);
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

function logJobAccepted(data, label) {
  appendLog(
    `${label} accepted | job ${data.jobId} | position ${data.queuePosition ?? "?"} | status ${data.status}`
  );
}

async function printUploadedSvg() {
  if (!state.systemInitialized) {
    appendLog("Print blocked: system not initialized. Use /configuration and Send scanner config.", true);
    return;
  }
  if (!state.lastSvgFile) {
    appendLog("Choose an SVG file first (Choose SVG). Each print sends the file with the request.", true);
    return;
  }
  const formData = new FormData();
  formData.append("svg", state.lastSvgFile);
  try {
    appendLog(`Print submitted at ${formatTimestamp()}.`);
    const data = await apiPostForm("/api/cmd/print", formData);
    logJobAccepted(data, "Print");
    trackJob(data.jobId, data.jobType || "print");
    clearSelectedSvgUi();
    await refreshStatus();
    await refreshJobQueue();
  } catch (error) {
    appendLog(`Print error: ${error.message}`, true);
  }
}

async function bulkPrintUploadedSvg() {
  if (!state.systemInitialized) {
    appendLog("Bulk print blocked: system not initialized. Use /configuration and Send scanner config.", true);
    return;
  }
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
  state.bulkStopRequested = false;
  state.bulkRequestedTotal = copies;
  state.bulkPrintedCount = 0;
  updateBulkProgressLabel();

  const formData = new FormData();
  formData.append("svg", state.lastSvgFile);
  formData.append("copies", String(copies));

  try {
    appendLog(`Bulk print submitted (${copies} copies).`);
    const data = await apiPostForm("/api/cmd/print/bulk", formData);
    logJobAccepted(data, "Bulk print");
    trackJob(data.jobId, data.jobType || "bulk", { copiesRequested: copies });
    state.bulkRunning = true;
    updateBulkUiState();
    clearSelectedSvgUi();
    await refreshStatus();
    await refreshJobQueue();
  } catch (error) {
    appendLog(`Bulk print error: ${error.message}`, true);
  }
}

function findBulkStopTargetJobId() {
  for (const job of state.trackedJobs.values()) {
    if (job.jobType === "bulk" && !isTerminalJobStatus(job.status)) {
      return job.jobId;
    }
  }
  return null;
}

async function stopBulkPrint() {
  state.bulkStopRequested = true;
  try {
    const targetJobId = findBulkStopTargetJobId();
    const body = targetJobId ? { targetJobId } : {};
    const data = await apiPostJson("/api/cmd/bulk/stop", body);
    logJobAccepted(data, "Bulk stop");
    trackJob(data.jobId, data.jobType || "bulk_stop");
    appendLog("Stop bulk requested.");
    await refreshJobQueue();
  } catch (error) {
    appendLog(`Stop request error: ${error.message}`, true);
  }
}

async function runVoid() {
  try {
    const data = await apiPostJson("/api/cmd/void");
    logJobAccepted(data, "Void");
    trackJob(data.jobId, data.jobType || "void");
    await refreshStatus();
    await refreshJobQueue();
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
  if (!state.systemInitialized) {
    throw new Error("System not initialized. Configure on /configuration and press Send scanner config.");
  }
  const data = await apiPostJson("/api/config/scanner/capture/oneshot", {});
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
  await refreshSystemInitStatus();
  await refreshStatus();
  await refreshJobQueue();
  startAutoStatusRefresh();
  try {
    await loadLatestCapture();
  } catch (error) {
    appendLog(`Initial capture check: ${error.message}`, true);
  }
}

initPage();
