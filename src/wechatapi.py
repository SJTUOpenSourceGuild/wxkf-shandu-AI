from AbstractApi import *
from RedisUtils import *
from Logger import logger
import tempfile

WECHAT_API_TYPE = {
        'GET_ACCESS_TOKEN' : ['/cgi-bin/gettoken', 'GET'],
        'SYNC_MSG' : ['/cgi-bin/kf/sync_msg?access_token=ACCESS_TOKEN', 'POST'],
        'SEND_MSG' : ['/cgi-bin/kf/send_msg?access_token=ACCESS_TOKEN', 'POST'],
        'SEND_MSG_ON_EVENT' : ['/cgi-bin/kf/send_msg_on_event?access_token=ACCESS_TOKEN', 'POST'],
        'GET_USER_INFO': ['/cgi-bin/kf/customer/batchget?access_token=ACCESS_TOKEN', 'POST'],
        'UPLOAD_FILE' : ['/cgi-bin/media/upload?access_token=ACCESS_TOKEN&type=TYPE', 'POST-FILE'],
        'DOWNLOAD_FILE' : ['/cgi-bin/media/get?access_token=ACCESS_TOKEN&media_id=MEDIA_ID', 'GET-FILE'],
        'CHANGE_KEFU_USERNAME' : ['/cgi-bin/kf/account/update?access_token=ACCESS_TOKEN', 'POST']
}

class WechatApi(AbstractApi) :
    def __init__(self, corpid, secret) :
        self.corpid = corpid
        self.secret = secret
        self.access_token = None

    def getAccessToken(self) :
        if self.access_token is None :
            self.refreshAccessToken()
        return self.access_token

    def refreshAccessToken(self) :
        response = self.httpCall(
                WECHAT_API_TYPE['GET_ACCESS_TOKEN'],
                {
                    'corpid'    :   self.corpid,
                    'corpsecret':   self.secret,
                })
        self.access_token = response.get('access_token')


"""
获取上次拉取后收到的所有消息，利用redis保存cursor，防止后续重复拉取
@Params:
    * token:回调事件返回的token字段，10分钟内有效；可不填，如果不填接口有严格的频率限制。不多于128字节
    * open_kf_id:指定拉取某个客服账号的消息
@Returns
    * res: list，一组消息
"""
def fetchWechatMsg(token, open_kf_id,
                   sCorpID=os.environ['WECHAT_CORP_ID'], secret=os.environ['WECHAT_SECRET']):
    redis_conn, err_code = RedisConnect()
    cursor = ""
    has_more = 1
    api = WechatApi(sCorpID, secret=secret)
    res = []
    while has_more == 1:
        if err_code == 0 and redis_conn.exists('wechat_cursor'):
            cursor = redis_conn.get('wechat_cursor')
        response = api.httpCall(
                WECHAT_API_TYPE['SYNC_MSG'],
               {
                   "cursor" : cursor,
                   "token" : token,
                   "limit" : 10,
                #    "voice_format" : "",
                   "open_kfid" : open_kf_id

               })
        if err_code == 0:
            redis_conn.set('wechat_cursor', response['next_cursor'])
        res += response['msg_list']
        has_more = response['has_more']
    return res

"""
针对每个用户，保存了上次收到用户消息后，客服已经发送的消息数目，用于应对客服不能发送超过5条消息的问题
增加消息发送量，客服发送消息成功后调用
"""
def msgSendCountIncrease(uionid):
    key = "user:" + uionid + ":msg_send_count"
    redis_conn, err_code = RedisConnect()
    if err_code == 0 and redis_conn.exists('wechat_cursor'):
        redis_conn.incr(key)
        return True
    else:
        return False

"""
针对每个用户，保存了上次收到用户消息后，客服已经发送的消息数目，用于应对客服不能发送超过5条消息的问题
清空消息发送量,收到用户发送的消息后调用
"""
def msgSendCountClear(uionid):
    key = "user:" + uionid + ":msg_send_count"
    redis_conn, err_code = RedisConnect()
    if err_code == 0 and redis_conn.exists('wechat_cursor'):
        redis_conn.set(key, 0)
        return True
    else:
        return False

