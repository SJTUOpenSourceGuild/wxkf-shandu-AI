from mysql.MysqlUtils import MysqlOpsBasic
from Logger import logger
import uuid
import datetime
import json
import hashlib
import os
from utils.utils import calculate_file_hash
from TXCOSManager import TXCOSManager

database_name = os.getenv('MYSQL_DATABASE')
user_table_name = "users"
user_profile_table_name = "user_profile"
msg_table_name = "msg_from_wechat"
text_msg_table_name = "text_msg"
wechat_artical_msg_table_name = "wechat_artical_msg"
wechat_artical_table_name = "wechat_artical"
file_msg_table_name = "file_msg"
file_table_name = "files"

class WechatMysqlOps(MysqlOpsBasic):

    def __init__(self):
        super().__init__()
        logger.info("WechatMysqlOps init")
        if not self.is_database_exist(database_name):
            self.create_database(database_name)
        self.select_database(database_name)

    """
    根据union id判断用户是否存在，存在返回用户对应id，否则返回0/-1
    """
    def ifUserExist(self, union_id):
        try:
            res = self.query(user_table_name, ['id'], 'union_id = "' + union_id + '"')
            if not res[0] or len(res[1]) == 0:
                return 0
            return int(res[1][0][0])
        except Exception as e:
            logger.error("执行query失败, union id = " + union_id + ", error = " + str(e))
            return -1;


    def save_user_to_db(self, customer_info):
        if not 'unionid' in customer_info:
            logger.error("no unionid in customer_info")
            return
        if self.ifUserExist(customer_info["unionid"]) > 0:
            logger.warning("user (union id =" + customer_info["unionid"] + " already exist")
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
    
    def saveWechatTextMsg(self, userinfo, msg):
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
    保存消息，需要注意的是这里是基础消息，没有具体内容，内容在其他table中
    @Params
        - user_unionid: 用户在微信系统 中的unionid
        - msg:字典，微信客服回调函数的参数，需要包含如下字段：
            - msg_id
            - msgtype
            - open_kfid
            - send_time
    @Returns:
       - id: 保存成功返回消息在数据库中的id，否则返回-1
    """
    def saveWechatMsg(self, user_unionid, msg):
        try:
            res, new_msg_id = self.insert(msg_table_name,{"msg_id":msg["msgid"], "msg_type":msg['msgtype'],"user_union_id":user_unionid, "open_kfid":msg["open_kfid"], "send_time":datetime.datetime.fromtimestamp(int(msg['send_time'])).strftime("%Y-%m-%d %H:%M:%S"), "origin_data":json.dumps(msg)})
            if not res:
                logger.error("insert " + msg_table_name + " failed!")
                return -1
        except Exception as e:
            logger.error("insert " + msg_table_name + " failed!")
            return -1
        return int(new_msg_id)
    
    """
    保存微信公众号文章消息
    """
    def saveWechatArticalMsg(self, userinfo,msg, artical_id):

        if not 'unionid' in userinfo:
            logger.error("没有unionid，消息无效，无法正常保存")
            return -1

        if msg['msgtype'] != 'link':
            logger.error("msg不是link类型")
            return -1

        artical_msg_list = self.getArticalMsgWithArticalIdByUnionId(userinfo['unionid'], artical_id)
        if len(artical_msg_list) > 0:
            # 如果用户已经拥有指向artical_id的公众号文章消息，就不再重复保存了
            logger.warning("user (uninon id = {}) already own msg to artical (artical id = {})".format(userinfo['unionid'], artical_id))
            return artical_msg_list[0][0]

        if self.saveWechatMsg(userinfo['unionid'], msg) <= 0:
            return -1

        new_wechat_artical_msg_id = 0

        try:
            artical_url = msg['link']['url']
            # 插入微信公众号文章消息
            res, new_wechat_artical_id = self.insert(wechat_artical_msg_table_name,{"msg_id":msg["msgid"],"artical_id":artical_id,"title":msg['link']['title'], "url":artical_url})
            if not res:
                logger.warning("insert wechat artical message failed! artical id = ", artical_id)
            else:
                new_wechat_artical_msg_id = msg["msgid"]
        except Exception as e:
            logger.warning("insert failed!", new_wechat_artical_msg_id)
        finally:
            return new_wechat_artical_msg_id


    """
    @Params:
        - wechat_artical_content: 直接使用wechatCrawler中的getWechatArticalContent结果
    @Returns:
        插入成功就返回公众号文章在数据库中的id，失败返回-1
    """
    def saveWechatArtical(self, wechat_artical_content, msg):
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
    """
    保存文件
    如果文件在数据库中不存在，则插入
    如果文件已经存在于数据库，则返回当前文件的id
    @Params
      * data: dict，需要包含如下关键字：
          file_name
          file_type
          file_size
          hash  非空
          url 非空
    """
    def saveFileDict(self, data):
        # 1. 判断数据是否已经存在
        # 2. 如果已经存在，就返回对应数据的id
        # 3. 如果不存在，则插入后返回新数据的id
        res = self.ifFileExist(data['hash'])
        if res > 0:
            # 已经存在指定hash的公众号文章
            return res
        res, new_file_id = self.insert(file_table_name,data)
        if not res:
            logger.warning("insert failed!" + file_table_name)
            return -1;
        return int(new_file_id)

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
    def saveWechatArticalDict(self, data):
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
            res, data = self.query(wechat_artical_table_name, ['id'], 'url = "' + artical_url + '"')
            if not res:
                return 0
            if len(data) < 1 or len(data[0]) < 1:
                return 0
            return int(data[0][0])
        except Exception as e:
            logger.error("执行query失败, artical url = " + artical_url + ", error = " + str(e))
            return -1;

    def getWechatArticalByUrl(self, artical_url):
        try:
            res, data = self.query(wechat_artical_table_name, None, 'url = "' + artical_url + '"')
            if not res:
                return ""
            return data[0]
        except Exception as e:
            logger.error("执行query失败, hash = " + artical_hash + ", error = " + str(e))
            return "";
    """
    判断指定hash的文件是否已经存在，如果已经存在，则返回id，不存在返回0，出错返回-1
    """
    def ifFileExist(self, file_hash):
        try:
            res = self.query(file_table_name, ['id'], 'hash = "' + file_hash + '"')
            if not res[0] or len(res[1]) == 0:
                return 0
            return int(res[1][0][0])
        except Exception as e:
            logger.error("执行query失败, hash = " + artical_hash + ", error = " + str(e))
            return -1;

    def getFileById(self, file_id):
        try:
            res, data = self.query(file_table_name, None, 'id = "' + str(file_id) + '"')
            if not res:
                return ""
            return data[0]
        except Exception as e:
            logger.error("执行query失败, file_id = " + str(file_id) + ", error = " + str(e))
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

    def setFileSummary(self, file_id, summary):
        error_code,res = self.update(file_table_name, {"summary":summary}, "id = " + str(file_id))
        return error_code


    """
    判断用户是否拥有指向指定公众号文章的消息
    根据用户的unionid获取他拥有的所有指向指定公众号文章的(公众号文章)消息
    @Params:
      - union_id:指定用户的union_id
      - artical_id: 指定公众号文章在数据库中的id
    @Return: 
        Array: 数组，包含用户拥有的公众号文章消息
    """
    def getArticalMsgWithArticalIdByUnionId(self, union_id, artical_id):
        # 编写SQL查询
        sql = """
            SELECT wechat_artical_msg.*
            FROM msg_from_wechat
            INNER JOIN wechat_artical_msg
                ON msg_from_wechat.msg_id = wechat_artical_msg.msg_id
            WHERE
                msg_from_wechat.user_union_id = '{}'
                AND wechat_artical_msg.artical_id = {};
            """.format(union_id, artical_id)
        results = self.excute_cmd(sql)
        return results

    """
    保存文件信息消息
    """
    def saveFileMsg(self, userinfo,msg, file_id, file_name):

        if not 'unionid' in userinfo:
            logger.error("没有unionid，消息无效，无法正常保存")
            return -1

        if msg['msgtype'] != 'file':
            logger.error("msg不是file类型")
            return -1

        file_msg_list = self.getFileMsgWithFileIdByUnionId(userinfo['unionid'], file_id)
        if len(file_msg_list) > 0:
            # 如果用户已经拥有指向artical_id的公众号文章消息，就不再重复保存了
            logger.warning("user (uninon id = {}) already own msg to artical (artical id = {})".format(userinfo['unionid'], file_id))
            return file_msg_list[0][0]

        if self.saveWechatMsg(userinfo['unionid'], msg) <= 0:
            return -1

        new_file_msg_id = 0

        try:
            res, new_file_msg_id = self.insert(file_msg_table_name,{"msg_id":msg["msgid"],"file_id":file_id, "file_name":file_name})
            print(res, ", ",new_file_msg_id)
            if not res:
                logger.warning("insert file message failed! file id = ", file_id)
            else:
                new_file_msg_id = msg["msgid"]
        except Exception as e:
            logger.warning("insert failed!", new_file_msg_id)
        finally:
            return new_file_msg_id

    def getFileMsgWithFileIdByUnionId(self, union_id, file_id):
        # 编写SQL查询
        sql = """
            SELECT file_msg.*
            FROM msg_from_wechat
            INNER JOIN file_msg
                ON msg_from_wechat.msg_id = file_msg.msg_id
            WHERE
                msg_from_wechat.user_union_id = '{}'
                AND file_msg.file_id = {};
            """.format(union_id, file_id)
        results = self.excute_cmd(sql)
        return results




    """
    @Params:
        - file_info: dict, {file_name, file_type, url}
        - msg
    @Returns:
        插入成功就返回公众号文章在数据库中的id，失败返回-1
    """
    def saveFile(self, file_path, bucket_name, key):
        filename_with_ext = os.path.basename(file_path)
        filename, file_ext = os.path.splitext(filename_with_ext)
        hash_str = calculate_file_hash(file_path)
        filesize = os.path.getsize(file_path)

        file_dict = {}
        file_dict["hash"] = hash_str
        file_dict['file_name'] = filename_with_ext
        file_dict['file_size'] = filesize
        file_dict['file_type'] = file_ext[1:]
        file_dict['tx_cos_bucket_name'] = bucket_name
        file_dict['tx_cos_key'] = key

        try:
            file_id = self.saveFileDict(file_dict)
            if file_id <= 0:
                logger.error("保存文件出错")
                return -1
        except Exception as e:
            logger.error("保存文件出错")
            return -1
        return file_id


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

        file_path = "./logs/test2.pdf"
        filename_with_ext = os.path.basename(file_path)
        filename, file_ext = os.path.splitext(filename_with_ext)
        CosManager = TXCOSManager()
        CosManager.uploadFileWithRetry(file_path,'wx-minip-bangwodu-01-1320810990', filename_with_ext, "user-upload-files/test/")
        url = CosManager.getObjectUrl('wx-minip-bangwodu-01-1320810990', "user-upload-files/test/" + filename_with_ext)

        print(self.saveFile("./logs/test2.pdf", 'wx-minip-bangwodu-01-1320810990',"user-upload-files/test/" + filename_with_ext))


if __name__ == "__main__":
        wechat_db_ops = WechatMysqlOps()
        wechat_db_ops.test()
