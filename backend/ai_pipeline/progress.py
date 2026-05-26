"""
ai_pipeline/progress.py — Pipeline progress tracker.

Writes granular stage updates directly to MongoDB so the frontend
can poll GET /api/meetings/<id>/status and show a live progress bar.

Stage lifecycle:  pending → running → completed | failed
"""

import logging
import time
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class PipelineProgress:
    """
    Wraps a MongoDB meeting document and provides a clean API for
    updating pipeline stage states and recording timing metrics.

    Usage:
        progress = PipelineProgress(db, meeting_id)
        with progress.stage("transcription"):
            result = whisper.transcribe(audio)
        # stage automatically marked completed (or failed on exception)
    """

    STAGES = ["upload", "transcription", "nlp", "summarization", "sentiment"]

    def __init__(self, db, meeting_id: str):
        self.db         = db
        self.meeting_id = meeting_id
        self._timings: dict = {}

    @contextmanager
    def stage(self, name: str, label: str = None):
        """
        Context manager that:
        - marks the stage as 'running' on entry
        - marks it 'completed' on clean exit
        - marks it 'failed' and re-raises on exception
        Records wall-clock duration in self._timings.
        """
        display = label or name
        logger.info(f"[Pipeline:{self.meeting_id}] ▶ Stage '{display}' started")
        self._set_stage(name, "running")
        t0 = time.monotonic()
        try:
            yield
            elapsed = round(time.monotonic() - t0, 2)
            self._timings[name] = elapsed
            self._set_stage(name, "completed")
            logger.info(f"[Pipeline:{self.meeting_id}] ✓ Stage '{display}' done in {elapsed}s")
        except Exception as exc:
            elapsed = round(time.monotonic() - t0, 2)
            self._timings[name] = elapsed
            self._set_stage(name, "failed")
            logger.error(
                f"[Pipeline:{self.meeting_id}] ✗ Stage '{display}' failed "
                f"after {elapsed}s — {exc}"
            )
            raise

    def set_overall_status(self, status: str, error: str = None):
        """Update the top-level meeting.status field."""
        from models.models import MeetingModel
        MeetingModel.set_status(self.db, self.meeting_id, status, error)

    def update_meeting_field(self, field: str, value):
        """Write an arbitrary field to the meeting document."""
        from bson import ObjectId
        from models.models import utcnow
        self.db.meetings.update_one(
            {"_id": ObjectId(self.meeting_id)},
            {"$set": {field: value, "updated_at": utcnow()}},
        )

    def get_timings(self) -> dict:
        """Return per-stage wall-clock timings (seconds)."""
        return dict(self._timings)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _set_stage(self, stage: str, status: str):
        from models.models import MeetingModel
        MeetingModel.set_stage(self.db, self.meeting_id, stage, status)
