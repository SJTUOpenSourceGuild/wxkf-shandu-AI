import pika
from threading import Thread
import threading
import json
import time
import os
import uuid
from wxkf_decode.WXBizJsonMsgCrypt import WXBizJsonMsgCrypt
import xmltodict
from wechatapi import WechatApi, WECHAT_API_TYPE, fetchWechatMsg, sendWechatMsgTouser, sendWechatMsgTouserOnEvent, getUserinfoList,uploadFileFromUrl, uploadFile, downloadFile,getMsgSendCount,msgSendCountClear,msgSendCountIncrease,deleteLastClickedWechatArticalInfo, getLastClickedInfo
from utils.FileUtils import read_file
from mysql.WechatMysqlOps import WechatMysqlOps
from crawler.wechatCrawler import getWechatArticalContent
from utils.utils import is_url,truncate_string_to_bytes, calculate_file_hash
from crawler.urlCrawler import fetch_and_parse
from coze import askAI
import datetime
from Logger import logger
from TXCOSManager import TXCOSManager

WechatKFCallBackQueueName = "wechat_kefu_callback_queue"
ClickedWechatArticalInfoQueueName = "clicked_wechat_artical_info_queue"
WechatKFMsgSendMaxTime = 5
sCorpID = os.environ['WECHAT_CORP_ID']

# ------------- 菜单消息处理 -----------------

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
    res = getLastClickedInfo(unionid)
    if res == None:
        response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "text", {"content": "激活成功！"},sCorpID=sCorpID)
        msgSendCountIncrease(unionid)
    else:
        if 'type' not in res or  res['type'] == "wechat-artical":
            send_res = sendWechatArticalInfo(res['title'], res['desc'], res['url'], res['image_url'], msg['external_userid'], msg['open_kfid'], sCorpID)
            if int(send_res['errcode']) != 0:
                logger.error("activemenu Handler send wechat artical info failed! err_msg = " + send_res['errmsg'])
            else:
                deleteLastClickedWechatArticalInfo(unionid)
            msgSendCountIncrease(unionid)

def usageTutorialFileMenuHandler(msg, unionid, sCorpID):
    media_id = uploadFile("./tutorial_videos/usage_file.mp4", "video")
    response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "video", {"media_id": media_id},sCorpID=sCorpID)
    msgSendCountIncrease(unionid)

def usageTutorialPCFileMenuHandler(msg, unionid, sCorpID):
    media_id = uploadFile("./tutorial_videos/usage_file_pc.mp4", "video")
    response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "video", {"media_id": media_id},sCorpID=sCorpID)
    msgSendCountIncrease(unionid)

def usageTutorialArticalMenuHandler(msg, unionid, sCorpID):
    media_id = uploadFile("./tutorial_videos/usage_artical.mp4", "video")
    response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "video", {"media_id": media_id},sCorpID=sCorpID)
    msgSendCountIncrease(unionid)

"""
收到菜单消息时，用消息内容获取处理方法
"""
menuString2Handler = {
        "如何快速总结文件？":usageTutorialFileMenuHandler,
        "如何在电脑上快速总结文件？":usageTutorialPCFileMenuHandler,
        "如何快速总结微信公众号文章？":usageTutorialArticalMenuHandler,
        "激活会话":activemenuHandler,
        "加入内测群":joinTestGroup
        }

# ------------- helper -----------------
"""
根据external_userid获取用户具体信息，包括昵称、头像、性别、unionid等
"""
def getUserInfo(external_userid):
    user_info_resp = getUserinfoList([external_userid])
    if 'customer_list' not in user_info_resp:
        logger.warning("获取的用户信息错误")
        return

    customer_list = user_info_resp['customer_list']
    if len(customer_list) <= 0:
        logger.warning("获取到的用户数据为0个（应为1个）")
        return

    customer_info = customer_list[0]
    return customer_info

