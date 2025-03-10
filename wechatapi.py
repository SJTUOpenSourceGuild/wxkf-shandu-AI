from AbstractApi import *

WECHAT_API_TYPE = {
        'GET_ACCESS_TOKEN' : ['/cgi-bin/gettoken', 'GET'],
        'SYNC_MSG' : ['/cgi-bin/kf/sync_msg?access_token=ACCESS_TOKEN', 'POST'],
        'SEND_MSG' : ['/cgi-bin/kf/send_msg?access_token=ACCESS_TOKEN', 'POST'],
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


def fetchWechatMsg(token, open_kf_id,
                   sCorpID=os.environ['WECHAT_CORP_ID'], secret=os.environ['WECHAT_SECRET']):
    api = WechatApi(sCorpID, secret=secret)
    response = api.httpCall(
               WECHAT_API_TYPE['SYNC_MSG'],
               {
                   "cursor" : "",
                   "token" : token,
                #    "limit" : "",
                #    "voice_format" : "",
                   "open_kfid" : open_kf_id

               })
    msgDict = response
    print(msgDict)
    return msgDict

def sendWechatMsgTouser(external_userid, open_kf_id, msgid, msg, msg_type = 'text'
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