"""
针对每个用户，保存了上次收到用户消息后，客服已经发送的消息数目，用于应对客服不能发送超过5条消息的问题
获取已经发送的消息数目,一般用于在达到发送上限前提醒用户发送消息给客服
"""
def getMsgSendCount(uionid):
    key = "user:" + uionid + ":msg_send_count"
    redis_conn, err_code = RedisConnect()
    if err_code == 0 and redis_conn.exists('wechat_cursor'):
        send_count  = redis_conn.get(key)
        return int(send_count)
    return 1000

"""
为了实现用户在小程序（或其他地方）点击微信公众号文章后，跳转客服，客服发送用户最近点击的文章给客户
删除最近点击的公众号文章信息
在给用户发送了最近点击的公众号文章后删除，防止重复发送
"""
def deleteLastClickedWechatArticalInfo(uionid):
    key = "unionid:" + uionid +":last_clicked_artical_info"
    redis_conn, err_code = RedisConnect()
    if err_code != 0:
        logger.warning("connect to redis failed!")
        return False

    deleted_count = redis_conn.delete(key)
    if deleted_count <= 0:
        logger.warning("delete " + key + " failed!")
    return deleted_count > 0

"""
为了实现用户在小程序（或其他地方）点击微信公众号文章后，跳转客服，客服发送用户最近点击的文章给客户
保存最近点击的公众号文章信息
ps:目前是在golang端保存的，本函数没用到过，未经测试
wechatArticalInfo: {"title":"", "desc":"", "url":"", "image_url":""}
"""
def setLastClickedWechatArticalInfo(uionid, wechatArticalInfo):
    """保存用户最后一次点击记录"""
    key = "unionid:" + uionid +":last_clicked_artical_info"
    redis_conn, err_code = RedisConnect()
    if err_code != 0:
        logger.warning("connect to redis failed!")
        return False


    # 使用管道保证原子操作
    with redis_conn.pipeline() as pipe:
        pipe.hset(key, mapping=wechatArticalInfo)
        pipe.expire(key, 10 * 60)  # 10分钟后过期   
        pipe.execute()
    return True

"""
为了实现用户在小程序（或其他地方）点击微信公众号文章后，跳转客服，客服发送用户最近点击的文章给客户
获取最近点击的公众号文章数据
"""
def getLastClickedWechatArticalInfo(uionid):
    """获取用户最后一次点击记录"""
    key = "unionid:" + uionid +":last_clicked_artical_info"
    redis_conn, err_code = RedisConnect()
    if err_code != 0:
        logger.warning("connect to redis failed!")
        return None
    data = redis_conn.hgetall(key)
    
    if not data:
        logger.warning("no value corresponding to " + key)
        return None
    
    return data

def getLastClickedInfo(uionid):
    """获取用户最后一次点击记录"""
    key = "unionid:" + uionid +":last_click_info"
    redis_conn, err_code = RedisConnect()
    if err_code != 0:
        logger.warning("connect to redis failed!")
        return None
    data = redis_conn.hgetall(key)
    
    if not data:
        logger.warning("no value corresponding to " + key)
        return None
    
    return data

"""
将本地文件上传为临时素材，获取media_id,参见：https://developer.work.weixin.qq.com/document/25551
TODO: 目前只支持image，后续增加
"""
def uploadFile(file_path, file_type = "image",
                        sCorpID=os.environ['WECHAT_CORP_ID'], secret=os.environ['WECHAT_SECRET']):
    api = WechatApi(sCorpID, secret=secret)
    file_name = os.path.basename(file_path)
    with open(file_path, "rb") as file:
        try:
            files = {
                "media": (file_name, file, "application/octet-stream")  # 自动填充 filename/content-type
            }
            response = api.httpCall(
                WECHAT_API_TYPE['UPLOAD_FILE'],
                files,
                [('TYPE',file_type)]
            )
            if response['errcode'] == 0:
                return response['media_id']
            else:
                return ""
        except Exception as e:
            print(e)
            return ""
    return ""

def downloadFile(media_id, path,
                        sCorpID=os.environ['WECHAT_CORP_ID'], secret=os.environ['WECHAT_SECRET']):
    api = WechatApi(sCorpID, secret=secret)
    response = api.httpCall(
            WECHAT_API_TYPE['DOWNLOAD_FILE'],
            {'path':path},
            [('MEDIA_ID',media_id)]
            )
    return path + response.get('filename')

