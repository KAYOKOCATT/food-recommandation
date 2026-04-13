from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from django.conf import settings
from sklearn.feature_extraction.text import TfidfVectorizer
from wordcloud import WordCloud

from apps.foods.models import Foods
from apps.recommendations.models import YelpReview


class HomeWordCloudService:
    DATA_DIR = settings.BASE_DIR / "data" / "recommendations"
    FOOD_WORDCLOUD_FILE = DATA_DIR / "home_food_recommend_wordcloud.png"
    YELP_WORDCLOUD_FILE = DATA_DIR / "home_yelp_review_wordcloud.png"
    IMAGE_WIDTH = 1200
    IMAGE_HEIGHT = 480
    MAX_WORDS = 120
    FOOD_MIN_TOKEN_LENGTH = 2
    YELP_MAX_FEATURES = 5000
    YELP_TOP_WORDS = 120
    YELP_MIN_DF = 3
    YELP_MAX_DF = 0.6
    YELP_REVIEW_LIMIT = 1000000
    CHINESE_FONT_CANDIDATES = (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/msyhbd.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    )
    _TOKEN_SPLIT_RE = re.compile(r"[，。！？；：、,.!?:;()\[\]{}<>/\\|\"'\s]+")
    _CJK_OR_LATIN_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{2,}")
    _YELP_STOP_WORDS = [
        *list(TfidfVectorizer(stop_words="english").get_stop_words()),
        "food",
        "place",
        "good",
        "great",
        "really",
        "just",
        "like",
        "restaurant",
        "service",
        "time",
        "nice",
        "ve",
        "ordered",
        "best",
        "delicious",
        "love",
        "amazing",
        "excellent",
        "friendly",
        "definitely",
        "favorite",
        "perfect",
        "horrible",
        "terrible",
        "worst",
        "awful",
        "got",
        "don",
        "came",
        "went",
        "come",
        "going",
        "try",
        "tried",
        "little",
        "wait",
        "said",
        "asked",
        "told",
        "took",
        "make",
        "know",
    ]

    @classmethod
    def build_all(cls) -> dict[str, Path]:
        cls.build_food_wordcloud()
        cls.build_yelp_wordcloud()
        return {
            "food": cls.FOOD_WORDCLOUD_FILE,
            "yelp": cls.YELP_WORDCLOUD_FILE,
        }

    @classmethod
    def build_food_wordcloud(cls) -> Path:
        frequencies = cls._food_frequencies()
        return cls._render_wordcloud(
            frequencies=frequencies,
            output_path=cls.FOOD_WORDCLOUD_FILE,
            font_path=cls._resolve_font_path(),
        )

    @classmethod
    def build_yelp_wordcloud(cls) -> Path:
        frequencies = cls._yelp_tfidf_frequencies()
        return cls._render_wordcloud(
            frequencies=frequencies,
            output_path=cls.YELP_WORDCLOUD_FILE,
            font_path=None,
        )

    @classmethod
    def get_image_path(cls, kind: str) -> Path:
        if kind == "food":
            return cls.FOOD_WORDCLOUD_FILE
        if kind == "yelp":
            return cls.YELP_WORDCLOUD_FILE
        raise ValueError(f"Unsupported wordcloud kind: {kind}")

    @classmethod
    def image_exists(cls, kind: str) -> bool:
        return cls.get_image_path(kind).exists()

    @classmethod
    def _food_frequencies(cls) -> dict[str, float]:
        counter: Counter[str] = Counter()
        texts = (
            Foods.objects.exclude(recommend__isnull=True)
            .exclude(recommend__exact="nan")
            .values_list("recommend", flat=True)
        )
        for text in texts.iterator(chunk_size=500):
            for token in cls._tokenize_food_text(str(text or "")):
                counter[token] += 1
        return cls._normalize_counter(counter, fallback_label="暂无菜品推荐语")

    @classmethod
    def _yelp_tfidf_frequencies(cls) -> dict[str, float]:
        texts = [
            text.strip()
            for text in YelpReview.objects.exclude(text__exact="")
            .exclude(text__isnull=True)
            .order_by("-id")
            .values_list("text", flat=True)
            [: cls.YELP_REVIEW_LIMIT]
            .iterator(chunk_size=1000)
            if str(text or "").strip()
        ]
        if not texts:
            return {"no reviews yet": 1.0}

        vectorizer = TfidfVectorizer(
            max_features=cls.YELP_MAX_FEATURES,
            min_df=cls.YELP_MIN_DF,
            max_df=cls.YELP_MAX_DF,
            stop_words=cls._YELP_STOP_WORDS,
            token_pattern=r"(?u)\b[a-zA-Z]{2,}\b",
            ngram_range=(1, 2),
            norm="l2",
        )
        try:
            tfidf_matrix = vectorizer.fit_transform(texts)
        except ValueError:
            return {"no reviews yet": 1.0}

        feature_names = vectorizer.get_feature_names_out()
        if len(feature_names) == 0:
            return {"no reviews yet": 1.0}

        mean_tfidf = tfidf_matrix.mean(axis=0).A1
        ranked = sorted(
            zip(feature_names, mean_tfidf),
            key=lambda item: item[1],
            reverse=True,
        )[: cls.YELP_TOP_WORDS]
        return {word: float(weight) for word, weight in ranked if weight > 0} or {"no reviews yet": 1.0}

    @classmethod
    def _render_wordcloud(
        cls,
        *,
        frequencies: dict[str, float],
        output_path: Path,
        font_path: str | None,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        wordcloud = WordCloud(
            width=cls.IMAGE_WIDTH,
            height=cls.IMAGE_HEIGHT,
            background_color="white",
            colormap="viridis",
            max_words=cls.MAX_WORDS,
            collocations=False,
            font_path=font_path,
        ).generate_from_frequencies(frequencies)
        image = wordcloud.to_image()
        image.save(output_path)
        return output_path

    @classmethod
    def _tokenize_food_text(cls, text: str) -> list[str]:
        tokens: list[str] = []
        for chunk in cls._TOKEN_SPLIT_RE.split(text.strip()):
            if not chunk:
                continue
            for token in cls._CJK_OR_LATIN_RE.findall(chunk):
                normalized = token.lower() if token.isascii() else token
                if len(normalized) >= cls.FOOD_MIN_TOKEN_LENGTH:
                    tokens.append(normalized)
        return tokens

    @staticmethod
    def _normalize_counter(
        counter: Counter[str],
        *,
        fallback_label: str,
    ) -> dict[str, float]:
        if not counter:
            return {fallback_label: 1.0}
        return {token: float(count) for token, count in counter.most_common(120)}

    @classmethod
    def _resolve_font_path(cls) -> str | None:
        for path in cls.CHINESE_FONT_CANDIDATES:
            if path.exists():
                return str(path)
        return None
