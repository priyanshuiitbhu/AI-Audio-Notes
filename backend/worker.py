import sys
import os
import time
import logging
from urllib.parse import urlsplit
import redis
from rq import Worker
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WORKER] [%(levelname)s]: %(message)s",
)
logger = logging.getLogger("audio_worker_process")

listen = ["audio_jobs"]


def safe_redis_location() -> str:
    try:
        parsed = urlsplit(settings.REDIS_URL)
        database = parsed.path or "/0"
        return f"{parsed.scheme}://{parsed.hostname or 'unknown'}:{parsed.port or 6379}{database}"
    except Exception:
        return "configured Redis service"


def run_worker():
    logger.info(f"Connecting to Redis at {safe_redis_location()}...")
    while True:
        try:
            conn = redis.from_url(settings.REDIS_URL)
            conn.ping()
            logger.info("Connected to Redis. Starting RQ Worker listening to 'audio_jobs' queue...")
            worker = Worker(listen, connection=conn)
            worker.work(with_scheduler=True)
        except redis.exceptions.ConnectionError:
            logger.warning("Could not connect to Redis. Retrying in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Worker stopped by user.")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Worker encountered an unexpected error: {e}. Retrying in 5s...")
            time.sleep(5)


if __name__ == "__main__":
    run_worker()
