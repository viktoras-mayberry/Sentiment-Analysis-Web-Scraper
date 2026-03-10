"""
Three-tier sentiment analysis with automatic fallback.

Tier 1: HuggingFace Transformers (twitter-roberta-base-sentiment)
Tier 2: VADER (rule-based, fast)
Tier 3: TextBlob (pattern-based, basic)

Configured via config.yaml (sentiment.model). Falls through tiers
automatically if a library is unavailable.
"""

from utils.config import config
from utils.logger import get_logger

logger = get_logger(__name__)


class SentimentAnalyzer:
    """Multi-tier sentiment analyzer with automatic fallback."""

    def __init__(self):
        self.model_type = config.sentiment.get("model", "transformers")
        self.transformer_model_name = config.sentiment.get(
            "transformer_model",
            "cardiffnlp/twitter-roberta-base-sentiment-latest",
        )
        self.confidence_threshold = config.sentiment.get(
            "confidence_threshold", 0.5
        )
        self._analyzer = None
        self._initialize()

    def _initialize(self):
        """Try configured model first, fall back through tiers on failure."""
        if self.model_type == "transformers":
            if self._init_transformers():
                return
            logger.warning("Transformers unavailable, falling back to VADER")
            self.model_type = "vader"

        if self.model_type == "vader":
            if self._init_vader():
                return
            logger.warning("VADER unavailable, falling back to TextBlob")
            self.model_type = "textblob"

        if self.model_type == "textblob":
            if self._init_textblob():
                return

        logger.error(
            "No sentiment analysis library available! "
            "Install at least one: transformers+torch, vaderSentiment, or textblob"
        )

    def _init_transformers(self):
        """Load HuggingFace sentiment-analysis pipeline."""
        try:
            from transformers import pipeline

            logger.info(
                f"Loading transformer model: {self.transformer_model_name}"
            )
            self._analyzer = pipeline(
                "sentiment-analysis",
                model=self.transformer_model_name,
                truncation=True,
                max_length=512,
            )
            logger.info("Transformer sentiment model loaded successfully")
            return True
        except Exception as e:
            logger.debug(f"Failed to load transformers: {e}")
            return False

    def _init_vader(self):
        """Initialize VADER rule-based sentiment analyzer."""
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

            self._analyzer = SentimentIntensityAnalyzer()
            logger.info("VADER sentiment analyzer initialized")
            return True
        except ImportError:
            logger.debug("vaderSentiment not installed")
            return False

    def _init_textblob(self):
        """Initialize TextBlob pattern-based sentiment."""
        try:
            from textblob import TextBlob

            # Test that it works
            TextBlob("test").sentiment
            self._analyzer = "textblob"  # Flag that TextBlob is available
            logger.info("TextBlob sentiment analyzer initialized")
            return True
        except ImportError:
            logger.debug("TextBlob not installed")
            return False

    def analyze(self, text):
        """Analyze the sentiment of a single text"""
        if not text or not self._analyzer:
            return {"label": "neutral", "score": 0.0, "confidence": 0.0}

        if len(text) > 1000:
            text = text[:1000]

        if self.model_type == "transformers":
            return self._analyze_transformers(text)
        elif self.model_type == "vader":
            return self._analyze_vader(text)
        elif self.model_type == "textblob":
            return self._analyze_textblob(text)

        return {"label": "neutral", "score": 0.0, "confidence": 0.0}

    def _analyze_transformers(self, text):
        """Analyze sentiment using HuggingFace transformers"""
        try:
            result = self._analyzer(text)[0]
            label = result["label"].lower()
            confidence = result["score"]

            if label == "positive":
                score = confidence    # 0.0 to 1.0
            elif label == "negative":
                score = -confidence   # -1.0 to 0.0
            else:
                score = 0.0           # neutral

            if "pos" in label:
                label = "positive"
            elif "neg" in label:
                label = "negative"
            else:
                label = "neutral"

            return {
                "label": label,
                "score": round(score, 4),
                "confidence": round(confidence, 4),
            }
        except Exception as e:
            logger.debug(f"Transformer analysis failed: {e}")
            return {"label": "neutral", "score": 0.0, "confidence": 0.0}

    def _analyze_vader(self, text):
        """Analyze sentiment using VADER"""
        try:
            scores = self._analyzer.polarity_scores(text)
            compound = scores["compound"]

            if compound >= 0.05:
                label = "positive"
            elif compound <= -0.05:
                label = "negative"
            else:
                label = "neutral"

            confidence = abs(compound)

            return {
                "label": label,
                "score": round(compound, 4),
                "confidence": round(confidence, 4),
            }
        except Exception as e:
            logger.debug(f"VADER analysis failed: {e}")
            return {"label": "neutral", "score": 0.0, "confidence": 0.0}

    def _analyze_textblob(self, text):
        """Analyze sentiment using TextBlob"""
        try:
            from textblob import TextBlob

            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity

            if polarity > 0.1:
                label = "positive"
            elif polarity < -0.1:
                label = "negative"
            else:
                label = "neutral"

            return {
                "label": label,
                "score": round(polarity, 4),
                "confidence": round(subjectivity, 4),
            }
        except Exception as e:
            logger.debug(f"TextBlob analysis failed: {e}")
            return {"label": "neutral", "score": 0.0, "confidence": 0.0}

    def analyze_batch(self, texts):
        """Analyze sentiment for a list of texts"""
        if self.model_type == "transformers" and self._analyzer:
            try:
                truncated = [t[:1000] if t else "" for t in texts]
                results = self._analyzer(truncated)
                return [
                    self._format_transformer_result(r) for r in results
                ]
            except Exception as e:
                logger.debug(f"Batch analysis failed, falling back to one-by-one: {e}")

        return [self.analyze(t) for t in texts]

    def _format_transformer_result(self, result):
        """Format a single transformer pipeline result."""
        label = result["label"].lower()
        confidence = result["score"]

        if "pos" in label:
            return {"label": "positive", "score": round(confidence, 4), "confidence": round(confidence, 4)}
        elif "neg" in label:
            return {"label": "negative", "score": round(-confidence, 4), "confidence": round(confidence, 4)}
        else:
            return {"label": "neutral", "score": 0.0, "confidence": round(confidence, 4)}


