import React, { useState } from "react";
import { api } from "../lib/api";
import { Copy, FileText, Sparkles, Check } from "lucide-react";

export default function Content() {
  const [form, setForm] = useState({ niche: "", keywords: "", target_audience: "", affiliate_product: "" });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [copied, setCopied] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setResult(null); setLoading(true);
    try {
      const { data } = await api.post("/ai/content", form);
      setResult(data);
    } catch (e2) {
      setErr(e2.response?.data?.detail || "Generation failed");
    } finally { setLoading(false); }
  };

  const copyArticle = () => {
    if (!result) return;
    navigator.clipboard.writeText(result.article_markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="p-6 sm:p-10 max-w-5xl" data-testid="content-page">
      <div className="mb-10">
        <div className="text-xs uppercase tracking-[0.2em] text-[#00D084] mb-2">Content autopilot</div>
        <h1 className="font-serif text-4xl sm:text-5xl tracking-tighter">Affiliate-ready blog posts</h1>
        <p className="text-[#A3B3AA] mt-2 max-w-xl">Describe your niche, we draft a 700-1000 word SEO post with affiliate placeholders.</p>
      </div>

      <form onSubmit={submit} className="card p-6 mb-8" data-testid="content-form">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="label">Niche</label>
            <input className="input" value={form.niche} onChange={e=>setForm({...form, niche: e.target.value})} required placeholder="e.g. home espresso machines" data-testid="content-niche-input" />
          </div>
          <div>
            <label className="label">Target keywords</label>
            <input className="input" value={form.keywords} onChange={e=>setForm({...form, keywords: e.target.value})} required placeholder="best espresso machine under $500" data-testid="content-keywords-input" />
          </div>
          <div>
            <label className="label">Target audience (optional)</label>
            <input className="input" value={form.target_audience} onChange={e=>setForm({...form, target_audience: e.target.value})} placeholder="beginner home baristas" data-testid="content-audience-input" />
          </div>
          <div>
            <label className="label">Affiliate product (optional)</label>
            <input className="input" value={form.affiliate_product} onChange={e=>setForm({...form, affiliate_product: e.target.value})} placeholder="Breville Barista Express" data-testid="content-product-input" />
          </div>
        </div>
        <button className="btn-primary mt-6" disabled={loading} data-testid="content-generate-btn">
          <Sparkles size={16} /> {loading ? "Writing…" : "Generate post"}
        </button>
        {err && <div className="text-[#EF4444] text-sm mt-4" data-testid="content-error">{err}</div>}
      </form>

      {result && (
        <div className="space-y-6" data-testid="content-result">
          <div className="card p-6">
            <div className="text-xs uppercase tracking-[0.15em] text-[#00D084] mb-2">Title</div>
            <h2 className="font-serif text-3xl tracking-tighter mb-4">{result.title}</h2>
            <div className="text-xs uppercase tracking-[0.15em] text-[#00D084] mb-2">Meta description</div>
            <p className="text-sm text-[#A3B3AA] mb-4">{result.meta_description}</p>
            <div className="text-xs uppercase tracking-[0.15em] text-[#00D084] mb-2">Outline</div>
            <ul className="list-disc list-inside text-sm text-[#A3B3AA] space-y-1">
              {result.outline.map((o, i) => <li key={i}>{o}</li>)}
            </ul>
          </div>

          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-sans text-lg font-semibold flex items-center gap-2"><FileText size={16} className="text-[#00D084]" /> Article</h3>
              <button onClick={copyArticle} className="btn-secondary" data-testid="content-copy-btn">
                {copied ? <><Check size={14}/> Copied</> : <><Copy size={14}/> Copy markdown</>}
              </button>
            </div>
            <pre className="whitespace-pre-wrap font-mono text-xs bg-[#04120C] border border-[#173627] rounded-lg p-4 text-[#F4F0E6] overflow-x-auto" data-testid="content-article-text">
{result.article_markdown}
            </pre>
          </div>

          <div className="card p-6">
            <div className="text-xs uppercase tracking-[0.15em] text-[#00D084] mb-3">CTA suggestions</div>
            <ul className="space-y-2">
              {result.cta_suggestions.map((c, i) => <li key={i} className="text-sm text-[#F4F0E6]">→ {c}</li>)}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
