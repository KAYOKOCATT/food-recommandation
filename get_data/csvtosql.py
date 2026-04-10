import random
import os
from pathlib import Path

import pandas as pd
import pymysql


def run_sql(csv_path: str = "food.csv") -> None:
    connection = pymysql.connect(
        host=os.getenv('MYSQL_HOST', 'localhost'),
        user=os.getenv('MYSQL_USER', 'root'),
        password=os.getenv('MYSQL_PASSWORD', '5247'),
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
        values = (data['标题'], data['类型'], description, data['图片'], price_random)
        sql = """
            insert into myapp_foods(foodname, foodtype, recommend, imgurl, price)
            values (%s, %s, %s, %s, %s)
        """

        try:
            cursor.execute(sql, values)
            connection.commit()
        except Exception as e:
            print(f" 插入第{i+1}条数据失败：{str(e)}")
            connection.rollback()
    cursor.close()
    connection.close()


if __name__ == "__main__":
    run_sql()
