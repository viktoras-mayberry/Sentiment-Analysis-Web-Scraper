# Nigerian Governorship Election - Sentiment Analysis Web Scraper

A multi-platform web scraping and NLP pipeline that collects public discourse about Nigerian governorship candidates, performs sentiment analysis, and generates comprehensive reports.

## Features

- **Multi-Platform Scraping** - Collects data from Nairaland, Reddit, Twitter/X, and Facebook
- **Dynamic Candidate Discovery** - Identifies candidates from mention frequency (no hardcoded lists)
- **Three-Tier Sentiment Analysis** - HuggingFace Transformers > VADER > TextBlob fallback chain
- **Parallel Processing** - ThreadPoolExecutor for concurrent scraping across platforms
- **Ethical Compliance** - Rate limiting, robots.txt respect, author anonymization (SHA-256)
- **Structured Output** - SQLite database, JSON/CSV exports, and Markdown reports

## Project Structure

```
Web Scrapper/
├── main.py                  # Pipeline orchestrator (entry point)
├── config.yaml              # All configuration (API keys, states, settings)
├── requirements.txt         # Python dependencies
├── report_generator.py      # Markdown report builder
├── scrapers/
│   ├── base.py              # Abstract base scraper class
│   ├── nairaland.py         # Nairaland HTML scraper (BeautifulSoup)
│   ├── reddit.py            # Reddit scraper (PRAW)
│   ├── twitter.py           # Twitter/X scraper (Tweepy API v2)
│   └── facebook.py          # Facebook scraper (Graph API)
├── analysis/
│   ├── candidates.py        # Candidate identification (regex + frequency)
│   ├── sentiment.py         # Sentiment analysis (transformers/VADER/TextBlob)
│   └── profiler.py          # Candidate profile aggregation
├── storage/
│   └── database.py          # SQLite storage + JSON/CSV export
├── utils/
│   ├── config.py            # YAML config loader
│   ├── logger.py            # Logging setup
│   └── helpers.py           # Text cleaning, hashing, date utilities
├── tests/
│   ├── test_helpers.py      # Utility function tests
│   ├── test_candidates.py   # Candidate identification tests
│   ├── test_sentiment.py    # Sentiment analysis tests
│   ├── test_database.py     # Database operations tests
│   └── test_profiler.py     # Profile builder tests
├── seed_demo_data.py        # Demo data seeder for sample output
└── output/
    ├── data/
    │   ├── election_data.db          # SQLite database
    │   ├── scraped_posts.json        # Raw posts export
    │   ├── scraped_posts.csv         # Raw posts CSV
    │   ├── sentiment_results.json    # Sentiment scores
    │   └── candidate_profiles.json   # Aggregated profiles
    └── reports/
        └── election_report.md        # Final Markdown report
```

## Quick Start

### 1. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

pip install -r requirements.txt
```

### 2. Configure API Keys

Edit `config.yaml` and add your credentials:

```yaml
api_keys:
  twitter:
    bearer_token: "YOUR_TWITTER_BEARER_TOKEN"
  reddit:
    client_id: "YOUR_REDDIT_CLIENT_ID"
    client_secret: "YOUR_REDDIT_CLIENT_SECRET"
    user_agent: "NigeriaElectionScraper/1.0"
  facebook:
    access_token: "YOUR_FACEBOOK_ACCESS_TOKEN"
```

> **Note:** Nairaland requires no API key. Platforms with missing/invalid keys will gracefully skip.

### 3. Run the Pipeline

```bash
# Full pipeline (scrape + analyze + report)
python main.py

# Parallel scraping (faster, uses more resources)
python main.py --parallel

# Override states
python main.py --states Lagos Kano Rivers

