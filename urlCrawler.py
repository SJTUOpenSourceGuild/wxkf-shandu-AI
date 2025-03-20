import requests
from bs4 import BeautifulSoup, Comment
from urllib.parse import urljoin
import os

import scrapy

def fetch_and_parse(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # 自动抛出 HTTP 错误
        
        # 处理编码
        response.encoding = response.apparent_encoding
        html_content = response.text
        
        # 解析 HTML
        soup = BeautifulSoup(html_content, "html.parser")
        return soup
    except requests.exceptions.RequestException as e:
        print(f"请求异常：{e}")
        return None



def parse(response):
    print(response)

def start_requests(url):
    res = scrapy.Request(url=url)
    print(res)


if __name__ == "__main__":
    start_requests("https://docs.scrapy.org/en/latest/intro/tutorial.html")
