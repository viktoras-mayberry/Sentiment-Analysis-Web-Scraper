"""
Dynamic identification of Nigerian governorship election candidates from
scraped data.

The scraper collects posts from political forums (Nairaland, Reddit, Twitter,
Facebook) that discuss governorship elections across Nigeria's 36 states + FCT.
This module surfaces *only* plausible governorship candidates by applying
progressively stricter filters:

  1. Regex extraction of 2–3 word capitalized sequences from post text
  2. Stop-word rejection (common English words, institutions, non-name nouns)
  3. Stop-phrase rejection (political parties, organisations, place names)
  4. Title-prefix stripping  (Mr, Dr, Gov, Former, Alhaji …)
  5. Name-variant deduplication (merges "Sanwo Olu" / "Olu Sanwo")
  6. **Governorship + state proximity gate** — the name must appear within
     150 chars of a governorship keyword ("governor", "governorship",
     "gubernatorial") AND the post must mention the target state name.
     This structural rule ensures only people discussed as governorship
     candidates *for a specific state* survive — no blocklists needed.
  7. Minimum mention count + governorship-specific scoring
"""

import re
from collections import Counter, defaultdict
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Governorship-specific context words used for scoring
# ---------------------------------------------------------------------------
GOVERNORSHIP_CONTEXT_WORDS = {
    "governor", "governorship", "gubernatorial", "guber",
    "candidate", "aspirant", "running", "contest", "campaign",
    "elect", "election", "ticket", "primary", "nominated",
    "apc", "pdp", "lp", "nnpp", "apga",
}

# ---------------------------------------------------------------------------
# Stop words  (lowercase) — any extracted name containing one of these words
# is immediately rejected.
# ---------------------------------------------------------------------------
STOP_WORDS = {
    # Function words
    "the", "this", "that", "which", "when", "where", "what", "how",
    "and", "but", "for", "with", "from", "into", "about", "if", "so",
    "is", "are", "was", "were", "has", "had", "not", "no", "yes",
    "in", "on", "at", "to", "of", "by", "as", "or", "an", "who",
    "him", "her", "his", "its", "our", "your", "their", "them",
    # Fillers / common starts
    "good", "dear", "please", "thank", "very", "also", "just",
    "some", "every", "many", "most", "such", "only", "after",
    "before", "during", "between", "under", "over", "being",
    "having", "getting", "becoming", "despite", "although", "even",
    "still", "yet", "then", "now", "here", "there", "why",
    "best", "worst", "full", "new", "old", "big", "real", "self",
    "remaining", "other", "another", "certain", "same",
    # Geography / nationality
    "nigerian", "nigeria", "african", "africa", "american", "british",
    "united", "states", "south", "north", "west", "east", "central",
    "european", "global", "international", "world",
    "port", "bridge", "road", "street", "avenue",
    "belt", "middle", "zone", "area", "region", "district",
    "cross", "rivers", "river",
    # Government / institutions
    "federal", "government", "state", "national", "assembly",
    "president", "presidential", "senate", "house", "representatives",
    "ministry", "minister", "commission", "commissioner", "committee",
    "council", "bureau", "agency", "department", "authority",
    "tribunal", "court", "supreme", "appeal", "reform", "sector",
    "honorary", "special", "adviser", "advisor", "governors",
    # Calendar
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday",
    # Platforms / media
    "facebook", "twitter", "reddit", "nairaland", "whatsapp",
    "instagram", "youtube", "channels", "sunrise", "daily",
    # Organisations / commerce
    "airways", "airline", "airlines",
    "foundation", "association", "corporation", "company",
    "university", "college", "institute", "academy", "school",
    "hospital", "clinic", "bank", "union",
    "program", "programme", "center", "centre", "group",
    "management", "development", "voluntary", "agencies",
    # Non-name nouns
    "officer", "polling", "electronic", "transmission", "unit",
    "rock", "party", "congress", "movement", "democratic",
    "progressives", "labour", "people", "peoples",
    "former", "chairman", "obidient", "breaking", "local",
    "independent", "electoral", "security", "economic",
    "alert", "fraud", "scale", "results",
    "business", "executive", "primary", "secondary",
    "ushering", "advanced", "power", "energy",
    "main", "market", "traditional", "rulers",
    "golden", "jubilee", "award", "prize",
    "play", "dey", "guber", "does", "will", "can", "could", "should",
    "automatic", "ticket", "governor", "candidate",
    "animal", "farm", "money", "application", "legacies", "legacy",
    "permanent", "secretary", "secretaries", "architect",
    "chapter", "section", "article", "page", "volume",
    "fact", "truth", "lie", "issue", "matter", "point",
    "number", "total", "balance", "account", "credit",
    # Religious
    "god", "jesus", "allah", "holy", "church", "mosque", "father",
    # Verbs / adjectives
    "love", "hate", "like", "want", "need", "know", "think",
    "believe", "hope", "feel", "let", "make", "take", "give",
    "come", "going", "doing", "say", "said", "told", "received",
    "left", "right", "since", "until", "high", "low", "long",
}

