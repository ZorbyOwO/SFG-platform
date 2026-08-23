const API_BASE_URL = "http://localhost:8000";
const KIOSK_ID = "SFG-KIOSK-001";
const page = document.body.dataset.page;

const showError = (message) => {
  const target = document.getElementById("error");
  if (!target) return;
  target.textContent = message;
  target.hidden = false;
};

const kioskKey = () => sessionStorage.getItem("sfg_kiosk_key") || "";
const payment = () => JSON.parse(sessionStorage.getItem("sfg_payment_session") || "null");
const setPayment = (value) => sessionStorage.setItem("sfg_payment_session", JSON.stringify(value));
const clearPayment = () => {
  sessionStorage.removeItem("sfg_payment_session");
  sessionStorage.removeItem("sfg_identification");
  sessionStorage.removeItem("sfg_receipt");
};

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("X-Kiosk-Key", kioskKey());
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new Error(body.message || "The kiosk service could not complete the request.");
    error.code = body.error;
    throw error;
  }
  return response.status === 204 ? null : response.json();
}

function requireSetup() {
  if (!kioskKey()) {
    window.location.replace("index.html");
    return false;
  }
  return true;
}

if (page === "setup") {
  clearPayment();
  document.getElementById("setup-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const value = document.getElementById("kiosk-key").value;
    if (!value) return showError("Load the local development kiosk key first.");
    sessionStorage.setItem("sfg_kiosk_key", value);
    document.getElementById("kiosk-key").value = "";
    window.location.assign("amount.html");
  });
}

if (page === "amount" && requireSetup()) {
  document.getElementById("amount-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const amount = Number(document.getElementById("amount").value);
    if (!Number.isFinite(amount) || amount <= 0) return showError("Enter an amount greater than zero.");
    try {
      const result = await api("/pay/session", { method: "POST", body: JSON.stringify({ kiosk_id: KIOSK_ID, amount }) });
      setPayment(result);
      window.location.assign("scan.html");
    } catch (error) { showError(error.message); }
  });
}

if (page === "scan" && requireSetup()) {
  const current = payment();
  if (!current) window.location.replace("amount.html");
  const video = document.getElementById("camera");
  let stream = null;
  const stopCamera = () => { if (stream) stream.getTracks().forEach((track) => track.stop()); stream = null; video.srcObject = null; };
  navigator.mediaDevices?.getUserMedia({ video: { facingMode: "user" }, audio: false }).then((active) => {
    stream = active; video.srcObject = active;
  }).catch(() => showError("Camera permission is required. Check browser settings and try again."));
  document.getElementById("capture").addEventListener("click", async () => {
    if (!stream || !video.videoWidth) return showError("Wait for the camera preview before capturing.");
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.86));
    canvas.width = 1; canvas.height = 1;
    if (!blob) return showError("The camera frame could not be prepared.");
    const form = new FormData();
    form.set("session_id", current.session_id); form.set("nonce", current.nonce); form.set("frame", blob, "capture.jpg");
    try {
      const result = await api("/pay/identify", { method: "POST", headers: { "X-SFG-Simulation": "success" }, body: form });
      stopCamera();
      sessionStorage.setItem("sfg_identification", JSON.stringify(result));
      window.location.assign("confirm.html");
    } catch (error) { stopCamera(); showError(error.message); }
  });
  const cancel = async () => {
    stopCamera();
    try { await api("/pay/cancel", { method: "POST", body: JSON.stringify({ session_id: current.session_id }) }); } catch { /* best-effort reset */ }
    clearPayment(); window.location.assign("amount.html");
  };
  document.getElementById("cancel").addEventListener("click", cancel);
  window.addEventListener("pagehide", stopCamera, { once: true });
}

if (page === "confirm" && requireSetup()) {
  const current = payment();
  const identity = JSON.parse(sessionStorage.getItem("sfg_identification") || "null");
  if (!current || !identity) window.location.replace("amount.html");
  document.getElementById("identity").textContent = identity?.citizen_display_name || "Matched customer";
  document.getElementById("masked-ic").textContent = identity?.masked_ic || "Masked identity";
  document.getElementById("confirm-amount").value = `MYR ${identity?.amount || "0.00"}`;
  document.getElementById("confirm-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const pinInput = document.getElementById("pin");
    const pin = pinInput.value;
    if (!/^\d{6}$/.test(pin)) return showError("Enter the six-digit main account PIN.");
    pinInput.value = "";
    try {
      const receipt = await api("/pay/confirm", { method: "POST", body: JSON.stringify({ session_id: current.session_id, nonce: current.nonce, pin }) });
      sessionStorage.removeItem("sfg_identification");
      sessionStorage.setItem("sfg_receipt", JSON.stringify(receipt));
      sessionStorage.removeItem("sfg_payment_session");
      window.location.assign("receipt.html");
    } catch (error) { showError(error.message); }
  });
  document.getElementById("cancel").addEventListener("click", async () => {
    try { await api("/pay/cancel", { method: "POST", body: JSON.stringify({ session_id: current.session_id }) }); } catch { /* best-effort reset */ }
    document.getElementById("pin").value = "";
    clearPayment(); window.location.assign("amount.html");
  });
}

if (page === "receipt" && requireSetup()) {
  const receipt = JSON.parse(sessionStorage.getItem("sfg_receipt") || "null");
  if (!receipt) window.location.replace("amount.html");
  document.getElementById("reference").textContent = receipt?.reference || "—";
  document.getElementById("receipt-amount").textContent = `MYR ${receipt?.amount || "0.00"}`;
  document.getElementById("merchant").textContent = receipt?.merchant_name || "—";
  document.getElementById("completed").textContent = receipt?.verification_completed_at ? new Date(receipt.verification_completed_at).toLocaleString("en-MY", { dateStyle: "medium", timeStyle: "short" }) : "—";
  document.getElementById("balance").textContent = `MYR ${receipt?.balance_after || "0.00"}`;
  sessionStorage.removeItem("sfg_receipt");
}
