import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { mapFamilyMember, mapTransaction, mapWallet } from "../contracts/mappers";
import type { FamilyMember, Transaction, Wallet } from "../models/domain";
import { services } from "../services";
import { Icon } from "../components/Icon";

const formatMoney = (amount: number) => new Intl.NumberFormat("en-MY", { style: "currency", currency: "MYR" }).format(amount);

export function Dashboard() {
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [family, setFamily] = useState<FamilyMember[]>([]);
  const [hidden, setHidden] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const load = async () => {
    try {
      const [walletDto, transactionDtos, familyDtos] = await Promise.all([
        services.wallet.getWallet(), services.transactions.listTransactions(), services.family.listFamilyMembers(),
      ]);
      setWallet(mapWallet(walletDto)); setTransactions(transactionDtos.map(mapTransaction)); setFamily(familyDtos.map(mapFamilyMember));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load dashboard."); }
  };
  useEffect(() => { void load(); }, []);
  const topup = async () => { setBusy(true); setError(""); try { await services.wallet.createTopUp(50, crypto.randomUUID()); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Top-up failed."); } finally { setBusy(false); } };
  return <div className="page-wrap">
    <header className="page-header"><div><p className="eyebrow">Sunday, 23 August</p><h1>Good morning, Aisyah.</h1><p>Here is your family wallet overview.</p></div><Link className="avatar-link" to="/profile" aria-label="Open profile">AR</Link></header>
    {services.mode === "mock" && <div className="simulation-banner wide" role="status">Simulation mode is active. Balances and activity below are demonstration data.</div>}
    {error && <div className="form-error" role="alert">{error}</div>}
    <section className="dashboard-grid">
      <article className="wallet-card"><div className="wallet-card-top"><div><span>Available balance</span><button className="link-button light-link" onClick={() => setHidden((value) => !value)}>{hidden ? "Show" : "Hide"}</button></div><Icon name="wallet" /></div><strong>{hidden ? "MYR ••••••" : wallet ? formatMoney(wallet.availableBalance) : "MYR —"}</strong><button className="button white full" onClick={topup} disabled={busy}>{busy ? "Processing…" : "Top up MYR 50"}</button><p>Simulated funding only. No bank or card is connected.</p></article>
      <article className="card overview-card"><div className="section-heading"><div><p className="eyebrow">Managed profiles</p><h2>Family Members</h2></div><Link to="/family">Manage</Link></div><div className="family-summary">{family.slice(0, 3).map((member) => <div key={member.id}><div className="member-avatar">{member.fullName.split(" ").map((part) => part[0]).slice(0, 2).join("")}</div><div><strong>{member.fullName}</strong><span>{member.relationship} · {formatMoney(member.wallet.availableBalance)}</span></div><Link to="/family" aria-label={`Manage ${member.fullName}`}><Icon name="arrow" /></Link></div>)}</div></article>
      <article className="card activity-card"><div className="section-heading"><div><p className="eyebrow">Latest updates</p><h2>Recent activity</h2></div><Link to="/transactions">View all</Link></div><div className="transaction-list">{transactions.slice(0, 5).map((item) => <Link to={`/transactions/${item.id}`} key={item.id}><span className={`transaction-mark ${item.direction}`} aria-hidden="true">{item.direction === "credit" ? "+" : "−"}</span><span className="transaction-copy"><strong>{item.title}</strong><small>{new Date(item.occurredAt).toLocaleString("en-MY", { dateStyle: "medium", timeStyle: "short" })}</small></span><span className={`transaction-amount ${item.direction}`}>{item.direction === "credit" ? "+" : "−"}{formatMoney(item.amount)}</span></Link>)}</div></article>
    </section>
  </div>;
}
