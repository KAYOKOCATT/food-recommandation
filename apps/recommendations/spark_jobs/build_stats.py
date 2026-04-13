from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from typing import Any

os.environ['PYSPARK_PYTHON'] = sys.executable
os.environ['PYSPARK_DRIVER_PYTHON'] = sys.executable

def build_yelp_spark_stats(
    *,
    data_dir: str | Path,
    output_dir: str | Path,
    top_k: int = 10,
    app_name: str = "sc_food_rec-yelp-stats",
) -> dict[str, Path]:
    """Build Yelp aggregate statistics with Spark SQL and persist them as JSON files."""
    spark = _create_spark_session(app_name)
    try:
        data_path = Path(data_dir)
        business_path = data_path / "yelp_academic_dataset_business.json"
        review_path = data_path / "yelp_academic_dataset_review.json"
        if not business_path.exists():
            raise FileNotFoundError(f"Business file not found: {business_path}")
        if not review_path.exists():
            raise FileNotFoundError(f"Review file not found: {review_path}")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Read Yelp JSONL with Spark so the heavy scan and aggregation stay in the batch layer.
        business_df = spark.read.json(str(business_path)).select(
            "business_id",
            "name",
            "city",
            "state",
            "categories",
            "stars",
            "review_count",
            "is_open",
        )
        review_df = spark.read.json(str(review_path)).select(
            "business_id",
            "stars",
            "date",
        )

        functions = _functions()
        restaurant_df = business_df.filter(
            functions.col("categories").rlike("(?i)Restaurants|Cafe|Cafes")
        )
        review_with_month = review_df.withColumn(
            "year_month",
            functions.substring("date", 1, 7),
        )

        historical_hot = (
            restaurant_df.select(
                "business_id",
                "name",
                "city",
                "state",
                "stars",
                "review_count",
            )
            .orderBy(functions.desc("review_count"), functions.desc("stars"), "name")
            .limit(max(int(top_k), 1))
        )

        city_top = (
            restaurant_df.filter(functions.col("city").isNotNull() & (functions.col("city") != ""))
            .withColumn(
                "city_rank",
                functions.row_number().over(
                    _window().partitionBy("city").orderBy(
                        functions.desc("review_count"),
                        functions.desc("stars"),
                        functions.asc("name"),
                    )
                ),
            )
            .filter(functions.col("city_rank") <= max(int(top_k), 1))
            .orderBy("city", "city_rank")
        )

        monthly_stats = (
            review_with_month.filter(functions.col("year_month").isNotNull())
            .groupBy("year_month")
            .agg(
                functions.count("*").alias("review_count"),
                functions.round(functions.avg("stars"), 4).alias("avg_stars"),
            )
            .orderBy("year_month")
        )

        outputs = {
            "hot": output_path / "yelp_spark_hot.json",
            "city_top": output_path / "yelp_spark_city_top.json",
            "monthly_stats": output_path / "yelp_spark_monthly_stats.json",
        }
        _write_json(outputs["hot"], _collect_rows(historical_hot))
        _write_json(outputs["city_top"], _collect_rows(city_top))
        _write_json(outputs["monthly_stats"], _collect_rows(monthly_stats))
        return outputs
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


def _window():
    from pyspark.sql import Window

    return Window


def _collect_rows(dataframe) -> list[dict[str, Any]]:
    return [
        row.asDict(recursive=True)
        for row in dataframe.toLocalIterator()
    ]


def _write_json(path: Path, payload: list[dict[str, Any]]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