def sendWechatArticalInfo(title, desc, url, post_image_url, external_userid, open_kfid, sCorpID):
    tmp_post_id = uploadFileFromUrl(post_image_url)
    if len(tmp_post_id) == 0:
        logger.error("upload post image failed!")
        return

    data = {
        "title" : truncate_string_to_bytes(title, 128),
        "desc" : truncate_string_to_bytes(desc,512),
        "url" : truncate_string_to_bytes(url,2048),
        "thumb_media_id": tmp_post_id}
    try:
        response = sendWechatMsgTouser(external_userid, open_kfid,str(uuid.uuid4()).replace("-", "")[:32], 'link', data, sCorpID=sCorpID)
        if int(response['errcode']) != 0:
            logger.error("activemenu Handler send wechat artical info failed! err_msg = " + send_res['errmsg'])
        else:
            deleteLastClickedWechatArticalInfo(unionid)
    except Exception as e:
        logger.error("send wechat message to user failed!")

def sendFileInfo(file_name,bucket_name, key, external_userid, open_kfid):
    CosManager = TXCOSManager()
    CosManager.downloadFileWithRetry("./files/" + file_name, "wx-minip-bangwodu-01-1320810990", key)
    media_id = uploadFile("./files/" + file_name, "file")
    os.remove("./files/" + file_name)
    response = sendWechatMsgTouser(external_userid, open_kfid,str(uuid.uuid4()).replace("-", "")[:32], "file", {"media_id": media_id},sCorpID=sCorpID)

"""
如果处理过程中出错了，集中调用本函数
"""
def exceptionHandler(msg):
    response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "text", {"content":"出错了……\n请重试或在小程序中反馈问题，我们重视用户的每一次发声！"},sCorpID=sCorpID)
    if int(response['errcode']) != 0:
        logger.error("send message failed during exception handler")
        
# ----------------- Event Handlers ---------------

"""
处理用户进入微信客服会话的事件
"""
def enterEventMsgHandler(msg, customer_info):
    if not 'unionid' in customer_info:
        logger.error("no unionid in customer_info")
        return
    needSendWechatInfo = False
    needSendFileInfo = False
    res = getLastClickedInfo(customer_info["unionid"])

    if res == None:
        # 没有微信文章点击信息
        pass
    else:
        # 存在点击
        if 'type' not in res:
            needSendWechatInfo = True
        if res['type'] == "wechat-artical":
            needSendWechatInfo = True
        if res['type'] == "file":
            needSendFileInfo = True

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
        if needSendWechatInfo:
            sendWechatArticalInfo(res['title'], res['desc'], res['url'], res['image_url'], msg['event']['external_userid'], msg['event']['open_kfid'], customer_info['unionid'])
            msgSendCountIncrease(customer_info['unionid'])
            return
        if needSendFileInfo:
            sendFileInfo(res['filename'], res['bucket_name'], res['key'],msg['event']['external_userid'], msg['event']['open_kfid'])
            msgSendCountIncrease(customer_info['unionid'])
            return
        welcome_menu = []

        welcome_menu.append({"type":"text", "text":{"content":"使用教程："}})
        welcome_menu.append({"type":"click","click": {
            "id": "201",
            "content": "如何快速总结文件？"
        }})
        welcome_menu.append({"type":"click","click": {
            "id": "201",
            "content": "如何在电脑上快速总结文件？"
        }})
        welcome_menu.append({"type":"click","click": {
            "id": "203",
            "content": "如何快速总结微信公众号文章？"
        }})

        welcome_menu.append({"type":"text", "text":{"content":"\n"}})
        welcome_menu.append({"type":"text", "text":{"content": "\n请点击下方“激活会话”选项，否则后续可能出现无法收到消息的情况："}})
        welcome_menu.append({"type": "click", "click": {"id": "101", "content": "激活会话"}})

        welcome_menu.append({"type":"text", "text":{"content":"\n"}})
        welcome_menu.append({"type":"miniprogram", "miniprogram": {"appid":"wx394fd56312f409e6","pagepath":"pages/index/index.html","content":"点击进入微信小程序"}})
        response = sendWechatMsgTouserOnEvent(msg['event']['welcome_code'],str(uuid.uuid4()).replace("-", "")[:32], 'msgmenu', {"head_content": "欢迎使用帮我读！\n", "list": welcome_menu},sCorpID=sCorpID)
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
            response = sendWechatMsgTouser(msg['event']['external_userid'],msg['event']['open_kfid'], str(uuid.uuid4()).replace("-", "")[:32], 'msgmenu', {"head_content": head_content, "list": welcome_menu,"tail_content": "⬆️点击上方“激活会话”选项"},sCorpID=sCorpID)
        else:
            if needSendWechatInfo:
                sendWechatArticalInfo(res['title'], res['desc'], res['url'], res['image_url'], msg['event']['external_userid'], msg['event']['open_kfid'], customer_info['unionid'])
                msgSendCountIncrease(customer_info['unionid'])
            if needSendFileInfo:
                sendFileInfo(res['filename'], res['bucket_name'], res['key'], msg['event']['external_userid'], msg['event']['open_kfid'])
                msgSendCountIncrease(customer_info['unionid'])

