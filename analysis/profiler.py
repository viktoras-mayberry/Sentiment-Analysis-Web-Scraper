"""
Candidate profile builder.

Aggregates sentiment results, post data, and engagement metrics into
per-candidate profiles with platform breakdowns, key themes, demographic
insights, and top excerpts.
"""

import json
from collections import Counter
from utils.config import config
from utils.logger import get_logger

logger = get_logger(__name__)


def build_profiles(db, candidates_by_state):
    """Build and save profiles for all identified candidates across states."""
    all_profiles = {}

    for state in config.states:
        logger.info(f"Building profiles for {state}...")
        candidates = candidates_by_state.get(state, [])

        if not candidates:
            logger.warning(f"No candidates identified for {state}")
            all_profiles[state] = []
            continue

        state_profiles = []
        for candidate in candidates:
            profile = _build_single_profile(db, candidate, state)
            state_profiles.append(profile)

        # Sort by overall sentiment score (most positive first)
        state_profiles.sort(
            key=lambda p: p["sentiment"]["overall_score"], reverse=True
        )

        all_profiles[state] = state_profiles
        logger.info(f"{state}: Built {len(state_profiles)} candidate profiles")

    # Save profiles to JSON for the report generator
    _save_profiles(all_profiles)

    return all_profiles


def _build_single_profile(db, candidate, state):
    """Assemble a single candidate's profile from posts, sentiment, and metadata."""
    name = candidate["name"]
    logger.debug(f"Building profile for {name} ({state})")

    # Get all sentiment results for this candidate
    sentiment_data = db.get_sentiment_for_candidate(name, state)

    # Get all posts mentioning this candidate
    posts = db.get_posts_mentioning(name, state)

    # Build the profile
    profile = {
        "name": name,
        "state": state,
        "mention_count": candidate["count"],
        "platforms_found": candidate["platforms"],
        "sentiment": _calculate_sentiment_summary(sentiment_data),
        "platform_breakdown": _calculate_platform_breakdown(sentiment_data),
        "top_positive_excerpts": _get_top_excerpts(sentiment_data, "positive", 5),
        "top_negative_excerpts": _get_top_excerpts(sentiment_data, "negative", 5),
        "key_themes": _extract_themes(posts, name),
        "demographic_insights": _infer_demographics(posts, name),
        "engagement": _calculate_engagement(posts),
        "post_count": len(posts),
    }

    return profile


def _calculate_sentiment_summary(sentiment_data):
    """Calculate overall score and positive/negative/neutral percentages."""
    if not sentiment_data:
        return {
            "overall_score": 0.0,
            "positive_pct": 0.0,
            "negative_pct": 0.0,
            "neutral_pct": 0.0,
            "total_analyzed": 0,
        }

    total = len(sentiment_data)
    scores = [s["sentiment_score"] for s in sentiment_data]
    labels = [s["sentiment_label"] for s in sentiment_data]

    positive_count = labels.count("positive")
    negative_count = labels.count("negative")
    neutral_count = labels.count("neutral")

    return {
        "overall_score": round(sum(scores) / total, 4),
        "positive_pct": round(positive_count / total * 100, 1),
        "negative_pct": round(negative_count / total * 100, 1),
        "neutral_pct": round(neutral_count / total * 100, 1),
        "total_analyzed": total,
    }


def _calculate_platform_breakdown(sentiment_data):
    """Group sentiment scores by platform and compute per-platform averages."""
    if not sentiment_data:
        return {}

    # Group sentiment scores by platform
    platform_scores = {}
    for entry in sentiment_data:
        platform = entry.get("platform", "unknown")
        if platform not in platform_scores:
            platform_scores[platform] = {"scores": [], "labels": []}
        platform_scores[platform]["scores"].append(entry["sentiment_score"])
        platform_scores[platform]["labels"].append(entry["sentiment_label"])

    # Calculate averages per platform
    breakdown = {}
    for platform, data in platform_scores.items():
        scores = data["scores"]
        labels = data["labels"]
        count = len(scores)
        breakdown[platform] = {
            "score": round(sum(scores) / count, 4) if count else 0.0,
            "count": count,
            "positive_pct": round(labels.count("positive") / count * 100, 1),
            "negative_pct": round(labels.count("negative") / count * 100, 1),
        }

    return breakdown


def _get_top_excerpts(sentiment_data, label, n=5):
    """Return the N strongest-scoring excerpts for a given sentiment label."""
    # Filter to the requested sentiment label
    filtered = [
        s for s in sentiment_data
        if s.get("sentiment_label") == label
    ]

    # Sort by absolute score (strongest sentiment first)
    filtered.sort(key=lambda s: abs(s.get("sentiment_score", 0)), reverse=True)

    excerpts = []
    for entry in filtered[:n]:
        text = entry.get("text", "")
        # Truncate long texts for readability in reports
        if len(text) > 200:
            text = text[:200] + "..."

        excerpts.append({
            "text": text,
            "platform": entry.get("platform", "unknown"),
            "score": entry.get("sentiment_score", 0),
            "date": entry.get("date", ""),
        })

    return excerpts


