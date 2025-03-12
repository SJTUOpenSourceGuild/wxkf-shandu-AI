import atexit
import signal
import pymysql
import os

class mysqlOps:
    """
    将SQL语句保存一些接口，方便使用。

    构造函数需要给定mysql数据库的
    - host
        数据库地址，如果省略，会读取环境变量MYSQL_HOST
    - user
        数据库用户名，如果省略，会读取环境变量MYSQL_USERNAME
    - password
        数据库用户密码，如果省略，会读取环境变量MYSQL_PASSWORD
    - databasee
        使用的数据库名，默认为None
    - port
        数据库端口，默认为3306
    """
    def __init__(self, host=os.getenv('MYSQL_HOST'), user=os.getenv('MYSQL_USERNAME'), password=os.getenv('MYSQL_PASSWORD'), port=3306, database=None):
        signal.signal(signal.SIGINT, self.signal_exit)
        atexit.register(self.cleanUp)
        try:
            self.db = pymysql.connect(host=host,
                                      user=user,
                                      password=password,
                                      database=database,
                                      port=port)
        except Exception as e:
            print("connect mysql server failed: ", e)
            exit()
        if not self.db.open:
            print("connect mysql server failed")
            exit()

    def __del__(self):
        self.cleanUp()

    def signal_exit(self,signum,frame):
        self.cleanUp()
        exit()

    def cleanUp(self):
        try:
            self.db.close()
        except Exception as e:
            print(e)

    def excute_cmd(self,sql_cmd):
        """执行sql语句

        Args:
          sql_cmd: String，要执行的sql语句

        Returns:
          tuple: sql执行结果

        Raises:
          pymysql.err.ProgrammingError
        """
        with self.db.cursor() as cursor:
            try:
                cursor.execute(sql_cmd)
                self.db.commit()
            except Exception as e:
                self.db.rollback()
                raise e
            else:
                return cursor.fetchall()

    def get_db_version(self):
        """
        获取数据库版本
        """
        return self.excute_cmd("SELECT VERSION()")

    def get_databases(self):
        """
        获取所有数据库
        Returns:
          List: 数组，元素为表示数据库的字符串

        """
        dbs = []
        databases = self.excute_cmd("SHOW DATABASES")
        for db in databases:
            dbs.append(db[0])
        return dbs

    def is_database_exist(self, database_name):
        """
        判断指定database是否存在
        Args:
          database_name: 想要查看是否存在的数据库名

        Returns:
          bool: 表示指定数据库是否存在
        """
        return database_name in self.get_databases()

    def create_database(self, database_name):
        """
        创建数据库

        Args:
          database_name: 希望创建的数据库名称
        Returns:
          None
        """
        if self.is_database_exist(database_name):
            return
        return self.excute_cmd("CREATE DATABASE " + database_name)

    def select_database(self, database_name):
        """
        选择数据库
        """
        return self.excute_cmd("USE " + database_name)

    def get_tables(self):
        """
        获取本数据库的所有table名称

        Returns:
            list: 每个是字符串，表的名字
        """
        retval = []
        tables = self.excute_cmd("SHOW TABLES")
        for table in tables:
            retval.append(table[0])
        return retval

    def is_table_exist(self, table_name):
        """
        判断数据库是否存在
        """
        return table_name in self.get_tables()

    def get_table_columns(self, table_name):
        """
        获取表格的所有字段

        Returns:
         list: 每个元素是字符串，表示字段名
        """
        res = []
        sql = "DESCRIBE " + table_name
        columns = self.excute_cmd(sql)
        for column in columns:
            res.append(column[0])
        return res

    def create_table(self,name, columns, foreign_key=None, unique_list=None):
        """新建表

        Args:
          name: String，表名
          columns: list, 表的字段列表
                    其中每一项是字典，其中必须包含字段'name'和'type'，表示字段名和字段数据类型。
                    可选字段:
                      'comment', 对字段的描述
                      'postfix'，该字段对应list，当该字段存在时，list中每一项都会被追加到这个字段后，
                      比如'postfix':['NOT NULL', 'AUTO_INCREMENT', 'PRIMARY KEY']
          foreign_key: 长度为3的list，可选，执行表的外键。
                       第1个元素表示外键在本表内对应的column名，比如在参数columns中
                       第2个元素表示外键对应的表格名
                       第3个元素表示外键对应的表格中的column名
                       例如: ["foreight_id", "other_table", "id"]
          unique: list，每个元素是columns中的列

        Returns:
          bool: 表示表创建是否成功
          String: 执行信息

        Raises:
        """
        if self.is_table_exist(name):
            return False, "table already exist"
        sql = "CREATE TABLE "
        sql += name + " ("
        for column in columns:
            sql += column['name'] + " "
            sql += column['type'] + " "
            if 'postfix' in column:
                for pf in column['postfix']:
                    sql += pf + " "
            if 'comment' in column and len(column['comment']) > 0:
                sql += " COMMENT '" + column['comment'] + "' "
            sql += ","
        sql = sql[:-1] # 删除最后一个逗号
        if foreign_key:
            sql += ", FOREIGN KEY ( " + foreign_key[0] + " ) REFERENCES " + foreign_key[1] + "(" + foreign_key[2] + ")"

        if unique_list and len(unique_list) > 0:
            sql += ", UNIQUE("
            for unique_item in unique_list:
                sql += unique_item + ","
            sql = sql[:-1] # 删除最后一个逗号
            sql += ")"
        sql += ")"

        try:
            res = self.excute_cmd(sql)
        except Exception as e:
            return False, str(e)
        else:
            return True, str(res)

    def copy_table(self, source_table, new_table):
        """
        未完成

        新建表格，并将source_table中的数据，复制到新表

        TODO:未完成，只完成了表格的拷贝，但是没完成数据拷贝
        """
        sql = "SHOW CREATE TABLE " + source_table
        try:
            res = self.excute_cmd(sql)
        except Exception as e:
            return False, str(e)

        create_new_table_sql = res[0][1].replace(source_table, new_table, 1)

        try:
            res = self.excute_cmd(create_new_table_sql)
        except Exception as e:
            return False, str(e)
        else:
            return True, str(res)

    def copy_table_to_other_db(self, other, source_table, new_table = None):
        """
        未完成

        在other数据库中新建表格new_table（如果new_table为None，则创建和source_table同名的table），并将source_table中的数据，复制到新表

        TODO:未完成，只完成了表格的拷贝，但是没完成数据拷贝
        """
        sql = "SHOW CREATE TABLE " + source_table
        try:
            res = self.excute_cmd(sql)
        except Exception as e:
            return False, str(e)

        create_new_table_sql = res[0][1]
        """
        if isinstance(new_table, str) and len(new_table) > 0:
            create_new_table_sql = create_new_table_sql.replace(source_table, new_table, 1)

        try:
            res = other.excute_cmd(create_new_table_sql)
        except Exception as e:
            return False, str(e)
        """
        all_data = self.query(source_table,limit=5)
        return True, ""

    def insert(self, table_name, kv_dict):
        """向表格插入数据

        Args:
          table_name: String，需要插入数据的表名
          kv_dict: Dict,每一项key是字段名，value是字段的值

        Returns:
          bool: 表示表创建是否成功
          String: 执行信息

        Raises:
        """
        if len(kv_dict) == 0:
            return False, "插入内容为空"
        sql = "INSERT INTO "
        sql += table_name + "("
        for k,v in kv_dict.items():
            if isinstance(v, str):
                if len(v) > 0:
                    sql += k + ","
            else:
                sql += k + ","

        sql = sql[:-1] # 删除最后一个逗号
        sql += ") VALUES ("

        for k,v in kv_dict.items():
            if isinstance(v, str):
                if len(v) > 0:
                    sql += "'" + v + "',"
            else:
                sql += str(v) + ","

        sql = sql[:-1]
        sql += ")"
        try:
            res = self.excute_cmd(sql)
        except Exception as e:
            return False, str(e)
        else:
            return True, str(res)

    def query(self, table_name, col_names = None, filter_condition = None, limit = None, offset = None):
        """
        Args:
            table_name: 查询的table名
            col_names: List,可选，为None时表示获取所有字段信息，每一项是Str
            filter_condition:可选 String，表示结果过滤语句，比如'age > 10 AND age < 40 OR gender == "male"'。效果相当于在SQL SELECT语句后加WHERE filter_conditions
            limit: 可选，Number，表示最大结果数量
            offset: 可选，Number, 表示结果开头的便宜距离

        Returns:
          bool: 表示表创建是否成功
          String/tuple: 执行失败时是字符串，表示错误信息，成功时是tuple

        """
        sql = "SELECT "
        if col_names == None or len(col_names) < 1:
            sql += "* FROM "
        else:
            for col_name in col_names:
                sql += col_name + ","
            sql = sql[:-1] # 删除最后一个逗号
            sql += " FROM "
        sql += table_name
        if filter_condition != None:
            sql += " WHERE " + filter_condition

        if limit != None:
            sql += " LIMIT " + str(limit)
            if offset != None:
                sql += " OFFSET " + str(offset)
        elif offset != None:
            # offset不能单独存在，必须和limit一起
            return False, "不能单独设置offset"

        try:
            res = self.excute_cmd(sql)
        except Exception as e:
            return False, str(e)
        else:
            return True, res

    def update(self, table_name, kv_dict, filter_condition):
        """
        Args:
          table_name: String，需要更新数据的表名
          kv_dict: Dict,每一项key是字段名，value是字段的值
          filter_condition: String，表示结果过滤语句，比如'age > 10 AND age < 40 OR gender == "male"'。效果相当于在SQL SELECT语句后加WHERE filter_conditions。

          filter_condition为None时表示修改所有字段，危险！！！最好通过count_num函数确定影响范围

        Returns:
          bool: 表示表更新是否成功
          String: 执行信息
        """
        sql = "UPDATE " + table_name + " SET "
        for k,v in kv_dict.items():
            if isinstance(v, str):
                sql += k + "='" + v + "',"
            else:
                sql += k + "=" + str(v) + ","
        sql = sql[:-1] # 删除最后一个逗号
        if filter_condition != None:
            sql += " WHERE " + filter_condition

        try:
            res = self.excute_cmd(sql)
        except Exception as e:
            return False, str(e)
        else:
            return True, str(res)

    def delete(self, table_name, filter_condition):
        """
        删除数据项

        Args:
          table_name: String，需要删除数据的表名
          filter_condition: String，表示结果过滤语句，比如'age > 10 AND age < 40 OR gender == "male"'。效果相当于在SQL SELECT语句后加WHERE filter_conditions。

          filter_condition为None时表示删除所有字段，危险！！！最好通过count_num函数确定影响范围

        Returns:
          bool: 表示表删除是否成功
          String: 执行信息
        """
        if filter_condition == None or not isinstance(filter_condition, str) or len(filter_condition):
            return False, "filter_condition 必须是字符串，且不能为空"
        sql = "DELETE FROM " + table_name
        sql += " WHERE " + filter_condition
        try:
            res = self.excute_cmd(sql)
        except Exception as e:
            return False, str(e)
        else:
            return True, str(res)

    def data_num(self,table_name,filter_condition = None):
        """
        判断满足filter_condition的数据是否存在，返回满足filter_condition数据的数量

        Args:
          table_name: 数据所在的table
          filter_condition: 数据的过滤条件，比如code = xx
        Returns:
          Number: 表示数据的数量
        """
        if not self.is_table_exist(table_name):
            # table不存在则返回0
            return 0
        sql = "SELECT count(*) FROM " + table_name
        if filter_condition != None:
            sql += " WHERE " + filter_condition
        try:
            res = self.excute_cmd(sql)
        except Exception as e:
            return False, -1
        else:
            return True, int(res[0][0])