"""
处理用户撤回消息事件
"""
def recallMsgEventMsgHandler(msg, customer_info):
    # 处理用户撤回消息事件
    response = sendWechatMsgTouser(msg['event']['external_userid'], msg['event']['open_kfid'],str(uuid.uuid4()).replace("-", "")[:32], "text", {"content": "你叫：" + customer_info['nickname'] +"，你刚刚撤回了一条消息"},sCorpID=sCorpID)


eventType2Handler = {
        "enter_session":enterEventMsgHandler,
        "user_recall_msg":recallMsgEventMsgHandler
    }


# ----------------- Message Handlers ---------------
"""
处理用户发送的文字消息
"""
def textMsgHandler(msg):
    customer_info = getUserInfo(msg['external_userid'])
    msgSendCountClear(customer_info['unionid'])
    if 'external_userid' not in msg:
        logger.warning("no external_userid in msg")
        return

    customer_info = getUserInfo(msg['external_userid'])
    wechat_db_ops = WechatMysqlOps()
    wechat_db_ops.save_user_to_db(customer_info)

    if 'menu_id' in msg['text']:
        # 通过点击菜单选项发送的文字
        menuString2Handler[msg['text']['content']](msg, customer_info['unionid'],sCorpID)
        return

    if is_url(msg['text']['content']): # 如果文本整体是一个url，则特殊处理
        html =fetch_and_parse(msg['text']['content'])
        response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "text", {"content": "你叫：" + customer_info['nickname'] +"，你刚刚发送了一个网址：" + html.title.text},sCorpID=sCorpID)
        if int(response['errcode']) == 0:
            msgSendCountIncrease(customer_info['unionid'])
    else:
        #response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "text", {"content": "你叫：" + customer_info['nickname'] +"，你刚刚发送了：" + msg['text']['content']},sCorpID=sCorpID)
        response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "text", {"content": "目前暂不支持文字问答，敬请期待！"},sCorpID=sCorpID)

        msgSendCountIncrease(customer_info['unionid'])


        if int(response['errcode']) == 0:
            msgSendCountIncrease(customer_info['unionid'])
