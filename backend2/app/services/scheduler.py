from apscheduler.schedulers.background import BackgroundScheduler
from app.logger import logger

_scheduler = None


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler()

    # Auto-scrape every 24 hours
    try:
        _scheduler.add_job(
            _safe_scrape,
            trigger="interval",
            hours=24,
            id="auto_scrape",
            replace_existing=True,
        )
        logger.info("Scheduler: auto-scrape every 24h")
    except Exception as e:
        logger.warning(f"Could not schedule auto-scrape: {e}")

    # Cache eviction every 30 minutes
    try:
        _scheduler.add_job(
            _evict_caches,
            trigger="interval",
            minutes=30,
            id="cache_eviction",
            replace_existing=True,
        )
        logger.info("Scheduler: cache eviction every 30m")
    except Exception as e:
        logger.warning(f"Could not schedule cache eviction: {e}")

    # BM25 index rebuild every 6 hours (ensures freshness after scrapes)
    try:
        _scheduler.add_job(
            _rebuild_bm25,
            trigger="interval",
            hours=6,
            id="bm25_rebuild",
            replace_existing=True,
        )
        logger.info("Scheduler: BM25 rebuild every 6h")
    except Exception as e:
        logger.warning(f"Could not schedule BM25 rebuild: {e}")

    _scheduler.start()


def _safe_scrape():
    try:
        from app.admin.scraper import scrape_all_sources
        result = scrape_all_sources()
        logger.info(f"Scheduled scrape complete: {result}")
    except Exception as e:
        logger.error(f"Scheduled scrape failed: {e}")


def _evict_caches():
    try:
        from app.chat.cache import evict_all_expired
        evict_all_expired()
    except Exception as e:
        logger.error(f"Cache eviction failed: {e}")


def _rebuild_bm25():
    try:
        from app.chat.hybrid_search import get_bm25_index
        get_bm25_index(force_rebuild=True)
        logger.info("BM25 index rebuilt by scheduler")
    except Exception as e:
        logger.error(f"BM25 rebuild failed: {e}")
