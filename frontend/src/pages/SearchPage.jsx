/**
 * pages/SearchPage.jsx — Full-text search across all meetings.
 */
import { useNavigate }   from "react-router-dom";
import { useSearch }     from "../hooks/useMeetings";
import { Search, Loader, FileText, Mic } from "lucide-react";

export function SearchPage() {
  const navigate = useNavigate();
  const { query, results, loading, search } = useSearch();

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="font-display text-3xl text-[var(--text)]">Search</h1>
        <p className="text-[var(--text-2)] text-sm mt-1">Search across transcripts and summaries.</p>
      </div>

      <div className="relative">
        <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-3)]" />
        <input
          className="input-field pl-11 py-3 text-base"
          placeholder="Search meetings, transcripts, summaries…"
          value={query}
          onChange={(e) => search(e.target.value)}
          autoFocus
        />
        {loading && <Loader size={16} className="absolute right-4 top-1/2 -translate-y-1/2 animate-spin text-[var(--brand)]" />}
      </div>

      {query && !loading && results.length === 0 && (
        <div className="text-center py-12 text-[var(--text-3)]">No results found for "{query}"</div>
      )}

      {results.length > 0 && (
        <div className="space-y-2 stagger">
          {results.map((r, i) => (
            <button key={i} onClick={() => navigate(`/meetings/${r.meeting_id}`)}
              className="glass glass-hover rounded-xl p-4 text-left w-full">
              <div className="flex items-center gap-2 mb-1.5">
                {r.match_type === "transcript" ? <Mic size={13} className="text-brand-400" /> : <FileText size={13} className="text-amber-400" />}
                <span className="text-xs font-medium text-[var(--text-3)] capitalize">{r.match_type} match</span>
              </div>
              <p className="text-sm font-semibold text-[var(--text)] mb-1">{r.meeting_title}</p>
              <p className="text-xs text-[var(--text-2)] line-clamp-2">{r.snippet}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default SearchPage;
