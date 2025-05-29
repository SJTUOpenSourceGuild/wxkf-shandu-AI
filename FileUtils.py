from PDFUtils import readPDF
from WordUtils import read_docx, read_doc_by_antiword, read_txt_safe
from typing import Optional
import os
import pathlib

def read_file(file_path: str) -> Optional[str]:
    """
    通用文件读取入口函数
    支持格式：.pdf, .docx, .doc, .txt
    """
    # 检查文件有效性
    if not validate_file(file_path):
        return None

    # 获取小写后缀名
    suffix = pathlib.Path(file_path).suffix.lower()
    
    # 调度器映射
    handler_map = {
        '.pdf': readPDF,
        '.docx': read_docx,
        '.doc': read_doc_by_antiword,
        '.txt': read_txt_safe
    }

    # 选择处理函数
    handler = handler_map.get(suffix)
    if not handler:
        print(f"不支持的文件格式: {suffix}")
        return None

    try:
        return handler(file_path)
    except Exception as e:
        print(f"文件读取失败: {str(e)}")
        return None

def validate_file(file_path: str) -> bool:
    """文件验证基础检查"""
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return False
    if not os.path.isfile(file_path):
        print(f"路径不是文件: {file_path}")
        return False
    if os.path.getsize(file_path) == 0:
        print("警告：文件为空")
    return True

if __name__ == "__main__":
    files = [
        "./logs/个人简历2全面的.pdf",         # PDF文件
        "test.docx",      # DOCX文件
        "test2.doc",   # DOC文件
        "test.txt",          # 文本文件
        "image.png",          # 不支持格式
        "nonexistent.txt"     # 不存在文件
    ]

    for file in files:
        print(f"\n正在处理 {file}:")
        content = read_file(file)
        if content:
            print(f"前50字符预览: {content[:50].strip()}...")
