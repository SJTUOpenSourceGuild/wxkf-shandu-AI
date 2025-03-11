from AbstractApi import *
from RedisUtils import *

WECHAT_API_TYPE = {
        'GET_ACCESS_TOKEN' : ['/cgi-bin/gettoken', 'GET'],
        'SYNC_MSG' : ['/cgi-bin/kf/sync_msg?access_token=ACCESS_TOKEN', 'POST'],
        'SEND_MSG' : ['/cgi-bin/kf/send_msg?access_token=ACCESS_TOKEN', 'POST'],
        'GET_USER_INFO': ['/cgi-bin/kf/customer/batchget?access_token=ACCESS_TOKEN', 'POST'],
        'UPLOAD_FILE' : ['/cgi-bin/media/upload?access_token=ACCESS_TOKEN&type=TYPE', 'POST'],
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
TODO: 需要在数据库中保存cursor，实现消息的增量拉取
> 强烈建议对该字段入库保存，每次请求读取带上，请求结束后更新。避免因意外丢，导致必须从头开始拉取，引起消息延迟。

SYNC_MSG的返回数据结构如下：
{
    "errcode": 0,
    "errmsg": "ok",
    "next_cursor": "4gw7MepFLfgF2VC5npN",
    "has_more": 1,
    "msg_list": [
        {
            "msgid": "from_msgid_4622416642169452483",
            "open_kfid": "wkAJ2GCAAASSm4_FhToWMFea0xAFfd3Q",
            "external_userid": "wmAJ2GCAAAme1XQRC-NI-q0_ZM9ukoAw",
            "send_time": 1615478585,
            "origin": 3,
            "msgtype": "MSG_TYPE"
        }
    ]
}
在判断获取成功后，返回错误吗和msg_list

TODO: 这里最好不要一个一个处理，而是利用cursor实现增量拉取后，一次处理完能够获得的所有消息，知道has_more变成0
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

def sendWechatMsgTouser(external_userid, open_kf_id, msgid, msg, msg_type = 'text',
                        sCorpID=os.environ['WECHAT_CORP_ID'], secret=os.environ['WECHAT_SECRET']):
    api = WechatApi(sCorpID, secret=secret)
    response = api.httpCall(
        WECHAT_API_TYPE['SEND_MSG'],
        {
            "touser" : external_userid,
            "open_kfid": open_kf_id,
            "msgid": msgid,
            "msgtype" : msg_type,
            "text" : {
                "content" : msg
            }
        }
    )
    return response

"""
根据external_userid_list获取用户具体信息，包括昵称、头像、性别、unionid等
external_userid_list：需要查询的一组external_userid，比如["wmxxxxxxxxxxxxxxxxxxxxxx","zhangsan"]
need_enter_session_context:是否需要返回客户48小时内最后一次进入会话的上下文信息。0-不返回 1-返回

结果格式：{'errcode': 0, 'errmsg': 'ok', 'customer_list': [{'external_userid': 'wmxxxxxxxxxx', 'nickname': '昵称', 'avatar': 'http://wx.qlogo.cn/xxxx', 'gender': 1}], 'invalid_external_userid': []}
"""
def getUserinfo(external_userid_list, need_enter_session_context = 0,
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
