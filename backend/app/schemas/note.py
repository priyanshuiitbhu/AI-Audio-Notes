from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class NoteUploadResponse(BaseModel):
    id: str
    file_name: str
    status: str
    progress: int
    current_stage: str
    message: str


class NoteStatusResponse(BaseModel):
    id: str
    status: str
    progress: int
    current_stage: str
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None


class NoteListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    file_name: str
    file_size: int
    mime_type: str
    duration_seconds: Optional[float] = None
    status: str
    progress: int
    current_stage: str
    summary_preview: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class NoteDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    file_name: str
    storage_key: str
    file_size: int
    mime_type: str
    duration_seconds: Optional[float] = None
    language_code: str
    status: str
    progress: int
    current_stage: str
    transcript: Optional[str] = None
    summary: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class NoteRetryResponse(BaseModel):
    id: str
    status: str
    message: str


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    storage: str
    gnani_configured: bool
    llm_configured: bool
    timestamp: str
