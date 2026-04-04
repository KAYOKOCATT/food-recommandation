import pandas as pd

data = pd.read_csv('food.csv',encoding='utf-8-sig')
data.dropna(inplace=True)#删除空值
data.drop_duplicates(subset=['标题'],keep='first',inplace=True)#删除重复值
data['描述'] = data['描述'].str.replace(r'[\\]','',regex=True)#删除换行符
data['描述'] = data['描述'].str.strip()#删除空格
data.to_csv('food1.csv',encoding='utf-8-sig',index=False)
print('清洗完成')

