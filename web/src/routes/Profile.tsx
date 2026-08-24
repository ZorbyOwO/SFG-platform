import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import type { EnrollmentSessionDto } from "../contracts/dto";
import { useAuth } from "../app/AuthContext";
import { FaceCaptureGuide } from "../components/FaceCaptureGuide";
import { CameraPreview, useCameraPreview } from "../components/CameraPreview";
import { SecretField } from "../components/SecretField";
import { services } from "../services";
import { biometricCore, captureGuidance, isAccepted, type BiometricSessionDto } from "../services/biometricCore";

type ProfileData = Awaited<ReturnType<typeof services.profile.getProfile>>;
type SecurityDialog = "password" | "pin" | "face" | null;

const blockedPins = new Set(["000000", "111111", "222222", "333333", "444444", "555555", "666666", "777777", "888888", "999999", "123456", "654321", "121212", "123123"]);
const safePin = (value: string) => /^\d{6}$/.test(value) && !blockedPins.has(value);

export function Profile() {
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [dialog, setDialog] = useState<SecurityDialog>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");
  const [currentPin, setCurrentPin] = useState("");
  const [newPin, setNewPin] = useState("");
  const [newPinConfirm, setNewPinConfirm] = useState("");
  const [faceConsent, setFaceConsent] = useState(false);
  const [faceSession, setFaceSession] = useState<EnrollmentSessionDto | null>(null);
  const [coreSession, setCoreSession] = useState<BiometricSessionDto | null>(null);
  const [facePositions, setFacePositions] = useState<string[]>([]);
  const [faceGuidance, setFaceGuidance] = useState("");
  const [faceComplete, setFaceComplete] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const auth = useAuth();
  const navigate = useNavigate();
  const faceCamera = useCameraPreview();

  const loadProfile = async () => setProfile(await services.profile.getProfile());
  useEffect(() => { void loadProfile().catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load profile.")); }, []);
  useEffect(() => {
    if (!dialog) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy && !(dialog === "face" && faceSession && !faceComplete)) closeDialog();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => { document.body.style.overflow = previousOverflow; window.removeEventListener("keydown", closeOnEscape); };
  }, [dialog, busy, faceSession, faceComplete]);

  const closeDialog = () => {
    faceCamera.stopCamera();
    // An abandoned re-enrolment must leave the existing enrolment untouched.
    if (coreSession && !faceComplete) {
      void services.auth.getAccessToken().then((token) => {
        if (token && coreSession) void biometricCore.cancel(token, coreSession);
      });
    }
    setDialog(null); setError(""); setSuccess("");
    setCurrentPassword(""); setNewPassword(""); setNewPasswordConfirm("");
    setCurrentPin(""); setNewPin(""); setNewPinConfirm("");
    setFaceConsent(false); setFaceSession(null); setCoreSession(null);
    setFacePositions([]); setFaceGuidance(""); setFaceComplete(false);
  };
  const requireToken = async (): Promise<string> => {
    const token = await services.auth.getAccessToken();
    if (!token) throw new Error("Your session expired. Sign in again to continue.");
    return token;
  };
  const openDialog = (next: Exclude<SecurityDialog, null>) => { closeDialog(); setDialog(next); };
  const logout = async () => { await auth.signOut(); navigate("/"); };

  const changePassword = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError(""); setSuccess("");
    try {
      if (newPassword !== newPasswordConfirm) throw new Error("The password confirmation does not match.");
      if (newPassword.length < 8 || !/[A-Z]/.test(newPassword) || !/[a-z]/.test(newPassword) || !/\d/.test(newPassword)) throw new Error("Use at least 8 characters with uppercase, lowercase, and a number.");
      await services.profile.changePassword(currentPassword, newPassword, newPasswordConfirm);
      setCurrentPassword(""); setNewPassword(""); setNewPasswordConfirm(""); setSuccess("Password changed successfully. Use the new password next time you log in.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to change the password."); }
    finally { setBusy(false); }
  };
  const changePin = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError(""); setSuccess("");
    try {
      if (!safePin(newPin)) throw new Error("Choose a less predictable six-digit PIN.");
      if (newPin !== newPinConfirm) throw new Error("The PIN confirmation does not match.");
      if (currentPin === newPin) throw new Error("Your new PIN must be different from the current PIN.");
      await services.profile.changePin(currentPin, newPin, newPinConfirm);
      setCurrentPin(""); setNewPin(""); setNewPinConfirm(""); setSuccess("PIN changed successfully. Your new PIN is ready for protected wallet actions.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to change the PIN."); }
    finally { setBusy(false); }
  };
  const startFace = async () => {
    if (!faceConsent) return;
    setError("");
    const cameraReady = faceCamera.status === "active" || await faceCamera.startCamera();
    if (!cameraReady) return;
    setBusy(true); setError("");
    try {
      setFaceSession(await services.profile.startFaceReenrollment());
      setFacePositions([]);
      setFaceGuidance("");
      const token = await services.auth.getAccessToken();
      setCoreSession(token ? await biometricCore.startSession(token, "reenrol") : null);
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to start face re-enrolment."); }
    finally { setBusy(false); }
  };
  const captureFace = async (pose: string) => {
    if (!faceSession) return;
    if (faceCamera.status !== "active") { setError("Enable the camera preview before recording a position."); return; }
    setBusy(true); setError("");
    try {
      if (coreSession) {
        const frame = await faceCamera.captureFrame();
        if (!frame) throw new Error("The camera frame was not ready. Wait for the preview and try again.");
        const outcome = await biometricCore.capture(await requireToken(), coreSession, pose, frame);
        if (!isAccepted(outcome)) {
          setFaceGuidance(captureGuidance(outcome));
          setFacePositions(outcome.positions_complete);
          return;
        }
        await services.biometric.capturePosition(faceSession, pose);
        setFaceGuidance("");
        setFacePositions(outcome.positions_complete);
        return;
      }
      const result = await services.biometric.capturePosition(faceSession, pose);
      if (result.capture_status !== "CAPTURE_READY" || result.liveness_status !== "PAD_LIVE") throw new Error("This capture did not pass the face and liveness checks. Try again.");
      setFacePositions(result.positions_complete);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to capture this position."); }
    finally { setBusy(false); }
  };
  const completeFace = async () => {
    if (!faceSession) return;
    setBusy(true); setError("");
    try {
      // The replacement generation is swapped in atomically before account state moves.
      if (coreSession) await biometricCore.complete(await requireToken(), coreSession);
      await services.profile.completeFaceReenrollment(faceSession.session_id);
      await loadProfile(); faceCamera.stopCamera(); setCoreSession(null); setFaceComplete(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to complete face re-enrolment."); }
    finally { setBusy(false); }
  };

  return <div className="page-wrap narrow-page">
    <header className="page-header compact-header"><div><p className="eyebrow">Account</p><h1>Profile and security</h1><p>Manage the two keys that protect your SFG identity and wallet.</p></div></header>
    {error && !dialog && <div className="form-error" role="alert">{error}</div>}
    <section className="card profile-card">{!profile ? <div className="skeleton-card" /> : <><div className="profile-identity"><div className="member-avatar large">{profile.citizen_display_name.split(" ").map((part) => part[0]).slice(0, 2).join("")}</div><div><h2>{profile.citizen_display_name}</h2><p>{profile.ic_number_masked}</p></div><span className="account-ready-badge">Account ready</span></div><div className="review-list"><div><span>Account status</span><strong>{profile.account_status.replaceAll("_", " ").toUpperCase()}</strong></div><div><span>Face enrolment</span><strong>{profile.enrolment_status.replaceAll("_", " ")}</strong></div><div><span>Payment protection</span><strong>Face match + six-digit PIN</strong></div></div></>}</section>

    <section className="card security-actions"><div className="section-heading"><div><p className="eyebrow">Security centre</p><h2>Your account controls</h2></div></div>
      <div className="security-action-grid">
        <button className="security-action-card" type="button" onClick={() => openDialog("password")}><span className="security-icon" aria-hidden="true">Aa</span><span><strong>Change password</strong><small>Confirm your current password, then create a new one.</small></span><b aria-hidden="true">›</b></button>
        <button className="security-action-card" type="button" onClick={() => openDialog("pin")}><span className="security-icon pin" aria-hidden="true">••</span><span><strong>Change PIN</strong><small>Replace the six-digit PIN used for wallet authorisation.</small></span><b aria-hidden="true">›</b></button>
        <button className="security-action-card" type="button" onClick={() => openDialog("face")}><span className="security-icon face" aria-hidden="true">◎</span><span><strong>Re-enrol face</strong><small>Replace the current face template using the three-position guide.</small></span><b aria-hidden="true">›</b></button>
      </div>
      <div className="security-footnote"><strong>Important</strong><p>A successful face match only identifies you. A PIN is still required before an SFG kiosk can approve a payment.</p></div>
      <button className="button secondary full" type="button" onClick={logout}>Log out</button>
    </section>

    {dialog && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy && !(dialog === "face" && faceSession && !faceComplete)) closeDialog(); }}>
      <section className={`modal-card security-modal ${dialog === "face" ? "face-security-modal" : ""}`} role="dialog" aria-modal="true" aria-labelledby="security-modal-title">
        <div className="topup-modal-header"><div><p className="eyebrow">Account security</p><h2 id="security-modal-title">{dialog === "password" ? "Change password" : dialog === "pin" ? "Change payment PIN" : "Re-enrol your face"}</h2></div><button className="modal-close" type="button" onClick={closeDialog} disabled={busy || (dialog === "face" && Boolean(faceSession) && !faceComplete)} aria-label="Close security dialog">×</button></div>

        {dialog === "password" && <form className="security-form" onSubmit={changePassword}>
          <p>Confirm the password you use to log in, then choose a strong replacement.</p>
          {services.mode === "mock" && <div className="simulation-banner">Use the password created in this simulation, or <strong>Password1</strong> for the default mock login.</div>}
          <SecretField label="Current password" autoComplete="current-password" value={currentPassword} onChange={setCurrentPassword} />
          <SecretField label="New password" autoComplete="new-password" value={newPassword} onChange={setNewPassword} />
          <SecretField label="Confirm new password" autoComplete="new-password" value={newPasswordConfirm} onChange={setNewPasswordConfirm} />
          <div className="requirements-grid"><span className={newPassword.length >= 8 ? "valid" : ""}>{newPassword.length >= 8 ? "✓" : "○"} 8+ characters</span><span className={/[A-Z]/.test(newPassword) && /[a-z]/.test(newPassword) ? "valid" : ""}>{/[A-Z]/.test(newPassword) && /[a-z]/.test(newPassword) ? "✓" : "○"} Upper + lowercase</span><span className={/\d/.test(newPassword) ? "valid" : ""}>{/\d/.test(newPassword) ? "✓" : "○"} Includes a number</span></div>
          {error && <div className="form-error" role="alert">{error}</div>}{success && <div className="form-success" role="status">{success}</div>}
          <button className="button primary full" disabled={busy || Boolean(success)}>{busy ? "Changing password…" : success ? "Password changed" : "Change password"}</button>
        </form>}

        {dialog === "pin" && <form className="security-form" onSubmit={changePin}>
          <p>Your PIN is never displayed in Profile. Confirm the current PIN before replacing it.</p>
          {services.mode === "mock" && <div className="simulation-banner">Use the PIN created during registration, or <strong>246802</strong> for the default mock login.</div>}
          <SecretField label="Current six-digit PIN" autoComplete="current-password" inputMode="numeric" maxLength={6} digitsOnly value={currentPin} onChange={setCurrentPin} />
          <SecretField label="New six-digit PIN" autoComplete="new-password" inputMode="numeric" maxLength={6} digitsOnly value={newPin} onChange={setNewPin} />
          <SecretField label="Confirm new PIN" autoComplete="new-password" inputMode="numeric" maxLength={6} digitsOnly value={newPinConfirm} onChange={setNewPinConfirm} />
          <div className="requirements-grid"><span className={safePin(newPin) ? "valid" : ""}>{safePin(newPin) ? "✓" : "○"} Six unpredictable digits</span><span className={newPin.length > 0 && newPin === newPinConfirm ? "valid" : ""}>{newPin.length > 0 && newPin === newPinConfirm ? "✓" : "○"} New PINs match</span><span className={newPin.length > 0 && newPin !== currentPin ? "valid" : ""}>{newPin.length > 0 && newPin !== currentPin ? "✓" : "○"} Different from current PIN</span></div>
          {error && <div className="form-error" role="alert">{error}</div>}{success && <div className="form-success" role="status">{success}</div>}
          <button className="button primary full" disabled={busy || !safePin(newPin) || newPin !== newPinConfirm || currentPin === newPin || Boolean(success)}>{busy ? "Changing PIN…" : success ? "PIN changed" : "Change PIN"}</button>
        </form>}

        {dialog === "face" && faceComplete && <div className="security-success" role="status"><span aria-hidden="true">✓</span><h3>Face re-enrolment complete</h3><p>Your replacement face enrolment is active. Your existing PIN remains unchanged.</p><button className="button primary full" type="button" onClick={closeDialog}>Done</button></div>}
        {dialog === "face" && !faceSession && !faceComplete && <div className="face-reenrol-intro">
          <CameraPreview camera={faceCamera} compact disabled={!faceConsent} />
          <p>Use this when your appearance has changed significantly or support asks you to replace your enrolment.</p>
          <div className="warning-card"><strong>Your current face template stays active until the replacement is complete.</strong><p>The new capture replaces it in one step once all three positions pass. If you close this window early, nothing changes.</p></div>
          <ul className="readiness-list"><li>About 2 minutes</li><li>Front, right, and left positions</li><li>Your PIN will not change</li><li>Raw frames are not retained</li></ul>
          <label className="check-row consent-check"><input type="checkbox" checked={faceConsent} onChange={(event) => setFaceConsent(event.target.checked)} /><span>I consent to replacing my current SFG face enrolment.</span></label>
          {error && <div className="form-error" role="alert">{error}</div>}
          <button className="button primary full" type="button" onClick={() => void startFace()} disabled={!faceConsent || busy || faceCamera.status === "requesting"}>{busy ? "Starting secure session…" : faceCamera.status === "requesting" ? "Waiting for camera permission…" : "Enable camera and start re-enrolment"}</button>
        </div>}
        {dialog === "face" && faceSession && !faceComplete && <div className="face-reenrol-capture"><div className="capture-session-note"><strong>Secure capture in progress</strong><span>Finish all positions before leaving this screen.</span></div><FaceCaptureGuide positions={facePositions} busy={busy} simulation={!coreSession} guidance={faceGuidance} camera={faceCamera} onCapture={(pose) => void captureFace(pose)} onComplete={() => void completeFace()} completeLabel="Activate replacement face" />{error && <div className="form-error" role="alert">{error}<button className="error-action" type="button" onClick={() => void startFace()}>Start a fresh session</button></div>}</div>}
      </section>
    </div>}
  </div>;
}