# Skip scraping, re-run analysis on existing data
python main.py --skip-scraping
```

### 4. Demo Mode (No API Keys Needed)

To see the full pipeline in action with sample data:

```bash
python seed_demo_data.py
```

This seeds realistic sample posts for Lagos and Kano, then runs the analysis pipeline to produce a complete report with candidate profiles, sentiment scores, and all data exports.

### 5. Run Tests

```bash
python -m unittest discover -s tests -v
```

59 tests covering helpers, candidate identification, sentiment analysis, database operations, and profile building.

## Pipeline Overview

```
Scraping → Storage → Candidate ID → Sentiment Analysis → Profiling → Report
```

1. **Scraping** - Each platform scraper collects posts matching election keywords for configured states
2. **Storage** - Posts saved to SQLite with deduplication (URL-based)
3. **Candidate Identification** - Regex extracts capitalized name sequences; frequency + election-context filtering identifies real candidates
4. **Sentiment Analysis** - Each post scored on [-1.0, +1.0] scale using the configured NLP model
5. **Profile Building** - Per-candidate aggregation: overall score, platform breakdown, top excerpts, key themes, engagement metrics
6. **Report Generation** - Markdown report with executive summaries, ranking tables, and detailed profiles

## Scraper Details

| Platform | Method | Auth | Notes |
|----------|--------|------|-------|
| Nairaland | BeautifulSoup HTML parsing | None | Scrapes politics section threads |
| Reddit | PRAW (official API) | OAuth client credentials | Searches r/Nigeria, r/NigeriaNews |
| Twitter/X | Tweepy API v2 | Bearer token | Free tier has limited search |
| Facebook | Graph API (requests) | Access token | Disabled by default (API restrictions) |

All scrapers inherit from `BaseScraper` and implement `scrape_state(state)`. Each enforces:
- Configurable request delays (default 2s)
- Retry logic with exponential backoff
- Author anonymization before storage

## Sentiment Analysis

Three-tier fallback system:

| Tier | Library | Accuracy | Speed | Best For |
|------|---------|----------|-------|----------|
| 1 | HuggingFace Transformers (`twitter-roberta-base`) | High | Slow | Social media text, informal English |
| 2 | VADER | Medium | Fast | Rule-based, punctuation-aware |
| 3 | TextBlob | Basic | Fast | Simple polarity detection |

The system automatically falls back if a library is unavailable.

## Candidate Identification

Candidates are discovered dynamically (not hardcoded):

1. **Regex extraction** - Finds 2-3 consecutive capitalized words (handles hyphenated Nigerian names like "Sanwo-Olu")
2. **Stop-name filtering** - Removes state names, institutions, days/months, platform names
3. **Election-context scoring** - Names must co-occur with election keywords (governor, candidate, APC, PDP, etc.)
4. **Cross-platform bonus** - Names found on 2+ platforms get 1.5x score weight
5. **Top-N selection** - Returns up to 20 candidates per state, ranked by weighted score

## Output Format

### Report (`output/reports/election_report.md`)

Per state:
- Executive summary (candidates found, posts analyzed, platforms)
- Candidate ranking table with sentiment scores
- Detailed profiles: sentiment breakdown, platform comparison, key themes, top excerpts, engagement metrics

### Data Exports

- `scraped_posts.json` / `.csv` - Raw collected posts
- `sentiment_results.json` - Per-post sentiment scores linked to candidates
- `candidate_profiles.json` - Aggregated candidate profiles

## Configuration Reference

Key settings in `config.yaml`:

| Setting | Default | Description |
|---------|---------|-------------|
| `general.time_range_months` | 12 | How far back to scrape |
| `general.max_posts_per_platform` | 500 | Post limit per platform per state |
| `general.request_delay` | 2 | Seconds between requests |
| `sentiment.model` | transformers | NLP model: transformers, vader, textblob |
| `platforms.*.enabled` | varies | Enable/disable each platform |
| `states` | Lagos, Kano | States to analyze |

## Assumptions & Limitations

- Only **public data** is collected; no private accounts or groups
- Author identities are **anonymized** (SHA-256 hashing) before storage
- Sentiment models may misclassify **sarcasm** or culturally-specific expressions
- Twitter API free tier has **limited search** capabilities
- Facebook Graph API has **restricted** public post search since 2018
- Candidate identification may miss names not following standard capitalization patterns
- Nigerian **Pidgin** text is partially supported (transformer model handles it better than VADER/TextBlob)

## Further Reading

See [DOCUMENTATION.md](DOCUMENTATION.md) for in-depth coverage of architecture decisions, data flow, API access challenges, and scalability notes.

## Ethical Considerations

- All scraped data comes from publicly accessible sources
- `robots.txt` compliance is respected where applicable
- Request delays prevent server overload
- No automated logins or credential stuffing
- Author data is anonymized to protect privacy
- The tool is designed for research and analysis purposes only
