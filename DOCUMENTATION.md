# Technical Documentation

## Architecture Overview

The system follows a pipeline architecture with six sequential stages:

```
Scraping → Storage → Candidate ID → Sentiment Analysis → Profiling → Reporting
```

Each stage is a separate module with clean interfaces, making it straightforward to swap out components (e.g., replace VADER with a fine-tuned model) without touching the rest of the pipeline.

### Module Dependency Graph

```
main.py
├── scrapers/
│   ├── base.py          ← abstract interface
│   ├── nairaland.py     ← BeautifulSoup + requests
│   ├── reddit.py        ← PRAW
│   ├── twitter.py       ← Tweepy
│   └── facebook.py      ← Graph API + requests
├── storage/
│   └── database.py      ← SQLite + JSON/CSV export
├── analysis/
│   ├── candidates.py    ← regex + frequency filtering
│   ├── sentiment.py     ← transformers/VADER/TextBlob
│   └── profiler.py      ← aggregation + theme extraction
├── report_generator.py  ← Markdown output
└── utils/
    ├── config.py        ← YAML singleton
    ├── logger.py        ← dual console/file logging
    └── helpers.py       ← retry, delay, text cleaning
```

## Design Decisions

### Why ThreadPoolExecutor over asyncio

The scrapers use `requests`, `PRAW`, and `Tweepy` — all synchronous libraries. Wrapping them in `asyncio` would require `run_in_executor` calls anyway, adding complexity without real benefit. `ThreadPoolExecutor` parallelizes I/O-bound network calls naturally and works with every library out of the box.

SQLite writes are serialized back to the main thread because SQLite's default threading mode doesn't support concurrent writers. The pattern is: threads scrape in parallel → results collected → main thread writes to DB.

### Why regex over spaCy NER for candidate identification

spaCy's `en_core_web_sm` NER model is trained on Western news text and consistently misclassifies Nigerian names — especially hyphenated Yoruba names like "Sanwo-Olu" or honorific-prefixed names like "Alhaji Ganduje." A regex pattern matching 2-3 consecutive capitalized words with optional hyphens/apostrophes proves more reliable for this domain.

The regex approach also avoids a ~50MB model download as a hard dependency. spaCy NER is still available as an optional enhancement in `try_spacy_ner()` for users who want to experiment.

### Three-tier sentiment fallback

Not every deployment environment has GPU support or the disk space for transformer models. The fallback chain ensures the system always works:

1. **Transformers** (`twitter-roberta-base-sentiment`) — best accuracy for social media text, handles Nigerian Pidgin reasonably well since it was trained on ~124M tweets
2. **VADER** — rule-based, no downloads needed, handles punctuation/capitalization emphasis well but struggles with Pidgin and sarcasm
3. **TextBlob** — basic polarity detection, last resort

The active tier is logged on startup so users know which model is running.

### Cross-platform candidate validation

A name appearing on 2+ platforms is a stronger signal of genuine candidacy than one found only on a single forum thread. The scoring formula applies a 1.5x multiplier for cross-platform mentions, combined with election-context co-occurrence scoring. This effectively suppresses noise (journalists, commentators, foreign politicians) while surfacing actual candidates.

## Data Flow

### 1. Scraping

Each scraper implements `BaseScraper.scrape_state(state)` and returns a list of standardized post dicts:

```python
{
    "platform": "nairaland",
    "state": "Lagos",
    "text": "Sanwo-Olu has done well with infrastructure...",
    "author": "a3f2b8c1d4e5",  # SHA-256 hash (first 12 chars)
    "date": "2025-08-15 14:30:00",
    "url": "https://www.nairaland.com/...",
    "likes": 45,
    "shares": 0,
    "keyword_used": "Lagos governorship election"
}
```

Authors are anonymized before the dict is even constructed — raw usernames never reach the database.

### 2. Candidate Identification

The regex pattern `[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?(?:\s+...){1,2}` captures:
- Standard names: "Peter Obi", "Bola Tinubu"
- Hyphenated names: "Sanwo-Olu", "Abdul-Azeez"
- Three-part names: "Babajide Olusola Sanwo-Olu"

A stop-name list prevents false positives from state names ("Cross River"), institutions ("National Assembly"), days/months, and platform names.

### 3. Sentiment Scoring

Scores are normalized to [-1.0, +1.0]:
- Transformers: confidence mapped directly (positive → +score, negative → −score)
- VADER: compound score used directly (already [-1, +1])
- TextBlob: polarity used directly (already [-1, +1])

Each post gets linked to every candidate it mentions, creating a many-to-many relationship in the `sentiment_results` table. Posts mentioning no specific candidate are tagged "General" to preserve overall state sentiment data.

### 4. Profile Building

Profiles aggregate across three database tables:
- **Sentiment summary**: mean score, positive/negative/neutral percentages
- **Platform breakdown**: per-platform score comparison
- **Key themes**: most frequent non-stopword terms in posts about the candidate
- **Demographics**: platform audience distribution, support-base indicators (youth/urban/rural/diaspora), regional references
- **Excerpts**: top 5 strongest-scored positive and negative quotes
- **Engagement**: total likes, shares, average likes per post