"""
处理用户发送的链接（公众号文章）消息
"""
def linkMsgHandler(msg):
    customer_info = getUserInfo(msg['external_userid'])
    msgSendCountClear(customer_info['unionid'])
    if 'external_userid' not in msg:
        logger.warning("no external_userid in msg")
        return

    customer_info = getUserInfo(msg['external_userid']) # 每次都要获取用户信息吗？
    wechat_db_ops = WechatMysqlOps()
    try:
        if wechat_db_ops.ifUserExist(customer_info['unionid']) <= 0:
            wechat_db_ops.save_user_to_db(customer_info)
    except Exception as e:
        logger.error("save_user_to_db failed")

    artical_msg_id = -1
    artical_id = -1

    updateSummary = True
    # 首先查看数据库中是否有该文章
    if wechat_db_ops.ifWechatArticalExistByUrl(msg['link']['url']) > 0:
        # 已经存在文章
        logger.info("artical already exist")
        artical = wechat_db_ops.getWechatArticalByUrl(msg['link']['url'])
        # TODO: 目前只能通过查看表的结构获取对应列，后续考虑优化
        artical_content = artical[9]
        artical_id = artical[0]
        ai_answer = artical[10]
        updateSummary = ai_answer == None or len(ai_answer) == 0
    else:
        # 新文章
        logger.info("new artical")
        err_code, info_dict = getWechatArticalContent(msg['link']['url'])
        artical_id = wechat_db_ops.saveWechatArtical(info_dict, msg)
        artical_content = info_dict['parsed_content']
        if err_code != 0:
            logger.error("获取公众号文章数据失败")
            exceptionHandler(msg)
            return
    if updateSummary:
        try:
            ai_answer = askAI(artical_content)
        except Exception as e:
            logger.error("askAI failed! error = " + str(e))
            exceptionHandler(msg)
            return

    try:
        artical_msg_id = wechat_db_ops.saveWechatArticalMsg(customer_info, msg, int(artical_id))
    except Exception as e:
        exceptionHandler(msg)
        logger.error("saveWechatArticalMsg failed, error = " + str(e))

    try:
        content = "《" + msg['link']['title'] +"》：\n" + ai_answer
        menu_list = []
        if len(content.encode('utf-8')) > 1024:
            content = content.encode('utf-8')[:1000].decode('utf-8', 'ignore') + "……\n"
        menu_list.append({ "type":"miniprogram", "miniprogram": {"appid":"wx394fd56312f409e6","pagepath":"pages/index/index.html?tab=artical&target_link_msg_id=" + str(artical_msg_id),"content":"点击去小程序查看更多：《"+ msg['link']['title'] +"》"}})
        menu_list.append({"type":"text", "text":{"content":"\n\n"}})

        menu_list.append({"type": "click", "click": {"id": "101", "content": "激活会话"}})
        response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "msgmenu", {"head_content":content,"list":menu_list},sCorpID=sCorpID)
        msgSendCountIncrease(customer_info['unionid'])
    except Exception as e:
        logger.error("sendWechatMsgTouser failed!")

    if artical_id > 0 and updateSummary and not wechat_db_ops.setWechatArticalSummary(artical_id, ai_answer):
        logger.error("update artical summary failed!")

"""
处理用户发送的文件消息
1. 下载文件
2. 判断文件是否已经存在
3. 将文件上传到COS
3. 获取文件内容
"""
def fileMsgHandler(msg):
    customer_info = getUserInfo(msg['external_userid'])
    msgSendCountClear(customer_info['unionid'])
    customer_info = getUserInfo(msg['external_userid']) # 每次都要获取用户信息吗？
    file_path = downloadFile(msg['file']['media_id'], "./files/")
    hash_str = calculate_file_hash(file_path)
    wechat_db_ops = WechatMysqlOps()
    file_id = wechat_db_ops.ifFileExist(hash_str)
    file_name = os.path.basename(file_path)
    updateSummary = True
    if file_id > 0:
        # 文件已经存在
        file_info = wechat_db_ops.getFileById(file_id)
        ai_answer = file_info[6]
        updateSummary = len(ai_answer) == 0
    else :
        # 新文件
        CosManager = TXCOSManager()
        CosManager.uploadFileWithRetry(file_path,'wx-minip-bangwodu-01-1320810990', file_name, "user-upload-files/" + customer_info['unionid'] + "/")
        file_id = wechat_db_ops.saveFile(file_path, 'wx-minip-bangwodu-01-1320810990',"user-upload-files/" + customer_info['unionid'] + "/" + file_name)

    new_file_msg_id = wechat_db_ops.saveFileMsg(customer_info, msg, file_id, file_name)

    if updateSummary:
        content = read_file(file_path)
        if content == None:
            response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "text", {"content":"暂不支持《" + file_name + "》，换个文件试试。"},sCorpID=sCorpID)
            msgSendCountIncrease(customer_info['unionid'])
            exceptionHandler(msg)
            return;
        try:
            ai_answer = askAI(content)
        except Exception as e:
            logger.error("askAI failed!")
            exceptionHandler(msg)
            return

    os.remove(file_path)

    try:
        content = "《" + file_name + "》：\n" + ai_answer
        menu_list = []
        if len(content.encode('utf-8')) > 1024:
            content = content.encode('utf-8')[:1000].decode('utf-8', 'ignore') + "……\n"
        menu_list.append({ "type":"miniprogram", "miniprogram": {"appid":"wx394fd56312f409e6","pagepath":"pages/index/index.html?tab=file&target_file_msg_id=" + str(new_file_msg_id),"content":"点击去小程序查看更多：《"+ file_name +"》"}})
        menu_list.append({"type":"text", "text":{"content":"\n\n"}})
        menu_list.append({"type": "click", "click": {"id": "101", "content": "激活会话"}})
        response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "msgmenu", {"head_content":content,"list":menu_list},sCorpID=sCorpID)
        msgSendCountIncrease(customer_info['unionid'])
    except Exception as e:
        logger.error("sendWechatMsgTouser failed!")

    if file_id > 0 and updateSummary and not wechat_db_ops.setFileSummary(file_id, ai_answer):
        logger.error("update file summary failed!")
