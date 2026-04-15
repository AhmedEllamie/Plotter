const FIXED_BAUD_RATE = 250000;
const DEFAULT_STABLE_TTY_PORT = "/dev/printer_serial";
const MAX_FOCUS_VALUE = 255;
const MIN_FOCUS_VALUE = 0;
const FOCUS_STEP = 5;
const REQUIRED_QUAD_POINTS = 4;
const POINT_LABELS = ["TL", "TR", "BR", "BL"];

const uiState = {
  streamVisible: false,
  quadPoints: [],
  streamNaturalWidth: 0,
  streamNaturalHeight: 0,
  focusSyncInFlight: false,
  focusSyncQueued: false,
  lastAppliedQuadPointsPx: null,
};
const MAX_CONFIG_LOG_LINES = 100;

function showConfigMessage(message, isError = false) {
  const node = document.getElementById("configMessage");
  if (!node) return;
  node.textContent = message;
  node.className = isError ? "message-error" : "message-ok";
}

function appendConfigLog(message, isError = false) {
  const logBox = document.getElementById("configLogBox");
  if (!logBox) return;
  const line = document.createElement("div");
  line.className = `log-line${isError ? " error" : ""}`;
  line.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  logBox.prepend(line);
  while (logBox.childElementCount > MAX_CONFIG_LOG_LINES) {
    logBox.removeChild(logBox.lastElementChild);
  }
}

function readConnectionForm() {
  return {
    comPort: document.getElementById("comPort").value.trim(),
    baudRate: FIXED_BAUD_RATE,
  };
}

function readPrintSettingsForm() {
  return {
    width: document.getElementById("width").value.trim(),
    height: document.getElementById("height").value.trim(),
    xPosition: document.getElementById("xPosition").value.trim(),
    yPosition: document.getElementById("yPosition").value.trim(),
    scale: Number(document.getElementById("scale").value || 1),
    rotation: Number(document.getElementById("rotation").value || 0),
    invertX: document.getElementById("invertX").checked,
    invertY: document.getElementById("invertY").checked,
    penMode: document.getElementById("penMode").value,
    penMaxDistanceM: document.getElementById("penMaxDistanceM").value.trim(),
  };
}

function isAutofocusEnabled() {
  return Boolean(document.getElementById("autofocusEnabledRadio")?.checked);
}

function setAutofocusEnabled(enabled) {
  const enabledNode = document.getElementById("autofocusEnabledRadio");
  const disabledNode = document.getElementById("autofocusDisabledRadio");
  if (enabledNode) enabledNode.checked = Boolean(enabled);
  if (disabledNode) disabledNode.checked = !Boolean(enabled);
}

