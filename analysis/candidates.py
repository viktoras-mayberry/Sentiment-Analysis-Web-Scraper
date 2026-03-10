"""
Dynamic candidate identification from scraped data.

Discovers governorship candidates by extracting capitalized name sequences
(regex), filtering by mention frequency and election-context co-occurrence,
and scoring with a cross-platform validation bonus.
"""

import re
from collections import Counter, defaultdict
from utils.logger import get_logger

logger = get_logger(__name__)

# Words that commonly appear near candidate names in political discussions
ELECTION_CONTEXT_WORDS = {
    "governor", "governorship", "candidate", "election", "elect",
    "aspirant", "running", "contest", "campaign", "gubernatorial",
    "apc", "pdp", "lp", "nnpp", "apga",  # Major Nigerian parties
    "party", "ticket", "primary", "nominated", "senator",
    "hon", "honourable", "excellency", "dr", "chief", "engr",
    "prof", "alhaji", "pastor", "barrister",  # Nigerian honorifics
}

# Common words that look like names but aren't candidates
STOP_NAMES = {
    "Nigerian", "Nigeria", "Federal", "Government", "State",
    "National", "Assembly", "President", "Senate", "House",
    "Representatives", "Lagos", "Kano", "Abuja",  # State names
    "The", "This", "That", "Which", "When", "Where", "What",
    "United", "States", "African", "South", "North", "West", "East",
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
    "Saturday", "Sunday",
    "Facebook", "Twitter", "Reddit", "Nairaland", "WhatsApp",
    "Good", "Dear", "Please", "Thank",
}

# Add all 36 states + FCT as stop names
NIGERIAN_STATES = {
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa",
    "Benue", "Borno", "Cross River", "Delta", "Ebonyi", "Edo",
    "Ekiti", "Enugu", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano",
    "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa",
    "Niger", "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers",
    "Sokoto", "Taraba", "Yobe", "Zamfara", "FCT",
}


def identify_candidates(db):
    """Extract and filter candidate names from scraped posts for each state."""
    from utils.config import config

    candidates_by_state = {}

    for state in config.states:
        logger.info(f"Identifying candidates for {state}...")
        posts = db.get_posts_by_state(state)

        if not posts:
            logger.warning(f"No posts found for {state} — skipping")
            candidates_by_state[state] = []
            continue

        # Step 1: Extract all potential names from posts
        name_mentions = _extract_names_from_posts(posts)

        # Step 2: Filter and rank candidates
        candidates = _filter_candidates(name_mentions, posts, min_mentions=2)

        # Step 3: Save to database
        for candidate in candidates:
            db.save_candidate(
                name=candidate["name"],
                state=state,
                mention_count=candidate["count"],
                platforms_found=candidate["platforms"],
            )

        candidates_by_state[state] = candidates
        logger.info(
            f"{state}: Found {len(candidates)} potential candidates"
        )
        for c in candidates[:5]:  # Log top 5
            logger.info(
                f"  - {c['name']}: {c['count']} mentions "
                f"({', '.join(c['platforms'])})"
            )

    return candidates_by_state


def _extract_names_from_posts(posts):
    """Extract 2-3 word capitalized name sequences via regex, tracking platform of origin."""
    name_data = defaultdict(lambda: {"count": 0, "platforms": set(), "contexts": []})

    # Regex for 2-3 consecutive capitalized words (potential names)
    name_pattern = re.compile(r'\b([A-Z][a-z]+(?:[-\'][A-Z]?[a-z]+)?(?:\s+[A-Z][a-z]+(?:[-\'][A-Z]?[a-z]+)?){1,2})\b')

    for post in posts:
        text = post.get("text", "")
        platform = post.get("platform", "unknown")

        if not text:
            continue

        # Find all potential names in this post
        matches = name_pattern.findall(text)

        for name in matches:
            name = name.strip()

            # Skip if it's a stop word / state name / too short
            if _is_stop_name(name):
                continue

            # Skip single-word names that slipped through
            if len(name.split()) < 2:
                continue

            name_data[name]["count"] += 1
            name_data[name]["platforms"].add(platform)

            # Store a few context sentences (up to 3) for verification
            if len(name_data[name]["contexts"]) < 3:
                # Extract a ~100 char window around the name
                idx = text.find(name)
                if idx >= 0:
                    start = max(0, idx - 50)
                    end = min(len(text), idx + len(name) + 50)
                    context = text[start:end].strip()
                    name_data[name]["contexts"].append(context)

    return dict(name_data)


def _is_stop_name(name):
    """Filter out state names, institutions, and common phrases."""
    words = name.split()
    for word in words:
        if word in STOP_NAMES:
            return True

    # Check against state names
    if name in NIGERIAN_STATES:
        return True

    # Check if ALL words are stop words (e.g., "South West")
    if all(w in STOP_NAMES for w in words):
        return True

    return False


def _filter_candidates(name_mentions, posts, min_mentions=2):
    """Apply minimum-mention, election-context, and cross-platform filters."""
    candidates = []

    # Build a quick lookup: for each post, what context words appear?
    post_texts_lower = [p.get("text", "").lower() for p in posts]

    for name, data in name_mentions.items():
        count = data["count"]
        platforms = data["platforms"]

        # Filter 1: Minimum mentions
        if count < min_mentions:
            continue

        # Filter 2: Election context — does this name appear near election words?
        election_context_score = 0
        name_lower = name.lower()

        for post_text in post_texts_lower:
            if name_lower in post_text:
                # Count how many election context words appear in the same post
                context_hits = sum(
                    1 for word in ELECTION_CONTEXT_WORDS
                    if word in post_text
                )
                election_context_score += context_hits

        # Require at least some election context
        if election_context_score == 0:
            continue

        # Filter 3: Score with cross-platform bonus
        platform_bonus = 1.5 if len(platforms) >= 2 else 1.0
        score = count * platform_bonus * (1 + election_context_score / 10)

        candidates.append({
            "name": name,
            "count": count,
            "platforms": sorted(list(platforms)),
            "score": score,
            "election_context_score": election_context_score,
        })

    # Sort by score (highest first)
    candidates.sort(key=lambda c: c["score"], reverse=True)

    # Return top candidates (cap at 20 per state to avoid noise)
    return candidates[:20]


def try_spacy_ner(posts):
    """Optional spaCy NER-based name extraction. Returns {name: count} or empty dict."""
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
    except (ImportError, OSError):
        logger.debug(
            "spaCy not available — using regex-only name extraction"
        )
        return {}

    name_counts = Counter()
    for post in posts:
        text = post.get("text", "")
        if not text or len(text) > 5000:  # Skip very long texts for speed
            continue
        doc = nlp(text)
        for ent in doc.ents:
            if ent.label_ == "PERSON" and len(ent.text.split()) >= 2:
                name_counts[ent.text] += 1

    return dict(name_counts)
