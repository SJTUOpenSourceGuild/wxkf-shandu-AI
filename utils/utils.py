from urllib.parse import urlparse
import hashlib

def calculate_file_hash(file_path, algorithm='sha256', chunk_size=4096):
    """
    计算文件的哈希值
    :param file_path: 文件路径
    :param algorithm: 哈希算法（默认 sha256）
    :param chunk_size: 分块读取大小（优化大文件处理）
    :return: 十六进制哈希字符串
    """
    hash_object = hashlib.new(algorithm)
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            hash_object.update(chunk)
    return hash_object.hexdigest()

def is_url(url):
    try:
        result = urlparse(url)
        # 确保协议和网络位置存在，并且协议是http或https
        return all([result.scheme, result.netloc]) and result.scheme in {'http', 'https'}
    except:
        return False

"""
按照字符串的字节大小（不是字符大小）截取字符串
@Params:
    * s：需要截取的字符串
    * max_bytes：执行截取的字节大小
"""
def truncate_string_to_bytes(s: str, max_bytes: int, encoding: str = 'utf-8') -> str:
    # 将字符串编码为字节序列
    encoded = s.encode(encoding)
    # 截取前max_bytes个字节
    truncated_encoded = encoded[:max_bytes]
    # 解码并忽略无效字节（避免UnicodeDecodeError）
    return truncated_encoded.decode(encoding, errors='ignore')


if __name__ == "__main__":
    # 使用示例
    original_str = "这是一个测试字符串，用于检查截取前128字节的功能。" * 10  # 构造长字符串
    #truncated_str = truncate_string_to_bytes(original_str, 128)
    #print(f"截取后的字符串: {truncated_str}")
    #print(f"截取后的字节长度: {len(truncated_str.encode('utf-8'))}")  # 验证字节长度

    hash_str = calculate_file_hash("./logs/test2.pdf")
    print(hash_str)


