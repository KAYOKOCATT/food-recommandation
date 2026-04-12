from pathlib import Path

from apps.foods.ingestion import delete_csv

if delete_csv(Path("food.csv")):
    print("已成功删除food.csv文件")
else:
    print("food.csv文件不存在，无需删除")