def analyze_sentiment(db):
    """Score all posts and link sentiment results to mentioned candidates."""
    from utils.config import config

    analyzer = SentimentAnalyzer()

    for state in config.states:
        logger.info(f"Running sentiment analysis for {state}...")
        posts = db.get_posts_by_state(state)
        candidates = db.get_candidates_by_state(state)

        if not posts:
            logger.warning(f"No posts for {state} — skipping sentiment")
            continue

        candidate_names = [c["name"] for c in candidates]
        analyzed_count = 0

        # Process posts in batches for efficiency
        batch_size = 32
        for i in range(0, len(posts), batch_size):
            batch = posts[i:i + batch_size]
            texts = [p["text"] for p in batch]

            # Batch sentiment analysis
            results = analyzer.analyze_batch(texts)

            for post, sentiment in zip(batch, results):
                mentioned_candidates = [
                    name for name in candidate_names
                    if name.lower() in post["text"].lower()
                ]

                if mentioned_candidates:
                    for candidate_name in mentioned_candidates:
                        db.save_sentiment(
                            post_id=post["id"],
                            candidate_name=candidate_name,
                            label=sentiment["label"],
                            score=sentiment["score"],
                            confidence=sentiment["confidence"],
                        )
                        analyzed_count += 1
                else:
                    db.save_sentiment(
                        post_id=post["id"],
                        candidate_name="General",
                        label=sentiment["label"],
                        score=sentiment["score"],
                        confidence=sentiment["confidence"],
                    )
                    analyzed_count += 1

        logger.info(
            f"{state}: Analyzed {len(posts)} posts, "
            f"created {analyzed_count} sentiment entries"
        )
