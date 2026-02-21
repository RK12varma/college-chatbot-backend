from apscheduler.schedulers.background import BackgroundScheduler
from app.admin.scraper import scrape_all_sources

scheduler = BackgroundScheduler()

def start_scheduler():
    scheduler.add_job(scrape_all_sources, "interval", hours=6)
    scheduler.start()
    print("Scheduler started.")