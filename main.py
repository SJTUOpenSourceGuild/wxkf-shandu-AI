from fastapi import FastAPI, Request,Query
from fastapi.responses import PlainTextResponse
from WXBizJsonMsgCrypt import WXBizJsonMsgCrypt
import xmltodict
import sys
import os
import json
from wechatapi import WechatApi, WECHAT_API_TYPE

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/chat/callback")
def chat_callback(msg_signature: str = "", timestamp:int = 0, nonce: str= "", echostr: str= ""):
   #假设企业在企业微信后台上设置的参数如下
   sToken = os.environ['WECHAT_TOKEN']
   sEncodingAESKey = os.environ['WECHAT_AESKEY']
   sCorpID = os.environ['WECHAT_CORP_ID']
   wxcpt=WXBizJsonMsgCrypt(sToken,sEncodingAESKey,sCorpID)

   sVerifyMsgSig=msg_signature
   sVerifyTimeStamp=str(timestamp)
   sVerifyNonce=nonce
   sVerifyEchoStr=echostr

   ret,sEchoStr=wxcpt.VerifyURL(sVerifyMsgSig, sVerifyTimeStamp,sVerifyNonce,sVerifyEchoStr)
   if(ret!=0):
      print("ERR: VerifyURL ret: " + str(ret))
      sys.exit(1)
   else:
      print("done VerifyURL")
      #验证URL成功，将sEchoStr返回给企业号
      print(sEchoStr.decode('utf-8'))
      return PlainTextResponse(sEchoStr.decode('utf-8'))

@app.post("/chat/callback")
async def handle_wechat_message(
    request: Request,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
):
    """处理微信加密消息（POST请求）"""
    # 读取原始XML数据
    body = await request.body()
    data_dict = xmltodict.parse(body)

    sToken = os.environ['WECHAT_TOKEN']
    sEncodingAESKey = os.environ['WECHAT_AESKEY']
    sCorpID = os.environ['WECHAT_CORP_ID']
    wxcpt=WXBizJsonMsgCrypt(sToken,sEncodingAESKey,sCorpID)

    sReqNonce = nonce
    sReqTimeStamp = timestamp

    sReqMsgSig = msg_signature
    sReqData = json.dumps(data_dict["xml"])
    ret,sMsg=wxcpt.DecryptMsg( sReqData, sReqMsgSig, sReqTimeStamp, sReqNonce)
    if( ret!=0 ):
       print("ERR: DecryptMsg ret: " + str(ret))
       sys.exit(1)
    else:
       decoded_dict = xmltodict.parse(sMsg)
       print(decoded_dict)
       api = WechatApi(sCorpID, os.environ['WECHAT_SECRET'])
       response = api.httpCall(
               WECHAT_API_TYPE['SYNC_MSG'],
               {
                   "cursor" : "",
                   "token" : decoded_dict["xml"]["Token"],
                #    "limit" : "",
                #    "voice_format" : "",
                   "open_kfid" : decoded_dict["xml"]["OpenKfId"]

               })
            
       msgDict = response
       response = api.httpCall(
          WECHAT_API_TYPE['SEND_MSG'],
          {
              "touser" : msgDict['msg_list'][-1]['external_userid'],
              "open_kfid": msgDict['msg_list'][-1]['open_kfid'],
              "msgid": msgDict['msg_list'][-1]['msgid'],
              "msgtype" : "text",
              "text" : {
                  "content" : msgDict['msg_list'][-1]['text']['content']
              }
          }
       )

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ['WECHAT_FASTAPI_PORT']),ssl_keyfile=os.environ['SSL_KEYFILE_PATH'],ssl_certfile=os.environ['SSL_CERTIFILE_PATH'])
