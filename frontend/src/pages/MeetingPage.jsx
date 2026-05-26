/**
 * pages/MeetingPage.jsx — Full meeting view: transcript, AI analysis, charts, export.
 */

import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useMeeting } from "../hooks/useMeetings";
import { exportAPI, downloadBlob, analysisAPI } from "../services/api";
import { formatDistanceToNow, format } from "date-fns";
import toast from "react-hot-toast";
import {
  ArrowLeft, Download, RefreshCw, FileText, BarChart2,
  Mic, Loader, CheckCircle, AlertCircle, Clock, Globe,
  ChevronDown, ChevronRight, Copy, Users,
} from "lucide-react";
import SentimentTimelineChart  from "../components/charts/SentimentTimelineChart";
import SentimentDoughnutChart  from "../components/charts/SentimentDoughnutChart";
import SpeakerBarChart         from "../components/charts/SpeakerBarChart";

// ── Tab button ─────────────────────────────────────────────────────────────────
function Tab({ active, onClick, children }) {
  return (
    <button onClick={onClick}
      className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
        active
          ? "bg-brand-600/20 text-brand-300 border border-brand-600/30"
          : "text-[var(--text-3)] hover:text-[var(--text)] hover:bg-white/5"
      }`}>
      {children}
    </button>
  );
}

// ── Sentiment overview card ────────────────────────────────────────────────────
function SentimentCard({ overall }) {
  if (!overall?.label) return null;
  const colorMap = { positive: "text-green-400", negative: "text-red-400", neutral: "text-[var(--text-2)]" };
  const bgMap    = { positive: "bg-green-500/10 border-green-500/20", negative: "bg-red-500/10 border-red-500/20", neutral: "bg-white/5 border-white/10" };
  return (
    <div className={`rounded-xl p-4 border ${bgMap[overall.label] || bgMap.neutral}`}>
      <p className="text-xs text-[var(--text-3)] mb-1">Overall Sentiment</p>
      <p className={`text-lg font-bold font-display capitalize ${colorMap[overall.label]}`}>{overall.label}</p>
      <div className="grid grid-cols-3 gap-2 mt-3">
        {["positive","negative","neutral"].map((k) => (
          <div key={k} className="text-center">
            <p className="text-xs text-[var(--text-3)] capitalize">{k}</p>
            <p className="text-sm font-semibold text-[var(--text)]">{Math.round((overall[k] || 0) * 100)}%</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Action item card ───────────────────────────────────────────────────────────
function ActionItem({ item, idx }) {
  const priorityColor = { high: "badge-negative", medium: "badge-amber", low: "badge-neutral" };
  return (
    <div className="flex gap-3 p-3 rounded-xl glass glass-hover">
      <div className="w-6 h-6 rounded-lg bg-brand-600/20 flex items-center justify-center text-xs font-bold text-brand-400 flex-shrink-0 mt-0.5">
        {idx + 1}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-[var(--text)]">{item.text}</p>
        <div className="flex flex-wrap gap-2 mt-1.5">
          {item.assignee && <span className="badge badge-brand">@{item.assignee}</span>}
          {item.due_date  && <span className="badge badge-neutral">📅 {item.due_date}</span>}
          {item.priority  && <span className={`badge ${priorityColor[item.priority] || "badge-neutral"}`}>{item.priority}</span>}
        </div>
      </div>
    </div>
  );
}

// ── Transcript segment ─────────────────────────────────────────────────────────
function TranscriptSegment({ seg }) {
  const fmtTime = (s) => { const m = Math.floor(s / 60); return `${m}:${String(Math.floor(s % 60)).padStart(2, "0")}`; };
  const colors  = [
    "border-brand-500", "border-emerald-500", "border-amber-500",
    "border-rose-500",  "border-cyan-500",    "border-violet-500",
  ];
  const speakerIdx = parseInt(seg.speaker?.replace(/\D/g, "") || "1") - 1;
  const borderColor = colors[speakerIdx % colors.length];

  return (
    <div className={`transcript-block border-l-2 ${borderColor} group`}>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs font-semibold text-[var(--brand-light)]">{seg.speaker || "Speaker"}</span>
        <span className="text-xs font-mono text-[var(--text-3)]">{fmtTime(seg.start || 0)}</span>
      </div>
      <p className="text-sm text-[var(--text)] leading-relaxed">{seg.text}</p>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────
export default function MeetingPage() {
  const { id }   = useParams();
  const navigate = useNavigate();
  const { meeting, transcript, analysis, loading, error, refetch } = useMeeting(id);
  const [tab,        setTab]        = useState("summary");
  const [exporting,  setExporting]  = useState(false);
  const [retrying,   setRetrying]   = useState(false);
  const [txSearch,   setTxSearch]   = useState("");

  const handleExport = async (type) => {
    setExporting(true);
    try {
      const fn  = type === "full" ? exportAPI.fullPDF : exportAPI.transcriptPDF;
      const { data } = await fn(id);
      const name = `${(meeting?.ai_title || meeting?.title || "meeting").replace(/\s+/g, "_")}_${type}.pdf`;
      downloadBlob(data, name);
      toast.success("PDF downloaded");
    } catch {
      toast.error("Export failed");
    } finally {
      setExporting(false);
    }
  };

  const handleRetry = async () => {
    setRetrying(true);
    try {
      await analysisAPI.retry(id);
      toast.success("Analysis restarted");
      setTimeout(refetch, 2000);
    } catch (e) {
      toast.error(e.response?.data?.error || "Retry failed");
    } finally {
      setRetrying(false);
    }
  };

  const copyTranscript = () => {
    const text = transcript?.full_text || "";
    navigator.clipboard.writeText(text).then(() => toast.success("Transcript copied"));
  };

  if (loading) return (
    <div className="flex items-center justify-center py-24">
      <Loader size={28} className="animate-spin text-[var(--brand)]" />
    </div>
  );

  if (error) return (
    <div className="text-center py-24">
      <AlertCircle size={32} className="text-red-400 mx-auto mb-3" />
      <p className="text-[var(--text)] font-semibold">{error}</p>
      <button onClick={() => navigate(-1)} className="btn-ghost mt-4 px-5 py-2 text-sm">Go back</button>
    </div>
  );

  const filteredSegs = transcript?.segments?.filter((s) =>
    !txSearch || s.text?.toLowerCase().includes(txSearch.toLowerCase())
  ) || [];

  const sentiment = analysis?.sentiment_overall || {};
  const fmtDur = (s) => { if (!s) return "—"; const m = Math.floor(s / 60); return m > 0 ? `${m}m ${s % 60}s` : `${s}s`; };

  return (
    <div className="space-y-6 animate-fade-in">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="flex items-start gap-4">
        <button onClick={() => navigate(-1)} className="btn-ghost p-2 rounded-xl mt-1 flex-shrink-0">
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="font-display text-2xl text-[var(--text)] truncate">
            {meeting?.ai_title || meeting?.title}
          </h1>
          <div className="flex flex-wrap items-center gap-3 mt-1.5">
            {meeting?.created_at && (
              <span className="flex items-center gap-1 text-xs text-[var(--text-3)]">
                <Clock size={11} />
                {format(new Date(meeting.created_at), "MMM d, yyyy")} ·{" "}
                {formatDistanceToNow(new Date(meeting.created_at), { addSuffix: true })}
              </span>
            )}
            {meeting?.duration_seconds && (
              <span className="text-xs text-[var(--text-3)]">⏱ {fmtDur(meeting.duration_seconds)}</span>
            )}
            {meeting?.language && (
              <span className="flex items-center gap-1 text-xs text-[var(--text-3)] uppercase">
                <Globe size={11} /> {meeting.language}
              </span>
            )}
            {sentiment?.label && (
              <span className={`badge ${sentiment.label === "positive" ? "badge-positive" : sentiment.label === "negative" ? "badge-negative" : "badge-neutral"}`}>
                {sentiment.label}
              </span>
            )}
            {analysis?.meeting_score != null && (
              <span className="badge badge-brand">Score: {analysis.meeting_score}/100</span>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {meeting?.status === "failed" && (
            <button onClick={handleRetry} disabled={retrying}
              className="btn-ghost flex items-center gap-1.5 px-3 py-2 text-xs">
              {retrying ? <Loader size={12} className="animate-spin" /> : <RefreshCw size={12} />}
              Retry
            </button>
          )}
          <div className="relative group">
            <button disabled={exporting} className="btn-brand flex items-center gap-1.5 px-4 py-2 text-xs">
              {exporting ? <Loader size={13} className="animate-spin" /> : <Download size={13} />}
              Export PDF
            </button>
            <div className="absolute right-0 top-full mt-1 z-20 hidden group-hover:block w-44 rounded-xl border border-[var(--border)] shadow-card py-1"
              style={{ background: "var(--bg-2)" }}>
              <button onClick={() => handleExport("full")} className="flex items-center gap-2 w-full px-3 py-2 text-xs text-[var(--text-2)] hover:bg-white/5">
                <FileText size={12} /> Full report
              </button>
              <button onClick={() => handleExport("transcript")} className="flex items-center gap-2 w-full px-3 py-2 text-xs text-[var(--text-2)] hover:bg-white/5">
                <Mic size={12} /> Transcript only
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ── Tabs ────────────────────────────────────────────────────────────── */}
      <div className="flex gap-2 flex-wrap">
        {[["summary","Summary"],["transcript","Transcript"],["sentiment","Sentiment"],["actions","Actions"]].map(([k,l]) => (
          <Tab key={k} active={tab === k} onClick={() => setTab(k)}>{l}</Tab>
        ))}
      </div>

      {/* ══════════════════════════════════════════════════════════════════════ */}
      {/* SUMMARY TAB */}
      {/* ══════════════════════════════════════════════════════════════════════ */}
      {tab === "summary" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 stagger">
          <div className="lg:col-span-2 space-y-5">
            {/* AI Summary */}
            <div className="glass rounded-2xl p-6">
              <h3 className="text-sm font-semibold text-[var(--text-2)] mb-3">AI Summary</h3>
              {analysis?.summary
                ? <p className="text-sm text-[var(--text)] leading-relaxed">{analysis.summary}</p>
                : <p className="text-sm text-[var(--text-3)]">Summary not yet available.</p>}
            </div>

            {/* Key points */}
            {analysis?.key_points?.length > 0 && (
              <div className="glass rounded-2xl p-6">
                <h3 className="text-sm font-semibold text-[var(--text-2)] mb-3">Key discussion points</h3>
                <ul className="space-y-2">
                  {analysis.key_points.map((pt, i) => (
                    <li key={i} className="flex gap-2 text-sm text-[var(--text)]">
                      <span className="text-[var(--brand-light)] flex-shrink-0 mt-0.5">◆</span>
                      <span>{pt}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Decisions */}
            {analysis?.decisions?.length > 0 && (
              <div className="glass rounded-2xl p-6">
                <h3 className="text-sm font-semibold text-[var(--text-2)] mb-3">Decisions made</h3>
                <ul className="space-y-2">
                  {analysis.decisions.map((d, i) => (
                    <li key={i} className="flex gap-2 text-sm text-[var(--text)]">
                      <span className="text-green-400 flex-shrink-0 mt-0.5">✓</span>
                      <span>{d.text || d}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Recommendations */}
            {analysis?.recommendations?.length > 0 && (
              <div className="glass rounded-2xl p-6">
                <h3 className="text-sm font-semibold text-[var(--text-2)] mb-3">Smart recommendations</h3>
                <ul className="space-y-2">
                  {analysis.recommendations.map((r, i) => (
                    <li key={i} className="flex gap-2 text-sm text-[var(--text)]">
                      <span className="text-amber-400 flex-shrink-0 mt-0.5">💡</span>
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Right sidebar */}
          <div className="space-y-4">
            <SentimentCard overall={analysis?.sentiment_overall} />

            {/* Keywords */}
            {analysis?.keywords?.length > 0 && (
              <div className="glass rounded-2xl p-4">
                <h3 className="text-xs font-semibold text-[var(--text-2)] mb-3">Top keywords</h3>
                <div className="flex flex-wrap gap-1.5">
                  {analysis.keywords.slice(0, 18).map((k) => (
                    <span key={k.word} className="badge badge-neutral"
                      style={{ fontSize: `${Math.max(10, Math.min(14, 10 + k.score * 30))}px` }}>
                      {k.word}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Topics */}
            {analysis?.topics?.length > 0 && (
              <div className="glass rounded-2xl p-4">
                <h3 className="text-xs font-semibold text-[var(--text-2)] mb-3">Topics detected</h3>
                <div className="space-y-2">
                  {analysis.topics.map((t) => (
                    <div key={t.label}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-[var(--text)]">{t.label}</span>
                        <span className="text-[var(--text-3)]">{Math.round(t.confidence * 100)}%</span>
                      </div>
                      <div className="progress-track">
                        <div className="progress-fill" style={{ width: `${t.confidence * 100}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════ */}
      {/* TRANSCRIPT TAB */}
      {/* ══════════════════════════════════════════════════════════════════════ */}
      {tab === "transcript" && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <input className="input-field py-2 text-sm pl-9"
                placeholder="Search transcript…"
                value={txSearch}
                onChange={(e) => setTxSearch(e.target.value)} />
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-3)] text-xs">🔍</span>
            </div>
            <button onClick={copyTranscript} className="btn-ghost flex items-center gap-1.5 px-4 py-2 text-sm">
              <Copy size={13} /> Copy
            </button>
            <span className="text-xs text-[var(--text-3)]">{transcript?.word_count?.toLocaleString()} words</span>
          </div>

          <div className="glass rounded-2xl p-6 max-h-[600px] overflow-y-auto space-y-0">
            {filteredSegs.length > 0
              ? filteredSegs.map((seg, i) => <TranscriptSegment key={i} seg={seg} />)
              : transcript?.full_text
                ? <p className="text-sm text-[var(--text)] leading-relaxed whitespace-pre-wrap">{transcript.full_text}</p>
                : <p className="text-sm text-[var(--text-3)]">Transcript not yet available.</p>}
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════ */}
      {/* SENTIMENT TAB */}
      {/* ══════════════════════════════════════════════════════════════════════ */}
      {tab === "sentiment" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 stagger">
          <div className="glass rounded-2xl p-5">
            <h3 className="text-sm font-semibold text-[var(--text-2)] mb-4">Sentiment over time</h3>
            <SentimentTimelineChart data={analysis?.sentiment_timeline || []} />
          </div>
          <div className="glass rounded-2xl p-5">
            <h3 className="text-sm font-semibold text-[var(--text-2)] mb-4">Overall distribution</h3>
            <SentimentDoughnutChart
              data={{ positive: analysis?.sentiment_overall?.positive || 0, negative: analysis?.sentiment_overall?.negative || 0, neutral: analysis?.sentiment_overall?.neutral || 0 }}
              labels={["Positive","Negative","Neutral"]}
              colors={["#10b981","#ef4444","#94a3b8"]}
            />
          </div>
          {analysis?.sentiment_by_speaker && Object.keys(analysis.sentiment_by_speaker).length > 0 && (
            <div className="lg:col-span-2 glass rounded-2xl p-5">
              <h3 className="text-sm font-semibold text-[var(--text-2)] mb-4">Sentiment by speaker</h3>
              <SpeakerBarChart data={analysis.sentiment_by_speaker} />
            </div>
          )}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════ */}
      {/* ACTIONS TAB */}
      {/* ══════════════════════════════════════════════════════════════════════ */}
      {tab === "actions" && (
        <div className="space-y-5 stagger">
          <div className="glass rounded-2xl p-6">
            <h3 className="text-sm font-semibold text-[var(--text-2)] mb-4">
              Action items ({analysis?.action_items?.length || 0})
            </h3>
            {analysis?.action_items?.length > 0
              ? <div className="space-y-2">
                  {analysis.action_items.map((item, i) => <ActionItem key={i} item={item} idx={i} />)}
                </div>
              : <p className="text-sm text-[var(--text-3)]">No action items detected.</p>}
          </div>
        </div>
      )}
    </div>
  );
}