# ---------------------------------------------------------------------------
# Nigerian states (used to reject state names captured as candidate names
# and to build state-specific proximity filters)
# ---------------------------------------------------------------------------
NIGERIAN_STATES = {
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa",
    "Benue", "Borno", "Cross River", "Delta", "Ebonyi", "Edo",
    "Ekiti", "Enugu", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano",
    "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa",
    "Niger", "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers",
    "Sokoto", "Taraba", "Yobe", "Zamfara", "FCT",
}

# ---------------------------------------------------------------------------
# Stop phrases (lowercase) — full multi-word sequences rejected outright
# ---------------------------------------------------------------------------
STOP_PHRASES = {
    "all progressives congress", "peoples democratic party",
    "labour party", "new nigeria peoples party",
    "all progressives grand alliance",
    "aso rock", "aso villa",
    "obidient movement", "sunrise daily",
    "electronic transmission", "getting polling unit",
    "polling officer", "polling unit",
    "supreme court", "appeal court",
    "local government", "civil service",
    "central bank", "world bank",
    "cross rivers", "cross river", "port harcourt",
    "fraud alert", "full scale",
    "best governor", "dey play",
    "traditional rulers", "remaining governors",
    "automatic ticket", "kano governor", "lagos governor",
    "rivers governor", "delta governor", "edo governor",
}

# ---------------------------------------------------------------------------
# Title prefixes stripped from the beginning of extracted names
# ---------------------------------------------------------------------------
TITLE_PREFIXES = {
    "mr", "mrs", "ms", "dr", "prof", "engr", "chief", "alhaji",
    "hajia", "hon", "honourable", "sen", "senator", "gov", "governor",
    "former", "late", "pastor", "reverend", "rev", "barrister",
    "justice", "sir", "dame", "prince", "princess", "father",
    "mallam", "malam", "oba", "emir", "architect", "arc",
    "high", "grand",
}

# ---------------------------------------------------------------------------
# Precomputed sets for fast lookups
# ---------------------------------------------------------------------------
_STOP_PHRASES_LOWER = {p.lower() for p in STOP_PHRASES}
_NIGERIAN_STATES_LOWER = {s.lower() for s in NIGERIAN_STATES}

# Governorship keywords used in the proximity gate
_GOVERNORSHIP_KEYWORDS = {"governor", "governorship", "gubernatorial", "guber"}

# Presidential keywords — used to detect names that are predominantly
# discussed in presidential (not governorship) context
_PRESIDENTIAL_KEYWORDS = {"president", "presidential", "presidency"}


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

        name_mentions = _extract_names_from_posts(posts)
        name_mentions = _deduplicate_variants(name_mentions)
        candidates = _filter_candidates(name_mentions, posts, state, min_mentions=2)

        for candidate in candidates:
            db.save_candidate(
                name=candidate["name"],
                state=state,
                mention_count=candidate["count"],
                platforms_found=candidate["platforms"],
            )

        candidates_by_state[state] = candidates
        logger.info(f"{state}: Found {len(candidates)} potential candidates")
        for c in candidates[:5]:
            logger.info(
                f"  - {c['name']}: {c['count']} mentions "
                f"({', '.join(c['platforms'])})"
            )

    return candidates_by_state


