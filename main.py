import argparse
import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
import colorlog
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from agent.graph import build_graph, get_initial_state
from config import Config
from dashboard.app import app


class StreamTee:
    """Mirror stdout prints from nodes into the rotating logger cleanly."""

    def __init__(self, logger: logging.Logger, original_stream):
        self.logger = logger
        self.original_stream = original_stream

    def write(self, message: str):
        self.original_stream.write(message)
        msg = message.strip()
        if msg:
            self.logger.info(msg)

    def flush(self):
        self.original_stream.flush()


def setup_logging() -> logging.Logger:
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger("JobAgent")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    # Daily rotating file handler
    file_handler = TimedRotatingFileHandler(delay=True, 
        "logs/agent.log", when="midnight", interval=1, backupCount=14, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(file_handler)

    # Colorized console handler[cite: 10]
    console_handler = colorlog.StreamHandler()
    console_handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    logger.addHandler(console_handler)
    return logger


def run_pipeline(dry_run: bool = True):
    logger = logging.getLogger("JobAgent")
    logger.info(f"=== Starting Autonomous Job Agent Pipeline (dry_run={dry_run}) ===")
    original_stdout = sys.stdout
    sys.stdout = StreamTee(logger, original_stdout)
    try:
        graph = build_graph()
        graph.invoke(get_initial_state(dry_run=dry_run))
    except Exception as exc:
        logger.error(f"Pipeline execution error: {exc}", exc_info=True)
    finally:
        sys.stdout = original_stdout
    logger.info("=== Pipeline Execution Completed ===")


def main():
    parser = argparse.ArgumentParser(description="Autonomous AI Job Application Agent")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate applications and email sends without live external actions.",
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Execute the pipeline immediately on startup.",
    )
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Run CLI/scheduler only without starting the Flask web server.",
    )
    args = parser.parse_args()

    logger = setup_logging()

    if args.run_now:
        run_pipeline(dry_run=args.dry_run)
        if args.no_dashboard:
            return

    # Configure daily APScheduler in IST[cite: 7, 10]
    tz = pytz.timezone(Config.TIMEZONE)
    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(
        run_pipeline,
        trigger="cron",
        hour=Config.SCHEDULE_HOUR,
        minute=Config.SCHEDULE_MINUTE,
        kwargs={"dry_run": args.dry_run},
        id="daily_job_agent",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"APScheduler active: Scheduled daily at {Config.SCHEDULE_HOUR:02d}:{Config.SCHEDULE_MINUTE:02d} {Config.TIMEZONE} (dry_run={args.dry_run})"
    )

    if not args.no_dashboard:
        logger.info(f"Starting Flask Monitoring Dashboard at http://127.0.0.1:{Config.FLASK_PORT}")
        app.run(host="0.0.0.0", port=Config.FLASK_PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()