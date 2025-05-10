from MysqlUtils import MysqlOpsBasic
from Logger import logger
import uuid
import datetime
import json
from wechatCrawler import getWechatArticalContent
import hashlib
import os

database_name = os.getenv('MYSQL_DATABASE')
user_table_name = "users"
user_profile_table_name = "user_profile"
msg_table_name = "msg_from_wechat"
text_msg_table_name = "text_msg"
wechat_artical_msg_table_name = "wechat_artical_msg"
wechat_artical_table_name = "wechat_artical"

class WechatMysqlOps(MysqlOpsBasic):

    def __init__(self):
        super().__init__()
        logger.info("WechatMysqlOps init")
        if not self.is_database_exist(database_name):
            self.create_database(database_name)
        self.select_database(database_name)

    def save_user_to_db(self, customer_info):
        if not 'unionid' in customer_info:
            logger.error("no unionid in customer_info")
            return
        uid = str(uuid.uuid4()).replace("-", "")[:32]
        res, new_id = self.insert(user_table_name,{"uid":uid, "union_id":customer_info['unionid']})
        if not res:
            logger.error("insert " + user_table_name + " failed!")
            return
    
        #同时插入profile信息
        res, new_user_profile_id = self.insert(user_profile_table_name,{"user_id":new_id, "nickname":customer_info['nickname'], "avatar":customer_info['avatar'], "gender":customer_info['gender']})
        if not res:
            logger.error("insert " + user_profile_table_name + " failed!")
    
    def saveWechatTextMsg(self, userinfo,msg):
        if not 'unionid' in userinfo:
            logger.error("没有unionid，消息无效，无法正常保存")
            return

        if msg['msgtype'] != 'text':
            logger.error("msg类型不是text")
        res, new_msg_id = self.insert(msg_table_name,{"msg_id":msg["msgid"], "msg_type":msg['msgtype'],"user_union_id":userinfo['unionid'], "open_kfid":msg["open_kfid"], "send_time":datetime.datetime.fromtimestamp(int(msg['send_time'])).strftime("%Y-%m-%d %H:%M:%S"), "origin_data":json.dumps(msg)})
        if not res:
            logger.error("insert " + msg_table_name + " failed!")
            return
    
        res, new_text_msg_id = self.insert(text_msg_table_name,{"msg_id":msg["msgid"],"content":msg['text']['content']})
        if not res:
            logger.error("insert " + text_msg_table_name + " failed!")
    
    """
    这里相对比较复杂，先保存公众号文章，然后在创建新的公众号文章消息
    """
    def saveWechatArticalMsg(self, userinfo,msg, wechat_artical_content):
        artical_url = msg['link']['url']
        if msg['link']['title'] != wechat_artical_content['title']:
            logger.warning("标题好像有问题")

        if 'content_html' not in wechat_artical_content:
            logger.error("公众号文章内容错误")
            return -1, -1

        sha = hashlib.sha1()
        sha.update("".join(wechat_artical_content['content_html'].get_text()).encode('utf-8'))

        wechat_artical_dict = {}
        wechat_artical_dict["hash"] = sha.hexdigest()
        if 'title' in wechat_artical_content:
            wechat_artical_dict['title'] = wechat_artical_content['title']
        else:
            wechat_artical_dict['title'] = msg['link']['title']
        wechat_artical_dict['cover_url'] = msg['link']['pic_url']
        wechat_artical_dict['description'] = msg['link']['desc']
        if 'author' in wechat_artical_content:
            wechat_artical_dict['author'] = wechat_artical_content['author']
        if 'nickname' in wechat_artical_content:
            wechat_artical_dict['nickname'] = wechat_artical_content['nickname']
        wechat_artical_dict['url'] = artical_url
        wechat_artical_dict['html'] = wechat_artical_content['content_html']
        if 'parsed_content' in wechat_artical_content:
            wechat_artical_dict['parsed_content'] = wechat_artical_content['parsed_content']

        try:
            artical_id = self.saveWechatArtical(wechat_artical_dict)
            if artical_id <= 0:
                logger.error("保存公众号文章出错")
                return -1,-1
        except Exception as e:
            logger.error("保存公众号文章出错")
            return -1,-1

        if not 'unionid' in userinfo:
            logger.error("没有unionid，消息无效，无法正常保存")
            return -1, -1

        if msg['msgtype'] != 'link':
            logger.error("msg不是link类型")
            return -1, -1

        try:
            res, new_msg_id = self.insert(msg_table_name,{"msg_id":msg["msgid"], "msg_type":msg['msgtype'],"user_union_id":userinfo['unionid'], "open_kfid":msg["open_kfid"], "send_time":datetime.datetime.fromtimestamp(int(msg['send_time'])).strftime("%Y-%m-%d %H:%M:%S"), "origin_data":json.dumps(msg)})
            if not res:
                logger.error("insert " + msg_table_name + " failed!")
                return -1, artical_id
        except Exception as e:
            logger.error("insert " + msg_table_name + " failed!")
            return -1, artical_id


        try:
            # 插入微信公众号文章消息
            res, new_wechat_artical_msg_id = self.insert(wechat_artical_msg_table_name,{"msg_id":msg["msgid"],"artical_id":artical_id,"title":msg['link']['title'], "url":artical_url})
            if not res:
                logger.warning("insert failed!", new_wechat_artical_msg_id)
        except Exception as e:
            logger.warning("insert failed!", new_wechat_artical_msg_id)
        finally:
            return new_msg_id, artical_id


    """
    保存微信公众号文章
    如果内容在数据库中不存在，则插入
    如果文章已经存在于数据库，则返回当前公众号文章的id
    @Params
      * data: dict，需要包含如下关键字：
          hash  非空
          title    
          cover_url
          description
          author
          nickname
          url 非空
          html 非空
          parsed_content
          summary
    """
    def saveWechatArtical(self, data):
        # 1. 判断数据是否已经存在
        # 2. 如果已经存在，就返回对应数据的id
        # 3. 如果不存在，则插入后返回新数据的id
        res = self.ifWechatArticalExist(data['hash'])
        if res > 0:
            # 已经存在指定hash的公众号文章
            return res
        res, new_wechat_artical_id = self.insert(wechat_artical_table_name,data)
        if not res:
            logger.warning("insert failed!" + wechat_artical_table_name)
            return -1;
        return int(new_wechat_artical_id)

    def ifWechatArticalExistByUrl(self, artical_url):
        try:
            res = self.query(wechat_artical_table_name, ['id'], 'url = "' + artical_url + '"')
            if not res[0] or len(res[1]) == 0:
                return 0
            return int(res[1][0][0])
        except Exception as e:
            logger.error("执行query失败, hash = " + artical_hash + ", error = " + str(e))
            return -1;

    def getWechatArticalByUrl(self, artical_url):
        try:
            res = self.query(wechat_artical_table_name, ['parsed_content'], 'url = "' + artical_url + '"')
            if not res[0] or len(res[1]) == 0:
                return ""
            return res[1][0][0]
        except Exception as e:
            logger.error("执行query失败, hash = " + artical_hash + ", error = " + str(e))
            return "";

    """
    判断指定hash的公众号文章是否已经存在，如果已经存在，则返回id，不存在返回0，出错返回-1
    """
    def ifWechatArticalExist(self, artical_hash):
        try:
            res = self.query(wechat_artical_table_name, ['id'], 'hash = "' + artical_hash + '"')
            if not res[0] or len(res[1]) == 0:
                return 0
            return int(res[1][0][0])
        except Exception as e:
            logger.error("执行query失败, hash = " + artical_hash + ", error = " + str(e))
            return -1;

    def setWechatArticalSummary(self, artical_id, summary):
        error_code,res = self.update(wechat_artical_table_name, {"summary":summary}, "id = " + str(artical_id))
        return error_code

    def test(self):
        """
        wechat_artical_dict = {
                "hash":"xxxxqqqq",
                "title":"title",
                "cover_url":"cover_url",
                "description":"description",
                "author":'author',
                "nickname":'nickname',
                "url":'artical_url',
                "html":'content_html',
                "parsed_content": 'parsed_content'
                }
        res, new_text_msg_id = self.insert(wechat_artical_table_name,wechat_artical_dict)
        """
        error_code,res = self.update(wechat_artical_table_name, {"summary":"summary 2"}, "id = 2")
        print(error_code,"|" ,res)

if __name__ == "__main__":
        wechat_db_ops = WechatMysqlOps()
        wechat_db_ops.test()