def _extract_names_from_posts(posts):
    """Extract 2-3 word capitalized name sequences via regex, tracking platform of origin.

    After the initial regex extraction, performs a case-insensitive recount
    to capture mentions where forum users wrote the name in lowercase.
    """
    name_data = defaultdict(lambda: {"count": 0, "platforms": set(), "contexts": []})

    name_pattern = re.compile(
        r'\b([A-Z][a-z]+(?:[-\'][A-Z]?[a-z]+)?'
        r'(?:\s+[A-Z][a-z]+(?:[-\'][A-Z]?[a-z]+)?){1,2})\b'
    )

    for post in posts:
        text = post.get("text", "")
        platform = post.get("platform", "unknown")
        if not text:
            continue

        matches = name_pattern.findall(text)
        for raw_name in matches:
            raw_name = raw_name.strip()
            if raw_name.endswith("'s"):
                raw_name = raw_name[:-2].strip()

            if _is_stop_name(raw_name):
                continue

            name = _strip_title_prefix(raw_name)
            if not name or len(name.split()) < 2:
                continue

            if _is_stop_name(name):
                continue

            name_data[name]["count"] += 1
            name_data[name]["platforms"].add(platform)

            if len(name_data[name]["contexts"]) < 3:
                idx = text.find(raw_name)
                if idx >= 0:
                    start = max(0, idx - 50)
                    end = min(len(text), idx + len(raw_name) + 50)
                    name_data[name]["contexts"].append(text[start:end].strip())

    # Case-insensitive recount: forum users often write names in lowercase.
    # For each discovered name, count how many posts contain it (case-insensitive).
    post_texts_lower = [p.get("text", "").lower() for p in posts]
    post_platforms = [p.get("platform", "unknown") for p in posts]
    for name in list(name_data.keys()):
        nl = name.lower()
        ci_count = 0
        ci_platforms = set()
        for tl, plat in zip(post_texts_lower, post_platforms):
            if nl in tl:
                ci_count += 1
                ci_platforms.add(plat)
        if ci_count > name_data[name]["count"]:
            name_data[name]["count"] = ci_count
            name_data[name]["platforms"] |= ci_platforms

    return dict(name_data)


def _strip_title_prefix(name):
    """Remove leading title words like Mr, Dr, Gov, Former, etc."""
    words = name.split()
    while words and words[0].lower() in TITLE_PREFIXES:
        words = words[1:]
    return " ".join(words)


def _is_stop_name(name):
    """Reject names containing stop words, matching stop phrases, or state names."""
    name_lower = name.lower()

    if name_lower in _STOP_PHRASES_LOWER:
        return True

    words = name.split()
    for word in words:
        if word.lower() in STOP_WORDS:
            return True

    if name_lower in _NIGERIAN_STATES_LOWER:
        return True

    return False


def _deduplicate_variants(name_mentions):
    """
    Merge name variants that refer to the same person.

    Handles cases like:
      - "Peter Obi" and "Mr Peter Obi" (title prefix already stripped)
      - "Obi Peter" (reversed order) and "Peter Obi"
      - "Peter Obi's" possessive forms (regex shouldn't catch these, but safety net)

    Strategy: for each pair of names, if one is a subset of the other's words
    (in any order), merge into the longer or more-mentioned form.
    """
    names = list(name_mentions.keys())
    merged = {}
    skip = set()

    names_sorted = sorted(names, key=lambda n: name_mentions[n]["count"], reverse=True)

    for i, name_a in enumerate(names_sorted):
        if name_a in skip:
            continue

        words_a = set(name_a.lower().split())
        best = name_a

        for j, name_b in enumerate(names_sorted):
            if i == j or name_b in skip:
                continue
            words_b = set(name_b.lower().split())

            if words_a == words_b or words_a.issubset(words_b) or words_b.issubset(words_a):
                data_a = name_mentions[name_a]
                data_b = name_mentions[name_b]
                data_a["count"] += data_b["count"]
                data_a["platforms"] |= data_b["platforms"]
                data_a["contexts"].extend(data_b["contexts"][:3])
                skip.add(name_b)

        merged[best] = name_mentions[best]

    return merged


_ROLE_WINDOW = 80    # chars each side — role detection (gov vs pres)
_STATE_WINDOW = 100  # chars each side — state + gov proximity gate

