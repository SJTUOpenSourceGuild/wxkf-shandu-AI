from mysql.MysqlUtils import MysqlOpsBasic
from Logger import logger
import uuid
import datetime
import json
import hashlib
import os

database_name = os.getenv('MYSQL_DATABASE')
user_table_name = "users"
user_profile_table_name = "user_profile"
msg_table_name = "msg_from_wechat"
file_msg_table_name = "file_msg"
file_table_name = "files"

class FileMysqlOps(MysqlOpsBasic):

    def __init__(self):
        super().__init__()
        logger.info("FileMysqlOps init")
        if not self.is_database_exist(database_name):
            self.create_database(database_name)
        self.select_database(database_name)

    """
    保存文件信息消息
    """
    def saveFileMsg(self, userinfo,msg, file_id):

        if not 'unionid' in userinfo:
            logger.error("没有unionid，消息无效，无法正常保存")
            return -1

        if msg['msgtype'] != 'file':
            logger.error("msg不是file类型")
            return -1

        file_msg_list = self.getFileMsgWithFileIdByUnionId(userinfo['unionid'], artical_id)
        if len(file_msg_list) > 0:
            # 如果用户已经拥有指向artical_id的公众号文章消息，就不再重复保存了
            logger.warning("user (uninon id = {}) already own msg to artical (artical id = {})".format(userinfo['unionid'], artical_id))
            return file_msg_list[0][0]

        if self.saveWechatMsg(userinfo['unionid'], msg) <= 0:
            return -1

        new_file_msg_id = 0

        try:
            file_url = ""# TODO: 这里应该是上传到COS后获取到的url
            # 插入微信公众号文章消息
            res, new_file_id = self.insert(file_msg_table_name,{"msg_id":msg["msgid"],"file_id":file_id,"file_name":"", "url":file_url})
            if not res:
                logger.warning("insert file message failed! file id = ", file_id)
            else:
                new_file_msg_id = msg["msgid"]
        except Exception as e:
            logger.warning("insert failed!", new_file_msg_id)
        finally:
            return new_file_msg_id

    def getFileMsgWithFileIdByUnionId(self, union_id, file_id):
        pass


    """
    @Params:
        - wechat_artical_content: 直接使用wechatCrawler中的getWechatArticalContent结果
    @Returns:
        插入成功就返回公众号文章在数据库中的id，失败返回-1
    """
    def saveFile(self, wechat_artical_content, msg):
        artical_url = msg['link']['url']

        if 'content_html' not in wechat_artical_content:
            logger.error("公众号文章内容错误")
            return -1

        sha = hashlib.sha1()
        sha.update("".join(wechat_artical_content['content_html'].get_text()).encode('utf-8'))

        wechat_artical_dict = {}
        wechat_artical_dict["hash"] = sha.hexdigest()
        wechat_artical_dict['title'] = wechat_artical_content['title']
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
            artical_id = self.saveWechatArticalDict(wechat_artical_dict)
            if artical_id <= 0:
                logger.error("保存公众号文章出错")
                return -1
        except Exception as e:
            logger.error("保存公众号文章出错")
            return -1
        return artical_id

    def ifFileExist(self, artical_hash):
        try:
            res = self.query(wechat_artical_table_name, ['id'], 'hash = "' + artical_hash + '"')
            if not res[0] or len(res[1]) == 0:
                return 0
            return int(res[1][0][0])
        except Exception as e:
            logger.error("执行query失败, hash = " + artical_hash + ", error = " + str(e))
            return -1;

    def setFileSummary(self, artical_id, summary):
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
