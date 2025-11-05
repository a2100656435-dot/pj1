#import hashlib, os, re

def scan_file(path):
    """简单文本提取 + 基础扫描"""
    # 读取文件内容
    with open(path, 'rb') as f:
        data = f.read()

    # 尝试解码为文本
    text = data.decode(errors="ignore")

    # 提取网址
    urls = re.findall(r'http[s]?://[^\s"\']+', text)

    # 计算哈希
    sha = hashlib.sha256(data).hexdigest()

    # 返回扫描结果
    result = {
        "file_name": os.path.basename(path),
        "file_hash": sha,
        "url_count": len(urls),
        "urls": urls[:5],  # 只取前5个演示
        "has_login_word": any(word in text.lower() for word in ["login", "verify", "password"]),
        "text_extract": text[:1000]  # 提取前1000个字符展示
    }

    return result
