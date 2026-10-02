import sys
import os
import time
import logging
import redis
from rq import Worker, Queue, Connection
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WORKER] [%(levelname)s]: %(message)s",
)
logger = logging.getLogger("audio_worker_process")

listen = ["audio_jobs"]


def run_worker():
    logger.info(f"Connecting to Redis at {settings.REDIS_URL}...")
    while True:
        try:
            conn = redis.from_url(settings.REDIS_URL)
            conn.ping()
            logger.info("Connected to Redis. Starting RQ Worker listening to 'audio_jobs' queue...")
            with Connection(conn):
                worker = Worker(map(Queue, listen))
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
