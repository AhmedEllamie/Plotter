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
  profileSaveTimer: null,
  profileSaveInFlight: false,
  profileSaveQueued: false,
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
    apiKey: document.getElementById("apiKey").value.trim(),
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
  document.getElementById("apiKey").value = String(connection.apiKey || "");

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

function persistConnectionSettings() {
  saveConnectionSettings(readConnectionForm());
}

function setApiKey() {
  const apiKey = String(document.getElementById("apiKey").value || "").trim();
  if (!apiKey) {
    showConfigMessage("API key cannot be empty.", true);
    appendConfigLog("Set API key failed: empty value.", true);
    return;
  }
  const connection = loadConnectionSettings();
  saveConnectionSettings({ ...connection, apiKey });
  showConfigMessage("API key saved.");
  appendConfigLog("API key saved.");
}

function getApiKey() {
  const connection = loadConnectionSettings();
  const apiKey = String(connection.apiKey || "").trim();
  document.getElementById("apiKey").value = apiKey;
  if (apiKey) {
    showConfigMessage("API key loaded from local settings.");
    appendConfigLog("API key loaded.");
  } else {
    showConfigMessage("No saved API key found.", true);
    appendConfigLog("Get API key: no saved value.", true);
  }
}

function persistPrintSettings() {
  savePrintSettings(readPrintSettingsForm());
  queueServerUiProfileSave();
}

function persistCaptureSettings() {
  saveCaptureSettings(readCaptureSettingsForm());
  queueServerUiProfileSave();
}

function buildServerUiProfilePayload() {
  const print = readPrintSettingsForm();
  const capture = readCaptureSettingsForm();
  const cachedQuadPointsPx = Array.isArray(uiState.lastAppliedQuadPointsPx)
    ? uiState.lastAppliedQuadPointsPx.map((point) => [Number(point[0]), Number(point[1])])
    : [];
  const computedQuadPointsPx = buildQuadPointsPxFromCapture(capture, { requireQuadPoints: false });
  const quadPointsPx = Array.isArray(cachedQuadPointsPx) && cachedQuadPointsPx.length === REQUIRED_QUAD_POINTS
    ? cachedQuadPointsPx
    : (Array.isArray(computedQuadPointsPx) ? computedQuadPointsPx : []);
  return {
    print: {
      width: String(print.width || "").trim(),
      height: String(print.height || "").trim(),
      xPosition: String(print.xPosition || "").trim(),
      yPosition: String(print.yPosition || "").trim(),
      scale: Number(print.scale || 1),
      rotation: Number(print.rotation || 0),
      invertX: Boolean(print.invertX),
      invertY: Boolean(print.invertY),
    },
    capture: {
      autofocus_enabled: Boolean(capture.autofocusEnabled),
      manual_focus_value: Number(capture.manualFocusValue || 35),
      quad_points: quadPointsPx,
    },
  };
}

function applyServerUiProfile(profile) {
  if (!profile || typeof profile !== "object") {
    return;
  }
  const print = typeof profile.print === "object" && profile.print !== null ? profile.print : {};
  const capture = typeof profile.capture === "object" && profile.capture !== null ? profile.capture : {};

  if (typeof print.width === "string") document.getElementById("width").value = print.width;
  if (typeof print.height === "string") document.getElementById("height").value = print.height;
  if (typeof print.xPosition === "string") document.getElementById("xPosition").value = print.xPosition;
  if (typeof print.yPosition === "string") document.getElementById("yPosition").value = print.yPosition;
  if (Number.isFinite(Number(print.scale))) document.getElementById("scale").value = Number(print.scale);
  if (Number.isFinite(Number(print.rotation))) document.getElementById("rotation").value = Number(print.rotation);
  if (typeof print.invertX !== "undefined") document.getElementById("invertX").checked = Boolean(print.invertX);
  if (typeof print.invertY !== "undefined") document.getElementById("invertY").checked = Boolean(print.invertY);

  const autofocusEnabled = typeof capture.autofocus_enabled !== "undefined"
    ? capture.autofocus_enabled
    : capture.autofocusEnabled;
  if (typeof autofocusEnabled !== "undefined") {
    setAutofocusEnabled(Boolean(autofocusEnabled));
  }
  const manualFocusValue = Number.isFinite(Number(capture.manual_focus_value))
    ? capture.manual_focus_value
    : capture.manualFocusValue;
  if (Number.isFinite(Number(manualFocusValue))) {
    document.getElementById("manualFocusValue").value = clamp(Number(manualFocusValue), MIN_FOCUS_VALUE, MAX_FOCUS_VALUE);
  }
  const quadPointsPx = Array.isArray(capture.quad_points) ? capture.quad_points : [];
  if (quadPointsPx.length === REQUIRED_QUAD_POINTS) {
    uiState.lastAppliedQuadPointsPx = quadPointsPx
      .filter((point) => Array.isArray(point) && point.length === 2)
      .map((point) => [Number(point[0]), Number(point[1])])
      .filter((point) => Number.isFinite(point[0]) && Number.isFinite(point[1]));
  }

  persistPrintSettings();
  persistCaptureSettings();
  renderFocusLabel();
  renderFocusMode();
  renderQuadPoints();
}

