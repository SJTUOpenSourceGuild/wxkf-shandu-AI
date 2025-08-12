## 简介

本项目“帮我读AI”项目的一部分，“帮我读AI”的设计架构中，由Golang，采用Gin接收来自微信的回调函数，然后将消息直接发送给RabbitMQ消息队列。python从消息队列中获取回调数据后加以处理。

这样设计的好处是，可以结合Golang的高并发特性，和Python的生态。
因为笔者想做的服务，需要结合AI大语言模型、从链接中获取微信文章数据等功能，python由较好的生态。

## 运行

配置好环境后执行如下命令：

`python main.py`


其中配置环境包括下文提到的环境变量配置以及安装依赖

### 环境变量配置

项目正常运行，需要设置如下环境变量

#### 微信客服

* WECHAT_TOKEN
* WECHAT_AESKEY
* WECHAT_CORP_ID
* WECHAT_SECRET

这4个都是从[微信客服](https://kf.weixin.qq.com/)处获得，也就是需要开通*微信客服*并且**完成企业认证**。

具体获取方式如下：

首先需要获取企业ID，*微信客服*开通完成后就可以在[企业信息](https://kf.weixin.qq.com/kf/frame#/corpinfo)处看到企业ID了，将*WECHAT_CORP_ID*环境变量设置为企业ID。

然后来获取TOKEN和EncodingAESKey，两者是在**配置回调**的时候自行填写或者随机生成的，获得后分别设志伟WECHAT_TOKEN和WECHAT_AESKEY两个环境变量

配置回调完成后（具体配置方法见下文），就可以获得Secret了，设置为WECHAT_SECRET环境变量。
在配置回调过程中，填写的URL必须是https（不确定），配置方法见下问FastAPI相关

#### 大语言模型

项目使用“扣子”的大语言模型，因此想要正确运行，需要配置扣子相关的如下信息。
具体含义和使用方法参见coze官方文档

* COZE_API_BASE: 可以省略，如果不设置则采用coze官方的url
* COZE_API_TOKEN
* COZE_BOT_ID

#### 数据库

用到了2种数据库，Redis和MySQL，因此需要设置相关环境变量

* MYSQL_HOST
* MYSQL_PORT
* MYSQL_USERNAME
* MYSQL_PASSWORD

* REDIS_HOST
* REDIS_PORT
* REDIS_PASSWORD


#### 对象存储

项目采用腾讯云的对象存储保存文件，使用前需要配置如下环境变量

* COS_SECRET_ID
* COS_SECRET_KEY
* COS_REGION

#### RabbitMQ

另外服务使用了RabbitMQ消息队列，因此需要指定RabbitMQ服务器及用户密码
这部分是RabbitMQ相关的环境变量，包括HOST、PORT、USERNAME、PASSWORD等

* RABBITMQ_HOST
* RABBITMQ_PORT
* RABBITMQ_USERNAME
* RABBITMQ_PASSWORD

### 微信客服的回调配置

回调配置需要加解密，官方提供了各种语言的[加解密库](https://developer.work.weixin.qq.com/devtool/introduce?id=36388)，以Python为例，利用官方提供的WXBizJsonMsgCrypt类，分别填入与回调配置中相同的Token、EncodingAESKey和企业ID：
```python
wxcpt=WXBizJsonMsgCrypt(sToken,sEncodingAESKey,sCorpID)
```

利用`VerifyURL`就可以完成对回调数据的解密了：

```python
ret,sEchoStr=wxcpt.VerifyURL(sVerifyMsgSig, sVerifyTimeStamp,sVerifyNonce,sVerifyEchoStr)
```

只需要将结果中的`sEchoStr`返回即可，不过这里需要注意的是，在FastAPI中需要借助PlainTextResponse完成返回：`return PlainTextResponse(sEchoStr)`，直接返回sEchoStr会导致配置失败。

## 代码结构

* main.py: 消息队列主要处理逻辑，包括如何解析微信客服回调信息，如何处理等
* wechatapi.py: 微信客服相关官方接口相关处理逻辑
* RedisUtils.py: Redis相关代码
* TXCOSManager.py: 腾讯云对象存储相关
* coze.py: 扣子相关
* wxkf_decode/ -> 微信客服加码/解码相关
* crawler/ -> 微信公众号文字爬虫
* mysql/ -> 数据库相关
* utils/ -> 工具类
