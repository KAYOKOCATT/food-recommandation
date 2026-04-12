from pathlib import Path

from apps.foods.ingestion import crawl_to_csv

def main():
    url_input = input("请输入要爬取的网站：").strip()
    num = int(input("请输入要爬取的页数：").strip())
    result = crawl_to_csv(url_input, num, Path("food.csv"))
    print(f"完成，共写入 {result.row_count} 条数据到 {result.csv_path}")

if __name__ == "__main__":
    main()
