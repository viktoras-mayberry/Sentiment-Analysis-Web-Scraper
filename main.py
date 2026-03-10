"""
Pipeline orchestrator. Runs scraping, candidate identification, sentiment
analysis, profile building, data export, and report generation.

Supports sequential and parallel (ThreadPoolExecutor) scraping modes.
"""

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.config import config
from utils.logger import get_logger

logger = get_logger(__name__)


def parse_args():
    """Parse command-line arguments for optional overrides."""
    parser = argparse.ArgumentParser(
        description="Web Scraper for Nigerian Election Sentiment Analysis"
    )
    parser.add_argument(
        "--states",
        nargs="+",
        help="Override states to scrape (e.g., --states Lagos Kano)",
    )
    parser.add_argument(
        "--skip-scraping",
        action="store_true",
        help="Skip scraping and run analysis on existing data",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run scrapers in parallel using threads (faster but uses more resources)",
    )
    return parser.parse_args()


def _scrape_single(scraper, state):
    """Thread worker: run one scraper for one state and return results."""
    try:
        posts = scraper.scrape_state(state)
        return (scraper.platform_name, state, posts or [])
    except Exception as e:
        logger.error(f"{scraper.platform_name} failed for {state}: {e}", exc_info=True)
        return (scraper.platform_name, state, [])


def run_scrapers(states, parallel=False):
    """Run all enabled scrapers for each state (sequential or parallel)."""
    from scrapers.nairaland import NairalandScraper
    from scrapers.reddit import RedditScraper
    from scrapers.twitter import TwitterScraper
    from scrapers.facebook import FacebookScraper
    from storage.database import Database

    db = Database()
    all_scrapers = [
        NairalandScraper(),
        RedditScraper(),
        TwitterScraper(),
        FacebookScraper(),
    ]

    # Only use scrapers that are enabled in config
    active_scrapers = [s for s in all_scrapers if s.is_enabled()]
    if not active_scrapers:
        logger.warning("No platforms are enabled in config.yaml!")
        return

    logger.info(f"Active platforms: {[s.platform_name for s in active_scrapers]}")
    logger.info(f"Mode: {'parallel' if parallel else 'sequential'}")

    total_posts = 0
    start_time = time.time()

    if parallel:
        for state in states:
            logger.info(f"--- Scraping data for {state} State (parallel) ---")

            with ThreadPoolExecutor(max_workers=len(active_scrapers)) as executor:
                futures = {
                    executor.submit(_scrape_single, scraper, state): scraper.platform_name
                    for scraper in active_scrapers
                }

                for future in as_completed(futures):
                    platform_name, state_name, posts = future.result()
                    if posts:
                        db.save_posts(posts)
                        total_posts += len(posts)
                        logger.info(f"  {platform_name}: {len(posts)} posts collected")
                    else:
                        logger.info(f"  {platform_name}: No posts found")
    else:
        for state in states:
            logger.info(f"--- Scraping data for {state} State ---")
            for scraper in active_scrapers:
                try:
                    posts = scraper.scrape_state(state)
                    if posts:
                        db.save_posts(posts)
                        total_posts += len(posts)
                        logger.info(f"  {scraper.platform_name}: {len(posts)} posts collected")
                    else:
                        logger.info(f"  {scraper.platform_name}: No posts found")
                except Exception as e:
                    logger.error(
                        f"  {scraper.platform_name} failed for {state}: {e}",
                        exc_info=True,
                    )

    elapsed = round(time.time() - start_time, 1)
    logger.info(f"Total posts collected: {total_posts} (in {elapsed}s)")
    db.close()


def run_analysis():
    """Run candidate ID, sentiment analysis, profiling, and data export."""
    from analysis.candidates import identify_candidates
    from analysis.sentiment import analyze_sentiment
    from analysis.profiler import build_profiles
    from storage.database import Database

    db = Database()

    logger.info("--- Identifying candidates ---")
    candidates = identify_candidates(db)

    logger.info("--- Running sentiment analysis ---")
    analyze_sentiment(db)

    logger.info("--- Building candidate profiles ---")
    profiles = build_profiles(db, candidates)

    logger.info("--- Exporting data ---")
    if config.storage.get("export_json", True):
        db.export_to_json()
    if config.storage.get("export_csv", True):
        db.export_to_csv()
    db.export_sentiment_to_json()

    db.close()
    return profiles


def generate_reports(profiles):
    """Generate output reports (Markdown summary)."""
    from report_generator import generate_report

    logger.info("--- Generating reports ---")
    generate_report(profiles)


def main():
    """Entry point: parse args, scrape, analyze, report."""
    args = parse_args()

    states = args.states if args.states else config.states

    logger.info("=" * 60)
    logger.info("Nigerian Election Sentiment Analysis - Starting")
    logger.info(f"States: {states}")
    logger.info(f"Time range: past {config.time_range_months} months")
    logger.info("=" * 60)

    if not args.skip_scraping:
        run_scrapers(states, parallel=args.parallel)
    else:
        logger.info("Skipping scraping (--skip-scraping flag set)")

    profiles = run_analysis()
    generate_reports(profiles)

    logger.info("=" * 60)
    logger.info("Pipeline complete!")
    logger.info("Check output/ directory for results:")
    logger.info("  - output/data/scraped_posts.json")
    logger.info("  - output/data/scraped_posts.csv")
    logger.info("  - output/data/sentiment_results.json")
    logger.info("  - output/data/candidate_profiles.json")
    logger.info("  - output/reports/election_report.md")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
