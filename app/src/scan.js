// Camera scan: Chromium BarcodeDetector when it can read Data Matrix,
// otherwise the vendored zxing-js build (Data Matrix and QR).

export async function startScan({ video, onText, onStatus }) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error("This browser has no camera API. Type the tube code instead.");
  }
  const formats = await supportedFormats();
  if (formats.includes("data_matrix")) {
    onStatus("Point the camera at the Data Matrix or QR code.");
    return detectWithBarcodeDetector(video, formats, onText);
  }
  onStatus("Point the camera at the Data Matrix or QR code.");
  return detectWithZxing(video, onText);
}

async function supportedFormats() {
  if (typeof BarcodeDetector === "undefined" || !BarcodeDetector.getSupportedFormats) return [];
  try {
    return await BarcodeDetector.getSupportedFormats();
  } catch {
    return [];
  }
}

async function openCamera(video) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: false,
    video: { facingMode: { ideal: "environment" } },
  });
  video.srcObject = stream;
  video.setAttribute("playsinline", "");
  video.muted = true;
  await video.play();
  return stream;
}

function stopStream(stream) {
  for (const track of stream.getTracks()) track.stop();
}

async function detectWithBarcodeDetector(video, formats, onText) {
  const wanted = formats.filter((format) => format === "data_matrix" || format === "qr_code");
  const stream = await openCamera(video);
  const detector = new BarcodeDetector({ formats: wanted });
  let running = true;
  const tick = async () => {
    if (!running) return;
    try {
      const codes = await detector.detect(video);
      if (codes && codes.length && codes[0].rawValue) {
        running = false;
        stopStream(stream);
        onText(codes[0].rawValue);
        return;
      }
    } catch {
      // A frame can fail before the camera has a picture.
    }
    if (running) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  return () => {
    running = false;
    stopStream(stream);
  };
}

async function detectWithZxing(video, onText) {
  const imported = await import("../vendor/zxing-browser.js");
  const Reader = imported.BrowserMultiFormatReader;
  const reader = new Reader();
  let stopped = false;
  const controls = await reader.decodeFromVideoDevice(undefined, video, (result, error, controls) => {
    if (stopped || !result) return;
    stopped = true;
    try {
      controls.stop();
    } catch {
      // The camera track is stopped again below.
    }
    const text = typeof result.getText === "function" ? result.getText() : String(result.text || "");
    if (text) onText(text);
  });
  return () => {
    stopped = true;
    try {
      controls.stop();
    } catch {
      // Already stopped after a successful read.
    }
  };
}

export function cameraErrorText(error) {
  const name = error && error.name;
  if (name === "NotAllowedError" || name === "PermissionDeniedError") {
    return "Camera permission was denied. Type the tube code instead.";
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") {
    return "No camera is available. Type the tube code instead.";
  }
  if (error && error.message) return error.message;
  return "The camera could not start. Type the tube code instead.";
}