if __name__ == '__main__':
    mysql = mysqlOps()
    print(mysql.get_databases())
    print(mysql.create_database("quant_test"))
    mysql.select_database("quant_test")
    print(mysql.get_tables())

    res, msg = mysql.create_table("table_name3",
            [{"name":"name1", "type":"CHAR(20)", 'comment':"名称"},{"name":"name2", "type":"INT"}])
    """
    res, msg = mysql.create_table("table_name2",
                 [{"name":"name1", "type":"CHAR(20)", "postfix":["PRIMARY KEY"]},{"name":"name2", "type":"INT"}])
    """
    if res:
        print("create table succeed")
    else:
        print("create table fail")
        print(msg)

    """
    res, msg = mysql.insert("table_name",{"name1":"12", "name2":2})
    if res:
        print("succeed")
        print(msg)
    else:
        print("fail")
        print(msg)
    tables = mysql.get_tables()
    for table in tables:
        res, msg = mysql.copy_table_to_other_db(back_mysql,table)
        if res:
            print("succeed")
            print(msg)
        else:
            print("fail")
            print(msg)
    res, msg = mysql.data_num("table_name","name1 = 1")
    if res:
        print("succeed")
        print(type(msg))
        print(msg)
    else:
        print("fail")
        print(type(msg))
        print(msg)
    res, msg = mysql.update("table_name", {"name1":"100","name2":200}, "name2 = 1")
    if res:
        print("succeed")
        print(msg)
    else:
        print("failed")
        print(msg)
    """
