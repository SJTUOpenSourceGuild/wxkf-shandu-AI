from MysqlUtils import MysqlOpsBasic
from Logger import logger
import uuid
import datetime
import json
from wechatCrawler import getWechatArticalContentWithImageLink

database_name = "wechat_db"
user_table_name = "users"
user_profile_table_name = "user_profile"
msg_table_name = "msg_from_wechat"
text_msg_table_name = "text_msg"
link_msg_table_name = "link_msg"

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
    
    def saveWechatLinkMsg(self, userinfo,msg):
        if not 'unionid' in userinfo:
            logger.error("没有unionid，消息无效，无法正常保存")
            return

        if msg['msgtype'] != 'link':
            logger.error("msg不是link类型")
            return

        res, new_msg_id = self.insert(msg_table_name,{"msg_id":msg["msgid"], "msg_type":msg['msgtype'],"user_union_id":userinfo['unionid'], "open_kfid":msg["open_kfid"], "send_time":datetime.datetime.fromtimestamp(int(msg['send_time'])).strftime("%Y-%m-%d %H:%M:%S"), "origin_data":json.dumps(msg)})
        if not res:
            logger.error("insert " + msg_table_name + " failed!")
            return

        err_code, info_dict = getWechatArticalContentWithImageLink(msg['link']['url'])
        if err_code != 0:
            logger.error("获取公众号文章数据失败")

        if msg['link']['title'] != info_dict['title']:
            logger.warning("标题好像有问题")

        res, new_text_msg_id = self.insert(link_msg_table_name,{"msg_id":msg["msgid"],"title":msg['link']['title'], "cover_url":msg['link']['pic_url'], "description":msg['link']['desc'], "url":msg['link']['url'], "html":info_dict['content_html'], "parsed_content":info_dict['parsed_content']})
        if not res:
            logger.warning("insert failed!", new_text_msg_id)
        return info_dict['parsed_content']
