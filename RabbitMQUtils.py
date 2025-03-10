import pika
from threading import Thread
import threading
import json
import time
import os
from WXBizJsonMsgCrypt import WXBizJsonMsgCrypt
import xmltodict
from wechatapi import WechatApi, WECHAT_API_TYPE, fetchWechatMsg, sendWechatMsgTouser

def process_task(task_data: dict):
    """模拟耗时任务处理（如调用模型、写入数据库）"""
    print("task data = ",task_data)
    # print(f"Processing task {task_data['id']}: {task_data['action']}")
    # TODO: 实际业务逻辑

    sToken = os.environ['WECHAT_TOKEN']
    sEncodingAESKey = os.environ['WECHAT_AESKEY']
    sCorpID = os.environ['WECHAT_CORP_ID']
    wxcpt=WXBizJsonMsgCrypt(sToken,sEncodingAESKey,sCorpID)

    sReqNonce = task_data['nonce']
    sReqTimeStamp = task_data['timestamp']
    sReqMsgSig = task_data['sign']

    data_dict = xmltodict.parse(task_data['data'])

    sReqData = json.dumps(data_dict["xml"])
    ret,sMsg=wxcpt.DecryptMsg( sReqData, sReqMsgSig, sReqTimeStamp, sReqNonce)
    print("sMsg = ", sMsg)
    if( ret!=0 ):
       print("ERR: DecryptMsg ret: " + str(ret))
       return
    else:
       decoded_dict = xmltodict.parse(sMsg)
       print(decoded_dict)

       msgDict = fetchWechatMsg(decoded_dict["xml"]["Token"], decoded_dict["xml"]["OpenKfId"], sCorpID=sCorpID)
       response = sendWechatMsgTouser(msgDict['msg_list'][-1]['external_userid'], msgDict['msg_list'][-1]['open_kfid'],msgDict['msg_list'][-1]['msgid'], msgDict['msg_list'][-1]['text']['content'],sCorpID=sCorpID)
       print(response)
    return {"status": "success", "result": "processed"}

def consume_messages():
    """RabbitMQ 消费者线程"""

    credentials = pika.PlainCredentials(
      username=os.environ['RABBITMQ_USERNAME'],  # 替换为你的用户名
      password=os.environ['RABBITMQ_PASSWORD']  # 替换为你的密码
    )
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
        # TODO: 存储处理结果（如写入数据库）
        print(result)
        ch.basic_ack(delivery_tag=method.delivery_tag)  # 手动确认
    except Exception as e:
        print(f"Error processing task: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)  # 拒绝并丢弃


def process_message(body):
    time.sleep(1)
    # 模拟耗时操作（如数据库写入）
    print(f" [x] Received: {body.decode()}")
    # TODO: 实际业务逻辑

def callback(ch, method, properties, body):
    threading.Thread(target=process_message, args=(body,)).start()
    ch.basic_ack(delivery_tag=method.delivery_tag)  # 手动确认


if __name__ == '__main__':
    consume_messages()
    """
    # 连接到 RabbitMQ
    connection = pika.BlockingConnection(pika.ConnectionParameters('140.143.183.20'))
    channel = connection.channel()

    # 声明队列（确保存在）
    channel.queue_declare(queue='hello_durable')

    channel.basic_qos(prefetch_count=1)  # 控制并发量
    # 订阅队列
    channel.basic_consume(
        queue='hello_durable',
        auto_ack=False,  # 自动确认消息
        on_message_callback=callback
    )

    print(' [*] Waiting for messages. Press CTRL+C to exit.')
    channel.start_consuming()
    """
