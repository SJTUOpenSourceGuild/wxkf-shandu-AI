import pika
from threading import Thread
import threading
import json
import time
import os
import uuid
from WXBizJsonMsgCrypt import WXBizJsonMsgCrypt
import xmltodict
from wechatapi import WechatApi, WECHAT_API_TYPE, fetchWechatMsg, sendWechatMsgTouser, sendWechatMsgTouserOnEvent, getUserinfo,getLastClickedWechatArticalInfo,uploadFileFromUrl, uploadFile,getMsgSendCount,msgSendCountClear,msgSendCountIncrease,deleteLastClickedWechatArticalInfo
from WechatMysqlOps import WechatMysqlOps
from wechatCrawler import getWechatArticalContent
from utils import is_url,truncate_string_to_bytes
from urlCrawler import fetch_and_parse
from wechatLKERequest import askAI
import datetime
from Logger import logger

WechatKFCallBackQueueName = "wechat_kefu_callback_queue"
ClickedWechatArticalInfoQueueName = "clicked_wechat_artical_info_queue"
WechatKFMsgSendMaxTime = 5

def sendWechatArticalInfo(title, desc, url, post_image_url, external_userid, open_kfid, sCorpID):
    res = uploadFileFromUrl(post_image_url)
    tmp_post_id = ""
    if int(res['errcode']) != 0:
        logger.error("upload post image failed!")
        return {"errcode": -1, "errmsg":"upload post image failed!"}
    else:
        tmp_post_id = res['media_id']

    data = {
        "title" : truncate_string_to_bytes(title, 128),
        "desc" : truncate_string_to_bytes(desc,512),
        "url" : truncate_string_to_bytes(url,2048),
        "thumb_media_id": tmp_post_id}
    try:
        response = sendWechatMsgTouser(external_userid, open_kfid,str(uuid.uuid4()).replace("-", "")[:32], 'link', data, sCorpID=sCorpID)
    except Exception as e:
        logger.error("send wechat message to user failed!")
    return response

def joinTestGroup(msg, unionid, sCorpID):
    res = uploadFile("invite.jpeg")
    if int(res['errcode']) != 0:
        logger.error("upload post image failed!")
        return
    else:
        tmp_post_id = res['media_id']
    response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "image", {"media_id": tmp_post_id},sCorpID=sCorpID)
    msgSendCountIncrease(unionid)


def activemenuHandler(msg, unionid, sCorpID):
    res = getLastClickedWechatArticalInfo(unionid)
    if res == None:
        response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "text", {"content": "激活成功！"},sCorpID=sCorpID)
        msgSendCountIncrease(unionid)
    else:
        send_res = sendWechatArticalInfo(res['title'], res['desc'], res['url'], res['image_url'], msg['external_userid'], msg['open_kfid'], sCorpID)
        if int(send_res['errcode']) != 0:
            logger.error("activemenu Handler send wechat artical info failed! err_msg = " + send_res['errmsg'])
        else:
            deleteLastClickedWechatArticalInfo(unionid)
        msgSendCountIncrease(unionid)

def usageTutorialMenuHandler(msg, unionid, sCorpID):
    response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "text", {"content": "转发微信公众号给我，我会帮您快速理解文章～"},sCorpID=sCorpID)
    msgSendCountIncrease(unionid)

"""
收到菜单消息时，用消息内容获取处理方法
"""
menuString2Handler = {
        "点击查看如何使用":usageTutorialMenuHandler,
        "激活会话":activemenuHandler,
        "加入内测群":joinTestGroup
        }

