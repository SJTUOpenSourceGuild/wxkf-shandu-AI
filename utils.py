from urllib.parse import urlparse

def is_url(url):
    try:
        result = urlparse(url)
        # 确保协议和网络位置存在，并且协议是http或https
        return all([result.scheme, result.netloc]) and result.scheme in {'http', 'https'}
    except:
        return False
