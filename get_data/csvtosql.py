from pathlib import Path

from apps.foods.ingestion import import_csv_to_foods


def run_sql(csv_path: str = "food.csv") -> None:
    result = import_csv_to_foods(Path(csv_path))
    print(f"已导入 {result.created_count} 条数据，来源文件：{result.csv_path}")


if __name__ == "__main__":
    run_sql()
