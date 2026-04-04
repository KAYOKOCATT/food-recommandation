import requests 
from lxml import html
import csv
import os.path

etree = html.etree
#打开csv文件没有则创建
if not os.path.exists('food.csv'):
    fp = open('food.csv','a+',encoding='utf-8-sig',newline='')
    csv_writer = csv.writer(fp)
    csv_writer.writerow(['图片','标题','描述','作者','收藏数量','评论数量','类型'])
else:
    fp =open('food.csv','a+',encoding='utf-8-sig',newline='')
    csv_writer= csv.writer(fp)

#输入要爬取的网站,以/结尾
url_input = input('请输入要爬取的网站：').strip()
if not url_input.endswith('/'):
    url_input = url_input + '/'
#输入要爬取的页数
num = int(input('请输入要爬取的页数：').strip())
#循环爬取
for i in range(num):
    #模拟浏览器请求
    headers ={
        'user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0'
    }
    #获取页面
    url = f'{url_input}?page={i+1}'
    page_text =requests.get(url=url,headers=headers).text
    #Utf-8编码
    html.encoding = 'utf-8'
    #将页面转化成树状结构
    tree = etree.HTML(page_text)
    #解析数据
    li_list = tree.xpath('//ul[@class="menu_list"][1]/li')
    type_list = tree.xpath('//*[@class="all_article_header"]/h1/text()')
    type = type_list[0] if type_list else '其他'
    
    for li in li_list:
        try:
            imgurl = li.xpath(".//a/div/img/@src")[0]
            title = li.xpath('.//div[@class="txt"]/a/h4/text()')[0]
            describe =li.xpath('.//div[@class="txt"]/a/p/text()')[0]
            author =li.xpath('.//div[@class="writer"]/a/text()')[0]
            collect =li.xpath('.//div[@class="list_collect"]/span/text()')[0]
            comment =li.xpath('.//div[@class="praise"]/span/text()')[0]
            csv_writer.writerow([imgurl,title,describe,author,collect,comment,type])
        except Exception as e:
            
            print(f'这条数据爬取失败，错误：{e}')
fp.close()