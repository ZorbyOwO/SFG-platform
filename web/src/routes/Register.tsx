import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { EnrollmentSessionDto } from "../contracts/dto";
import { useAuth } from "../app/AuthContext";
import { FaceCaptureGuide } from "../components/FaceCaptureGuide";
import { useCameraPreview } from "../components/CameraPreview";
import { SecretField } from "../components/SecretField";
import { services } from "../services";
import { biometricCore, captureGuidance, isAccepted, type BiometricSessionDto } from "../services/biometricCore";

const stepLabels = ["Account", "Consent", "Face scan", "PIN", "Review"];
const blockedPins = new Set(["000000", "111111", "222222", "333333", "444444", "555555", "666666", "777777", "888888", "999999", "123456", "654321", "121212", "123123"]);

function pinIsSafe(pin: string, ic: string): boolean {
  const digits = ic.replace(/\D/g, "");
  const dates = new Set([digits.slice(0, 6), `${digits.slice(4, 6)}${digits.slice(2, 4)}${digits.slice(0, 2)}`]);
  return /^\d{6}$/.test(pin) && !blockedPins.has(pin) && !dates.has(pin);
}

export function Register() {
  const [step, setStep] = useState(1);
  const [details, setDetails] = useState({ full_name: "", email: "", ic: "", password: "", password_confirm: "" });
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [capturePrepared, setCapturePrepared] = useState(false);
  const [session, setSession] = useState<EnrollmentSessionDto | null>(null);
  const [coreSession, setCoreSession] = useState<BiometricSessionDto | null>(null);
  const [positions, setPositions] = useState<string[]>([]);
  const [guidance, setGuidance] = useState("");
  const [pin, setPin] = useState("");
  const [pinConfirm, setPinConfirm] = useState("");
  const [reviewAccepted, setReviewAccepted] = useState(false);
  const [activated, setActivated] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const auth = useAuth();
  const navigate = useNavigate();
  const camera = useCameraPreview();

  const execute = async (action: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await action(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to continue."); }
    finally { setBusy(false); }
  };

  const account = (event: FormEvent) => {
    event.preventDefault();
    void execute(async () => {
      await services.auth.register(details);
      auth.setAuthenticated(true);
      setDetails((current) => ({ ...current, password: "", password_confirm: "" }));
      setStep(2);
    });
  };
  /** Open both the account-state session and, where available, the real CoreCV session. */
  const openSessions = async () => {
    const accountSession = await services.biometric.startEnrollment();
    setSession(accountSession);
    setPositions([]);
    setGuidance("");
    const token = await services.auth.getAccessToken();
    if (!token) {
      // No trusted-tier identity in this mode; the flow stays an explicit simulation.
      setCoreSession(null);
      return;
    }
    setCoreSession(await biometricCore.startSession(token, "enrol"));
  };

  const consent = () => void execute(async () => {
    if (!consentAccepted) throw new Error("Confirm biometric consent before continuing.");
    await openSessions();
    setCapturePrepared(false);
    setStep(3);
  });
  const restartCapture = () => void execute(async () => {
    await openSessions();
    setCapturePrepared(true);
  });
  const capture = (pose: string) => void execute(async () => {
    if (!session) throw new Error("Start a new enrolment session.");
    if (camera.status !== "active") throw new Error("Enable the camera preview before recording a position.");

    if (coreSession) {
      const frame = await camera.captureFrame();
      if (!frame) throw new Error("The camera frame was not ready. Wait for the preview and try again.");
      const outcome = await biometricCore.capture(await requireToken(), coreSession, pose, frame);
      if (!isAccepted(outcome)) {
        setGuidance(captureGuidance(outcome));
        setPositions(outcome.positions_complete);
        return;
      }
      // The trusted tier already accepted the pose; mirror it into account state.
      await services.biometric.capturePosition(session, pose);
      setGuidance("");
      setPositions(outcome.positions_complete);
      return;
    }

    const result = await services.biometric.capturePosition(session, pose);
    if (result.capture_status !== "CAPTURE_READY" || result.liveness_status !== "PAD_LIVE") throw new Error("This capture did not pass the face and liveness checks. Adjust your position and try again.");
    setPositions(result.positions_complete);
  });
  const requireToken = async (): Promise<string> => {
    const token = await services.auth.getAccessToken();
    if (!token) throw new Error("Your session expired. Sign in again to continue enrolment.");
    return token;
  };
  const finishCapture = () => void execute(async () => {
    if (!session || positions.length < 3) throw new Error("Capture front, right, and left positions first.");
    if (coreSession) await biometricCore.complete(await requireToken(), coreSession);
    await services.biometric.completeEnrollment(session.session_id);
    camera.stopCamera();
    setCoreSession(null);
    setStep(4);
  });
  const beginCapture = () => {
    setCapturePrepared(true);
    void camera.startCamera();
  };
  const submitPin = (event: FormEvent) => {
    event.preventDefault();
    void execute(async () => {
      if (!pinIsSafe(pin, details.ic)) throw new Error("Choose a less predictable six-digit PIN that is not based on your IC birth date.");
      if (pin !== pinConfirm) throw new Error("The PIN confirmation does not match.");
      await services.biometric.setPin(pin, pinConfirm);
      setPin(""); setPinConfirm(""); setStep(5);
    });
  };
  const activate = () => void execute(async () => {
    if (!reviewAccepted) throw new Error("Confirm the final privacy and account acknowledgement.");
    await services.biometric.activate();
    setActivated(true);
  });

  const passwordChecks = [
    [details.password.length >= 8, "8+ characters"],
    [/[A-Z]/.test(details.password) && /[a-z]/.test(details.password), "Uppercase + lowercase"],
    [/\d/.test(details.password), "At least one number"],
    [details.password.length > 0 && details.password === details.password_confirm, "Passwords match"],
  ] as const;
  const pinSafe = pinIsSafe(pin, details.ic);

  return <main className="auth-page register-page">
    <aside className="auth-brand-panel registration-panel">
      <div className="brand light"><span className="brand-mark white">SFG</span><span>Sarawak Facial Gateway</span></div>
      <div><p className="eyebrow light-text">Create account</p><h2>Set up your wallet in five clear steps.</h2><ol className="step-list">{stepLabels.map((label, index) => <li key={label} className={step === index + 1 ? "active" : step > index + 1 ? "done" : ""}><span>{step > index + 1 ? "✓" : index + 1}</span>{label}</li>)}</ol></div>
      <p className="panel-note">No payment is ever approved by a face alone. Your private six-digit PIN remains the second step.</p>
    </aside>
    <section className="auth-form-panel register-form-panel"><div className="auth-form register-form">
      <Link className="back-link" to="/platform">Exit registration</Link><p className="eyebrow">Step {step} of 5 · {stepLabels[step - 1]}</p>
      {services.mode === "mock" && <div className="simulation-banner" role="status">Simulation mode performs no real identity, biometric, banking, or payment check.</div>}
      {services.mode === "supabase" && <div className="simulation-banner" role="status">Account and wallet data are saved in Supabase. Face detection, liveness, and template creation run on the SFG server. IC numbers are not checked against a government system, and top-ups remain simulated.</div>}

      {step === 1 && <form onSubmit={account}><h1>Your details</h1><p className="form-intro">Use your legal details. Your 12-digit IC becomes your private login identifier.</p><div className="form-grid">
        <label className="span-2">Full legal name<input autoComplete="name" value={details.full_name} onChange={(event) => setDetails({ ...details, full_name: event.target.value })} required /></label>
        <label>Email<input type="email" autoComplete="email" value={details.email} onChange={(event) => setDetails({ ...details, email: event.target.value })} required /></label>
        <label>IC number<input inputMode="numeric" autoComplete="username" placeholder="000000-00-0000" value={details.ic} onChange={(event) => setDetails({ ...details, ic: event.target.value })} required /></label>
        <SecretField label="Password" autoComplete="new-password" value={details.password} onChange={(value) => setDetails({ ...details, password: value })} />
        <SecretField label="Confirm password" autoComplete="new-password" value={details.password_confirm} onChange={(value) => setDetails({ ...details, password_confirm: value })} />
      </div><div className="requirements-grid" aria-label="Password requirements">{passwordChecks.map(([valid, label]) => <span className={valid ? "valid" : ""} key={label}>{valid ? "✓" : "○"} {label}</span>)}</div><button className="button primary full" disabled={busy || passwordChecks.some(([valid]) => !valid)}>{busy ? "Creating account…" : "Create account and continue"}</button></form>}

      {step === 2 && <section className="registration-section"><h1>Your face, your choice</h1><p className="form-intro">SFG needs explicit permission before the enrolment camera can start.</p>
        <div className="privacy-points">
          <div><span>1</span><p><strong>What is created</strong>A mathematical face template for future identity comparison—not a payment approval.</p></div>
          <div><span>2</span><p><strong>What is retained</strong>The reusable template is kept privately. Raw camera frames are temporary and removed after extraction.</p></div>
          <div><span>3</span><p><strong>Your control</strong>You can re-enrol or request biometric withdrawal through the account-support process.</p></div>
        </div>
        <div className="notice-card"><strong>Before the camera opens</strong><p>Use a well-lit, private place. Remove face coverings that prevent a clear scan. Glasses may remain unless glare blocks your eyes.</p></div>
        <label className="check-row consent-check"><input type="checkbox" checked={consentAccepted} onChange={(event) => setConsentAccepted(event.target.checked)} /><span>I understand how my face template is used and I consent to biometric enrolment for SFG identification.</span></label>
        <button className="button primary full" type="button" onClick={consent} disabled={!consentAccepted || busy}>{busy ? "Preparing enrolment…" : "Give consent and continue"}</button>
      </section>}

      {step === 3 && <section className="registration-section"><h1>Guided face enrolment</h1><p className="form-intro">Three guided positions make the future CoreCV enrolment capture consistent and easier to verify.</p>
        {!capturePrepared ? <div className="capture-preflight">
          <div className="preflight-visual"><div className="face-guide" aria-hidden="true" /></div>
          <div><h2>Get camera-ready</h2><ul className="readiness-list"><li>Only you are visible</li><li>Your face is evenly lit</li><li>Camera is at eye level</li><li>Keep a neutral expression</li></ul></div>
          <button className="button primary full span-all" type="button" onClick={beginCapture}>Enable camera and begin</button>
        </div> : <FaceCaptureGuide positions={positions} busy={busy} simulation={!coreSession} guidance={guidance} camera={camera} onCapture={capture} onComplete={finishCapture} completeLabel="Accept capture and continue" />}
        {error && <div className="form-error" role="alert">{error}<button className="error-action" type="button" onClick={restartCapture}>Start a fresh session</button></div>}
      </section>}

      {step === 4 && <form onSubmit={submitPin}><h1>Create your payment PIN</h1><p className="form-intro">This six-digit PIN is the second factor for kiosk payments and protected wallet actions.</p>
        <div className="pin-privacy-note"><span aria-hidden="true">••••••</span><p><strong>Your face identifies. Your PIN authorises.</strong>SFG will never display or send your PIN back to you.</p></div>
        <SecretField label="Six-digit PIN" autoComplete="new-password" inputMode="numeric" maxLength={6} digitsOnly value={pin} onChange={setPin} />
        <SecretField label="Confirm PIN" autoComplete="new-password" inputMode="numeric" maxLength={6} digitsOnly value={pinConfirm} onChange={setPinConfirm} />
        <div className="requirements-grid" aria-label="PIN requirements"><span className={pin.length === 6 ? "valid" : ""}>{pin.length === 6 ? "✓" : "○"} Exactly six digits</span><span className={pinSafe ? "valid" : ""}>{pinSafe ? "✓" : "○"} Not a sequence or birth date</span><span className={pin.length > 0 && pin === pinConfirm ? "valid" : ""}>{pin.length > 0 && pin === pinConfirm ? "✓" : "○"} PINs match</span></div>
        <button className="button primary full" disabled={busy || !pinSafe || pin !== pinConfirm}>{busy ? "Securing PIN…" : "Save PIN and review"}</button>
      </form>}

      {step === 5 && !activated && <section className="registration-section"><h1>Review and activate</h1><p className="form-intro">Check the details below. You can update your PIN and face enrolment later from Profile.</p><div className="review-list"><div><span>Name</span><strong>{details.full_name}</strong></div><div><span>IC number</span><strong>******-**-{details.ic.replace(/\D/g, "").slice(-4)}</strong></div><div><span>Face enrolment</span><strong>3 positions accepted</strong></div><div><span>Payment PIN</span><strong>Created and hidden</strong></div><div><span>Account protection</span><strong>Face + PIN</strong></div></div>
        <label className="check-row consent-check"><input type="checkbox" checked={reviewAccepted} onChange={(event) => setReviewAccepted(event.target.checked)} /><span>I confirm these details and acknowledge the prototype privacy notice and account terms.</span></label>
        <button className="button primary full" type="button" onClick={activate} disabled={!reviewAccepted || busy}>{busy ? "Activating account…" : "Activate my SFG account"}</button>
      </section>}
      {step === 5 && activated && <section className="registration-success" role="status"><span aria-hidden="true">✓</span><p className="eyebrow">Registration complete</p><h1>Your account is ready</h1><p>Your face enrolment and PIN setup are complete. Future kiosk payments still require both a successful live-face match and your PIN.</p><button className="button primary" type="button" onClick={() => navigate("/dashboard")}>Go to dashboard</button><Link className="button secondary" to="/profile">Review security settings</Link></section>}
      {error && step !== 3 && <div className="form-error" role="alert">{error}</div>}
    </div></section>
  </main>;
}