"""
目前没有使用
"""
class wechatArticalInfoClickConsumer:
    def __init__(self, queue_name = ClickedWechatArticalInfoQueueName, prefetch_num = 2):
        self.sToken = os.environ['WECHAT_TOKEN']
        self.sEncodingAESKey = os.environ['WECHAT_AESKEY']
        self.sCorpID = os.environ['WECHAT_CORP_ID']
        self.connect(queue_name, prefetch_num)

    def start(self):
        logger.info(" [*] Waiting for tasks. To exit press CTRL+C")
        self.channel.start_consuming()
        
    def connect(self, queue_name = ClickedWechatArticalInfoQueueName, prefech_num = 2):
        credentials = pika.PlainCredentials(username=os.environ['RABBITMQ_USERNAME'], password=os.environ['RABBITMQ_PASSWORD'])

        connection = pika.BlockingConnection(pika.ConnectionParameters(os.environ['RABBITMQ_HOST'], os.environ['RABBITMQ_PORT'], credentials=credentials, heartbeat=30))
        self.channel = connection.channel()

        # 声明持久化队列
        # channel.queue_declare(queue='hello_durable', durable=True)
        self.channel.queue_declare(queue=queue_name, durable=True)

        # 每次最多处理一条消息（避免过载）
        self.channel.basic_qos(prefetch_count=prefech_num)

        self.channel.basic_consume(queue=queue_name, on_message_callback=self.on_message)

    def on_message(self,ch, method, properties, body):
        try:
            task_data = json.loads(body.decode())
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            logger.warning("处理消息时出错，放弃处理并丢弃消息" + str(e))