def _extract_themes(posts, candidate_name):
    """Extract top recurring words from posts about a candidate (excluding stopwords)."""
    # Common English stop words + Nigerian political stop words
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "must",
        "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
        "us", "them", "my", "your", "his", "its", "our", "their",
        "this", "that", "these", "those", "what", "which", "who", "whom",
        "and", "but", "or", "nor", "not", "no", "so", "if", "then",
        "than", "too", "very", "just", "don", "now", "here", "there",
        "when", "where", "why", "how", "all", "each", "every", "both",
        "few", "more", "most", "other", "some", "such", "only", "own",
        "same", "also", "for", "from", "to", "of", "in", "on", "at",
        "by", "with", "about", "against", "between", "through", "during",
        "before", "after", "above", "below", "up", "down", "out", "off",
        "over", "under", "again", "further",
        # Nigerian context stop words
        "na", "dey", "dis", "dat", "sef", "sha", "abi", "wey", "dem",
        "una", "oga", "abeg", "jare", "like", "one", "people", "even",
        "still", "already", "much", "many", "well", "say", "said",
        "going", "come", "get", "got", "make", "want", "know", "think",
        "good", "bad", "new", "old", "first", "last", "long", "great",
    }

    # Also exclude the candidate's own name parts
    name_parts = {word.lower() for word in candidate_name.split()}

    word_counts = Counter()

    for post in posts:
        text = post.get("text", "").lower()
        # Extract words (letters only, 3+ characters)
        words = [
            w for w in text.split()
            if len(w) >= 3
            and w.isalpha()
            and w not in stop_words
            and w not in name_parts
        ]
        word_counts.update(words)

    # Get top 15 themes
    themes = [
        {"theme": word, "count": count}
        for word, count in word_counts.most_common(15)
    ]

    return themes


def _infer_demographics(posts, candidate_name):
    """Infer demographic patterns: platform audience, support base, regional mentions."""
    if not posts:
        return {"platform_audience": {}, "support_indicators": [], "regional_mentions": []}

    # Track platform discussion volume as a proxy for audience demographics
    # (Twitter skews younger/urban, Nairaland is more diverse, Reddit is diaspora)
    platform_counts = Counter()
    for post in posts:
        platform_counts[post.get("platform", "unknown")] += 1

    platform_audience = {}
    total = sum(platform_counts.values())
    for platform, count in platform_counts.most_common():
        platform_audience[platform] = {
            "posts": count,
            "share_pct": round(count / total * 100, 1),
        }

    # Look for demographic indicators in text
    demographic_keywords = {
        "youth": ["youth", "young", "student", "gen-z", "millennial", "next generation"],
        "urban": ["city", "urban", "metropolitan", "lagos island", "ikeja", "lekki", "victoria island"],
        "rural": ["rural", "village", "farm", "local government", "grassroots"],
        "women": ["women", "maternal", "gender", "female empowerment"],
        "diaspora": ["diaspora", "abroad", "overseas", "foreign"],
        "business": ["business", "entrepreneur", "trader", "market", "commerce", "economy"],
        "religious": ["church", "mosque", "imam", "pastor", "christian", "muslim"],
    }

    support_indicators = []
    name_lower = candidate_name.lower()

    for category, keywords in demographic_keywords.items():
        mentions = 0
        for post in posts:
            text = post.get("text", "").lower()
            if name_lower in text:
                if any(kw in text for kw in keywords):
                    mentions += 1
        if mentions > 0:
            support_indicators.append({
                "category": category,
                "mentions": mentions,
                "strength": "strong" if mentions >= 3 else "moderate" if mentions >= 2 else "weak",
            })

    support_indicators.sort(key=lambda x: x["mentions"], reverse=True)

    # Look for regional/area mentions in discussions about the candidate
    regional_keywords = [
        "north", "south", "east", "west", "central",
        "senatorial", "local government", "lga",
    ]
    regional_mentions = []
    for post in posts:
        text = post.get("text", "").lower()
        if name_lower in text:
            for region in regional_keywords:
                if region in text:
                    regional_mentions.append(region)

    regional_counts = Counter(regional_mentions).most_common(5)
    regional_summary = [{"region": r, "mentions": c} for r, c in regional_counts]

    return {
        "platform_audience": platform_audience,
        "support_indicators": support_indicators,
        "regional_mentions": regional_summary,
    }


def _calculate_engagement(posts):
    """Aggregate likes and shares across all posts mentioning a candidate."""
    if not posts:
        return {"total_likes": 0, "total_shares": 0, "avg_likes": 0.0}

    total_likes = sum(p.get("likes", 0) for p in posts)
    total_shares = sum(p.get("shares", 0) for p in posts)

    return {
        "total_likes": total_likes,
        "total_shares": total_shares,
        "avg_likes": round(total_likes / len(posts), 1) if posts else 0.0,
    }


def _save_profiles(all_profiles):
    """Save profiles to output/data/candidate_profiles.json."""
    import os

    output_path = "output/data/candidate_profiles.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_profiles, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"Saved candidate profiles to {output_path}")
