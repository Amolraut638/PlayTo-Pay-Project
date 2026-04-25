import React, { useEffect, useMemo, useState, useCallback } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowDownToLine,
  Building2,
  IndianRupee,
  RefreshCcw,
  Send,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  AlertCircle,
  TrendingUp,
  Wifi,
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api/v1";
const POLL_INTERVAL = 2000;

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatMoney(paise) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format((paise || 0) / 100);
}

function formatDate(iso) {
  return new Date(iso).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function StatusBadge({ status }) {
  const config = {
    pending:    { icon: Clock,        cls: "bg-amber-50 text-amber-700 border-amber-200",   label: "Pending" },
    processing: { icon: Loader2,      cls: "bg-blue-50 text-blue-700 border-blue-200",      label: "Processing" },
    completed:  { icon: CheckCircle2, cls: "bg-emerald-50 text-emerald-700 border-emerald-200", label: "Completed" },
    failed:     { icon: XCircle,      cls: "bg-rose-50 text-rose-700 border-rose-200",      label: "Failed" },
  }[status] || { icon: AlertCircle, cls: "bg-zinc-100 text-zinc-600 border-zinc-200", label: status };

  const Icon = config.icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${config.cls}`}>
      <Icon size={11} className={status === "processing" ? "animate-spin" : ""} />
      {config.label}
    </span>
  );
}

function Skeleton({ className }) {
  return <div className={`animate-pulse rounded bg-zinc-100 ${className}`} />;
}

// ─── API ────────────────────────────────────────────────────────────────────

async function apiFetch(path, merchantId, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(merchantId ? { "X-Merchant-Id": merchantId } : {}),
      ...(options.headers || {}),
    },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

// ─── App ────────────────────────────────────────────────────────────────────

function App() {
  const [merchants, setMerchants]     = useState([]);
  const [merchantId, setMerchantId]   = useState(() => localStorage.getItem("merchantId") || "");
  const [dashboard, setDashboard]     = useState(null);
  const [loading, setLoading]         = useState(false);
  const [dashLoading, setDashLoading] = useState(true);
  const [amount, setAmount]           = useState("");
  const [bankAccountId, setBankAccountId] = useState("");
  const [message, setMessage]         = useState(null); // { type: "success"|"error", text }
  const [lastRefresh, setLastRefresh] = useState(null);

  const selectedMerchant = useMemo(
    () => merchants.find((m) => m.id === merchantId),
    [merchants, merchantId]
  );

  const loadDashboard = useCallback(async (showLoader = false) => {
    if (!merchantId) return;
    if (showLoader) setDashLoading(true);
    try {
      const data = await apiFetch("/dashboard", merchantId);
      setDashboard(data);
      setLastRefresh(new Date());
      if (!bankAccountId && data.bank_accounts?.length) {
        setBankAccountId(data.bank_accounts[0].id);
      }
    } catch (e) {
      // silent on background poll
    } finally {
      if (showLoader) setDashLoading(false);
    }
  }, [merchantId, bankAccountId]);

  // Load merchants once
  useEffect(() => {
    fetch(`${API_BASE}/merchants`)
      .then((r) => r.json())
      .then((data) => {
        setMerchants(data);
        if (!merchantId && data.length) {
          setMerchantId(data[0].id);
          localStorage.setItem("merchantId", data[0].id);
        }
      })
      .catch(() => {});
  }, []);

  // Load dashboard + poll
  useEffect(() => {
    if (!merchantId) return;
    localStorage.setItem("merchantId", merchantId);
    loadDashboard(true);
    const iv = setInterval(() => loadDashboard(false), POLL_INTERVAL);
    return () => clearInterval(iv);
  }, [merchantId]);

  async function submitPayout(e) {
    e.preventDefault();
    setLoading(true);
    setMessage(null);
    try {
      const amountPaise = Math.round(Number(amount) * 100);
      if (amountPaise <= 0) throw new Error("Amount must be greater than 0");
      await apiFetch("/payouts", merchantId, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ amount_paise: amountPaise, bank_account_id: bankAccountId }),
      });
      setAmount("");
      setMessage({ type: "success", text: `Payout of ${formatMoney(amountPaise)} created. Funds are held.` });
      await loadDashboard(false);
    } catch (e) {
      setMessage({ type: "error", text: e.message });
    } finally {
      setLoading(false);
    }
  }

  const availablePaise = dashboard?.available_balance_paise ?? 0;
  const heldPaise      = dashboard?.held_balance_paise ?? 0;
  const totalCredits   = dashboard?.recent_ledger_entries
    ?.filter((e) => e.direction === "credit")
    .reduce((s, e) => s + e.amount_paise, 0) ?? 0;

  return (
    <div className="min-h-screen bg-paper font-sans text-ink">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-line bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-lg bg-ink text-white shadow-sm">
              <IndianRupee size={18} />
            </div>
            <div>
              <h1 className="text-base font-semibold leading-tight">Playto Pay</h1>
              <p className="text-xs text-zinc-500">Payout Engine</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {lastRefresh && (
              <span className="hidden items-center gap-1 text-xs text-zinc-400 sm:flex">
                <Wifi size={11} className="text-emerald-500" />
                Live · {lastRefresh.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </span>
            )}
            <select
              className="rounded-lg border border-line bg-white px-3 py-1.5 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ink/20"
              value={merchantId}
              onChange={(e) => { setMerchantId(e.target.value); setDashboard(null); }}
            >
              {merchants.map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:grid lg:grid-cols-[1fr_340px]">
        {/* Left column */}
        <div className="space-y-6">
          {/* Balance cards */}
          <div className="grid gap-4 sm:grid-cols-3">
            <BalanceCard
              title="Available Balance"
              value={dashLoading ? null : formatMoney(availablePaise)}
              sub={dashLoading ? null : `${(availablePaise / 100).toFixed(2)} INR`}
              tone="mint"
              icon={<IndianRupee size={16} />}
            />
            <BalanceCard
              title="Held Balance"
              value={dashLoading ? null : formatMoney(heldPaise)}
              sub="pending + processing"
              icon={<Clock size={16} />}
            />
            <BalanceCard
              title="Total Received"
              value={dashLoading ? null : formatMoney(totalCredits)}
              sub="recent credits"
              icon={<TrendingUp size={16} />}
            />
          </div>

          {/* Payout history */}
          <Panel title="Payout History" icon={<RefreshCcw size={15} />}>
            {dashLoading ? (
              <div className="space-y-3 py-2">
                {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
              </div>
            ) : !dashboard?.payouts?.length ? (
              <EmptyState icon={<Send size={28} />} text="No payouts yet. Create your first payout →" />
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-xs font-medium uppercase tracking-wider text-zinc-400">
                      <th className="py-3 pr-4">Date</th>
                      <th className="py-3 pr-4">Amount</th>
                      <th className="py-3 pr-4">Bank</th>
                      <th className="py-3 pr-4">Attempts</th>
                      <th className="py-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {dashboard.payouts.map((p) => (
                      <tr key={p.id} className="hover:bg-zinc-50/60 transition-colors">
                        <td className="py-3 pr-4 text-xs text-zinc-500">{formatDate(p.created_at)}</td>
                        <td className="py-3 pr-4 font-semibold">{formatMoney(p.amount_paise)}</td>
                        <td className="py-3 pr-4 text-zinc-600">{p.bank_account_label}</td>
                        <td className="py-3 pr-4">
                          <span className="rounded bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-600">
                            {p.attempts}
                          </span>
                        </td>
                        <td className="py-3"><StatusBadge status={p.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          {/* Ledger */}
          <Panel title="Recent Ledger Entries" icon={<ArrowDownToLine size={15} />}>
            {dashLoading ? (
              <div className="space-y-3 py-2">
                {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
              </div>
            ) : !dashboard?.recent_ledger_entries?.length ? (
              <EmptyState icon={<ArrowDownToLine size={28} />} text="No ledger entries yet." />
            ) : (
              <div className="divide-y divide-line">
                {dashboard.recent_ledger_entries.map((entry) => (
                  <div key={entry.id} className="flex items-center justify-between py-2.5">
                    <div>
                      <p className="text-sm font-medium capitalize">
                        {entry.reason.replaceAll("_", " ")}
                      </p>
                      <p className="text-xs text-zinc-400">{entry.reference || entry.payout_id || "—"}</p>
                    </div>
                    <p className={`font-semibold tabular-nums ${entry.direction === "credit" ? "text-emerald-600" : "text-rose-600"}`}>
                      {entry.direction === "credit" ? "+" : "−"}{formatMoney(entry.amount_paise)}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>

        {/* Right column */}
        <aside className="mt-6 space-y-5 lg:mt-0">
          {/* Payout form */}
          <Panel title="Request Payout" icon={<Send size={15} />}>
            <form className="space-y-4" onSubmit={submitPayout}>
              <div>
                <label className="mb-1 block text-sm font-medium">Amount (INR)</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-zinc-400">₹</span>
                  <input
                    className="w-full rounded-lg border border-line py-2 pl-7 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-ink/20"
                    min="1"
                    step="0.01"
                    type="number"
                    placeholder="0.00"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    required
                  />
                </div>
                {amount && Number(amount) > 0 && (
                  <p className="mt-1 text-xs text-zinc-400">
                    = {Math.round(Number(amount) * 100).toLocaleString("en-IN")} paise
                  </p>
                )}
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium">Bank Account</label>
                <select
                  className="w-full rounded-lg border border-line bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ink/20"
                  value={bankAccountId}
                  onChange={(e) => setBankAccountId(e.target.value)}
                  required
                >
                  {(dashboard?.bank_accounts || []).map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.label} ****{a.account_last4}
                    </option>
                  ))}
                </select>
              </div>

              <button
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-ink px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                disabled={loading || !bankAccountId}
                type="submit"
              >
                {loading ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
                {loading ? "Creating payout…" : "Create Payout"}
              </button>

              {message && (
                <div className={`flex items-start gap-2 rounded-lg border px-3 py-2.5 text-sm ${
                  message.type === "success"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                    : "border-rose-200 bg-rose-50 text-rose-800"
                }`}>
                  {message.type === "success"
                    ? <CheckCircle2 size={15} className="mt-0.5 shrink-0" />
                    : <XCircle size={15} className="mt-0.5 shrink-0" />}
                  {message.text}
                </div>
              )}
            </form>
          </Panel>

          {/* Balance summary */}
          {dashboard && (
            <Panel title="Balance Summary" icon={<IndianRupee size={15} />}>
              <div className="space-y-2">
                <SummaryRow label="Available" value={formatMoney(availablePaise)} valueClass="text-emerald-600 font-semibold" />
                <SummaryRow label="Held" value={formatMoney(heldPaise)} valueClass="text-amber-600 font-semibold" />
                <div className="my-2 border-t border-line" />
                <SummaryRow
                  label="Total"
                  value={formatMoney(availablePaise + heldPaise)}
                  valueClass="font-bold"
                />
              </div>
            </Panel>
          )}

          {/* Bank accounts */}
          <Panel title="Bank Accounts" icon={<Building2 size={15} />}>
            {dashLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
              </div>
            ) : (dashboard?.bank_accounts || []).map((a) => (
              <div key={a.id} className="mb-2 last:mb-0 rounded-lg border border-line bg-zinc-50 p-3">
                <p className="text-sm font-semibold">{a.label}</p>
                <p className="text-xs text-zinc-500">****{a.account_last4} · {a.ifsc}</p>
              </div>
            ))}
          </Panel>
        </aside>
      </main>
    </div>
  );
}

// ─── Sub-components ─────────────────────────────────────────────────────────

function BalanceCard({ title, value, sub, tone, icon }) {
  return (
    <div className={`rounded-xl border border-line p-4 shadow-sm ${tone === "mint" ? "bg-mint" : "bg-white"}`}>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">{title}</p>
        <span className="text-zinc-400">{icon}</span>
      </div>
      {value === null ? (
        <Skeleton className="h-7 w-28" />
      ) : (
        <p className="text-2xl font-bold tracking-tight">{value}</p>
      )}
      {sub && value !== null && <p className="mt-1 text-xs text-zinc-400">{sub}</p>}
    </div>
  );
}

function Panel({ title, icon, children }) {
  return (
    <section className="rounded-xl border border-line bg-white p-4 shadow-sm">
      <div className="mb-4 flex items-center gap-2 text-zinc-700">
        {icon}
        <h2 className="text-sm font-semibold">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function SummaryRow({ label, value, valueClass }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-zinc-500">{label}</span>
      <span className={valueClass}>{value}</span>
    </div>
  );
}

function EmptyState({ icon, text }) {
  return (
    <div className="flex flex-col items-center gap-2 py-8 text-zinc-400">
      {icon}
      <p className="text-sm">{text}</p>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);