def _filter_candidates(name_mentions, posts, state, min_mentions=2):
    """
    Filter names to keep only plausible governorship candidates for
    *this specific state*.  Fully data-driven, no hardcoded blocklists.

    Two proximity windows do the heavy lifting:

      1. **State+gov proximity** (200-char window): the name must appear
         within 100 chars of BOTH a governorship keyword AND the target
         state name.  Filters out other-state governors who happen to be
         mentioned in threads about this state.
      2. **Role detection** (160-char window): count how often the name
         appears near "governor" vs near "president".  If the name is
         closer to presidential context, it is a national figure, not a
         governorship candidate.
    """
    candidates = []
    post_texts_lower = [p.get("text", "").lower() for p in posts]

    state_lower = state.lower()
    state_variants = {state_lower}
    _state_abbreviations = {
        "fct": {"fct", "abuja", "federal capital"},
        "akwa ibom": {"akwa ibom", "akwa"},
        "cross river": {"cross river", "calabar"},
    }
    if state_lower in _state_abbreviations:
        state_variants.update(_state_abbreviations[state_lower])

    for name, data in name_mentions.items():
        count = data["count"]
        platforms = data["platforms"]

        if count < min_mentions:
            continue

        name_lower = name.lower()

        gov_prox = 0
        pres_prox = 0
        state_gov_prox = 0
        governorship_context_score = 0

        for post_text_lower in post_texts_lower:
            if name_lower not in post_text_lower:
                continue

            state_in_post = any(sv in post_text_lower for sv in state_variants)

            search_start = 0
            while True:
                idx = post_text_lower.find(name_lower, search_start)
                if idx == -1:
                    break

                # Role detection — narrow 80-char window
                r_start = max(0, idx - _ROLE_WINDOW)
                r_end = min(len(post_text_lower),
                            idx + len(name_lower) + _ROLE_WINDOW)
                role_window = post_text_lower[r_start:r_end]

                if any(kw in role_window for kw in _GOVERNORSHIP_KEYWORDS):
                    gov_prox += 1
                if any(kw in role_window for kw in _PRESIDENTIAL_KEYWORDS):
                    pres_prox += 1

                # State+gov proximity — wider 100-char window
                s_start = max(0, idx - _STATE_WINDOW)
                s_end = min(len(post_text_lower),
                            idx + len(name_lower) + _STATE_WINDOW)
                state_window = post_text_lower[s_start:s_end]

                has_gov_near = any(
                    kw in state_window for kw in _GOVERNORSHIP_KEYWORDS)
                has_state_near = any(
                    sv in state_window for sv in state_variants)
                if has_gov_near and has_state_near:
                    state_gov_prox += 1

                search_start = idx + 1

            if state_in_post:
                context_hits = sum(
                    1 for word in GOVERNORSHIP_CONTEXT_WORDS
                    if word in post_text_lower
                )
                governorship_context_score += context_hits

        # Gate 1: name + governorship + state must co-occur in proximity
        if state_gov_prox == 0:
            continue

        # Gate 2: must be discussed in governorship context
        if gov_prox == 0 or governorship_context_score == 0:
            continue

        # Gate 3: name appears near "governor" MORE than near "president"
        if pres_prox >= gov_prox:
            logger.debug(
                f"Skipping {name}: pres_prox ({pres_prox}) "
                f">= gov_prox ({gov_prox})"
            )
            continue

        platform_bonus = 1.5 if len(platforms) >= 2 else 1.0
        gov_ratio = gov_prox / max(count, 1)
        state_ratio = state_gov_prox / max(count, 1)
        score = (count * platform_bonus
                 * (1.0 + gov_ratio * 0.3 + state_ratio * 0.3)
                 * (1 + governorship_context_score / 10))

        candidates.append({
            "name": name,
            "count": count,
            "platforms": sorted(list(platforms)),
            "score": score,
            "governorship_context_score": governorship_context_score,
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:20]


def try_spacy_ner(posts):
    """Optional spaCy NER-based name extraction. Returns {name: count} or empty dict."""
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
    except (ImportError, OSError):
        logger.debug("spaCy not available — using regex-only name extraction")
        return {}

    name_counts = Counter()
    for post in posts:
        text = post.get("text", "")
        if not text or len(text) > 5000:
            continue
        doc = nlp(text)
        for ent in doc.ents:
            if ent.label_ == "PERSON" and len(ent.text.split()) >= 2:
                name_counts[ent.text] += 1

    return dict(name_counts)
