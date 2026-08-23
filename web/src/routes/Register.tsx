import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { EnrollmentSessionDto } from "../contracts/dto";
import { useAuth } from "../app/AuthContext";
import { services } from "../services";

const stepLabels = ["Account", "Consent", "Face scan", "PIN", "Review"];

export function Register() {
  const [step, setStep] = useState(1);
  const [details, setDetails] = useState({ full_name: "", email: "", ic: "", password: "", password_confirm: "" });
  const [session, setSession] = useState<EnrollmentSessionDto | null>(null);
  const [positions, setPositions] = useState<string[]>([]);
  const [pin, setPin] = useState(""); const [pinConfirm, setPinConfirm] = useState("");
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const auth = useAuth(); const navigate = useNavigate();
  const execute = async (action: () => Promise<void>) => { setBusy(true); setError(""); try { await action(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to continue."); } finally { setBusy(false); } };
  const account = (event: FormEvent) => { event.preventDefault(); execute(async () => { await services.auth.register(details); auth.setAuthenticated(true); setStep(2); }); };
  const consent = () => execute(async () => { setSession(await services.biometric.startEnrollment()); setStep(3); });
  const capture = (pose: string) => execute(async () => { if (!session) throw new Error("Start a new enrolment session."); const result = await services.biometric.capturePosition(session, pose); if (result.capture_status !== "CAPTURE_READY" || result.liveness_status !== "PAD_LIVE") throw new Error("The simulated capture did not pass. Try again."); setPositions(result.positions_complete); });
  const finishCapture = () => execute(async () => { if (!session || positions.length < 3) throw new Error("Capture front, right, and left positions first."); await services.biometric.completeEnrollment(session.session_id); setStep(4); });
  const submitPin = (event: FormEvent) => { event.preventDefault(); execute(async () => { await services.biometric.setPin(pin, pinConfirm); setPin(""); setPinConfirm(""); setStep(5); }); };
  const activate = () => execute(async () => { await services.biometric.activate(); navigate("/dashboard"); });
  return <main className="auth-page register-page">
    <aside className="auth-brand-panel registration-panel">
      <div className="brand light"><span className="brand-mark white">SFG</span><span>Sarawak Facial Gateway</span></div>
      <div><p className="eyebrow light-text">Create account</p><h2>Set up your wallet in five clear steps.</h2><ol className="step-list">{stepLabels.map((label, index) => <li key={label} className={step === index + 1 ? "active" : step > index + 1 ? "done" : ""}><span>{index + 1}</span>{label}</li>)}</ol></div>
      <p className="panel-note">You can stop at any time. Password, PIN, and camera inputs are cleared when their step ends.</p>
    </aside>
    <section className="auth-form-panel register-form-panel"><div className="auth-form register-form">
      <Link className="back-link" to="/">Exit registration</Link><p className="eyebrow">Step {step} of 5</p>
      {services.mode === "mock" && <div className="simulation-banner">Simulation mode performs no real identity, biometric, banking, or payment check.</div>}
      {step === 1 && <form onSubmit={account}><h1>Your details</h1><p className="form-intro">Your IC number becomes your login identifier.</p><div className="form-grid"><label className="span-2">Full legal name<input value={details.full_name} onChange={(e) => setDetails({ ...details, full_name: e.target.value })} required /></label><label>Email<input type="email" autoComplete="email" value={details.email} onChange={(e) => setDetails({ ...details, email: e.target.value })} required /></label><label>IC number<input inputMode="numeric" placeholder="000000-00-0000" value={details.ic} onChange={(e) => setDetails({ ...details, ic: e.target.value })} required /></label><label>Password<input type="password" autoComplete="new-password" value={details.password} onChange={(e) => setDetails({ ...details, password: e.target.value })} required /></label><label>Confirm password<input type="password" autoComplete="new-password" value={details.password_confirm} onChange={(e) => setDetails({ ...details, password_confirm: e.target.value })} required /></label></div><button className="button primary full" disabled={busy}>Continue</button></form>}
      {step === 2 && <section><h1>Biometric consent</h1><p className="form-intro">A camera image will be processed to create a mathematical face representation for kiosk identification. Raw images are not retained. This is a university prototype, not a government service.</p><div className="notice-card"><strong>Before you continue</strong><p>You may withdraw consent and request deletion. Transaction records may remain anonymized for ledger reconciliation.</p></div><button className="button primary full" onClick={consent} disabled={busy}>I understand and continue</button></section>}
      {step === 3 && <section><h1>Face scan</h1><p className="form-intro">Capture each guided position. The development adapter does not perform a real face match.</p><div className="capture-panel"><div className="face-guide" aria-hidden="true" /><p>{positions.length} of 3 positions ready</p></div><div className="capture-actions">{["front", "right", "left"].map((pose) => <button key={pose} className={`button ${positions.includes(pose) ? "complete" : "secondary"}`} onClick={() => capture(pose)} disabled={busy}>{positions.includes(pose) ? "Captured" : `Capture ${pose}`}</button>)}</div><button className="button primary full" onClick={finishCapture} disabled={busy || positions.length < 3}>Continue to PIN</button></section>}
      {step === 4 && <form onSubmit={submitPin}><h1>Create your PIN</h1><p className="form-intro">Use six digits. Avoid sequences, repeated patterns, and your birth date.</p><label>Six-digit PIN<input className="pin-field" inputMode="numeric" type="password" maxLength={6} value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))} required /></label><label>Confirm PIN<input className="pin-field" inputMode="numeric" type="password" maxLength={6} value={pinConfirm} onChange={(e) => setPinConfirm(e.target.value.replace(/\D/g, ""))} required /></label><button className="button primary full" disabled={busy}>Continue to review</button></form>}
      {step === 5 && <section><h1>Review and finish</h1><div className="review-list"><div><span>Name</span><strong>{details.full_name}</strong></div><div><span>IC number</span><strong>******-**-{details.ic.replace(/\D/g, "").slice(-4)}</strong></div><div><span>Face scan</span><strong>Ready for prototype</strong></div><div><span>PIN</span><strong>Created</strong></div></div><label className="check-row"><input type="checkbox" defaultChecked />I acknowledge the prototype terms and privacy notice placeholders.</label><button className="button primary full" onClick={activate} disabled={busy}>Finish registration</button></section>}
      {error && <div className="form-error" role="alert">{error}</div>}
    </div></section>
  </main>;
}
