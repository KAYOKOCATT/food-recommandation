import random
import os
import re
from pathlib import Path

import pandas as pd
import pymysql


def run_sql(csv_path: str = "food.csv") -> None:
    connection = pymysql.connect(
        host=os.getenv('MYSQL_HOST', 'localhost'),
        user=os.getenv('MYSQL_USER', 'root'),
        password=os.getenv('MYSQL_PASSWORD', '123456'),
        port=int(os.getenv('MYSQL_PORT', '3306')),
        database=os.getenv('MYSQL_DATABASE', 'food_recommend'),
        charset='utf8mb4'
        )
    cursor = connection.cursor()
    df = pd.read_csv(Path(csv_path), encoding='utf-8')

    for i in range(df.shape[0]):
        data = df.iloc[i]  # 获取每一行的数据
        price_random = random.randint(30, 100)

        description = str(data['描述'])
        if len(description) > 255:
            description = description[:255]
        collect_count = parse_stat_count(data.get('收藏数量', 0))
        comment_count = parse_stat_count(data.get('评论数量', 0))
        values = (
            data['标题'],
            data['类型'],
            description,
            data['图片'],
            price_random,
            collect_count,
            comment_count,
        )
        sql = """
            insert into myapp_foods(
                foodname, foodtype, recommend, imgurl, price, collect_count, comment_count
            )
            values (%s, %s, %s, %s, %s, %s, %s)
        """

        try:
            cursor.execute(sql, values)
            connection.commit()
        except Exception as e:
            print(f" 插入第{i+1}条数据失败：{str(e)}")
            connection.rollback()
    cursor.close()
    connection.close()


def parse_stat_count(raw_value: object) -> int:
    text = "" if raw_value is None else str(raw_value).strip()
    if not text or text.lower() == "nan":
        return 0

    compact_text = text.replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)", compact_text)
    if match is None:
        return 0

    number = float(match.group(1))
    if "万" in compact_text:
        number *= 10000
    elif "千" in compact_text:
        number *= 1000
    return max(int(number), 0)


if __name__ == "__main__":
    run_sql()
