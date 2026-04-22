const STORAGE_KEY = "automatedSignature.v1";

const DEFAULT_PRINT_SETTINGS = {
  width: "210mm",
  height: "297mm",
  xPosition: "50mm",
  yPosition: "50mm",
  scale: 1,
  rotation: 0,
  invertX: false,
  invertY: true,
  penMode: "start",
  penMaxDistanceM: "",
};

const DEFAULT_CONNECTION_SETTINGS = {
  comPort: "",
  baudRate: 250000,
  apiKey: "",
};

const DEFAULT_CAPTURE_SETTINGS = {
  autofocusEnabled: false,
  manualFocusValue: 35,
  quadPoints: [],
  streamFisheye: true,
};

function parseApiResponse(response) {
  return response.json().catch(() => {
    throw new Error(`Invalid API response (${response.status})`);
  }).then((payload) => {
    if (!response.ok || payload.success === false) {
      let message = payload?.message || `Request failed (${response.status})`;
      if (response.status === 401) {
        message = `${message} Configure a valid API key from the Configuration page.`;
      }
      throw new Error(message);
    }
    return payload.data;
  });
}

function buildAuthHeaders() {
  const connection = loadConnectionSettings();
  const apiKey = String(connection.apiKey || "").trim();
  if (!apiKey) {
    return {};
  }
  return { "X-API-Key": apiKey };
}

async function apiFetch(url, options = {}) {
  const providedHeaders = options.headers || {};
  const headers = { ...providedHeaders, ...buildAuthHeaders() };
  return fetch(url, { ...options, headers });
}

async function apiGet(url) {
  const response = await apiFetch(url, { method: "GET" });
  return parseApiResponse(response);
}

async function apiPostJson(url, body = {}) {
  const response = await apiFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseApiResponse(response);
}

async function apiPostForm(url, formData) {
  const response = await apiFetch(url, {
    method: "POST",
    body: formData,
  });
  return parseApiResponse(response);
}

function readStorageState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {
        print: { ...DEFAULT_PRINT_SETTINGS },
        connection: { ...DEFAULT_CONNECTION_SETTINGS },
        capture: { ...DEFAULT_CAPTURE_SETTINGS },
      };
    }

    const parsed = JSON.parse(raw);
    const print = typeof parsed?.print === "object" && parsed.print !== null ? parsed.print : {};
    const connection =
      typeof parsed?.connection === "object" && parsed.connection !== null ? parsed.connection : {};
    const capture = typeof parsed?.capture === "object" && parsed.capture !== null ? parsed.capture : {};

    return {
      print: { ...DEFAULT_PRINT_SETTINGS, ...print },
      connection: { ...DEFAULT_CONNECTION_SETTINGS, ...connection },
      capture: { ...DEFAULT_CAPTURE_SETTINGS, ...capture },
    };
  } catch (error) {
    return {
      print: { ...DEFAULT_PRINT_SETTINGS },
      connection: { ...DEFAULT_CONNECTION_SETTINGS },
      capture: { ...DEFAULT_CAPTURE_SETTINGS },
    };
  }
}

function writeStorageState(nextState) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(nextState));
}

function loadPrintSettings() {
  return readStorageState().print;
}

function savePrintSettings(printSettings) {
  const state = readStorageState();
  state.print = { ...DEFAULT_PRINT_SETTINGS, ...printSettings };
  writeStorageState(state);
  return state.print;
}

function loadConnectionSettings() {
  return readStorageState().connection;
}

function saveConnectionSettings(connectionSettings) {
  const state = readStorageState();
  state.connection = { ...DEFAULT_CONNECTION_SETTINGS, ...connectionSettings };
  writeStorageState(state);
  return state.connection;
}

function loadCaptureSettings() {
  return readStorageState().capture;
}

function saveCaptureSettings(captureSettings) {
  const state = readStorageState();
  state.capture = { ...DEFAULT_CAPTURE_SETTINGS, ...captureSettings };
  writeStorageState(state);
  return state.capture;
}
