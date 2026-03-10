"""
Markdown report generator.

Produces a per-state report with executive summaries, candidate rankings,
detailed profiles (sentiment, excerpts, themes, demographics, engagement),
and a methodology section.
"""

import os
import json
from datetime import datetime
from utils.config import config
from utils.logger import get_logger

logger = get_logger(__name__)

REPORT_DIR = "output/reports"


def generate_report(profiles):
    """Main function: generate the Markdown report from candidate profiles"""
    os.makedirs(REPORT_DIR, exist_ok=True)

    # Generate one comprehensive report for all states
    report_path = os.path.join(REPORT_DIR, "election_report.md")

    lines = []
    lines.append("# Nigerian Governorship Election - Sentiment Analysis Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Analysis Period:** Past {config.time_range_months} months")
    lines.append(f"**States Analyzed:** {', '.join(config.states)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Table of Contents
    lines.append("## Table of Contents")
    lines.append("")
    for state in config.states:
        anchor = state.lower().replace(" ", "-")
        lines.append(f"- [{state} State](#{anchor}-state)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Generate section for each state
    for state in config.states:
        state_profiles = profiles.get(state, [])
        lines.extend(_generate_state_section(state, state_profiles))

    # Methodology section
    lines.extend(_generate_methodology_section())

    # Write the report
    report_content = "\n".join(lines)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    logger.info(f"Report generated: {report_path}")
    return report_path


def _generate_state_section(state, profiles):
    """Generate the report section for one state"""
    lines = []
    anchor = state.lower().replace(" ", "-")
    lines.append(f"## {state} State")
    lines.append("")

    if not profiles:
        lines.append("*No candidates identified for this state. "
                     "This may indicate insufficient data from the scraping phase.*")
        lines.append("")
        lines.append("---")
        lines.append("")
        return lines

    # --- Executive Summary ---
    total_posts = sum(p.get("post_count", 0) for p in profiles)
    total_candidates = len(profiles)
    all_platforms = set()
    for p in profiles:
        all_platforms.update(p.get("platforms_found", []))

    lines.append("### Executive Summary")
    lines.append("")
    lines.append(f"- **Candidates Identified:** {total_candidates}")
    lines.append(f"- **Total Posts Analyzed:** {total_posts}")
    lines.append(f"- **Platforms with Data:** {', '.join(sorted(all_platforms)) if all_platforms else 'N/A'}")
    lines.append("")

    # --- Candidate Ranking Table ---
    lines.append("### Candidate Sentiment Rankings")
    lines.append("")
    lines.append("| Rank | Candidate | Sentiment Score | Positive % | Negative % | Mentions |")
    lines.append("|------|-----------|-----------------|------------|------------|----------|")

    for i, profile in enumerate(profiles, 1):
        sentiment = profile.get("sentiment", {})
        score = sentiment.get("overall_score", 0)
        pos_pct = sentiment.get("positive_pct", 0)
        neg_pct = sentiment.get("negative_pct", 0)

        # Score indicator
        if score > 0.1:
            indicator = "Positive"
        elif score < -0.1:
            indicator = "Negative"
        else:
            indicator = "Neutral"

        lines.append(
            f"| {i} | **{profile['name']}** | {score:+.3f} ({indicator}) "
            f"| {pos_pct:.1f}% | {neg_pct:.1f}% | {profile.get('mention_count', 0)} |"
        )

    lines.append("")

    # --- Detailed Profiles ---
    lines.append("### Detailed Candidate Profiles")
    lines.append("")

    for profile in profiles:
        lines.extend(_generate_candidate_detail(profile))

    lines.append("---")
    lines.append("")
    return lines


def _generate_candidate_detail(profile):
    """Generate the detailed section for one candidate"""
    lines = []
    name = profile["name"]
    state = profile["state"]
    sentiment = profile.get("sentiment", {})

    lines.append(f"#### {name}")
    lines.append("")
    lines.append(f"**State:** {state} | "
                f"**Mentions:** {profile.get('mention_count', 0)} | "
                f"**Platforms:** {', '.join(profile.get('platforms_found', []))}")
    lines.append("")

    # Sentiment Overview
    lines.append("**Sentiment Overview:**")
    lines.append("")
    score = sentiment.get("overall_score", 0)
    lines.append(f"- Overall Score: **{score:+.3f}**")
    lines.append(f"- Positive: {sentiment.get('positive_pct', 0):.1f}%")
    lines.append(f"- Negative: {sentiment.get('negative_pct', 0):.1f}%")
    lines.append(f"- Neutral: {sentiment.get('neutral_pct', 0):.1f}%")
    lines.append(f"- Total Posts Analyzed: {sentiment.get('total_analyzed', 0)}")
    lines.append("")

    # Platform Breakdown
    breakdown = profile.get("platform_breakdown", {})
    if breakdown:
        lines.append("**Sentiment by Platform:**")
        lines.append("")
        lines.append("| Platform | Score | Posts | Positive % | Negative % |")
        lines.append("|----------|-------|-------|------------|------------|")
        for platform, data in breakdown.items():
            lines.append(
                f"| {platform.capitalize()} | {data['score']:+.3f} "
                f"| {data['count']} | {data.get('positive_pct', 0):.1f}% "
                f"| {data.get('negative_pct', 0):.1f}% |"
            )
        lines.append("")

    # Key Themes
    themes = profile.get("key_themes", [])
    if themes:
        lines.append("**Key Discussion Themes:**")
        lines.append("")
        theme_strs = [f"`{t['theme']}` ({t['count']})" for t in themes[:10]]
        lines.append(", ".join(theme_strs))
        lines.append("")

    # Top Positive Excerpts
    pos_excerpts = profile.get("top_positive_excerpts", [])
    if pos_excerpts:
        lines.append("**Top Positive Excerpts:**")
        lines.append("")
        for excerpt in pos_excerpts[:3]:
            platform = excerpt.get("platform", "unknown")
            lines.append(f'> "{excerpt["text"]}"')
            lines.append(f'> *- {platform.capitalize()}, '
                        f'Score: {excerpt.get("score", 0):+.2f}*')
            lines.append("")

    # Top Negative Excerpts
    neg_excerpts = profile.get("top_negative_excerpts", [])
    if neg_excerpts:
        lines.append("**Top Negative Excerpts:**")
        lines.append("")
        for excerpt in neg_excerpts[:3]:
            platform = excerpt.get("platform", "unknown")
            lines.append(f'> "{excerpt["text"]}"')
            lines.append(f'> *- {platform.capitalize()}, '
                        f'Score: {excerpt.get("score", 0):+.2f}*')
            lines.append("")

    # Demographic Insights
    demographics = profile.get("demographic_insights", {})
    support_indicators = demographics.get("support_indicators", [])
    platform_audience = demographics.get("platform_audience", {})
    if support_indicators or platform_audience:
        lines.append("**Demographic Insights:**")
        lines.append("")
        if platform_audience:
            audience_parts = [
                f"{p.capitalize()} ({d['share_pct']}%)"
                for p, d in platform_audience.items()
            ]
            lines.append(f"- Platform Reach: {', '.join(audience_parts)}")
        if support_indicators:
            indicator_parts = [
                f"{s['category'].capitalize()} ({s['strength']}, {s['mentions']} mentions)"
                for s in support_indicators[:5]
            ]
            lines.append(f"- Support Indicators: {', '.join(indicator_parts)}")
        regional = demographics.get("regional_mentions", [])
        if regional:
            region_parts = [f"{r['region']} ({r['mentions']})" for r in regional]
            lines.append(f"- Regional References: {', '.join(region_parts)}")
        lines.append("")

    # Engagement Metrics
    engagement = profile.get("engagement", {})
    if engagement:
        lines.append("**Engagement Metrics:**")
        lines.append("")
        lines.append(f"- Total Likes/Reactions: {engagement.get('total_likes', 0):,}")
        lines.append(f"- Total Shares/Retweets: {engagement.get('total_shares', 0):,}")
        lines.append(f"- Average Likes per Post: {engagement.get('avg_likes', 0):.1f}")
        lines.append("")

    lines.append("---")
    lines.append("")
    return lines


def _generate_methodology_section():
    """Generate the methodology section explaining our approach"""
    lines = []
    lines.append("## Methodology")
    lines.append("")
    lines.append("### Data Collection")
    lines.append("")
    lines.append("Data was collected from multiple platforms using platform-specific methods:")
    lines.append("")
    lines.append("| Platform | Method | Authentication |")
    lines.append("|----------|--------|----------------|")
    lines.append("| Nairaland | HTML parsing (BeautifulSoup) | None required |")
    lines.append("| Reddit | PRAW (official API wrapper) | OAuth (client credentials) |")
    lines.append("| Twitter/X | Tweepy (API v2) | Bearer token |")
    lines.append("| Facebook | Graph API (requests) | Access token |")
    lines.append("")
    lines.append("### Candidate Identification")
    lines.append("")
    lines.append("Candidates were identified dynamically using a two-layer approach:")
    lines.append("")
    lines.append("1. **Regex-based name extraction** - Sequences of 2-3 capitalized words "
                "matching name patterns (handles hyphenated Nigerian names)")
    lines.append("2. **Frequency + context filtering** - Names must appear 2+ times near "
                "election-related keywords, with cross-platform validation bonus")
    lines.append("")
    lines.append("### Sentiment Analysis")
    lines.append("")

    model = config.sentiment.get("model", "transformers")
    lines.append(f"Primary model: **{model}**")
    lines.append("")
    lines.append("- Three-tier fallback: HuggingFace Transformers > VADER > TextBlob")
    lines.append("- Scores range from -1.0 (most negative) to +1.0 (most positive)")
    lines.append("- Handles English and Nigerian Pidgin text")
    lines.append("")
    lines.append("### Assumptions and Limitations")
    lines.append("")
    lines.append("- Only public data is collected; no private accounts or groups are accessed")
    lines.append("- Author identities are anonymized using SHA-256 hashing")
    lines.append("- Sentiment models may misclassify sarcasm or culturally-specific expressions")
    lines.append("- Twitter API free tier does not support search; results depend on API access level")
    lines.append("- Facebook Graph API has restricted public post search since 2018")
    lines.append("- Candidate identification may miss names not following standard capitalization")
    lines.append("")
    lines.append("### Ethical Compliance")
    lines.append("")
    lines.append("- All data sources are public and freely accessible")
    lines.append("- robots.txt compliance is respected where applicable")
    lines.append("- Request delays are enforced to avoid server overload")
    lines.append("- No automated logins or credential stuffing is performed")
    lines.append("- Author data is anonymized before storage")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Report generated by Nigerian Election Sentiment Analysis Tool*")
    lines.append("")

    return lines