function readCaptureSettingsForm() {
  return {
    autofocusEnabled: isAutofocusEnabled(),
    manualFocusValue: Number(document.getElementById("manualFocusValue").value || 35),
    quadPoints: uiState.quadPoints.map((point) => [point[0], point[1]]),
    streamFisheye: document.getElementById("streamFisheye").checked,
  };
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function renderFocusLabel() {
  const value = Number(document.getElementById("manualFocusValue").value || 35);
  document.getElementById("manualFocusValueLabel").textContent = String(value);
}

function renderFocusMode() {
  const disabled = isAutofocusEnabled();
  const focusDownBtn = document.getElementById("focusDownBtn");
  const focusUpBtn = document.getElementById("focusUpBtn");
  if (focusDownBtn) focusDownBtn.disabled = disabled;
  if (focusUpBtn) focusUpBtn.disabled = disabled;
}

function renderQuadPoints() {
  const overlay = document.getElementById("streamPointsOverlay");
  overlay.innerHTML = "";
  uiState.quadPoints.forEach((point, index) => {
    const marker = document.createElement("div");
    marker.className = "stream-point";
    marker.style.left = `${clamp(Number(point[0]), 0, 100)}%`;
    marker.style.top = `${clamp(Number(point[1]), 0, 100)}%`;
    marker.textContent = POINT_LABELS[index] || String(index + 1);
    overlay.appendChild(marker);
  });

  const status = document.getElementById("quadPointsStatus");
  if (status) {
    status.textContent = `Points: ${uiState.quadPoints.length}/${REQUIRED_QUAD_POINTS} (click on stream: top-left, top-right, bottom-right, bottom-left)`;
  }
}

function getStreamDisplaySize(img) {
  if (!img) {
    return { width: 0, height: 0 };
  }
  const wrapper = img?.closest(".stream-wrapper");
  if (wrapper) {
    return {
      width: Number(wrapper.clientWidth || 0),
      height: Number(wrapper.clientHeight || 0),
    };
  }
  const rect = img.getBoundingClientRect();
  return {
    width: Number(rect.width || 0),
    height: Number(rect.height || 0),
  };
}

function getStreamImageGeometry() {
  const img = document.getElementById("streamPreview");
  const displaySize = getStreamDisplaySize(img);
  const containerWidth = displaySize.width;
  const containerHeight = displaySize.height;
  const naturalWidth = Number(img.naturalWidth || uiState.streamNaturalWidth || 0);
  const naturalHeight = Number(img.naturalHeight || uiState.streamNaturalHeight || 0);
  if (!containerWidth || !containerHeight || !naturalWidth || !naturalHeight) {
    return {
      containerWidth,
      containerHeight,
      naturalWidth,
      naturalHeight,
      scale: 1,
      offsetX: 0,
      offsetY: 0,
      drawWidth: containerWidth,
      drawHeight: containerHeight,
    };
  }

  const rotatedWidth = naturalHeight;
  const rotatedHeight = naturalWidth;
  const scale = Math.max(containerWidth / rotatedWidth, containerHeight / rotatedHeight);
  const drawWidth = rotatedWidth * scale;
  const drawHeight = rotatedHeight * scale;
  const offsetX = (containerWidth - drawWidth) / 2;
  const offsetY = (containerHeight - drawHeight) / 2;
  return {
    containerWidth,
    containerHeight,
    naturalWidth,
    naturalHeight,
    scale,
    offsetX,
    offsetY,
    drawWidth,
    drawHeight,
  };
}

function updateStreamPreviewLayout() {
  const img = document.getElementById("streamPreview");
  const displaySize = getStreamDisplaySize(img);
  const containerWidth = displaySize.width;
  const containerHeight = displaySize.height;
  if (!containerWidth || !containerHeight) {
    return;
  }
  img.style.setProperty("--stream-rotated-width", `${containerHeight}px`);
  img.style.setProperty("--stream-rotated-height", `${containerWidth}px`);
}

function hydrateConfiguration() {
  const connection = loadConnectionSettings();
  const comPortInput = document.getElementById("comPort");
  const savedPort = String(connection.comPort || "").trim();
  if (savedPort) {
    comPortInput.value = savedPort;
  } else if (window.location.protocol !== "file:") {
    comPortInput.value = DEFAULT_STABLE_TTY_PORT;
  } else {
    comPortInput.value = "";
  }

  const print = loadPrintSettings();
  document.getElementById("width").value = print.width || "210mm";
  document.getElementById("height").value = print.height || "297mm";
  document.getElementById("xPosition").value = print.xPosition || "50mm";
  document.getElementById("yPosition").value = print.yPosition || "50mm";
  document.getElementById("scale").value = print.scale || 1;
  document.getElementById("rotation").value = print.rotation || 0;
  document.getElementById("invertX").checked = Boolean(print.invertX);
  document.getElementById("invertY").checked = Boolean(print.invertY);
  document.getElementById("penMode").value = print.penMode === "finish" ? "finish" : "start";
  document.getElementById("penMaxDistanceM").value = print.penMaxDistanceM || "";

  const capture = loadCaptureSettings();
  setAutofocusEnabled(Boolean(capture.autofocusEnabled));
  document.getElementById("manualFocusValue").value = clamp(Number(capture.manualFocusValue || 35), MIN_FOCUS_VALUE, MAX_FOCUS_VALUE);
  document.getElementById("streamFisheye").checked = Boolean(capture.streamFisheye);
  if (Array.isArray(capture.quadPoints)) {
    uiState.quadPoints = capture.quadPoints
      .filter((point) => Array.isArray(point) && point.length === 2)
      .map((point) => [Number(point[0]), Number(point[1])])
      .filter((point) => Number.isFinite(point[0]) && Number.isFinite(point[1]))
      .filter((point) => point[0] >= 0 && point[0] <= 100 && point[1] >= 0 && point[1] <= 100);
  }
  renderFocusLabel();
  renderFocusMode();
  updateStreamPreviewLayout();
  renderQuadPoints();
}

function setTtyPortStatus(message, isError = false) {
  const node = document.getElementById("ttyPortStatus");
  if (!node) return;
  node.textContent = message;
  node.className = isError ? "small-print message-error" : "small-print message-ok";
}

function persistConnectionSettings() {
  saveConnectionSettings(readConnectionForm());
}

function persistPrintSettings() {
  savePrintSettings(readPrintSettingsForm());
}

function persistCaptureSettings() {
  saveCaptureSettings(readCaptureSettingsForm());
}

async function scanSerialPorts() {
  const btn = document.getElementById("scanPortsBtn");
  if (btn) btn.disabled = true;
  appendConfigLog("Scanning serial ports...");
  try {
    const data = await apiGet("/api/serial-ports");
    const input = document.getElementById("comPort");
    const datalist = document.getElementById("serialPortsList");
    const previousValue = (input?.value || "").trim();
    const ports = (data.ports || [])
      .map((p) => String(p.device || "").trim())
      .filter(Boolean);
    const uniquePorts = Array.from(new Set(ports));

    datalist.innerHTML = "";

    uniquePorts.forEach((device) => {
      const option = document.createElement("option");
      option.value = device;
      datalist.appendChild(option);
    });

    if (previousValue) {
      input.value = previousValue;
    } else if (window.location.protocol !== "file:") {
      input.value = DEFAULT_STABLE_TTY_PORT;
    } else if (uniquePorts.length === 1) {
      input.value = uniquePorts[0];
    } else if (uniquePorts.length > 1) {
      const usb0 = uniquePorts.find((device) => /ttyUSB0$/i.test(device));
      input.value = usb0 || uniquePorts[0];
    }

    persistConnectionSettings();
    const count = uniquePorts.length;
    showConfigMessage(count ? `Found ${count} COM/USB serial port(s).` : "No COM/USB serial ports found.");
    appendConfigLog(count ? `Scan completed: found ${count} COM/USB serial port(s).` : "Scan completed: no COM/USB serial ports found.");
    await refreshTtyPortStatus();
  } catch (error) {
    showConfigMessage(`Scan failed: ${error.message}`, true);
    appendConfigLog(`Scan failed: ${error.message}`, true);
    setTtyPortStatus("Port status: check failed.", true);
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function refreshTtyPortStatus() {
  const comPort = document.getElementById("comPort").value.trim();
  if (!comPort) {
    setTtyPortStatus("Port status: empty.");
    return;
  }
  try {
    const data = await apiGet(`/api/serial-port-check?device=${encodeURIComponent(comPort)}`);
    const isReady = Boolean(data.exists) && Boolean(data.readable) && Boolean(data.writable);
    const flags = [
      data.exists ? "exists" : "missing",
      data.readable ? "readable" : "not-readable",
      data.writable ? "writable" : "not-writable",
    ].join(", ");
    const resolved = data.resolvedTarget && data.resolvedTarget !== comPort
      ? ` -> ${data.resolvedTarget}`
      : "";
    setTtyPortStatus(
      `Port status: ${isReady ? "ready" : "unavailable"} (${flags})${resolved}`,
      !isReady
    );
  } catch (error) {
    setTtyPortStatus(`Port status: check error (${error.message}).`, true);
  }
}

async function connectPrinter() {
  const comPort = document.getElementById("comPort").value.trim();
  const payload = { baudRate: FIXED_BAUD_RATE };
  if (comPort) {
    payload.comPort = comPort;
  }
  appendConfigLog(`Connecting printer${comPort ? ` on ${comPort}` : ""}...`);
  try {
    await apiPostJson("/api/connect", payload);
    persistConnectionSettings();
    showConfigMessage("Printer connected.");
    appendConfigLog("Printer connected.");
    await refreshTtyPortStatus();
  } catch (error) {
    showConfigMessage(`Connect error: ${error.message}`, true);
    appendConfigLog(`Connect failed: ${error.message}`, true);
    await refreshTtyPortStatus();
  }
}

async function disconnectPrinter() {
  appendConfigLog("Disconnecting printer...");
  try {
    await apiPostJson("/api/disconnect");
    showConfigMessage("Printer disconnected.");
    appendConfigLog("Printer disconnected.");
    await refreshTtyPortStatus();
  } catch (error) {
    showConfigMessage(`Disconnect error: ${error.message}`, true);
    appendConfigLog(`Disconnect failed: ${error.message}`, true);
    await refreshTtyPortStatus();
  }
}

async function runChangePen() {
  const mode = document.getElementById("penMode").value || "start";
  appendConfigLog(`Running ChangePen (${mode})...`);
  try {
    await apiPostJson(`/api/change-pen/${mode}`);
    persistPrintSettings();
    showConfigMessage(`ChangePen ${mode} completed.`);
    appendConfigLog(`ChangePen ${mode} completed.`);
  } catch (error) {
    showConfigMessage(`ChangePen error: ${error.message}`, true);
    appendConfigLog(`ChangePen ${mode} failed: ${error.message}`, true);
  }
}

async function runReset() {
  appendConfigLog("Resetting distance stats...");
  try {
    await apiPostJson("/api/reset", { clearUploadedSvg: false });
    showConfigMessage("Distance reset completed.");
    appendConfigLog("Distance reset completed.");
  } catch (error) {
    showConfigMessage(`Reset error: ${error.message}`, true);
    appendConfigLog(`Distance reset failed: ${error.message}`, true);
  }
}

async function setPenMaxDistance() {
  const rawValue = document.getElementById("penMaxDistanceM").value.trim();
  if (!rawValue) {
    showConfigMessage("Enter pen max distance in meters first.", true);
    appendConfigLog("Set pen max distance blocked: value is empty.", true);
    return;
  }
  appendConfigLog(`Updating pen max distance to ${rawValue}m...`);
  try {
    await apiPostJson("/api/pen-max-distance", { meters: Number(rawValue) });
    persistPrintSettings();
    showConfigMessage("Pen max distance updated.");
    appendConfigLog(`Pen max distance updated to ${rawValue}m.`);
  } catch (error) {
    showConfigMessage(`Set pen max distance error: ${error.message}`, true);
    appendConfigLog(`Set pen max distance failed: ${error.message}`, true);
  }
}

function mapDisplayPointToOriginal(pointPercent) {
  const geometry = getStreamImageGeometry();
  if (!geometry.containerWidth || !geometry.containerHeight || !geometry.naturalWidth || !geometry.naturalHeight) {
    const xFallback = Number(pointPercent[0]) / 100;
    const yFallback = Number(pointPercent[1]) / 100;
    return [clamp(xFallback, 0, 1), clamp(yFallback, 0, 1)];
  }

  const xDisplayPx = (Number(pointPercent[0]) / 100) * geometry.containerWidth;
  const yDisplayPx = (Number(pointPercent[1]) / 100) * geometry.containerHeight;
  const xRotated = (xDisplayPx - geometry.offsetX) / geometry.scale;
  const yRotated = (yDisplayPx - geometry.offsetY) / geometry.scale;

  const xOriginal = 1 - (yRotated / geometry.naturalWidth);
  const yOriginal = xRotated / geometry.naturalHeight;
  return [clamp(xOriginal, 0, 1), clamp(yOriginal, 0, 1)];
}

function cloneQuadPoints(points) {
  return points.map((point) => [Number(point[0]), Number(point[1])]);
}

function buildQuadPointsPxFromCapture(capture, options = {}) {
  const requireQuadPoints = Boolean(options.requireQuadPoints);
  const hasLocalQuadPoints = capture.quadPoints.length === REQUIRED_QUAD_POINTS;

  if (requireQuadPoints && !hasLocalQuadPoints) {
    throw new Error("Select 4 points first.");
  }

  const naturalWidth = Number(uiState.streamNaturalWidth || 0);
  const naturalHeight = Number(uiState.streamNaturalHeight || 0);
  if (hasLocalQuadPoints && naturalWidth && naturalHeight) {
    return capture.quadPoints.map((point) => {
      const [xNorm, yNorm] = mapDisplayPointToOriginal(point);
      return [
        Math.round(xNorm * naturalWidth),
        Math.round(yNorm * naturalHeight),
      ];
    });
  }

  if (requireQuadPoints) {
    throw new Error("Start stream once so scanner frame size is known.");
  }

  if (Array.isArray(uiState.lastAppliedQuadPointsPx) && uiState.lastAppliedQuadPointsPx.length === REQUIRED_QUAD_POINTS) {
    return cloneQuadPoints(uiState.lastAppliedQuadPointsPx);
  }

  return null;
}

function rememberAppliedQuadPoints(responseData, fallbackQuadPointsPx) {
  const frameWidth = Number(responseData?.manual_config?.frame_width || 0);
  const frameHeight = Number(responseData?.manual_config?.frame_height || 0);
  if (frameWidth && frameHeight) {
    uiState.streamNaturalWidth = frameWidth;
    uiState.streamNaturalHeight = frameHeight;
  }

  const responseQuadPoints = responseData?.manual_config?.quad_points;
  if (Array.isArray(responseQuadPoints) && responseQuadPoints.length === REQUIRED_QUAD_POINTS) {
    uiState.lastAppliedQuadPointsPx = cloneQuadPoints(responseQuadPoints);
    return;
  }
  if (Array.isArray(fallbackQuadPointsPx) && fallbackQuadPointsPx.length === REQUIRED_QUAD_POINTS) {
    uiState.lastAppliedQuadPointsPx = cloneQuadPoints(fallbackQuadPointsPx);
  }
}

async function applyScannerManualConfig(options = {}) {
  const capture = readCaptureSettingsForm();
  const quadPointsPx = buildQuadPointsPxFromCapture(capture, {
    requireQuadPoints: Boolean(options.requireQuadPoints),
  });

  const payload = {
    autofocus_enabled: Boolean(capture.autofocusEnabled),
    manual_focus_value: Number(capture.manualFocusValue || 35),
  };
  if (Array.isArray(quadPointsPx) && quadPointsPx.length === REQUIRED_QUAD_POINTS) {
    payload.quad_points = quadPointsPx;
  }

  const responseData = await apiPostJson("/api/scanner/manual-config", payload);
  rememberAppliedQuadPoints(responseData, quadPointsPx);
  return { responseData, payload };
}

function queueManualFocusSync() {
  uiState.focusSyncQueued = true;
  if (!uiState.focusSyncInFlight) {
    void flushManualFocusSync();
  }
}

async function flushManualFocusSync() {
  if (uiState.focusSyncInFlight || !uiState.focusSyncQueued) {
    return;
  }

  uiState.focusSyncInFlight = true;
  uiState.focusSyncQueued = false;
  const focusValue = Number(document.getElementById("manualFocusValue").value || 35);
  const autofocusMode = isAutofocusEnabled() ? "enabled" : "disabled";
  appendConfigLog(`Syncing focus config (autofocus ${autofocusMode}, manual ${focusValue})...`);
  try {
    await applyScannerManualConfig({ requireQuadPoints: false });
    showConfigMessage(`Focus config sent (autofocus ${autofocusMode}, manual ${focusValue}).`);
    appendConfigLog(`Focus config synced (autofocus ${autofocusMode}, manual ${focusValue}).`);
  } catch (error) {
    showConfigMessage(`Focus config sync failed: ${error.message}`, true);
    appendConfigLog(`Focus config sync failed: ${error.message}`, true);
  } finally {
    uiState.focusSyncInFlight = false;
    if (uiState.focusSyncQueued) {
      void flushManualFocusSync();
    }
  }
}

function registerPersistenceListeners() {
  const connectionFields = ["comPort"];
  const printFields = [
    "width",
    "height",
    "xPosition",
    "yPosition",
    "scale",
    "rotation",
    "invertX",
    "invertY",
    "penMode",
    "penMaxDistanceM",
  ];
  const captureFields = [
    "autofocusEnabledRadio",
    "autofocusDisabledRadio",
    "manualFocusValue",
    "streamFisheye",
  ];

  connectionFields.forEach((id) => {
    const node = document.getElementById(id);
    node.addEventListener("input", () => {
      persistConnectionSettings();
      void refreshTtyPortStatus();
    });
    node.addEventListener("change", () => {
      persistConnectionSettings();
      void refreshTtyPortStatus();
    });
  });

  printFields.forEach((id) => {
    const node = document.getElementById(id);
    node.addEventListener("input", persistPrintSettings);
    node.addEventListener("change", persistPrintSettings);
  });

  captureFields.forEach((id) => {
    const node = document.getElementById(id);
    node.addEventListener("input", persistCaptureSettings);
    node.addEventListener("change", persistCaptureSettings);
  });
}

function buildStreamUrl() {
  const capture = readCaptureSettingsForm();
  const params = new URLSearchParams();
  params.set("fisheye", capture.streamFisheye ? "1" : "0");
  return `/api/scanner/stream.mjpg?${params.toString()}`;
}

function showStreamInline() {
  persistCaptureSettings();
  const url = buildStreamUrl();
  const img = document.getElementById("streamPreview");
  updateStreamPreviewLayout();
  img.src = `${url}&t=${Date.now()}`;
  uiState.streamVisible = true;
  showConfigMessage("Live stream started.");
  appendConfigLog("Live stream started.");
}

function stopStreamInline() {
  const img = document.getElementById("streamPreview");
  img.src = "";
  uiState.streamVisible = false;
  showConfigMessage("Live stream stopped.");
  appendConfigLog("Live stream stopped.");
}

function clearQuadPoints() {
  uiState.quadPoints = [];
  renderQuadPoints();
  persistCaptureSettings();
  appendConfigLog("Quad points cleared.");
}

function adjustManualFocus(delta) {
  const input = document.getElementById("manualFocusValue");
  const current = Number(input.value || 35);
  const next = clamp(current + delta, MIN_FOCUS_VALUE, MAX_FOCUS_VALUE);
  input.value = String(next);
  renderFocusLabel();
  persistCaptureSettings();
  showConfigMessage(`Manual focus updated: ${next}.`);
  const direction = delta >= 0 ? "+" : "-";
  const step = Math.abs(delta);
  void apiPostJson("/api/scanner/focus-adjust", { direction, step })
    .then(() => {
      const autofocusMode = isAutofocusEnabled() ? "enabled" : "disabled";
      showConfigMessage(`Focus adjusted (${direction}${step}) and synced (autofocus ${autofocusMode}).`);
    })
    .catch(() => {
      // Fallback keeps compatibility if scanner does not support focus-adjust.
      queueManualFocusSync();
    });
}

function addQuadPointFromClick(event) {
  const img = document.getElementById("streamPreview");
  if (!uiState.streamVisible || !img.src) {
    showConfigMessage("Start stream first.", true);
    return;
  }
  const rect = img.getBoundingClientRect();
  if (!rect.width || !rect.height) {
    return;
  }
  const xInside = event.clientX - rect.left;
  const yInside = event.clientY - rect.top;
  if (xInside < 0 || yInside < 0 || xInside > rect.width || yInside > rect.height) {
    return;
  }

  const xPercent = (xInside / rect.width) * 100;
  const yPercent = (yInside / rect.height) * 100;
  if (!Number.isFinite(xPercent) || !Number.isFinite(yPercent)) {
    return;
  }

  if (uiState.quadPoints.length >= REQUIRED_QUAD_POINTS) {
    uiState.quadPoints = [];
  }
  uiState.quadPoints.push([
    clamp(Number(xPercent.toFixed(4)), 0, 100),
    clamp(Number(yPercent.toFixed(4)), 0, 100),
  ]);
  renderQuadPoints();
  persistCaptureSettings();
  showConfigMessage(`Point ${uiState.quadPoints.length}/${REQUIRED_QUAD_POINTS} selected. Click "Send scanner config".`);
}

async function sendScannerConfig() {
  appendConfigLog("Sending scanner config...");
  try {
    const { payload } = await applyScannerManualConfig({ requireQuadPoints: true });
    showConfigMessage(`Scanner config sent successfully.\nPayload:\n${JSON.stringify(payload, null, 2)}`);
    appendConfigLog("Scanner config sent successfully.");
  } catch (error) {
    showConfigMessage(`Send scanner config failed: ${error.message}`, true);
    appendConfigLog(`Scanner config failed: ${error.message}`, true);
  }
}

function registerActions() {
  document.getElementById("scanPortsBtn").addEventListener("click", scanSerialPorts);
  document.getElementById("connectBtn").addEventListener("click", connectPrinter);
  document.getElementById("disconnectBtn").addEventListener("click", disconnectPrinter);
  document.getElementById("setPenMaxBtn").addEventListener("click", setPenMaxDistance);
  document.getElementById("changePenBtn").addEventListener("click", runChangePen);
  document.getElementById("resetBtn").addEventListener("click", runReset);
  document.getElementById("showStreamBtn").addEventListener("click", showStreamInline);
  document.getElementById("stopStreamBtn").addEventListener("click", stopStreamInline);
  document.getElementById("clearPointsBtn").addEventListener("click", clearQuadPoints);
  document.getElementById("sendScannerConfigBtn").addEventListener("click", () => {
    void sendScannerConfig();
  });
  document.getElementById("focusDownBtn").addEventListener("click", () => {
    adjustManualFocus(-FOCUS_STEP);
  });
  document.getElementById("focusUpBtn").addEventListener("click", () => {
    adjustManualFocus(FOCUS_STEP);
  });
  document.getElementById("streamPreview").addEventListener("click", addQuadPointFromClick);
  document.getElementById("streamPreview").addEventListener("load", () => {
    const img = document.getElementById("streamPreview");
    uiState.streamNaturalWidth = Number(img.naturalWidth || 0);
    uiState.streamNaturalHeight = Number(img.naturalHeight || 0);
    updateStreamPreviewLayout();
    renderQuadPoints();
  });
  ["autofocusEnabledRadio", "autofocusDisabledRadio"].forEach((id) => {
    document.getElementById(id).addEventListener("change", () => {
      persistCaptureSettings();
      renderFocusMode();
      const mode = isAutofocusEnabled() ? "enabled" : "disabled";
      showConfigMessage(`Autofocus ${mode} selected. Sending to scanner...`);
      appendConfigLog(`Autofocus ${mode} selected. Sending update...`);
      void applyScannerManualConfig({ requireQuadPoints: false })
        .then(() => {
          showConfigMessage(`Autofocus ${mode} sent.`);
          appendConfigLog(`Autofocus ${mode} sent.`);
        })
        .catch((error) => {
          showConfigMessage(`Autofocus update failed: ${error.message}`, true);
          appendConfigLog(`Autofocus update failed: ${error.message}`, true);
        });
    });
  });
  window.addEventListener("resize", () => {
    updateStreamPreviewLayout();
    renderQuadPoints();
  });
}

function initConfigurationPage() {
  hydrateConfiguration();
  registerPersistenceListeners();
  registerActions();
  showConfigMessage("Settings are saved automatically in this browser.");
  appendConfigLog("Configuration page initialized.");
  void scanSerialPorts();
  void refreshTtyPortStatus();
}

initConfigurationPage();
