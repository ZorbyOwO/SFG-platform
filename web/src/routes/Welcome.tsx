import { Link } from "react-router-dom";

export function Welcome() {
  return <main className="welcome-page">
    <div className="welcome-visual" aria-hidden="true"><div className="gateway-lines" /><div className="welcome-orbit"><span>SFG</span></div></div>
    <section className="welcome-copy">
      <div className="brand compact"><span className="brand-mark">SFG</span><span>Sarawak Facial Gateway</span></div>
      <p className="eyebrow">Citizen wallet prototype</p>
      <h1>One secure place for your family wallet.</h1>
      <p>Register, manage Family Members, review wallet activity, and authorize kiosk payments with face identification plus your PIN.</p>
      <div className="button-row"><Link className="button primary" to="/login">Log in</Link><Link className="button secondary" to="/register">Create account</Link></div>
      <p className="fine-print">University prototype. No government identity check, banking connection, or real-money payment occurs.</p>
    </section>
  </main>;
}
