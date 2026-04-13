from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_yelp_als_recommendations(
    *,
    interactions_path: str | Path,
    output_path: str | Path,
    rank: int = 20,
    max_iter: int = 10,
    reg_param: float = 0.1,
    top_k: int = 20,
    app_name: str = "sc_food_rec-yelp-als",
) -> Path:
    """Train a Spark ALS model from JSONL interactions and persist top-k user recommendations."""
    spark = _create_spark_session(app_name)
    try:
        source = Path(interactions_path)
        if not source.exists():
            raise FileNotFoundError(f"Interaction file not found: {source}")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        functions = _functions()
        als, string_indexer = _ml_classes()

        raw_df = spark.read.json(str(source)).select("user_id", "business_id", "stars")
        ratings_df = raw_df.dropna().dropDuplicates(["user_id", "business_id"])
        if ratings_df.rdd.isEmpty():
            _write_json(output, {})
            return output

        user_indexer = string_indexer(
            inputCol="user_id",
            outputCol="user_index",
            handleInvalid="skip",
        ).fit(ratings_df)
        indexed_users = user_indexer.transform(ratings_df)

        business_indexer = string_indexer(
            inputCol="business_id",
            outputCol="business_index",
            handleInvalid="skip",
        ).fit(indexed_users)
        indexed_df = (
            business_indexer.transform(indexed_users)
            .withColumn("user_index", functions.col("user_index").cast("int"))
            .withColumn("business_index", functions.col("business_index").cast("int"))
            .withColumn("stars", functions.col("stars").cast("float"))
            .select("user_id", "business_id", "user_index", "business_index", "stars")
        )
        if indexed_df.rdd.isEmpty():
            _write_json(output, {})
            return output

        model = als(
            userCol="user_index",
            itemCol="business_index",
            ratingCol="stars",
            rank=max(int(rank), 1),
            maxIter=max(int(max_iter), 1),
            regParam=float(reg_param),
            coldStartStrategy="drop",
            nonnegative=True,
        ).fit(indexed_df)

        recommendations = model.recommendForAllUsers(max(int(top_k), 1))
        exploded = recommendations.select(
            "user_index",
            functions.explode("recommendations").alias("recommendation"),
        ).select(
            "user_index",
            functions.col("recommendation.itemIndex").cast("int").alias("business_index"),
            functions.round(functions.col("recommendation.rating"), 6).alias("score"),
        )

        user_lookup = indexed_df.select("user_index", "user_id").dropDuplicates(["user_index"])
        business_lookup = indexed_df.select("business_index", "business_id").dropDuplicates(
            ["business_index"]
        )
        hydrated = (
            exploded.join(user_lookup, on="user_index", how="inner")
            .join(business_lookup, on="business_index", how="inner")
            .select("user_id", "business_id", "score")
            .orderBy("user_id", functions.desc("score"), "business_id")
        )

        payload: dict[str, list[dict[str, Any]]] = {}
        for row in hydrated.toLocalIterator():
            user_id = str(row["user_id"])
            payload.setdefault(user_id, []).append(
                {
                    "business_id": str(row["business_id"]),
                    "score": float(row["score"]),
                }
            )

        _write_json(output, payload)
        return output
    finally:
        spark.stop()


def _create_spark_session(app_name: str):
    try:
        from pyspark.sql import SparkSession
    except ImportError as exc:  # pragma: no cover - depends on optional environment
        raise RuntimeError(
            "pyspark is required for Spark batch jobs. Install it before running this command."
        ) from exc

    return (
        SparkSession.builder.master("local[*]")
        .appName(app_name)
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def _functions():
    from pyspark.sql import functions

    return functions


def _ml_classes():
    from pyspark.ml.feature import StringIndexer
    from pyspark.ml.recommendation import ALS

    return ALS, StringIndexer


def _write_json(path: Path, payload: dict[str, list[dict[str, Any]]]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