class wechatKefuConsumer:
    def __init__(self, queue_name = WechatKFCallBackQueueName, prefetch_num = 2):
        self.sToken = os.environ['WECHAT_TOKEN']
        self.sEncodingAESKey = os.environ['WECHAT_AESKEY']
        self.sCorpID = os.environ['WECHAT_CORP_ID']
        self.connect(queue_name, prefetch_num)

    def start(self):
        logger.info(" [*] Waiting for tasks. To exit press CTRL+C")
        self.channel.start_consuming()
        
    def connect(self, queue_name = WechatKFCallBackQueueName, prefech_num = 2):
        credentials = pika.PlainCredentials(username=os.environ['RABBITMQ_USERNAME'], password=os.environ['RABBITMQ_PASSWORD'])

        connection = pika.BlockingConnection(pika.ConnectionParameters(os.environ['RABBITMQ_HOST'], os.environ['RABBITMQ_PORT'], credentials=credentials, heartbeat=30))
        self.channel = connection.channel()

        # 声明持久化队列
        self.channel.queue_declare(queue=queue_name, durable=True)

        # 每次最多处理一条消息（避免过载）
        self.channel.basic_qos(prefetch_count=prefech_num)

        self.channel.basic_consume(queue=queue_name, on_message_callback=self.on_message)

    def __getUserInfo(self, external_userid):
        user_info_resp = getUserinfo([external_userid])
        if 'customer_list' not in user_info_resp:
            logger.warning("获取的用户信息错误")
            return

        customer_list = user_info_resp['customer_list']
        if len(customer_list) <= 0:
            logger.warning("获取到的用户数据为0个（应为1个）")
            return

        customer_info = customer_list[0]
        return customer_info


    def on_message(self,ch, method, properties, body):
        # 收到消息后清空发送消息数量
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

        customer_info = self.__getUserInfo(msg['external_userid'])
        wechat_db_ops = WechatMysqlOps()
        wechat_db_ops.save_user_to_db(customer_info)

        if 'menu_id' in msg['text']:
            # 通过点击菜单选项发送的文字
            menuString2Handler[msg['text']['content']](msg, customer_info['unionid'],self.sCorpID)
            return

        if is_url(msg['text']['content']): # 如果文本整体是一个url，则特殊处理
            html =fetch_and_parse(msg['text']['content'])
            response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "text", {"content": "你叫：" + customer_info['nickname'] +"，你刚刚发送了一个网址：" + html.title.text},sCorpID=self.sCorpID)
            if int(response['errcode']) == 0:
                msgSendCountIncrease(customer_info['unionid'])
        else:
            #response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "text", {"content": "你叫：" + customer_info['nickname'] +"，你刚刚发送了：" + msg['text']['content']},sCorpID=self.sCorpID)
            response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "text", {"content": "目前暂不支持文字问答，敬请期待！"},sCorpID=self.sCorpID)

            msgSendCountIncrease(customer_info['unionid'])


            if int(response['errcode']) == 0:
                msgSendCountIncrease(customer_info['unionid'])

    def __linkMsgHandler(self, msg):
        # 链接
        if 'external_userid' not in msg:
            logger.warning("no external_userid in msg")
            return

        customer_info = self.__getUserInfo(msg['external_userid']) # 每次都要获取用户信息吗？
        wechat_db_ops = WechatMysqlOps()
        try:
            if wechat_db_ops.ifUserExist(customer_info['unionid']) <= 0:
                wechat_db_ops.save_user_to_db(customer_info)
        except Exception as e:
            logger.error("save_user_to_db failed")

        artical_msg_id = -1
        artical_id = -1

        # 首先查看数据库中是否有该文章
        if wechat_db_ops.ifWechatArticalExistByUrl(msg['link']['url']) > 0:
            # 已经存在文章
            logger.info("artical already exist")
            artical = wechat_db_ops.getWechatArticalByUrl(msg['link']['url'])
            # TODO: 目前只能通过查看表的结构获取对应列，后续考虑优化
            artical_content = artical[9]
            artical_id = artical[0]
            ai_answer = artical[10]
        else:
            # 新文章
            logger.info("new artical")
            err_code, info_dict = getWechatArticalContent(msg['link']['url'])
            artical_id = wechat_db_ops.saveWechatArtical(info_dict, msg)
            artical_content = info_dict['parsed_content']
            if err_code != 0:
                logger.error("获取公众号文章数据失败")
                return
            try:
                ai_answer = askAI(artical_content)
            except Exception as e:
                logger.error("askAI failed!")

        try:
            artical_msg_id = wechat_db_ops.saveWechatArticalMsg(customer_info, msg, int(artical_id))
        except Exception as e:
            logger.error("saveWechatArticalMsg failed, error = " + str(e))

        try:
            content = "《" + msg['link']['title'] +"》：\n" + ai_answer
            menu_list = []
            if len(content.encode('utf-8')) > 1024:
                content = content.encode('utf-8')[:1000].decode('utf-8', 'ignore') + "……\n"
            menu_list.append({ "type":"miniprogram", "miniprogram": {"appid":"wx394fd56312f409e6","pagepath":"pages/index/index.html?target_msg_id=" + str(artical_msg_id),"content":"点击去小程序查看更多：《"+ msg['link']['title'] +"》"}})
            menu_list.append({"type":"text", "text":{"content":"\n\n"}})
            menu_list.append({"type": "click", "click": {"id": "101", "content": "激活会话"}})
            response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "msgmenu", {"head_content":content,"list":menu_list},sCorpID=self.sCorpID)
            msgSendCountIncrease(customer_info['unionid'])
        except Exception as e:
            logger.error("sendWechatMsgTouser failed!")

        if artical_id > 0 and not wechat_db_ops.setWechatArticalSummary(artical_id, ai_answer):
            logger.error("update artical summary failed!")

    def __sendWechatArticalInfo(self, title, desc, url, post_image_url, external_userid, open_kfid, unionid):
        send_res = sendWechatArticalInfo(title, desc, url, post_image_url, external_userid, open_kfid, self.sCorpID)
        if int(send_res['errcode']) != 0:
            logger.error("activemenu Handler send wechat artical info failed! err_msg = " + send_res['errmsg'])
        else:
            deleteLastClickedWechatArticalInfo(unionid)
        return

    def __enterEventMsgHandler(self, msg, customer_info):
        if not 'unionid' in customer_info:
            logger.error("no unionid in customer_info")
            return
        needSendWechatInfo = False
        res = getLastClickedWechatArticalInfo(customer_info["unionid"])

        if res == None:
            # 没有点击信息
            pass
        else:
            # 存在点击
            needSendWechatInfo = True

        # 处理用户进入会话事件
        if 'welcome_code' in msg['event']:
            # 可以发送欢迎语（TODO：提醒用户发送消息，可以发送菜单，方便用户激活对话）
            """
            包含welcome_code的条件：用户在过去48小时里未收过欢迎语，且未向客服发过消息
            可能分为2种情况：
            1. 用户第一次使用，需要讲解如何使用
            2. 用户已经用过，但距离上次发送消息超过48小时了

            两种情况下都要提示用户激活会话（否则可能导致消息发送失败）
            """
            welcome_menu = []
            welcome_menu.append({"type":"miniprogram", "miniprogram": {"appid":"wx394fd56312f409e6","pagepath":"pages/index/index.html","content":"点击进入微信小程序"}})
            welcome_menu.append({"type": "click", "click": {"id": "102", "content": "加入内测群"}})

            if needSendWechatInfo:
                welcome_menu.append({"type":"text", "text":{"content":"下方是您最近在小程序中点击查看的文章链接："}})
                welcome_menu.append({"type":"view","view": {
                    "url": res['url'],
                    "content": "《" +res['title'] + "》"
                }})
            else:
                welcome_menu.append({"type":"click","click": {
                    "id": "201",
                    "content": "点击查看如何使用"
                }})

            welcome_menu.append({"type":"text", "text":{"content":"\n"}})
            welcome_menu.append({"type":"text", "text":{"content": "\n请点击下方“激活会话”选项，否则后续会出现无法收到消息的情况："}})
            welcome_menu.append({"type": "click", "click": {"id": "101", "content": "激活会话"}})
            response = sendWechatMsgTouserOnEvent(msg['event']['welcome_code'],str(uuid.uuid4()).replace("-", "")[:32], 'msgmenu', {"head_content": "欢迎使用帮我读AI！\n帮我读AI：帮您快速阅读公众号文章！\n", "list": welcome_menu},sCorpID=self.sCorpID)
            msgSendCountIncrease(customer_info['unionid'])
        else:
            # 无权发送欢迎语的情况，直接发送消息（可能失败）
            if getMsgSendCount(customer_info['unionid']) == WechatKFMsgSendMaxTime - 1:
                # 只能发送最后一条消息了
                head_content = ""
                if needSendWechatInfo:
                    head_content = "点击下方“激活会话”选项，接受刚刚点击的文章："
                else:
                    head_content = "点击下方“激活会话”选项，以继续接受消息："
                welcome_menu = [{"type": "click", "click": {"id": "101", "content": "激活会话"}},{"type":"text", "text":{"content":"\n"}}]
                response = sendWechatMsgTouser(msg['event']['external_userid'],msg['event']['open_kfid'], str(uuid.uuid4()).replace("-", "")[:32], 'msgmenu', {"head_content": head_content, "list": welcome_menu,"tail_content": "⬆️点击上方“激活会话”选项"},sCorpID=self.sCorpID)
            else:
                self.__sendWechatArticalInfo(res['title'], res['desc'], res['url'], res['image_url'], msg['event']['external_userid'], msg['event']['open_kfid'], customer_info['unionid'])
                msgSendCountIncrease(customer_info['unionid'])

    def __recallMsgEventMsgHandler(self, msg):
        # 处理用户撤回消息事件
        response = sendWechatMsgTouser(msg['event']['external_userid'], msg['event']['open_kfid'],str(uuid.uuid4()).replace("-", "")[:32], customer_info['nickname'] +"，你刚刚发送了什么？我没看见。",sCorpID=self.sCorpID)

    def __eventMsgHandler(self, msg):
        customer_info = self.__getUserInfo(msg['event']['external_userid'])
        # 事件
        if msg['event']['event_type'] == 'enter_session':
            self.__enterEventMsgHandler(msg, customer_info)
        elif msg['event']['event_type'] == 'user_recall_msg':
            self.__recallMsgEventMsgHandler(msg)
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
                    customer_info = self.__getUserInfo(msg['external_userid'])
                    msgSendCountClear(customer_info['unionid'])
                    self.__textMsgHandler(msg)
                elif msg['msgtype'] == 'link':
                    customer_info = self.__getUserInfo(msg['external_userid'])
                    msgSendCountClear(customer_info['unionid'])
                    self.__linkMsgHandler(msg)
                elif msg['msgtype'] == 'event':
                    self.__eventMsgHandler(msg)
                else:
                   # 暂不支持
                   customer_info = self.__getUserInfo(msg['external_userid'])
                   response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],str(uuid.uuid4()).replace("-", "")[:32], customer_info['nickname'] +"，此消息类型暂不支持。",sCorpID=self.sCorpID)
                   #msgSendCountIncrease()
    
            return True


if __name__ == '__main__':
    consumer_kefu = wechatKefuConsumer()
    thread_kefu = threading.Thread(target=consumer_kefu.start)
    thread_kefu.start()

    consumer_artical_info = wechatArticalInfoClickConsumer()
    thread_artical_info = threading.Thread(target=consumer_artical_info.start)
    thread_artical_info.start()

    thread_kefu.join()
    thread_artical_info.join()

    """
    consumer = wechatKefuConsumer()
    consumer.start()
    """