"""
处理用户事件和消息
"""
def eventMsgHandler(msg):
    customer_info = getUserInfo(msg['event']['external_userid'])
    if msg['event']['event_type'] in eventType2Handler:
        eventType2Handler[msg['event']['event_type']](msg, customer_info)

msgType2Handler = {
        "text":textMsgHandler,
        "link":linkMsgHandler,
        "file":fileMsgHandler,
        "event":eventMsgHandler
        }


class wechatKefuConsumer:
    def __init__(self, queue_name = WechatKFCallBackQueueName, prefetch_num = 2):
        self.sToken = os.environ['WECHAT_TOKEN']
        self.sEncodingAESKey = os.environ['WECHAT_AESKEY']
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

    def on_message(self,ch, method, properties, body):
        try:
            task_data = json.loads(body.decode())
            result = self.__process_task(task_data)
            if result:
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

    """
    解密微信客服消息, 返回(错误码, 解密后原文)
    """
    def __decode_msg(self, data):
        wxcpt=WXBizJsonMsgCrypt(self.sToken,self.sEncodingAESKey,sCorpID)
        sReqNonce = data['nonce']
        sReqTimeStamp = data['timestamp']
        sReqMsgSig = data['sign']
        data_dict = xmltodict.parse(data['data'])
        sReqData = json.dumps(data_dict["xml"])
        return wxcpt.DecryptMsg( sReqData, sReqMsgSig, sReqTimeStamp, sReqNonce)


    def __process_task(self, data: dict):
        logger.info("__process_task")
        ret,sMsg= self.__decode_msg(data)
        if ret != 0:
            logger.error("解密回调数据错误，结果为" + str(ret))
            return False
        else: # 解密成功，继续处理
            decoded_dict = xmltodict.parse(sMsg)
            # 从微信服务器获取消息的具体数据
            msg_list = fetchWechatMsg(decoded_dict["xml"]["Token"], decoded_dict["xml"]["OpenKfId"], sCorpID=sCorpID)
            for msg in msg_list:
                if msg["msgtype"] in msgType2Handler:
                    msgType2Handler[msg["msgtype"]](msg)
                else:
                    # 暂不支持
                    customer_info = getUserInfo(msg['external_userid'])
                    response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],str(uuid.uuid4()).replace("-", "")[:32], customer_info['nickname'] +"，此消息类型暂不支持。",sCorpID=sCorpID)
                    #msgSendCountIncrease()
            return True



if __name__ == '__main__':
    consumer_kefu = wechatKefuConsumer()
    thread_kefu = threading.Thread(target=consumer_kefu.start)
    thread_kefu.start()

    thread_kefu.join()

    """
    consumer = wechatKefuConsumer()
    consumer.start()
    """
