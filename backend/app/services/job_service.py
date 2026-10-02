import logging
import threading
from typing import Optional
import redis
from rq import Queue
from app.config import settings
from app.workers.audio_worker import process_audio_note

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None
_rq_queue: Optional[Queue] = None


def get_redis_client() -> Optional[redis.Redis]:
    global _redis_client
    if _redis_client is None:
        try:
            r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
            r.ping()
            _redis_client = r
            logger.info("Successfully connected to Redis.")
        except Exception as e:
            logger.warning(f"Could not connect to Redis at {settings.REDIS_URL}: {e}")
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


def enqueue_audio_job(note_id: str) -> bool:
    """
    Enqueues an audio processing job.
    Uses Redis + RQ if Redis is available.
    Falls back gracefully to an asynchronous daemon thread if Redis is offline,
    ensuring zero-downtime execution in all environments.
    """
    try:
        queue = get_rq_queue()
        if queue:
            job = queue.enqueue(
                process_audio_note,
                note_id,
                job_timeout="15m",
                result_ttl=86400,
            )
            logger.info(f"[note_id={note_id}] Successfully enqueued job to Redis RQ (Job ID: {job.id})")
            return True
    except Exception as e:
        logger.warning(f"[note_id={note_id}] Redis enqueue failed ({e}), falling back to background thread.")

    # Graceful background thread fallback
    logger.info(f"[note_id={note_id}] Dispatching processing to background thread worker.")
    thread = threading.Thread(
        target=process_audio_note,
        args=(note_id,),
        name=f"worker-{note_id}",
        daemon=True,
    )
    thread.start()
    return True
