import requests
from bs4 import BeautifulSoup, Comment
from urllib.parse import urljoin
import os

"""
@Params:
   * html: 输入时response = requests.get(url, headers=headers),response.text
   * article_url: 公众号文章的url
"""
def replace_img_with_link(html, article_url):
    soup = BeautifulSoup(html, 'html.parser')
    
    # 找到正文容器（根据实际页面调整选择器）
    content_div = soup.find('div', class_='rich_media_content')
    if not content_div:
        return "未找到正文内容"
    
    # 遍历所有元素（保留位置的关键）
    for element in content_div.find_all(True):
        if element.name == 'img':
            # 提取图片URL（优先data-src，其次src）
            img_url = element.get('data-src') or element.get('src')
            if img_url:
                # 转换为绝对URL
                full_url = urljoin(article_url, img_url)
                # 替换为链接文本（保留原位置）
                element.replace_with(f"[图片链接: {full_url}]")
        elif element.name == 'br':
            # 保留换行符（避免文本粘连）
            element.insert_after('\n')
    
    # 清理注释等无用内容
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    
    return content_div.get_text(strip=False, separator='\n')


"""
获取指定url的公众号文章信息
@Params:
    * url: 微信公众号文章地址
@Returns:
    * error_code: 0表示获取成功，否则表示获取失败
    * { author: 文章作者, publish_time: 发布时间, content_html: 文章内容部分的html, parsed_content: 解析后的文章内容}
"""
def getWechatArticalContentWithImageLink(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    response = requests.get(url, headers=headers)
    res = {}
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('h1', class_='rich_media_title')
        if title:
            res["title"] = title.get_text(strip=True, separator="\n")

        content_html = soup.find('div', class_='rich_media_content')
        if content_html:
            res["content_html"] = content_html
            res["parsed_content"] = content_html.get_text(strip=True, separator='\n')

        infoDiv = soup.find('div', class_="rich_media_meta_list")

        author = infoDiv.find('span', class_='rich_media_meta rich_media_meta_text')
        if author:
            res["author"]  = author.get_text(strip=True, separator="\n")

        nickname_span = infoDiv.find('span', class_='rich_media_meta rich_media_meta_nickname')
        nickname = nickname_span.find("a")
        if nickname:
            res["nickname"] = nickname.get_text(strip=True, separator="\n")
        return 0, res
        
    else:
        return -1, res

def downloadImages(soup):
    images = soup.find_all('img', class_='rich_pages')  # 注意：类名可能变化！

    # 2. 查找所有图片标签（微信图片通常包含在特定class中）
    if not images:
        print("未找到图片")
        return []

    # 3. 创建保存图片的目录
    save_dir = 'wechat_images'
    os.makedirs(save_dir, exist_ok=True)

    # 4. 遍历并下载图片
    for idx, img in enumerate(images):
        img_url = img.get('data-src') or img.get('src')  # 微信图片可能用data-src属性
        print(img_url)
        if not img_url:
            print(f"第 {idx+1} 张图片未找到URL")
            continue

        # 处理相对路径（例如：//mmbiz.qpic.cn/... 或 /path/to/img.jpg）
        full_url = urljoin(url, img_url)

        try:
            # 下载图片（需携带Referer反防盗链）
            img_headers = headers.copy()
            img_headers['Referer'] = url  # 关键：绕过微信图片防盗链
            img_response = requests.get(full_url, headers=img_headers, stream=True)
            img_response.raise_for_status()

            # 生成文件名（可从URL提取或自定义）
            file_ext = os.path.splitext(full_url)[-1].split('?')[0]  # 提取扩展名
            file_name = os.path.join(save_dir, f'image_{idx+1}{file_ext}')

            # 保存图片
            with open(file_name, 'wb') as f:
                for chunk in img_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"已保存：{file_name}")

        except Exception as e:
            print(f"下载失败（{full_url}）: {str(e)}")

# 示例使用
url = 'http://mp.weixin.qq.com/s?__biz=Mzk0MjYwOTQxNg==&mid=2247486729&idx=1&sn=d124c9d3a78ea4820b337794964a41e8&chksm=c3fc8e0fe3824a6ab1bddda8e6ee8de182578d0bfd6cb14795e4f96e2bdf6923a16240a678fe&mpshare=1&scene=1&srcid=0319mKvnfhdff4fMd4r8XNWW&sharer_shareinfo=82fd9feff5c3b4e459fe058609cd282f&sharer_shareinfo_first=82fd9feff5c3b4e459fe058609cd282f#rd'
url2 = "https://blog.csdn.net/luolinyin/article/details/121424135"

if __name__ == "__main__":
    err_code, res = getWechatArticalContentWithImageLink(url)
    print(res)

