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
from MysqlUtils import *

def save_user_to_db(customer_info):
    # 如果表中没有用户数据，先保存用户数据
    mysql = mysqlOps()
    user_table_name = "users"
    user_profile_table_name = "user_profile"

    if not mysql.is_database_exist("wechat_db"):
        mysql.create_database('wechat_db')
    mysql.select_database('wechat_db')

    uid = str(uuid.uuid4()).replace("-", "")[:32]
    if 'unionid' in customer_info:
        res, new_id = mysql.insert(user_table_name,{"uid":uid, "union_id":customer_info['unionid']})
    else: # 绑定认证过的公众号 or 小程序后才能获得union id，否则结果中没有union id
        # 测试用
        res, new_id = mysql.insert(user_table_name,{"uid":uid, "union_id":str(uuid.uuid4()).replace("-", "")[:32]})
    if not res:
        print("insert " + user_table_name + " failed!")


    #同时插入profile信息
    res, new_user_profile_id = mysql.insert(user_profile_table_name,{"user_id":new_id, "nickname":customer_info['nickname'], "avatar":customer_info['avatar'], "gender":customer_info['gender']})
    if not res:
        print("insert " + user_profile_table_name + " failed!")


def process_task(data: dict):
    sToken = os.environ['WECHAT_TOKEN']
    sEncodingAESKey = os.environ['WECHAT_AESKEY']
    sCorpID = os.environ['WECHAT_CORP_ID']
    wxcpt=WXBizJsonMsgCrypt(sToken,sEncodingAESKey,sCorpID)

    sReqNonce = data['nonce']
    sReqTimeStamp = data['timestamp']
    sReqMsgSig = data['sign']
    data_dict = xmltodict.parse(data['data'])

    sReqData = json.dumps(data_dict["xml"])

    ret,sMsg=wxcpt.DecryptMsg( sReqData, sReqMsgSig, sReqTimeStamp, sReqNonce)
    if( ret!=0 ):
        print("ERR: DecryptMsg ret: " + str(ret))
        return False
    else:
        decoded_dict = xmltodict.parse(sMsg)

        msg_list = fetchWechatMsg(decoded_dict["xml"]["Token"], decoded_dict["xml"]["OpenKfId"], sCorpID=sCorpID)
        for msg in msg_list:
            if msg['msgtype'] == 'text':
                response = getUserinfo([msg['external_userid']])
                customer_info = response['customer_list'][0]
                save_user_to_db(customer_info)

                response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "你叫：" + customer_info['nickname'] +"，你刚刚发送了：" + msg['text']['content'],sCorpID=sCorpID)
            elif msg['msgtype'] == 'event':
                response = getUserinfo([msg['event']['external_userid']])
                customer_info = response['customer_list'][0]
                # 事件
                if msg['event']['event_type'] == 'enter_session':
                    # 进入会话
                    response = sendWechatMsgTouserOnEvent(msg['event']['welcome_code'],str(uuid.uuid4()).replace("-", "")[:32], "你叫：" + customer_info['nickname'] +"，欢迎光临",sCorpID=sCorpID)
                elif msg['event']['event_type'] == 'user_recall_msg':
                    # 撤回消息
                    response = sendWechatMsgTouser(msg['event']['external_userid'], msg['event']['open_kfid'],str(uuid.uuid4()).replace("-", "")[:32], customer_info['nickname'] +"，你刚刚发送了什么？我没看见。",sCorpID=sCorpID)
                elif msg['event']['event_type'] == 'msg_send_fail':
                    # 消息发送失败
                    pass
            else:
               print("不支持消息: ", msg)
               response = getUserinfo([msg['external_userid']])
               customer_info = response['customer_list'][0]
               # 暂不支持
               response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],str(uuid.uuid4()).replace("-", "")[:32], customer_info['nickname'] +"，此消息类型暂不支持。",sCorpID=sCorpID)

        return True

def consume_messages():
    """RabbitMQ 消费者线程"""

    credentials = pika.PlainCredentials(username=os.environ['RABBITMQ_USERNAME'], password=os.environ['RABBITMQ_PASSWORD'])

    connection = pika.BlockingConnection(pika.ConnectionParameters(os.environ['RABBITMQ_HOST'], os.environ['RABBITMQ_PORT'], credentials=credentials))
    channel = connection.channel()

    # 声明持久化队列
    # channel.queue_declare(queue='hello_durable', durable=True)
    channel.queue_declare(queue='hello_durable', durable=True)

    # 每次最多处理一条消息（避免过载）
    channel.basic_qos(prefetch_count=1)


    channel.basic_consume(queue='hello_durable', on_message_callback=callback_json)
    print(" [*] Waiting for tasks. To exit press CTRL+C")
    channel.start_consuming()

def callback_json(ch, method, properties, body):
    try:
        task_data = json.loads(body.decode())
        result = process_task(task_data)
        if result:
            # 处理成功时才确认
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            """
            处理失败时拒绝并丢弃
            TODO: 本来想重新入队的，但发现重新入队后会马上被重新获取，可能出现一只循环处理同一个数据的问题，导致占用大量计算资源
            """
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        print(f"Error processing task: ", e)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

if __name__ == '__main__':
    consume_messages()
