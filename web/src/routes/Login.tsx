import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../app/AuthContext";
import { services } from "../services";

export function Login() {
  const [ic, setIc] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const auth = useAuth();
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError("");
    try { await services.auth.login(ic, password); setPassword(""); auth.setAuthenticated(true); navigate("/dashboard"); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to log in."); }
    finally { setBusy(false); }
  };
  return <main className="auth-page">
    <aside className="auth-brand-panel">
      <div className="brand light"><span className="brand-mark white">SFG</span><span>Sarawak Facial Gateway</span></div>
      <div><p className="eyebrow light-text">Citizen access</p><h2>Your family wallet, ready when you are.</h2><p>Use the IC number registered to your main account. Your password stays private and is never stored by the browser.</p></div>
      <p className="panel-note">Face identification is used only during enrolment and at the external merchant kiosk.</p>
    </aside>
    <section className="auth-form-panel">
      <form className="auth-form" onSubmit={submit}>
        <Link className="back-link" to="/platform">Back to platform</Link>
        <p className="eyebrow">Welcome back</p><h1>Log in</h1><p className="form-intro">Enter your registered IC number and password.</p>
        {services.mode === "mock" && <div className="simulation-banner" role="status">Simulation mode: any valid 12-digit IC and non-empty password will continue.</div>}
        {services.mode === "supabase" && <div className="simulation-banner" role="status">Secure login is connected to Supabase. IC numbers are unverified prototype identifiers.</div>}
        <label>IC number<input inputMode="numeric" autoComplete="username" placeholder="000000-00-0000" value={ic} onChange={(e) => setIc(e.target.value)} required /></label>
        <label>Password<div className="password-field"><input type={show ? "text" : "password"} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /><button type="button" onClick={() => setShow((value) => !value)}>{show ? "Hide" : "Show"}</button></div></label>
        {error && <div className="form-error" role="alert">{error}</div>}
        <button className="button primary full" disabled={busy}>{busy ? "Logging in…" : "Log in"}</button>
        <div className="form-links"><button type="button" className="link-button" title="Future scope">Forgot password</button><Link to="/register">Create an account</Link></div>
      </form>
    </section>
  </main>;
}
