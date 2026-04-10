import csv
import os
import re
import requests
from lxml import etree
from urllib.parse import urljoin

BASE_DOMAIN = "https://www.xiaochushuo.com"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

def clean_text(text):
    """清洗文本：去掉多余空白、换行"""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def get_page_html(url):
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return resp.text

def parse_page(page_text, page_url):
    tree = etree.HTML(page_text)

    # 分类名称，如：云南
    type_name = tree.xpath('string(//*[@id="listtitle"])')
    type_name = clean_text(type_name) if type_name else "其他"

    # 菜谱列表
    li_list = tree.xpath('//ul[@class="menu_list"]/li')

    data = []
    for li in li_list:
        try:
            # 菜谱链接
            recipe_href = li.xpath('./a/@href')
            recipe_url = urljoin(BASE_DOMAIN, recipe_href[0]) if recipe_href else ""

            # 图片
            imgurl = li.xpath('.//div[contains(@class,"img")]//img/@src')
            imgurl = imgurl[0].strip() if imgurl else ""

            # 标题：用 string(.) 获取完整文本，避免 span 标签导致标题缺失
            title = li.xpath('string(.//div[@class="txt"]/a/h4)')
            title = clean_text(title)

            # 描述
            describe = li.xpath('string(.//div[@class="txt"]/a/p[@class="pbm"])')
            describe = clean_text(describe)

            # 作者名
            author = li.xpath('string(.//div[@class="writer"]/a)')
            author = clean_text(author)

            # 作者主页
            author_href = li.xpath('.//div[@class="writer"]/a/@href')
            author_url = urljoin(BASE_DOMAIN, author_href[0]) if author_href else ""

            # 收藏数量
            collect = li.xpath('string(.//div[@class="list_collect"]/span)')
            collect = clean_text(collect)

            # 评论数量
            comment = li.xpath('string(.//div[@class="praise"]/span)')
            comment = clean_text(comment)

            data.append([
                type_name,
                title,
                describe,
                author,
                author_url,
                collect,
                comment,
                imgurl,
                recipe_url,
                page_url
            ])

        except Exception as e:
            print(f"这条数据解析失败，错误：{e}")

    return data

def save_to_csv(filename, rows):
    file_exists = os.path.exists(filename)

    with open(filename, 'a', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                '类型', '标题', '描述', '作者', '作者主页',
                '收藏数量', '评论数量', '图片', '菜谱链接', '来源页'
            ])
        writer.writerows(rows)

def main():
    url_input = input("请输入要爬取的网站：").strip()
    if not url_input.endswith('/'):
        url_input += '/'

    num = int(input("请输入要爬取的页数：").strip())

    all_rows = []

    for i in range(1, num + 1):
        if i == 1:
            url = url_input
        else:
            url = f"{url_input}?page={i}"

        print(f"正在爬取第 {i} 页：{url}")

        try:
            page_text = get_page_html(url)
            rows = parse_page(page_text, url)
            print(f"第 {i} 页获取到 {len(rows)} 条数据")
            all_rows.extend(rows)
        except Exception as e:
            print(f"第 {i} 页爬取失败：{e}")

    save_to_csv("food.csv", all_rows)
    print(f"完成，共写入 {len(all_rows)} 条数据到 food.csv")

if __name__ == "__main__":
    main()