## Challenges Faced

### API Access Barriers

Getting live data from all four platforms proved to be a significant practical challenge:

- **Nairaland**: No API exists, so HTML parsing was the only option. This turned out to be an advantage — no credentials needed, and the scraper works immediately. Nairaland served as the primary data source for end-to-end pipeline testing.

- **Reddit**: Requires registering an application at reddit.com/prefs/apps to obtain OAuth credentials (`client_id`, `client_secret`). The app registration also requires a manual review/approval step, which adds a delay before access is granted.

- **Twitter/X**: The free API tier only supports tweet posting — it does **not** include the `search_recent_tweets` endpoint needed for data collection. The Basic tier ($100/month) is the minimum for search access, and even then it's limited to the last 7 days. This is a real cost barrier for a research project.

- **Facebook**: The Graph API removed public post search entirely in v2.11+ (2018, post-Cambridge Analytica). You can only read posts from specific Page IDs, and getting a non-expired access token requires creating a Facebook App and submitting it for review — a process that takes weeks.

**How the pipeline handles this**: Each scraper checks for valid credentials on startup. If credentials are missing or access is denied, it logs a clear warning and returns an empty list. The pipeline continues with whatever platforms are accessible, so even with only Nairaland available, the full analysis chain (candidate identification → sentiment → profiling → report) runs end-to-end. This graceful degradation is by design — the system produces useful results regardless of how many platforms are reachable.

The sample output included in this repository was produced using data collected from the platforms that were accessible during development. The `seed_demo_data.py` script is also provided to demonstrate the full pipeline with representative sample data when no API keys are available.

### Platform-Specific Technical Challenges

#### Nairaland
- **No API**: Full HTML parsing required. The search URL format (`/search/{query}/0/0/0/{page}`) was determined by inspecting browser requests.
- **Inconsistent HTML structure**: Post bodies use `div.narrow`, but author links and date spans are in parent `<td>` or `<table>` elements — requiring upward DOM traversal.
- **Date formats**: Nairaland uses multiple date formats ("Jan 01, 2025", relative dates like "2 hours ago"). The date parser tries 7 formats.

#### Twitter/X
- **Rate limits**: Tweepy's `wait_on_rate_limit=True` handles 429 responses automatically by sleeping until the rate window resets.
- **Query length**: Twitter API v2 has a 512-character query limit. Long keyword phrases are trimmed automatically.

#### Reddit
- **read_only mode**: `user.me()` raises an exception in read-only mode, but the client still works for public data reads. The `_connect()` method handles this gracefully.
- **Comment pagination**: `replace_more(limit=0)` avoids deep-loading "MoreComments" objects, which would be very slow on popular threads.

#### Facebook
- **No keyword search**: Unlike the other scrapers which search by keyword, Facebook requires fetching all posts from specific pages and filtering locally. This fundamentally changes the scraping strategy.
- **Token expiration**: Facebook access tokens expire frequently, requiring periodic renewal through the developer portal.

## Assumptions

1. **Public data only**: All scraped content is from public forums, public tweets, and public Facebook pages. No private groups, DMs, or protected accounts are accessed.

2. **English-dominant text**: The transformer model handles standard English and some Pidgin. Pure Hausa, Yoruba, or Igbo text will get sentiment scores but accuracy is lower.

3. **Name patterns**: Candidate identification assumes names follow standard English capitalization. Names written entirely in lowercase or UPPERCASE will be missed.

4. **Mention = relevance**: If a candidate's name appears in a post, the post's sentiment is attributed to that candidate. This is a simplification — a post could mention a candidate neutrally while expressing sentiment about something else.

5. **API credentials**: Twitter, Reddit, and Facebook scrapers require valid API credentials. Without them, those platforms are skipped and analysis proceeds with whatever data is available (e.g., Nairaland only).

## Scalability Notes

- **Adding states**: Uncomment lines in `config.yaml`. The pipeline automatically handles any number of states.
- **Adding platforms**: Create a new class inheriting `BaseScraper`, implement `scrape_state()`, add it to the scraper list in `main.py`.
- **Batch processing**: Sentiment analysis processes posts in batches of 32 for transformer efficiency. This is configurable in `analyze_sentiment()`.
- **Database**: SQLite handles hundreds of thousands of posts without issues. For production scale (millions of posts), swap to PostgreSQL — the query interface is standard SQL, so migration is straightforward.

## Testing Approach

The system was tested with Lagos and Kano as target states. Key verification points:

- All 13 modules import cleanly with no circular dependencies
- Scrapers handle missing API credentials gracefully (log warning, return empty list)
- Sentiment analysis falls through tiers correctly when libraries are missing
- Report generates valid Markdown with correct table formatting
- SQLite database maintains referential integrity between posts and sentiment_results
- JSON/CSV exports produce parseable output files