"""
将网上文件文件上传为临时素材，获取media_id,参见：https://developer.work.weixin.qq.com/document/25551
TODO: 目前只支持image，后续增加
"""
def uploadFileFromUrl(url, 
                        sCorpID=os.environ['WECHAT_CORP_ID'], secret=os.environ['WECHAT_SECRET']):

    with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
        # 下载到临时文件
        with requests.get(url, stream=True) as r:
            for chunk in r.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
        return uploadFile(tmp_file.name)

"""
给用户发送消息
@Params:
    * external_userid: string,目标用户的external_userid
    * open_kf_id： string,发送消息的客服id
    * msgid: string, 消息id，由开发这根据自身情况设定（有长度限制）
    * msg_type: string,包括：text、link、menumsg等
    * data:dict, 满足msg_type要求的数据格式
"""
def sendWechatMsgTouser(external_userid, open_kf_id, msgid, msg_type = 'text', data={"content":"test"},
                        sCorpID=os.environ['WECHAT_CORP_ID'], secret=os.environ['WECHAT_SECRET']):
    api = WechatApi(sCorpID, secret=secret)
    try:
        response = api.httpCall(
            WECHAT_API_TYPE['SEND_MSG'],
            {
                "touser" : external_userid,
                "open_kfid": open_kf_id,
                "msgid": msgid,
                "msgtype" : msg_type,
                msg_type : data
            }
        )
    except Exception as e:
        logger.error("send Wechat Message to User failed! error = " + str(e))
        print(e)
    return response

"""
和sendWechatMsgTouser类似用于处理发送欢迎语等情况
"""
def sendWechatMsgTouserOnEvent(code, msgid, msg_type = 'text', data={"content":"你好"},
                        sCorpID=os.environ['WECHAT_CORP_ID'], secret=os.environ['WECHAT_SECRET']):
    api = WechatApi(sCorpID, secret=secret)
    response = api.httpCall(
        WECHAT_API_TYPE['SEND_MSG_ON_EVENT'],
        {
            "code": code,
            "msgid": msgid,
            "msgtype" : msg_type,
            msg_type : data
        }
    )
    return response

"""
根据external_userid_list获取用户具体信息，包括昵称、头像、性别、unionid等
external_userid_list：需要查询的一组external_userid，比如["wmxxxxxxxxxxxxxxxxxxxxxx","zhangsan"]
need_enter_session_context:是否需要返回客户48小时内最后一次进入会话的上下文信息。0-不返回 1-返回

结果格式：{'errcode': 0, 'errmsg': 'ok', 'customer_list': [{'external_userid': 'wmxxxxxxxxxx', 'nickname': '昵称', 'avatar': 'http://wx.qlogo.cn/xxxx', 'gender': 1}], 'invalid_external_userid': []}
"""
def getUserinfoList(external_userid_list, need_enter_session_context = 0,
        sCorpID=os.environ['WECHAT_CORP_ID'], secret=os.environ['WECHAT_SECRET']):
    api = WechatApi(sCorpID, secret=secret)
    response = api.httpCall(
            WECHAT_API_TYPE['GET_USER_INFO'],
            {
                "external_userid_list": external_userid_list,
                "need_enter_session_context": need_enter_session_context
                }
            )
    return response

"""
非常用方法，用于修改指定客服的nickname
TODO: 这里可以方便增加修改指定客服头像的方法
"""
def changeKefuUsername(open_kf_id, new_username,
                        sCorpID=os.environ['WECHAT_CORP_ID'], secret=os.environ['WECHAT_SECRET']):
    api = WechatApi(sCorpID, secret=secret)
    response = api.httpCall(
        WECHAT_API_TYPE['CHANGE_KEFU_USERNAME'],
        {
            "open_kfid": open_kf_id,
            "name": new_username,
        }
    )
    return response


if __name__ == '__main__':
    #changeKefuUsername('wkCP2rQAAAIsMapNIPdf8-raAEe02Lcw', "闪读AI")
    #res = uploadFile("1.jpeg")
    #res = uploadFileFromUrl("https://wework.qpic.cn/wwpic3az/137171_c45X6VRCTAGOcNo_1742733854/0")
    res = downloadFile("1cpk1SgsRual0tG4JJotTYAHxIjz54S5L-4OF0H1wjn5nkGS_HrENWg0fWJopbOet", "./logs/")
    print(res)
    
