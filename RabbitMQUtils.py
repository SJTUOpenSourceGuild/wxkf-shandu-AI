import pika
from threading import Thread
import threading
import json
import time
import os
from WXBizJsonMsgCrypt import WXBizJsonMsgCrypt
import xmltodict
from wechatapi import WechatApi, WECHAT_API_TYPE, fetchWechatMsg, sendWechatMsgTouser, getUserinfo


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
           response = getUserinfo([msg['external_userid']])
           response = sendWechatMsgTouser(msg['external_userid'], msg['open_kfid'],msg['msgid'], "你叫：" + response['customer_list'][0]['nickname'] +"，你刚刚发送了：" + msg['text']['content'],sCorpID=sCorpID)
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
