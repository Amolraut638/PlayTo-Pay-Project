import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { ArrowDownToLine, Building2, IndianRupee, RefreshCcw, Send } from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api/v1";

function formatMoney(paise) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format((paise || 0) / 100);
}

function statusClass(status) {
  return {
    pending: "bg-amber-100 text-amber-900",
    processing: "bg-blue-100 text-blue-900",
    completed: "bg-emerald-100 text-emerald-900",
    failed: "bg-rose-100 text-rose-900",
  }[status] || "bg-zinc-100 text-zinc-900";
}

function App() {
  const [merchants, setMerchants] = useState([]);
  const [merchantId, setMerchantId] = useState(localStorage.getItem("merchantId") || "");
  const [dashboard, setDashboard] = useState(null);
  const [amount, setAmount] = useState("");
  const [bankAccountId, setBankAccountId] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const selectedMerchant = useMemo(
    () => merchants.find((merchant) => merchant.id === merchantId),
    [merchants, merchantId]
  );

  async function api(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(merchantId ? { "X-Merchant-Id": merchantId } : {}),
        ...(options.headers || {}),
      },
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Request failed");
    }
    return data;
  }

  async function loadMerchants() {
    const data = await fetch(`${API_BASE}/merchants`).then((res) => res.json());
    setMerchants(data);
    if (!merchantId && data.length) {
      setMerchantId(data[0].id);
      localStorage.setItem("merchantId", data[0].id);
    }
  }

  async function loadDashboard() {
    if (!merchantId) return;
    const data = await api("/dashboard");
    setDashboard(data);
    if (!bankAccountId && data.bank_accounts.length) {
      setBankAccountId(data.bank_accounts[0].id);
    }
  }

  useEffect(() => {
    loadMerchants().catch((error) => setMessage(error.message));
  }, []);

  useEffect(() => {
    if (!merchantId) return;
    localStorage.setItem("merchantId", merchantId);
    loadDashboard().catch((error) => setMessage(error.message));
    const interval = setInterval(() => {
      loadDashboard().catch(() => {});
    }, 2000);
    return () => clearInterval(interval);
  }, [merchantId]);

  async function submitPayout(event) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      const amountPaise = Math.round(Number(amount) * 100);
      await api("/payouts", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ amount_paise: amountPaise, bank_account_id: bankAccountId }),
      });
      setAmount("");
      await loadDashboard();
      setMessage("Payout request created and funds are held.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-paper text-ink">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded bg-ink text-white">
              <IndianRupee size={20} />
            </div>
            <div>
              <h1 className="text-xl font-semibold">Playto Pay</h1>
              <p className="text-sm text-zinc-600">Payout engine dashboard</p>
            </div>
          </div>
          <select
            className="min-w-56 rounded border border-line bg-white px-3 py-2 text-sm"
            value={merchantId}
            onChange={(event) => setMerchantId(event.target.value)}
          >
            {merchants.map((merchant) => (
              <option key={merchant.id} value={merchant.id}>
                {merchant.name}
              </option>
            ))}
          </select>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl gap-5 px-4 py-6 sm:px-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-5">
          <div className="grid gap-4 md:grid-cols-3">
            <Metric title="Available" value={formatMoney(dashboard?.available_balance_paise)} tone="mint" />
            <Metric title="Held" value={formatMoney(dashboard?.held_balance_paise)} />
            <Metric title="Merchant" value={selectedMerchant?.name || "Loading"} compact />
          </div>

          <Panel title="Payout History" icon={<RefreshCcw size={17} />}>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-zinc-500">
                  <tr>
                    <th className="py-3 pr-3">Created</th>
                    <th className="py-3 pr-3">Amount</th>
                    <th className="py-3 pr-3">Bank</th>
                    <th className="py-3 pr-3">Attempts</th>
                    <th className="py-3 pr-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(dashboard?.payouts || []).map((payout) => (
                    <tr key={payout.id} className="border-b border-line last:border-0">
                      <td className="py-3 pr-3 text-zinc-600">
                        {new Date(payout.created_at).toLocaleString()}
                      </td>
                      <td className="py-3 pr-3 font-medium">{formatMoney(payout.amount_paise)}</td>
                      <td className="py-3 pr-3">{payout.bank_account_label}</td>
                      <td className="py-3 pr-3">{payout.attempts}</td>
                      <td className="py-3 pr-3">
                        <span className={`rounded px-2 py-1 text-xs font-medium ${statusClass(payout.status)}`}>
                          {payout.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {!dashboard?.payouts?.length && (
                    <tr>
                      <td className="py-6 text-zinc-500" colSpan="5">
                        No payouts yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel title="Recent Ledger" icon={<ArrowDownToLine size={17} />}>
            <div className="grid gap-2">
              {(dashboard?.recent_ledger_entries || []).map((entry) => (
                <div key={entry.id} className="flex items-center justify-between border-b border-line py-2 last:border-0">
                  <div>
                    <p className="text-sm font-medium">{entry.reason.replaceAll("_", " ")}</p>
                    <p className="text-xs text-zinc-500">{entry.reference || entry.payout_id}</p>
                  </div>
                  <p className={entry.direction === "credit" ? "text-emerald-700" : "text-rose-700"}>
                    {entry.direction === "credit" ? "+" : "-"}
                    {formatMoney(entry.amount_paise)}
                  </p>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <aside className="space-y-5">
          <Panel title="Request Payout" icon={<Send size={17} />}>
            <form className="space-y-4" onSubmit={submitPayout}>
              <label className="block text-sm font-medium">
                Amount in INR
                <input
                  className="mt-1 w-full rounded border border-line px-3 py-2"
                  min="1"
                  step="0.01"
                  type="number"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                  required
                />
              </label>
              <label className="block text-sm font-medium">
                Bank account
                <select
                  className="mt-1 w-full rounded border border-line bg-white px-3 py-2"
                  value={bankAccountId}
                  onChange={(event) => setBankAccountId(event.target.value)}
                  required
                >
                  {(dashboard?.bank_accounts || []).map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.label} ****{account.account_last4}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="flex w-full items-center justify-center gap-2 rounded bg-ink px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
                disabled={loading}
                type="submit"
              >
                <Send size={16} />
                {loading ? "Creating" : "Create payout"}
              </button>
              {message && <p className="rounded border border-line bg-white px-3 py-2 text-sm">{message}</p>}
            </form>
          </Panel>

          <Panel title="Bank Accounts" icon={<Building2 size={17} />}>
            <div className="space-y-2">
              {(dashboard?.bank_accounts || []).map((account) => (
                <div key={account.id} className="rounded border border-line bg-white p-3">
                  <p className="font-medium">{account.label}</p>
                  <p className="text-sm text-zinc-600">
                    ****{account.account_last4} · {account.ifsc}
                  </p>
                </div>
              ))}
            </div>
          </Panel>
        </aside>
      </section>
    </main>
  );
}

function Metric({ title, value, tone, compact }) {
  return (
    <div className={`rounded border border-line p-4 ${tone === "mint" ? "bg-mint" : "bg-white"}`}>
      <p className="text-sm text-zinc-600">{title}</p>
      <p className={`mt-2 font-semibold ${compact ? "text-lg" : "text-2xl"}`}>{value}</p>
    </div>
  );
}

function Panel({ title, icon, children }) {
  return (
    <section className="rounded border border-line bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        {icon}
        <h2 className="font-semibold">{title}</h2>
      </div>
      {children}
    </section>
  );
}

createRoot(document.getElementById("root")).render(<App />);
