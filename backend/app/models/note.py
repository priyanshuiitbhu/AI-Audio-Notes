import uuid
from datetime import datetime, timezone
import enum
from sqlalchemy import Column, String, Integer, BigInteger, Float, Text, DateTime, Enum as SAEnum
from app.database import Base


class NoteStatus(str, enum.Enum):
    UPLOADING = "UPLOADING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    TRANSCRIBING = "TRANSCRIBING"
    SUMMARIZING = "SUMMARIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def get_utc_now():
    return datetime.now(timezone.utc)


class Note(Base):
    __tablename__ = "notes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    file_name = Column(String(255), nullable=False)
    storage_key = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=False)
    duration_seconds = Column(Float, nullable=True)
    language_code = Column(String(20), default="en-IN", nullable=False)

    status = Column(String(50), default=NoteStatus.QUEUED.value, nullable=False, index=True)
    progress = Column(Integer, default=0, nullable=False)
    current_stage = Column(String(150), default="Queued", nullable=False)

    transcript = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "file_name": self.file_name,
            "storage_key": self.storage_key,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "duration_seconds": self.duration_seconds,
            "language_code": self.language_code,
            "status": self.status,
            "progress": self.progress,
            "current_stage": self.current_stage,
            "transcript": self.transcript,
            "summary": self.summary,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
