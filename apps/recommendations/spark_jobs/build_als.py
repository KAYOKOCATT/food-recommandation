from __future__ import annotations

import json
import shutil
from pathlib import Path


def build_yelp_als_recommendations(
    *,
    data_dir: str | Path,
    output_path: str | Path,
    rank: int = 20,
    max_iter: int = 10,
    reg_param: float = 0.1,
    top_k: int = 20,
    target_user_count: int = 30_000,
    target_review_count: int = 300_000,
    min_business_review_count: int = 10,
    min_user_review_count: int = 5,
    app_name: str = "sc_food_rec-yelp-als",
) -> Path:
    _prepare_hadoop_env()
    """Train a Spark ALS model from raw Yelp JSONL files and persist top-k user recommendations."""
    spark = _create_spark_session(app_name)
    try:
        source = Path(data_dir)
        business_path = source / "yelp_academic_dataset_business.json"
        review_path = source / "yelp_academic_dataset_review.json"
        if not business_path.exists():
            raise FileNotFoundError(f"Business file not found: {business_path}")
        if not review_path.exists():
            raise FileNotFoundError(f"Review file not found: {review_path}")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp_output_dir = output.with_suffix(f"{output.suffix}.tmp")
        if temp_output_dir.exists():
            shutil.rmtree(temp_output_dir)

        functions = _functions()
        als, string_indexer = _ml_classes()
        business_df = spark.read.json(str(business_path)).select(
            "business_id",
            "categories",
        )
        review_df = spark.read.json(str(review_path)).select(
            "user_id",
            "business_id",
            "stars",
        )
        restaurant_business_df = business_df.filter(
            functions.col("categories").rlike("(?i)Restaurants|Cafe|Cafes")
            & ~functions.col("categories").rlike("(?i)Grocery|Pharmacy|Department Store|Pet Food")
        ).select("business_id")
        ratings_df = (
            review_df.join(restaurant_business_df, on="business_id", how="inner")
            .dropna(subset=["user_id", "business_id", "stars"])
            .dropDuplicates(["user_id", "business_id"])
            .select("user_id", "business_id", "stars")
        )
        ratings_df = _bound_ratings_df(
            ratings_df,
            min_business_review_count=max(int(min_business_review_count), 1),
            min_user_review_count=max(int(min_user_review_count), 1),
            target_user_count=max(int(target_user_count), 1),
            target_review_count=max(int(target_review_count), 1),
        )
        if not _has_rows(ratings_df):
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
        if not _has_rows(indexed_df):
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
            functions.col("recommendation.business_index").cast("int").alias("business_index"),
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
        )
        _write_partitioned_recommendations(hydrated, temp_output_dir)
        _merge_partitioned_recommendations(temp_output_dir, output)
        return output
    finally:
        spark.stop()


def _bound_ratings_df(
    ratings_df,
    *,
    min_business_review_count: int,
    min_user_review_count: int,
    target_user_count: int,
    target_review_count: int,
):
    functions = _functions()

    business_counts = ratings_df.groupBy("business_id").count().filter(
        functions.col("count") >= min_business_review_count
    )
    bounded_df = ratings_df.join(
        business_counts.select("business_id"),
        on="business_id",
        how="inner",
    )

    user_counts = bounded_df.groupBy("user_id").count().filter(
        functions.col("count") >= min_user_review_count
    )
    top_users = user_counts.orderBy(functions.desc("count"), functions.asc("user_id")).limit(
        target_user_count
    )
    bounded_df = bounded_df.join(top_users.select("user_id"), on="user_id", how="inner")

    user_review_counts = bounded_df.groupBy("user_id").count().withColumnRenamed(
        "count",
        "user_review_count",
    )
    business_review_counts = bounded_df.groupBy("business_id").count().withColumnRenamed(
        "count",
        "business_review_count",
    )
    return (
        bounded_df.join(user_review_counts, on="user_id", how="inner")
        .join(business_review_counts, on="business_id", how="inner")
        .orderBy(
            functions.desc("user_review_count"),
            functions.desc("business_review_count"),
            functions.asc("user_id"),
            functions.asc("business_id"),
        )
        .limit(target_review_count)
        .select("user_id", "business_id", "stars")
    )


def _write_partitioned_recommendations(dataframe, temp_output_dir: Path) -> None:
    functions = _functions()
    (
        dataframe.repartition("user_id")
        .sortWithinPartitions("user_id", functions.desc("score"), "business_id")
        .write.mode("overwrite")
        .partitionBy("user_id")
        .json(str(temp_output_dir))
    )


def _merge_partitioned_recommendations(temp_output_dir: Path, output_path: Path) -> None:
    user_dirs = sorted(
        (
            path for path in temp_output_dir.iterdir()
            if path.is_dir() and path.name.startswith("user_id=")
        ),
        key=lambda path: path.name,
    )

    with output_path.open("w", encoding="utf-8") as target:
        target.write("{")
        first_user = True
        for user_dir in user_dirs:
            user_id = user_dir.name.split("=", 1)[1]
            rows: list[dict[str, float | str]] = []
            for part_file in sorted(user_dir.glob("part-*.json")):
                with part_file.open(encoding="utf-8") as source:
                    for line in source:
                        if not line.strip():
                            continue
                        record = json.loads(line)
                        business_id = str(record.get("business_id") or "")
                        if not business_id:
                            continue
                        rows.append(
                            {
                                "business_id": business_id,
                                "score": float(record.get("score") or 0.0),
                            }
                        )
            if not rows:
                continue
            rows.sort(key=lambda item: (-float(item["score"]), str(item["business_id"])))
            if not first_user:
                target.write(",")
            target.write(json.dumps(user_id, ensure_ascii=False))
            target.write(":")
            target.write(json.dumps(rows, ensure_ascii=False))
            first_user = False
        target.write("}")

    shutil.rmtree(temp_output_dir, ignore_errors=True)


def _has_rows(dataframe) -> bool:
    return bool(dataframe.limit(1).count())


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
        .config("spark.driver.memory", "8g")
        .config("spark.executor.memory", "8g")
        .config("spark.driver.maxResultSize", "512m")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.default.parallelism", "8")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .getOrCreate()
    )


def _functions():
    from pyspark.sql import functions

    return functions


def _ml_classes():
    from pyspark.ml.feature import StringIndexer
    from pyspark.ml.recommendation import ALS

    return ALS, StringIndexer


def _write_json(path: Path, payload: dict[str, list[dict[str, float | str]]]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def _prepare_hadoop_env():
    import os
    import sys
    from pyspark.sql import SparkSession

    HADOOP_HOME = r"D:\HadoopFake"
    HADOOP_BIN = rf"{HADOOP_HOME}\bin"

    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
    os.environ["HADOOP_HOME"] = HADOOP_HOME
    os.environ["hadoop.home.dir"] = HADOOP_HOME
    os.environ["PATH"] = HADOOP_BIN + ";" + os.environ["PATH"]
