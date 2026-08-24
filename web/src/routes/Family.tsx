import { type FormEvent, useEffect, useState } from "react";
import { FamilyEnrollmentModal } from "../components/FamilyEnrollmentModal";
import { mapFamilyMember } from "../contracts/mappers";
import type { FamilyMember } from "../models/domain";
import { services } from "../services";

const EMPTY_FORM = { full_name: "", ic: "", relationship: "" };

const formatMoney = (amount: number) => new Intl.NumberFormat("en-MY", {
  style: "currency",
  currency: "MYR",
}).format(amount);

export function Family() {
  const [items, setItems] = useState<FamilyMember[]>([]);
  const [adding, setAdding] = useState(false);
  const [enrolling, setEnrolling] = useState<FamilyMember | null>(null);
  const [transfer, setTransfer] = useState<FamilyMember | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [amount, setAmount] = useState("");
  const [pin, setPin] = useState("");

  const load = async () => {
    try {
      const rows = await services.family.listFamilyMembers();
      setItems(rows.map(mapFamilyMember));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load Family Members.");
    }
  };

  useEffect(() => { void load(); }, []);

  const add = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const created = await services.family.createFamilyMember({ ...form, idempotency_key: crypto.randomUUID() });
      const member = mapFamilyMember(created);
      setForm(EMPTY_FORM);
      setAdding(false);
      setEnrolling(member);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to add Family Member.");
    } finally {
      setBusy(false);
    }
  };

  const send = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!transfer) return;
    setBusy(true);
    setError("");
    try {
      await services.wallet.transferToFamilyMember(transfer.id, Number(amount), pin, crypto.randomUUID());
      setPin("");
      setAmount("");
      setTransfer(null);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to transfer.");
    } finally {
      setBusy(false);
    }
  };

  return <div className="page-wrap">
    <header className="page-header compact-header">
      <div>
        <p className="eyebrow">Managed profiles</p>
        <h1>Family Members</h1>
        <p>Add assisted profiles, complete their face capture, and transfer funds from your main wallet.</p>
      </div>
      <button className="button primary" onClick={() => { setError(""); setAdding(true); }}>Add Family Member</button>
    </header>

    <div className="simulation-banner wide" role="status">
      Every Family Member must complete front, right, and left face capture before wallet transfers are enabled.
    </div>
    {error && <div className="form-error" role="alert">{error}</div>}

    <div className="member-grid">
      {items.length === 0 ? <div className="card empty-state">
        <h2>No Family Members yet</h2>
        <p>Add a profile, then complete their required face capture.</p>
      </div> : items.map((member) => {
        const enrolled = member.enrolmentStatus === "ENROLMENT_COMPLETED";
        return <article className="card member-card" key={member.id}>
          <div className="member-avatar large">{member.fullName.split(" ").map((part) => part[0]).slice(0, 2).join("")}</div>
          <div>
            <p className="eyebrow">{member.relationship}</p>
            <h2>{member.fullName}</h2>
            <span>{member.icNumberMasked}</span>
          </div>
          <dl>
            <div><dt>Wallet balance</dt><dd>{formatMoney(member.wallet.availableBalance)}</dd></div>
            <div><dt>Face enrolment</dt><dd className={enrolled ? "status-ready" : "status-pending"}>{enrolled ? "Completed" : "Required"}</dd></div>
          </dl>
          {enrolled
            ? <button className="button secondary full" onClick={() => setTransfer(member)}>Transfer money</button>
            : <button className="button primary full" onClick={() => setEnrolling(member)}>Capture face</button>}
        </article>;
      })}
    </div>

    {adding && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) setAdding(false); }}>
      <form className="modal-card" onSubmit={add} role="dialog" aria-modal="true" aria-labelledby="add-family-title">
        <div className="section-heading">
          <div><p className="eyebrow">Step 1 of 2</p><h2 id="add-family-title">Add Family Member</h2></div>
          <button className="link-button" type="button" onClick={() => setAdding(false)} disabled={busy}>Close</button>
        </div>
        <p>First create the assisted profile. Face capture is required in the next step.</p>
        <label>Full legal name<input value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} required /></label>
        <label>IC number<input inputMode="numeric" placeholder="000000-00-0000" value={form.ic} onChange={(event) => setForm({ ...form, ic: event.target.value })} required /></label>
        <label>Relationship<input placeholder="For example, daughter or parent" value={form.relationship} onChange={(event) => setForm({ ...form, relationship: event.target.value })} required /></label>
        <div className="notice-card"><strong>Next: face capture</strong><p>This profile receives no independent login, password, PIN, or direct top-up.</p></div>
        <button className="button primary full" disabled={busy}>{busy ? "Creating…" : "Continue to face capture"}</button>
      </form>
    </div>}

    {enrolling && <FamilyEnrollmentModal
      member={enrolling}
      onClose={() => setEnrolling(null)}
      onComplete={load}
    />}

    {transfer && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) setTransfer(null); }}>
      <form className="modal-card" onSubmit={send} role="dialog" aria-modal="true" aria-labelledby="transfer-family-title">
        <div className="section-heading">
          <div><p className="eyebrow">PIN-authorized transfer</p><h2 id="transfer-family-title">Transfer to {transfer.fullName}</h2></div>
          <button className="link-button" type="button" onClick={() => { setTransfer(null); setPin(""); }} disabled={busy}>Close</button>
        </div>
        <label>Amount in MYR<input inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} required /></label>
        <label>Main account PIN<input type="password" inputMode="numeric" maxLength={6} value={pin} onChange={(event) => setPin(event.target.value.replace(/\D/g, ""))} required /></label>
        <button className="button primary full" disabled={busy}>{busy ? "Processing…" : "Confirm transfer"}</button>
      </form>
    </div>}
  </div>;
}
