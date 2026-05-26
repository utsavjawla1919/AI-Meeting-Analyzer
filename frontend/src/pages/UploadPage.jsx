/**
 * pages/UploadPage.jsx — Drag-and-drop meeting file upload with live progress.
 */

import { useState, useCallback } from "react";
import { useDropzone }  from "react-dropzone";
import { useNavigate }  from "react-router-dom";
import { meetingsAPI }  from "../services/api";
import { usePollStatus } from "../hooks/useMeetings";
import toast from "react-hot-toast";
import { Upload, File, X, CheckCircle, AlertCircle, Loader, Mic, Video } from "lucide-react";

const ACCEPTED = {
  "audio/*": [".mp3",".wav",".m4a",".ogg",".flac",".webm"],
  "video/*": [".mp4",".avi",".mkv",".mov",".webm"],
};

const MAX_MB = 500;

// ── Pipeline stage labels ──────────────────────────────────────────────────────
const STAGE_LABELS = {
  upload:        "Uploading file",
  transcription: "Speech-to-Text (Whisper)",
  nlp:           "NLP processing",
  summarization: "AI summarization",
  sentiment:     "Sentiment analysis",
};

function StageRow({ name, status }) {
  const icons = {
    pending:   <span className="w-4 h-4 rounded-full border-2 border-[var(--border-2)]" />,
    running:   <Loader size={14} className="animate-spin text-[var(--brand)]" />,
    completed: <CheckCircle size={14} className="text-green-400" />,
    failed:    <AlertCircle size={14} className="text-red-400" />,
  };
  return (
    <div className="flex items-center gap-3 py-1.5">
      {icons[status] || icons.pending}
      <span className={`text-sm ${status === "running" ? "text-[var(--text)] font-medium" : status === "completed" ? "text-green-400" : "text-[var(--text-3)]"}`}>
        {STAGE_LABELS[name] || name}
      </span>
      {status === "running" && (
        <div className="flex-1">
          <div className="progress-track">
            <div className="progress-fill w-3/4 animate-pulse" />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Processing status panel (after upload) ─────────────────────────────────────
function ProcessingPanel({ meetingId, initialStatus, onComplete }) {
  const { status, stages } = usePollStatus(meetingId, initialStatus, onComplete);
  const navigate = useNavigate();

  const isDone   = status === "completed";
  const isFailed = status === "failed";

  return (
    <div className="glass rounded-2xl p-6 space-y-4 animate-slide-up">
      <div className="flex items-center gap-3">
        {isDone   ? <CheckCircle size={20} className="text-green-400" /> :
         isFailed ? <AlertCircle size={20} className="text-red-400"   /> :
                    <Loader size={20} className="animate-spin text-[var(--brand)]" />}
        <h3 className="font-semibold text-[var(--text)]">
          {isDone ? "Analysis complete!" : isFailed ? "Analysis failed" : "Processing your meeting…"}
        </h3>
      </div>

      {/* Stage progress */}
      <div className="space-y-0.5 pl-1">
        {Object.entries(stages).map(([name, st]) => (
          <StageRow key={name} name={name} status={st} />
        ))}
      </div>

      {isDone && (
        <button onClick={() => navigate(`/meetings/${meetingId}`)}
          className="btn-brand w-full py-2.5 text-sm mt-2">
          View analysis →
        </button>
      )}
      {isFailed && (
        <p className="text-sm text-red-400">Something went wrong. Try uploading again.</p>
      )}
    </div>
  );
}

// ── Main Upload page ───────────────────────────────────────────────────────────
export default function UploadPage() {
  const navigate = useNavigate();
  const [file,     setFile]     = useState(null);
  const [title,    setTitle]    = useState("");
  const [progress, setProgress] = useState(0);
  const [uploading,setUploading]= useState(false);
  const [meetingId,setMeetingId]= useState(null);
  const [uploadErr,setUploadErr]= useState("");

  const onDrop = useCallback((accepted, rejected) => {
    if (rejected.length) {
      const err = rejected[0]?.errors?.[0]?.message || "File rejected";
      toast.error(err);
      return;
    }
    const f = accepted[0];
    if (f.size > MAX_MB * 1024 * 1024) {
      toast.error(`File exceeds ${MAX_MB} MB limit`);
      return;
    }
    setFile(f);
    setUploadErr("");
    // Auto-fill title from filename
    const base = f.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ");
    setTitle((t) => t || base);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, accept: ACCEPTED, maxFiles: 1, disabled: uploading || !!meetingId,
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file)        { setUploadErr("Please select a file"); return; }
    if (!title.trim()){ setUploadErr("Title is required"); return; }

    const fd = new FormData();
    fd.append("file",  file);
    fd.append("title", title.trim());

    setUploading(true);
    setProgress(0);
    setUploadErr("");

    try {
      const { data } = await meetingsAPI.upload(fd, setProgress);
      setMeetingId(data.meeting._id);
      toast.success("Uploaded! AI pipeline started.");
    } catch (err) {
      const msg = err.response?.data?.error || "Upload failed";
      setUploadErr(msg);
      toast.error(msg);
      setUploading(false);
    }
  };

  const fmt = (bytes) => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const isAudio = file?.type?.startsWith("audio");
  const isVideo = file?.type?.startsWith("video");

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="font-display text-3xl text-[var(--text)]">Upload meeting</h1>
        <p className="text-[var(--text-2)] text-sm mt-1">
          Supports audio and video files up to {MAX_MB} MB.
        </p>
      </div>

      {!meetingId ? (
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Drop zone */}
          <div
            {...getRootProps()}
            className={`
              rounded-2xl border-2 border-dashed p-10 text-center cursor-pointer transition-all duration-200
              ${isDragActive ? "dropzone-active" : "border-[var(--border)] hover:border-[var(--border-2)] hover:bg-white/[0.02]"}
            `}
          >
            <input {...getInputProps()} />

            {file ? (
              <div className="flex items-center gap-4 text-left">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-brand-600/20 flex-shrink-0">
                  {isAudio ? <Mic size={22} className="text-brand-400" /> :
                   isVideo ? <Video size={22} className="text-brand-400" /> :
                             <File size={22} className="text-brand-400" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-[var(--text)] truncate">{file.name}</p>
                  <p className="text-xs text-[var(--text-3)] mt-0.5">{fmt(file.size)} · {file.type}</p>
                </div>
                <button type="button" onClick={(e) => { e.stopPropagation(); setFile(null); setTitle(""); }}
                  className="text-[var(--text-3)] hover:text-red-400 transition-colors flex-shrink-0">
                  <X size={16} />
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="w-14 h-14 rounded-2xl bg-brand-600/15 flex items-center justify-center mx-auto">
                  <Upload size={24} className="text-brand-400" />
                </div>
                <div>
                  <p className="text-[var(--text)] font-semibold">
                    {isDragActive ? "Drop it here!" : "Drag & drop your recording"}
                  </p>
                  <p className="text-sm text-[var(--text-3)] mt-1">or click to browse files</p>
                </div>
                <div className="flex flex-wrap justify-center gap-2">
                  {["MP3","MP4","WAV","M4A","WEBM","OGG","FLAC"].map((ext) => (
                    <span key={ext} className="badge badge-neutral">{ext}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-[var(--text-2)] mb-1.5">Meeting title *</label>
            <input
              type="text"
              className="input-field"
              placeholder="e.g. Q3 Product Review — July 2025"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={120}
            />
          </div>

          {/* Upload progress */}
          {uploading && progress > 0 && (
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs text-[var(--text-3)]">
                <span>Uploading…</span><span>{progress}%</span>
              </div>
              <div className="progress-track">
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
            </div>
          )}

          {uploadErr && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20">
              <AlertCircle size={14} className="text-red-400 flex-shrink-0" />
              <p className="text-sm text-red-400">{uploadErr}</p>
            </div>
          )}

          <button type="submit" disabled={uploading || !file}
            className="btn-brand w-full py-3 text-sm flex items-center justify-center gap-2">
            {uploading
              ? <><Loader size={16} className="animate-spin" /> Uploading…</>
              : <><Upload size={16} /> Start analysis</>}
          </button>
        </form>
      ) : (
        <ProcessingPanel
          meetingId={meetingId}
          initialStatus="pending"
          onComplete={(s) => {
            if (s === "completed") {
              setTimeout(() => navigate(`/meetings/${meetingId}`), 1200);
            }
          }}
        />
      )}

      {/* Info cards */}
      {!meetingId && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            ["🎙️", "Speech-to-Text", "OpenAI Whisper transcribes your audio with timestamps"],
            ["🧠", "AI Analysis",    "Extracts action items, decisions, and key points"],
            ["📊", "Sentiment",      "Analyzes tone across speakers and over time"],
          ].map(([emoji, title, desc]) => (
            <div key={title} className="glass rounded-xl p-4 text-center">
              <p className="text-2xl mb-2">{emoji}</p>
              <p className="text-sm font-semibold text-[var(--text)]">{title}</p>
              <p className="text-xs text-[var(--text-3)] mt-1">{desc}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