async function loadServerUiProfile() {
  const profile = await apiGet("/api/config/ui-profile");
  applyServerUiProfile(profile);
}

function queueServerUiProfileSave() {
  if (uiState.profileSaveTimer) {
    clearTimeout(uiState.profileSaveTimer);
  }
  uiState.profileSaveTimer = setTimeout(() => {
    uiState.profileSaveTimer = null;
    void flushServerUiProfileSave();
  }, 500);
}

async function flushServerUiProfileSave() {
  if (uiState.profileSaveInFlight) {
    uiState.profileSaveQueued = true;
    return undefined;
  }
  uiState.profileSaveInFlight = true;
  const payload = buildServerUiProfilePayload();
  try {
    const data = await apiPostJson("/api/config/ui-profile", payload);
    rememberAppliedQuadPointsFromProfile(data);
    if (data && data.scannerApplyWarning) {
      appendConfigLog(`Scanner apply warning: ${data.scannerApplyWarning}`, true);
    }
    return data;
  } catch (error) {
    appendConfigLog(`UI profile save failed: ${error.message}`, true);
    return undefined;
  } finally {
    uiState.profileSaveInFlight = false;
    if (uiState.profileSaveQueued) {
      uiState.profileSaveQueued = false;
      void flushServerUiProfileSave();
    }
  }
}

async function saveServerUiProfileNow() {
  if (uiState.profileSaveTimer) {
    clearTimeout(uiState.profileSaveTimer);
    uiState.profileSaveTimer = null;
  }
  return flushServerUiProfileSave();
}

async function runChangePen() {
  const mode = document.getElementById("penMode").value || "start";
  appendConfigLog(`Running ChangePen (${mode})...`);
  try {
    await apiPostJson(`/api/config/change-pen/${mode}`);
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
    await apiPostJson("/api/config/reset", {});
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
    await apiPostJson("/api/config/pen-max-distance", { meters: Number(rawValue) });
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

function rememberAppliedQuadPointsFromProfile(profile) {
  if (!profile || typeof profile !== "object") {
    return;
  }
  const capture = profile.capture || {};
  const responseQuadPoints = capture.quad_points;
  if (Array.isArray(responseQuadPoints) && responseQuadPoints.length === REQUIRED_QUAD_POINTS) {
    uiState.lastAppliedQuadPointsPx = cloneQuadPoints(responseQuadPoints);
  }
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
    await saveServerUiProfileNow();
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
    node.addEventListener("input", persistConnectionSettings);
    node.addEventListener("change", persistConnectionSettings);
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
  const conn = readConnectionForm();
  const params = new URLSearchParams();
  params.set("fisheye", capture.streamFisheye ? "1" : "0");
  if (conn.apiKey) {
    params.set("token", conn.apiKey);
  }
  return `/api/config/scanner/stream.mjpg?${params.toString()}`;
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
  const direction = delta >= 0 ? "+" : "-";
  const step = Math.abs(delta);
  showConfigMessage(`Manual focus updated (${direction}${step}): ${next}. Use Send scanner config to apply.`);
  appendConfigLog(`Manual focus: ${next} (will apply on Send scanner config).`);
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
    const capture = readCaptureSettingsForm();
    buildQuadPointsPxFromCapture(capture, { requireQuadPoints: true });
    const data = await saveServerUiProfileNow();
    const warn = data && data.scannerApplyWarning;
    showConfigMessage(
      warn
        ? `Scanner config saved with warning: ${warn}`
        : "Scanner config sent successfully (via UI profile).",
      Boolean(warn),
    );
    appendConfigLog(warn ? `Scanner apply warning: ${warn}` : "Scanner config sent successfully.");
  } catch (error) {
    showConfigMessage(`Send scanner config failed: ${error.message}`, true);
    appendConfigLog(`Scanner config failed: ${error.message}`, true);
  }
}

function registerActions() {
  document.getElementById("setApiKeyBtn").addEventListener("click", setApiKey);
  document.getElementById("getApiKeyBtn").addEventListener("click", getApiKey);
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
      void saveServerUiProfileNow()
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

async function initConfigurationPage() {
  hydrateConfiguration();
  try {
    await loadServerUiProfile();
    appendConfigLog("Loaded configuration profile from server.");
  } catch (error) {
    appendConfigLog(`Server profile load failed, using local settings: ${error.message}`, true);
  }
  registerPersistenceListeners();
  registerActions();
  showConfigMessage("Settings are saved automatically in this browser.");
  appendConfigLog("Configuration page initialized.");
}

void initConfigurationPage();
