import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../components/Icon";
import { mapFamilyMember, mapTransaction, mapWallet } from "../contracts/mappers";
import type { FamilyMember, Transaction, Wallet } from "../models/domain";
import { services } from "../services";

const TOP_UP_OPTIONS = [20, 50, 100, 200, 500] as const;
const MIN_TOP_UP = 1;
const MAX_TOP_UP = 5000;
const CUSTOM_AMOUNT_PATTERN = /^\d+(?:\.\d{1,2})?$/;

const formatMoney = (amount: number) => new Intl.NumberFormat("en-MY", {
  style: "currency",
  currency: "MYR",
}).format(amount);

export function Dashboard() {
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [family, setFamily] = useState<FamilyMember[]>([]);
  const [displayName, setDisplayName] = useState("Citizen");
  const [hidden, setHidden] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [topUpOpen, setTopUpOpen] = useState(false);
  const [selectedTopUp, setSelectedTopUp] = useState<number | null>(20);
  const [customTopUp, setCustomTopUp] = useState("");
  const [topUpError, setTopUpError] = useState("");

  const customAmount = customTopUp.trim();
  const topUpAmount = customAmount ? Number(customAmount) : selectedTopUp;
  const hasValidTopUpAmount = topUpAmount !== null
    && Number.isFinite(topUpAmount)
    && topUpAmount >= MIN_TOP_UP
    && topUpAmount <= MAX_TOP_UP
    && (!customAmount || CUSTOM_AMOUNT_PATTERN.test(customAmount));
  const fundingNotice = services.mode === "supabase"
    ? "This creates a Supabase wallet transaction but does not charge a bank account or card."
    : services.mode === "api"
      ? "This creates a local development wallet transaction but does not charge a bank account or card."
      : "This updates demonstration data only and does not charge a bank account or card.";

  const load = async () => {
    try {
      const [walletDto, transactionDtos, familyDtos, profile] = await Promise.all([
        services.wallet.getWallet(),
        services.transactions.listTransactions(),
        services.family.listFamilyMembers(),
        services.profile.getProfile(),
      ]);
      setWallet(mapWallet(walletDto));
      setTransactions(transactionDtos.map(mapTransaction));
      setFamily(familyDtos.map(mapFamilyMember));
      setDisplayName(profile.citizen_display_name);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load dashboard.");
    }
  };

  useEffect(() => { void load(); }, []);

  useEffect(() => {
    if (!topUpOpen) return;
    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) setTopUpOpen(false);
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [topUpOpen, busy]);

  const openTopUp = () => {
    setSelectedTopUp(20);
    setCustomTopUp("");
    setTopUpError("");
    setTopUpOpen(true);
  };

  const closeTopUp = () => {
    if (!busy) setTopUpOpen(false);
  };

  const submitTopUp = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!hasValidTopUpAmount || topUpAmount === null) {
      setTopUpError("Enter an amount from MYR 1.00 to MYR 5,000.00 using no more than two decimal places.");
      return;
    }

    setBusy(true);
    setError("");
    setTopUpError("");
    try {
      await services.wallet.createTopUp(topUpAmount, crypto.randomUUID());
      await load();
      setTopUpOpen(false);
    } catch (reason) {
      setTopUpError(reason instanceof Error ? reason.message : "Top-up failed.");
    } finally {
      setBusy(false);
    }
  };

  return <div className="page-wrap">
    <header className="page-header">
      <div>
        <p className="eyebrow">{new Intl.DateTimeFormat("en-MY", { weekday: "long", day: "numeric", month: "long" }).format(new Date())}</p>
        <h1>Good morning, {displayName.split(" ")[0]}.</h1>
        <p>Here is your family wallet overview.</p>
      </div>
      <Link className="avatar-link" to="/profile" aria-label="Open profile">
        {displayName.split(" ").map((part) => part[0]).slice(0, 2).join("")}
      </Link>
    </header>
    {services.mode === "mock" && <div className="simulation-banner wide" role="status">Simulation mode is active. Balances and activity below are demonstration data.</div>}
    {services.mode === "supabase" && <div className="simulation-banner wide" role="status">Your account and wallet records below are loaded from Supabase. Top-ups remain simulated funding.</div>}
    {error && <div className="form-error" role="alert">{error}</div>}
    <section className="dashboard-grid">
      <article className="wallet-card">
        <div className="wallet-card-top">
          <div>
            <span>Available balance</span>
            <button className="link-button light-link" onClick={() => setHidden((value) => !value)}>{hidden ? "Show" : "Hide"}</button>
          </div>
          <Icon name="wallet" />
        </div>
        <strong>{hidden ? "MYR ••••••" : wallet ? formatMoney(wallet.availableBalance) : "MYR —"}</strong>
        <button className="button white full" onClick={openTopUp}>Top up</button>
        <p>Simulated funding only. No bank or card is connected.</p>
      </article>
      <article className="card overview-card">
        <div className="section-heading"><div><p className="eyebrow">Managed profiles</p><h2>Family Members</h2></div><Link to="/family">Manage</Link></div>
        <div className="family-summary">{family.slice(0, 3).map((member) => <div key={member.id}><div className="member-avatar">{member.fullName.split(" ").map((part) => part[0]).slice(0, 2).join("")}</div><div><strong>{member.fullName}</strong><span>{member.relationship} · {formatMoney(member.wallet.availableBalance)}</span></div><Link to="/family" aria-label={`Manage ${member.fullName}`}><Icon name="arrow" /></Link></div>)}</div>
      </article>
      <article className="card activity-card">
        <div className="section-heading"><div><p className="eyebrow">Latest updates</p><h2>Recent activity</h2></div><Link to="/transactions">View all</Link></div>
        <div className="transaction-list">{transactions.slice(0, 5).map((item) => <Link to={`/transactions/${item.id}`} key={item.id}><span className={`transaction-mark ${item.direction}`} aria-hidden="true">{item.direction === "credit" ? "+" : "−"}</span><span className="transaction-copy"><strong>{item.title}</strong><small>{new Date(item.occurredAt).toLocaleString("en-MY", { dateStyle: "medium", timeStyle: "short" })}</small></span><span className={`transaction-amount ${item.direction}`}>{item.direction === "credit" ? "+" : "−"}{formatMoney(item.amount)}</span></Link>)}</div>
      </article>
    </section>

    {topUpOpen && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) closeTopUp(); }}>
      <form className="modal-card topup-modal" onSubmit={submitTopUp} role="dialog" aria-modal="true" aria-labelledby="topup-title" noValidate>
        <div className="topup-modal-header">
          <div><p className="eyebrow">Wallet funding</p><h2 id="topup-title">Choose a top-up amount</h2></div>
          <button className="modal-close" type="button" onClick={closeTopUp} aria-label="Close top-up">×</button>
        </div>
        <p>Select a category or insert a custom amount.</p>
        <div className="topup-options" aria-label="Top-up amount categories">
          {TOP_UP_OPTIONS.map((amount) => <button
            className={`topup-option${selectedTopUp === amount && !customAmount ? " selected" : ""}`}
            type="button"
            key={amount}
            aria-pressed={selectedTopUp === amount && !customAmount}
            onClick={() => { setSelectedTopUp(amount); setCustomTopUp(""); setTopUpError(""); }}
          >
            <span>MYR</span>
            <strong>{amount}</strong>
          </button>)}
        </div>
        <div className="topup-divider"><span>or</span></div>
        <label>
          Insert your amount
          <div className="money-input">
            <span>MYR</span>
            <input
              type="number"
              inputMode="decimal"
              min={MIN_TOP_UP}
              max={MAX_TOP_UP}
              step="0.01"
              placeholder="0.00"
              value={customTopUp}
              onChange={(event) => { setCustomTopUp(event.target.value); setSelectedTopUp(null); setTopUpError(""); }}
              aria-describedby="topup-help"
            />
          </div>
        </label>
        <small id="topup-help" className="topup-help">Minimum MYR 1.00 · Maximum MYR 5,000.00</small>
        {topUpError && <div className="form-error topup-error" role="alert">{topUpError}</div>}
        <div className="topup-review" aria-live="polite">
          <div><span>Top-up amount</span><strong>{hasValidTopUpAmount && topUpAmount !== null ? formatMoney(topUpAmount) : "MYR —"}</strong></div>
          <div><span>Balance after top-up</span><strong>{hasValidTopUpAmount && topUpAmount !== null && wallet ? formatMoney(wallet.availableBalance + topUpAmount) : "MYR —"}</strong></div>
        </div>
        <p className="topup-disclaimer">Simulation only. {fundingNotice}</p>
        <button className="button primary full" type="submit" disabled={busy || !hasValidTopUpAmount}>{busy ? "Processing…" : "Confirm top up"}</button>
      </form>
    </div>}
  </div>;
}
