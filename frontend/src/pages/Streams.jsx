import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { motion } from "framer-motion";
import { Plus, Trash2, Banknote, X, Pencil } from "lucide-react";

const CATEGORIES = [
  ["affiliate", "Affiliate"],
  ["dividends", "Dividends"],
  ["rentals", "Rentals"],
  ["digital_products", "Digital Products"],
  ["crypto_staking", "Crypto Staking"],
  ["print_on_demand", "Print-on-Demand"],
  ["royalties", "Royalties"],
  ["interest", "Interest"],
  ["ads", "Ads"],
  ["other", "Other"],
];

const fmt2 = (n) => "$" + Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function Streams() {
  const [streams, setStreams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ name: "", category: "affiliate", initial_investment: 0, monthly_estimate: 0, notes: "" });
  const [logTarget, setLogTarget] = useState(null);
  const [logForm, setLogForm] = useState({ amount: "", note: "" });

  const load = () => {
    setLoading(true);
    api.get("/streams").then(r => setStreams(r.data)).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const openCreate = () => {
    setEditingId(null);
    setForm({ name: "", category: "affiliate", initial_investment: 0, monthly_estimate: 0, notes: "" });
    setShowForm(true);
  };

  const openEdit = (s) => {
    setEditingId(s.id);
    setForm({
      name: s.name,
      category: s.category,
      initial_investment: s.initial_investment ?? 0,
      monthly_estimate: s.monthly_estimate ?? 0,
      notes: s.notes || "",
    });
    setShowForm(true);
  };

  const saveStream = async (e) => {
    e.preventDefault();
    const payload = {
      ...form,
      initial_investment: Number(form.initial_investment),
      monthly_estimate: Number(form.monthly_estimate),
    };
    if (editingId) {
      await api.patch(`/streams/${editingId}`, payload);
    } else {
      await api.post("/streams", payload);
    }
    setShowForm(false);
    setEditingId(null);
    setForm({ name: "", category: "affiliate", initial_investment: 0, monthly_estimate: 0, notes: "" });
    load();
  };

  const del = async (id) => {
    if (!window.confirm("Delete this stream and all its entries?")) return;
    await api.delete(`/streams/${id}`);
    load();
  };

  const logIncome = async (e) => {
    e.preventDefault();
    await api.post(`/streams/${logTarget.id}/entries`, { amount: Number(logForm.amount), note: logForm.note });
    setLogTarget(null);
    setLogForm({ amount: "", note: "" });
    load();
  };

  return (
    <div className="p-6 sm:p-10 max-w-6xl" data-testid="streams-page">
      <div className="flex items-end justify-between mb-10 flex-wrap gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-[#00D084] mb-2">Your portfolio</div>
          <h1 className="font-serif text-4xl sm:text-5xl tracking-tighter">Income streams</h1>
        </div>
        <button onClick={openCreate} className="btn-primary" data-testid="open-add-stream-btn">
          <Plus size={16} /> Add stream
        </button>
      </div>

      {loading ? (
        <div className="text-[#A3B3AA]">Loading…</div>
      ) : streams.length === 0 ? (
        <div className="card p-12 text-center" data-testid="streams-empty">
          <div className="font-serif text-3xl mb-2">No streams yet</div>
          <div className="text-[#A3B3AA] mb-6">Add your first passive income source to start tracking.</div>
          <button onClick={openCreate} className="btn-primary" data-testid="empty-add-stream-btn">
            <Plus size={16} /> Create first stream
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {streams.map((s, i) => (
            <motion.div
              key={s.id}
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="card p-6"
              data-testid={`stream-card-${s.id}`}
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <span className="chip">{CATEGORIES.find(c => c[0] === s.category)?.[1] || s.category}</span>
                  <h3 className="font-sans text-xl font-semibold mt-3">{s.name}</h3>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => openEdit(s)} className="text-[#A3B3AA] hover:text-[#00D084]" data-testid={`edit-stream-${s.id}`}>
                    <Pencil size={16} />
                  </button>
                  <button onClick={() => del(s.id)} className="text-[#A3B3AA] hover:text-[#EF4444]" data-testid={`delete-stream-${s.id}`}>
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
              <div className="mt-2">
                <div className="text-xs uppercase tracking-[0.15em] text-[#A3B3AA]">Total earned</div>
                <div className="number-hero text-4xl mt-1">{fmt2(s.total_earned)}</div>
              </div>
              <div className="grid grid-cols-2 gap-3 mt-4 text-sm">
                <div>
                  <div className="text-xs text-[#A3B3AA]">Invested</div>
                  <div className="text-[#F4F0E6]">{fmt2(s.initial_investment)}</div>
                </div>
                <div>
                  <div className="text-xs text-[#A3B3AA]">Est. monthly</div>
                  <div className="text-[#F4F0E6]">{fmt2(s.monthly_estimate)}</div>
                </div>
              </div>
              {s.notes && <p className="text-sm text-[#A3B3AA] mt-4 line-clamp-2">{s.notes}</p>}
              <button onClick={() => setLogTarget(s)} className="btn-secondary w-full justify-center mt-5" data-testid={`log-income-${s.id}`}>
                <Banknote size={16} /> Log income
              </button>
            </motion.div>
          ))}
        </div>
      )}

      {/* Add/Edit Stream Modal */}
      {showForm && (
        <div className="fixed inset-0 z-30 bg-black/70 grid place-items-center p-4" onClick={() => { setShowForm(false); setEditingId(null); }}>
          <form
            onSubmit={saveStream}
            onClick={(e) => e.stopPropagation()}
            className="card p-8 w-full max-w-lg"
            data-testid="add-stream-form"
          >
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-serif text-3xl tracking-tighter">{editingId ? "Edit stream" : "New stream"}</h2>
              <button type="button" onClick={() => { setShowForm(false); setEditingId(null); }} className="text-[#A3B3AA] hover:text-[#F4F0E6]" data-testid="close-add-stream-btn"><X size={20} /></button>
            </div>

            <label className="label">Name</label>
            <input className="input mb-4" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required data-testid="stream-name-input" />

            <label className="label">Category</label>
            <select className="input mb-4" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} data-testid="stream-category-select">
              {CATEGORIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Initial investment ($)</label>
                <input className="input" type="number" step="0.01" value={form.initial_investment} onChange={e => setForm({ ...form, initial_investment: e.target.value })} data-testid="stream-investment-input" />
              </div>
              <div>
                <label className="label">Est. monthly ($)</label>
                <input className="input" type="number" step="0.01" value={form.monthly_estimate} onChange={e => setForm({ ...form, monthly_estimate: e.target.value })} data-testid="stream-estimate-input" />
              </div>
            </div>

            <label className="label mt-4">Notes</label>
            <textarea className="input mb-6" rows={3} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} data-testid="stream-notes-input" />

            <button className="btn-primary w-full justify-center" data-testid="submit-stream-btn">{editingId ? "Save changes" : "Create stream"}</button>
          </form>
        </div>
      )}

      {/* Log income modal */}
      {logTarget && (
        <div className="fixed inset-0 z-30 bg-black/70 grid place-items-center p-4" onClick={() => setLogTarget(null)}>
          <form
            onSubmit={logIncome}
            onClick={(e) => e.stopPropagation()}
            className="card p-8 w-full max-w-md"
            data-testid="log-income-form"
          >
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-serif text-3xl tracking-tighter">Log income</h2>
              <button type="button" onClick={() => setLogTarget(null)} className="text-[#A3B3AA] hover:text-[#F4F0E6]" data-testid="close-log-form-btn"><X size={20} /></button>
            </div>
            <div className="text-sm text-[#A3B3AA] mb-4">Stream: <span className="text-[#F4F0E6]">{logTarget.name}</span></div>

            <label className="label">Amount ($)</label>
            <input className="input mb-4" type="number" step="0.01" value={logForm.amount} onChange={e => setLogForm({ ...logForm, amount: e.target.value })} required data-testid="log-amount-input" />

            <label className="label">Note</label>
            <input className="input mb-6" value={logForm.note} onChange={e => setLogForm({ ...logForm, note: e.target.value })} data-testid="log-note-input" />

            <button className="btn-primary w-full justify-center" data-testid="submit-log-btn">Record</button>
          </form>
        </div>
      )}
    </div>
  );
}
