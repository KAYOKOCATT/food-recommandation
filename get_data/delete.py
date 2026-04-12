import os

try:
        os.remove('food.csv')
        print("已成功删除food.csv文件")
except Exception as e:
        print(f"删除food.csv文件失败: {str(e)}")