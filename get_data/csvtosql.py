import random
from sqlite3 import connect

import pandas as pd
import pymysql

def run_sql():
    connection = pymysql.connect(
        host='localhost', 
        user='root', 
        password='123456', 
        port=3306, 
        database='food_recommend',
        charset='utf8mb4'
        )
    cursor = connection.cursor()
    df=pd.read_csv('food1.csv', encoding='utf-8')
    
    for i in range(df.shape[0]):
        data =df.iloc[i] #获取每一行的数据
        price_random = random.randint(30, 100)
        
        description = str(data['描述'])
        if len(description) > 255:
            description = description[:255]
        data1= (data['标题'],data['类型'],description,data['图片'],price_random)
        sql ="insert into myapp_foods(foodname,foodtype,recommend,imgurl,price) values" +str(data1)+";"
        
        try:
            cursor.execute(sql)
            connection.commit()
        except Exception as e:
            print(f" 插入第{i+1}条数据失败：{str(e)}")
            connection.rollback()
    cursor.close()
    connection.close()

run_sql()