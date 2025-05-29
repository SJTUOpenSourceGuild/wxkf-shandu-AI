import PyPDF2

def readPDF(path):
    # 打开 PDF 文件（注意使用二进制读取模式）
    with open(path, 'rb') as file:
        try:
            # 创建 PDF 读取对象
            pdf_reader = PyPDF2.PdfReader(file)
    
            # 获取总页数
            num_pages = len(pdf_reader.pages)
    
            # 逐页提取文本
            res = ""
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                res += text
            return res
        except Exception as e:
            return None
    return None

