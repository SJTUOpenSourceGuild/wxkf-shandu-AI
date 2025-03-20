import sseclient
import requests
import json

import uuid
import os


bot_app_key = "PXJHVytI"  # 机器人密钥，不是BotBizId (从运营接口人处获取)
visitor_biz_id = "202403130001"  # 访客 ID（外部系统提供，需确认不同的访客使用不同的 ID）
streaming_throttle = 1  # 节流控制

def get_session():
    # 生成一个 UUID
    new_uuid = uuid.uuid4()
    # 将 UUID 转换为字符串
    session_id = str(new_uuid)
    return session_id


def get_request_id():  # 生成的request_id有48位
    # 生成 24 个字节的随机数据
    random_bytes = os.urandom(24)

    # 将随机数据转换为十六进制字符串
    request_id = random_bytes.hex()
    return request_id

def sse_client(sid: str, content):
    req_data = {
        "content": content,
        "bot_app_key": bot_app_key,
        "visitor_biz_id": visitor_biz_id,
        "session_id": sid,
        "streaming_throttle": streaming_throttle
    }
    try:
       resp = requests.post("https://wss.lke.cloud.tencent.com/v1/qbot/chat/sse", data=json.dumps(req_data),
                            stream=False, headers={"Accept": "text/event-stream"})
       client = sseclient.SSEClient(resp)
       for ev in client.events():
           # print(f'event:{ev.event}, "data:"{ev.data}')
           data = json.loads(ev.data)
           if ev.event == "reply":
               if data["payload"]["is_from_self"]:  # 自己发出的包
                   pass
               elif data["payload"]["is_final"]:  # 服务端event传输完毕；服务端的回复是流式的，最后一条回复的content，包含完整内容
                   return data["payload"]["content"]
           else:
               pass
    except Exception as e:
        return ""
        print(e)

def askAI(content):
    session_id = get_session()
    return sse_client(session_id, content)


if __name__ == "__main__":
    res = askAI("""好的，我现在需要解决用户遇到的Python报错问题：导入session模块时出现ModuleNotFoundError。用户提供了三个搜索结果，我需要仔细分析这些内容，找出解决方案。

首先，用户的错误信息是“ModuleNotFoundError: No module named 'session’”。根据网页2和网页3，这个错误通常是因为模块未安装、路径问题或拼写错误。但“session”可能是一个自定义模块，或者用户可能拼错了标准库或第三方库的名称。

接下来，检查网页1提到的导入机制。用户可能没有正确设置sys.path或项目结构，导致Python找不到模块。网页2提到项目结构、动态路径添加和PYTHONPATH配置，这可能相关。另外，网页3建议检查模块是否安装，但如果是自定义模块，安装不适用，需要检查路径。

然后，考虑可能的拼写错误。用户是否将模块名写错了？比如，标准库中有http.client中的session，或者第三方库如requests.Session，但直接导入'session'可能不正确。因此，可能是用户想导入其他模块，但名称错误。

另外，动态导入和相对导入的问题也需要考虑。网页1提到绝对导入和相对导入的区别，如果用户的自定义模块在包内，可能需要正确使用相对导入。此外，检查sys.path是否正确包含模块所在目录，如网页2中的动态添加路径方法。

最后，综合所有信息，解决方案应包括检查模块是否存在、拼写是否正确、路径配置、项目结构是否正确，以及可能的虚拟环境问题。需要分步骤引导用户排查，并引用相关网页的内容作为依据。""")
    print("----------")
    print("answer: ", res)
