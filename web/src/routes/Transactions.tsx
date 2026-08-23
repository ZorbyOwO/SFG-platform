import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { mapTransaction } from "../contracts/mappers";
import type { Transaction } from "../models/domain";
import { services } from "../services";

const formatMoney = (amount: number) => new Intl.NumberFormat("en-MY", { style: "currency", currency: "MYR" }).format(amount);

export function Transactions() {
  const [items, setItems] = useState<Transaction[]>([]); const [query, setQuery] = useState(""); const [filter, setFilter] = useState("all"); const [error, setError] = useState("");
  useEffect(() => { services.transactions.listTransactions().then((rows) => setItems(rows.map(mapTransaction))).catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load history.")); }, []);
  const visible = useMemo(() => items.filter((item) => (filter === "all" || item.type === filter) && `${item.title} ${item.reference}`.toLowerCase().includes(query.toLowerCase())), [items, query, filter]);
  return <div className="page-wrap"><header className="page-header compact-header"><div><p className="eyebrow">Wallet records</p><h1>Transaction history</h1><p>Search top-ups, kiosk payments, and Family Member transfers.</p></div></header>{error && <div className="form-error">{error}</div>}<section className="card history-card"><div className="history-tools"><label>Search<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Merchant or reference" /></label><label>Type<select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">All activity</option><option value="KIOSK_PAYMENT">Kiosk payments</option><option value="TOP_UP">Top-ups</option><option value="FAMILY_TRANSFER">Family transfers</option></select></label></div><div className="transaction-list detailed">{visible.length === 0 ? <div className="empty-state"><h2>No matching transactions</h2><p>Change the search or filter and try again.</p></div> : visible.map((item) => <Link to={`/transactions/${item.id}`} key={item.id}><span className={`transaction-mark ${item.direction}`}>{item.direction === "credit" ? "+" : "−"}</span><span className="transaction-copy"><strong>{item.title}</strong><small>{item.reference} · {new Date(item.occurredAt).toLocaleString("en-MY", { dateStyle: "medium", timeStyle: "short" })}</small></span><span className={`status-badge ${item.status.toLowerCase()}`}>{item.status}</span><span className={`transaction-amount ${item.direction}`}>{item.direction === "credit" ? "+" : "−"}{formatMoney(item.amount)}</span></Link>)}</div></section></div>;
}

export function TransactionDetails() {
  const { id = "" } = useParams(); const [item, setItem] = useState<Transaction | null>(null); const [error, setError] = useState("");
  useEffect(() => { services.transactions.getTransaction(id).then((dto) => setItem(mapTransaction(dto))).catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load transaction.")); }, [id]);
  return <div className="page-wrap narrow-page"><Link className="back-link" to="/transactions">Back to history</Link>{error ? <div className="form-error">{error}</div> : !item ? <div className="skeleton-card" /> : <section className="card detail-card"><p className="eyebrow">Transaction details</p><h1>{item.title}</h1><strong className={`detail-amount ${item.direction}`}>{item.direction === "credit" ? "+" : "−"}{formatMoney(item.amount)}</strong><div className="review-list"><div><span>Status</span><strong>{item.status}</strong></div><div><span>Reference</span><strong>{item.reference}</strong></div><div><span>Date and time</span><strong>{new Date(item.occurredAt).toLocaleString("en-MY", { dateStyle: "long", timeStyle: "short" })}</strong></div><div><span>Balance after</span><strong>{formatMoney(item.balanceAfter)}</strong></div></div></section>}</div>;
}
