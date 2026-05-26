/**
 * hooks/useMeetings.js — Data fetching hooks for meetings and analysis.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { meetingsAPI, analysisAPI } from "../services/api";

// ── useMeetings — paginated list ───────────────────────────────────────────────
export function useMeetings(params = {}) {
  const [data,    setData]    = useState({ meetings: [], total: 0, pages: 1 });
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data: res } = await meetingsAPI.list(params);
      setData(res);
    } catch (e) {
      setError(e.response?.data?.error || "Failed to load meetings");
    } finally {
      setLoading(false);
    }
  }, [JSON.stringify(params)]);  // eslint-disable-line

  useEffect(() => { fetch(); }, [fetch]);
  return { ...data, loading, error, refetch: fetch };
}

// ── useMeeting — single meeting with analysis ─────────────────────────────────
export function useMeeting(id) {
  const [meeting,    setMeeting]    = useState(null);
  const [transcript, setTranscript] = useState(null);
  const [analysis,   setAnalysis]   = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState(null);

  const fetch = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await meetingsAPI.get(id);
      setMeeting(data.meeting);
      setTranscript(data.transcript);
      setAnalysis(data.analysis);
    } catch (e) {
      setError(e.response?.data?.error || "Meeting not found");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { fetch(); }, [fetch]);
  return { meeting, transcript, analysis, loading, error, refetch: fetch };
}

// ── usePollStatus — polls meeting status until completed/failed ───────────────
export function usePollStatus(id, initialStatus, onComplete) {
  const [status, setStatus] = useState(initialStatus);
  const [stages, setStages] = useState({});
  const timerRef = useRef(null);
  const doneStatuses = ["completed", "failed"];

  const poll = useCallback(async () => {
    if (!id || doneStatuses.includes(status)) return;
    try {
      const { data } = await meetingsAPI.status(id);
      setStatus(data.status);
      setStages(data.processing_stages || {});
      if (doneStatuses.includes(data.status)) {
        onComplete?.(data.status);
      }
    } catch (_) {}
  }, [id, status, onComplete]);

  useEffect(() => {
    if (!id || doneStatuses.includes(status)) return;
    timerRef.current = setInterval(poll, 3000);
    return () => clearInterval(timerRef.current);
  }, [id, status, poll]);

  return { status, stages };
}

// ── useDashboardStats ─────────────────────────────────────────────────────────
export function useDashboardStats() {
  const [stats,   setStats]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  useEffect(() => {
    meetingsAPI.stats()
      .then(({ data }) => setStats(data))
      .catch((e) => setError(e.response?.data?.error || "Failed to load stats"))
      .finally(() => setLoading(false));
  }, []);

  return { stats, loading, error };
}

// ── useSearch ─────────────────────────────────────────────────────────────────
export function useSearch() {
  const [query,   setQuery]   = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef(null);

  const search = useCallback((q) => {
    setQuery(q);
    clearTimeout(debounceRef.current);
    if (!q.trim()) { setResults([]); return; }

    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const { data } = await analysisAPI.search({ q });
        setResults(data.results || []);
      } catch (_) {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 400);
  }, []);

  return { query, results, loading, search };
}
