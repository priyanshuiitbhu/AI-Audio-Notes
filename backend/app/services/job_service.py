import logging
import threading
from typing import Optional
from urllib.parse import urlsplit
import redis
from rq import Queue, Worker
from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None
_rq_queue: Optional[Queue] = None


def _safe_redis_location() -> str:
    """Return a log-safe Redis location without credentials or query parameters."""
    try:
        parsed = urlsplit(settings.REDIS_URL)
        database = parsed.path or "/0"
        return f"{parsed.scheme}://{parsed.hostname or 'unknown'}:{parsed.port or 6379}{database}"
    except Exception:
        return "configured Redis service"


def get_redis_client() -> Optional[redis.Redis]:
    global _redis_client
    if _redis_client is None:
        try:
            r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
            r.ping()
            _redis_client = r
            logger.info("Successfully connected to Redis.")
        except Exception as e:
            logger.warning(f"Could not connect to Redis at {_safe_redis_location()}: {type(e).__name__}")
            _redis_client = None
    return _redis_client


def get_rq_queue() -> Optional[Queue]:
    global _rq_queue
    r = get_redis_client()
    if r is not None and _rq_queue is None:
        _rq_queue = Queue("audio_jobs", connection=r)
    return _rq_queue


def check_redis_health() -> str:
    try:
        r = get_redis_client()
        if r and r.ping():
            return "connected"
    except Exception:
        pass
    return "disconnected"


def check_worker_health() -> str:
    """Report whether at least one live RQ worker is registered in Redis."""
    try:
        r = get_redis_client()
        if r is None:
            return "disconnected"
        workers = Worker.all(connection=r)
        return f"running ({len(workers)})" if workers else "not_running"
    except Exception:
        return "unknown"


def enqueue_audio_job(note_id: str) -> bool:
    """
    Enqueues an audio processing job.
    Uses Redis + RQ if Redis is available.
    Falls back gracefully to an asynchronous daemon thread if Redis is offline,
    ensuring zero-downtime execution in all environments.
    """
    from app.workers.audio_worker import process_audio_note

    try:
        queue = get_rq_queue()
        if queue:
            job = queue.enqueue(
                process_audio_note,
                note_id,
                job_timeout=settings.RQ_JOB_TIMEOUT_SECONDS,
                result_ttl=86400,
            )
            logger.info(f"[note_id={note_id}] Successfully enqueued job to Redis RQ (Job ID: {job.id})")
            return True
    except Exception as e:
        logger.warning(f"[note_id={note_id}] Redis enqueue failed ({type(e).__name__}).")

    if settings.REQUIRE_REDIS_QUEUE:
        logger.error(f"[note_id={note_id}] Redis/RQ is required but no queue is available.")
        return False

    # Local-development fallback. Production sets REQUIRE_REDIS_QUEUE=true.
    logger.info(f"[note_id={note_id}] Dispatching processing to background thread worker.")
    thread = threading.Thread(
        target=process_audio_note,
        args=(note_id,),
        name=f"worker-{note_id}",
        daemon=True,
    )
    thread.start()
    return True
