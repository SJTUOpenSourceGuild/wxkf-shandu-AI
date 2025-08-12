# -*- coding=utf-8
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from qcloud_cos.cos_exception import CosClientError, CosServiceError
import sys
import os
import logging
import requests


class TXCOSManager:
    def __init__(self):
        # 正常情况日志级别使用 INFO，需要定位时可以修改为 DEBUG，此时 SDK 会打印和服务端的通信信息
        #logging.basicConfig(level=logging.INFO, stream=sys.stdout)
        
        secret_id = os.environ['COS_SECRET_ID']     # 用户的 SecretId
        secret_key = os.environ['COS_SECRET_KEY']   # 用户的 SecretKey
        region = 'ap-shanghai'      # COS 支持的所有 region 列表参见 https://cloud.tencent.com/document/product/436/6224
        token = None                # 如果使用永久密钥不需要填入 token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见 https://cloud.tencent.com/document/product/436/14048
        scheme = 'https'           # 指定使用 http/https 协议来访问 COS，默认为 https，可不填
        config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Scheme=scheme)
        self.client = CosS3Client(config)

    def listAllFiles(self, bucketName, dirPrefix):
        response = self.client.list_objects(
            Bucket=bucketName,
            Prefix=dirPrefix
        )

    def uploadFile(self, file_path, bucketName, key = "test"):
        # 使用高级接口上传一次，不重试，此时没有使用断点续传的功能
        response = self.client.upload_file(
            Bucket=bucketName,
            Key=key,
            LocalFilePath=file_path,
            EnableMD5=False,
            progress_callback=None
        )

    def uploadFileWithRetry(self, file_path, bucketName, fileName,dirPrefix="", retryTime = 5):
        # 使用高级接口断点续传，失败重试时不会上传已成功的分块(这里重试10次)
        for i in range(0, retryTime):
            try:
                response = self.client.upload_file(
                Bucket=bucketName,
                Key=dirPrefix+fileName,
                LocalFilePath=file_path)
                print("success, ",response)
                break
            except CosClientError or CosServiceError as e:
                print("error, ",e)
                
    def downloadFile(self, target_file_path, bucketName, key):
        try:
            response = self.client.download_file(
                Bucket=bucketName,
                Key=key,
                DestFilePath=target_file_path
            )
            return True
        except Exception as e:
            print(e)
        return False

    def downloadFileWithRetry(self, target_file_path, bucketName, key, retryTime = 5):
        # 使用高级接口断点续传，失败重试时不会下载已成功的分块(这里重试10次)
        for i in range(0, retryTime):
            try:
                response = self.client.download_file(
                    Bucket=bucketName,
                    Key=key,
                    DestFilePath=target_file_path)
                return True
            except CosClientError or CosServiceError as e:
                print(e)
        return False

    def getObjectUrl(self, bucketName, key):
        try:
            url = self.client.get_object_url(
                    Bucket=bucketName,
                    Key=key
                    )
            return url;
        except Exception as e:
            print(e)
        return None


    """
    返回指定文件的大小（单位：字节，byte）
    """
    def getFileLength(self, bucketName, key):
        try:
            response = self.client.head_object(
                    Bucket=bucketName,
                    Key=key
                    )
            return int(response['Content-Length'])
        except Exception as e:
            print(e)
            return 0
        return 0

    def downloadFileFromUrl(self, url, filename = None):
        print(url)
        try:
            response = requests.get(url, stream=True)
            print(response)
            if response.status_code == 200:
                if filename == None:
                    filename = os.path.basename(url.split('?')[0])  # 去除URL参数
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                print(f"文件已下载: {filename}")
            else:
                print(f"下载失败，状态码: {response.status_code}")
        except Exception as e:
            print(f"错误: {str(e)}")

