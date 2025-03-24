import redis
from Logger import logger

"""
返回错误码和Redis连接

"""
def RedisConnect(host='localhost', port=6379, db_num = 0):
   # 创建 Redis 连接
    r = redis.Redis(
        host=host,
        port=port,
        db=db_num,
        decode_responses=True  # 自动解码二进制数据为字符串
    )
    try:
        r.ping()
        logger.info("Successfully connected to Redis!")
        return r, 0
    except redis.ConnectionError:
        logger.error("Failed to connect to Redis")
        return r, -1


if __name__ == "__main__":
    # 测试写入和读取
    redis_conn, _ = RedisConnect()
    redis_conn.set('foo', 'bar')
    value = redis_conn.get('foo')
    print(value)  # 输出: 'bar'
