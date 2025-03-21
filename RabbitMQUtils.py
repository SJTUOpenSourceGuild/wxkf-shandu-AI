import pika
from threading import Thread
import threading
import json
import time
import os
import uuid
from WXBizJsonMsgCrypt import WXBizJsonMsgCrypt
import xmltodict
from wechatapi import WechatApi, WECHAT_API_TYPE, fetchWechatMsg, sendWechatMsgTouser, sendWechatMsgTouserOnEvent, getUserinfo
from WechatMysqlOps import WechatMysqlOps
from wechatCrawler import getWechatArticalContentWithImageLink
from utils import is_url
from urlCrawler import fetch_and_parse
from wechatLKERequest import askAI
import datetime
from Logger import logger

class wechatKefuConsumer:
    def __init__(self, queue_name = "hello_durable", prefetch_num = 2):
        self.sToken = os.environ['WECHAT_TOKEN']
        self.sEncodingAESKey = os.environ['WECHAT_AESKEY']
        self.sCorpID = os.environ['WECHAT_CORP_ID']
        self.connect(queue_name, prefetch_num)
        
    def connect(self, queue_name = "hello_durable", prefech_num = 2):
        credentials = pika.PlainCredentials(username=os.environ['RABBITMQ_USERNAME'], password=os.environ['RABBITMQ_PASSWORD'])

        connection = pika.BlockingConnection(pika.ConnectionParameters(os.environ['RABBITMQ_HOST'], os.environ['RABBITMQ_PORT'], credentials=credentials, heartbeat=30))
        self.channel = connection.channel()

        # 声明持久化队列
        # channel.queue_declare(queue='hello_durable', durable=True)
        self.channel.queue_declare(queue=queue_name, durable=True)

        # 每次最多处理一条消息（避免过载）
        self.channel.basic_qos(prefetch_count=prefech_num)

        self.channel.basic_consume(queue=queue_name, on_message_callback=self.on_message)
        logger.info(" [*] Waiting for tasks. To exit press CTRL+C")
        self.channel.start_consuming()

    def on_message(self,ch, method, properties, body):
        try:
            task_data = json.loads(body.decode())
            result = self.__process_task(task_data)
            if result:
                # 处理成功时才确认
                ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                """
                处理失败时拒绝并丢弃
                TODO: 本来想重新入队的，但发现重新入队后会马上被重新获取，可能出现一只循环处理同一个数据的问题，导致占用大量计算资源
                """
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                logger.warning("处理消息失败，放弃处理并丢弃消息")
        except Exception as e:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            logger.warning("处理消息时出错，放弃处理并丢弃消息" + str(e))

    def reconnect(self):
        pass
    def __decode_msg(self, data):
        wxcpt=WXBizJsonMsgCrypt(self.sToken,self.sEncodingAESKey,self.sCorpID)
    
        sReqNonce = data['nonce']
        sReqTimeStamp = data['timestamp']
        sReqMsgSig = data['sign']
        data_dict = xmltodict.parse(data['data'])
    
        sReqData = json.dumps(data_dict["xml"])
    
        return wxcpt.DecryptMsg( sReqData, sReqMsgSig, sReqTimeStamp, sReqNonce)

    def __textMsgHandler(self, msg):
        if 'external_userid' not in msg:
            logger.warning("no external_userid in msg")
            return

        user_info_resp = getUserinfo([msg['external_userid']])

        if 'customer_list' not in user_info_resp:
            logger.warning("获取的用户信息错误")
            return

        customer_list = user_info_resp['customer_list']
        if len(customer_list) <= 0:
            logger.warning("获取到的用户数据为0个（应为1个）")
            return

        customer_info = customer_list[0]
        wechat_db_ops = WechatMysqlOps()
        wechat_db_ops.save_user_to_db(customer_info)
        wechat_db_ops.saveWechatTextMsg(customer_info, msg)

        if is_url(msg['text']['content']): # 如果文本整体是一个url，则特殊处理
            html =fetch_and_parse(msg['text']['content'])
            response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "你叫：" + customer_info['nickname'] +"，你刚刚发送了一个网址：" + html.title.text,sCorpID=self.sCorpID)
        else:
            response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "你叫：" + customer_info['nickname'] +"，你刚刚发送了：" + msg['text']['content'],sCorpID=self.sCorpID)

    def __linkMsgHandler(self, msg):
        # 链接
        if 'external_userid' not in msg:
            logger.warning("no external_userid in msg")
            return

        response = getUserinfo([msg['external_userid']])
        if 'customer_list' not in response:
            logger.warning("获取用户信息失败")


        customer_list = response['customer_list']
        if len(customer_list) <= 0:
            logger.warning("获取到的用户数量为0（应为1）")
            return

        customer_info = customer_list[0]
        wechat_db_ops = WechatMysqlOps()
        try:
            wechat_db_ops.save_user_to_db(customer_info)
        except Exception as e:
            logger.error("save_user_to_db failed")

        try:
            parsed_content = wechat_db_ops.saveWechatArticalMsg(customer_info, msg)
        except Exception as e:
            logger.error("saveWechatArticalMsg failed")


        try:
            ai_answer = askAI(parsed_content)
        except Exception as e:
            logger.error("askAI failed!")

        try:
            response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "《" + msg['link']['title'] +"》：\n" + ai_answer)
        except Exception as e:
            logger.error("sendWechatMsgTouser failed!")

    def __enterEventMsgHandler(self, msg):
        # 处理用户进入会话事件
        response = sendWechatMsgTouserOnEvent(msg['event']['welcome_code'],str(uuid.uuid4()).replace("-", "")[:32], "你叫：" + customer_info['nickname'] +"，欢迎光临",sCorpID=self.sCorpID)
        pass

    def __recallMsgEventMsgHandler(self, msg):
        # 处理用户撤回消息事件
        response = sendWechatMsgTouser(msg['event']['external_userid'], msg['event']['open_kfid'],str(uuid.uuid4()).replace("-", "")[:32], customer_info['nickname'] +"，你刚刚发送了什么？我没看见。",sCorpID=self.sCorpID)
        pass

    def __eventMsgHandler(self, msg):
        response = getUserinfo([msg['event']['external_userid']])
        customer_info = response['customer_list'][0]
        # 事件
        if msg['event']['event_type'] == 'enter_session':
            self.__enterEventMsgHandler(self, msg)
        elif msg['event']['event_type'] == 'user_recall_msg':
            self.__recallMsgEventMsgHandler(self, msg)
        elif msg['event']['event_type'] == 'msg_send_fail':
            # 消息发送失败
            pass

    def __process_task(self, data: dict):
        ret,sMsg= self.__decode_msg(data)
        if ret != 0:
            logger.error("解密回调数据错误，结果为" + str(ret))
            return False
        else: # 解密成功，继续处理
            decoded_dict = xmltodict.parse(sMsg)
            # 从微信服务器获取消息的具体数据
            msg_list = fetchWechatMsg(decoded_dict["xml"]["Token"], decoded_dict["xml"]["OpenKfId"], sCorpID=self.sCorpID)
            for msg in msg_list:
                if msg['msgtype'] == 'text':
                    self.__textMsgHandler(msg)
                elif msg['msgtype'] == 'link':
                    self.__linkMsgHandler(msg)
                elif msg['msgtype'] == 'event':
                    self.__eventMsgHandler(msg)
                else:
                   # 暂不支持
                   response = getUserinfo([msg['external_userid']])
                   customer_info = response['customer_list'][0]
                   response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],str(uuid.uuid4()).replace("-", "")[:32], customer_info['nickname'] +"，此消息类型暂不支持。",sCorpID=self.sCorpID)
    
            return True

if __name__ == '__main__':
    consumer = wechatKefuConsumer()
