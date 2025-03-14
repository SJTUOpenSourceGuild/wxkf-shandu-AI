## 简介

本项目主要处理微信客服的回调数据，有两种启动方式：

* 通过RabbitMQ消息队列，从消息队列中获取回调数据，然后处理
    * 启动入口`python RabbitMQUtils.py`
* 通过FastAPI，直接监听来自微信的回调函数，进而处理
    * 启动入口`python FastAPI_server.py`

前者的设计架构是由Golang，采用Gin接收来自微信的回调函数，然后将消息直接发送给RabbitMQ消息队列。python从消息队列中获取回调数据后加以处理。

这样设计的好处是，可以结合Golang的高并发特性，和Python的生态。
因为笔者想做的服务，需要结合AI大语言模型、从链接中获取微信文章数据等功能，python由较好的生态。

## 运行

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


#### 数据库

用到了2种数据库，Redis和MySQL，因此需要设置相关环境变量

* MYSQL_HOST
* MYSQL_PORT
* MYSQL_USERNAME
* MYSQL_PASSWORD

* REDIS_HOST
* REDIS_PORT
* REDIS_PASSWORD

#### RabbitMQ

另外服务使用了RabbitMQ消息队列，因此需要指定RabbitMQ服务器及用户密码
这部分是RabbitMQ相关的环境变量，包括HOST、PORT、USERNAME、PASSWORD等

* RABBITMQ_HOST
* RABBITMQ_PORT
* RABBITMQ_USERNAME
* RABBITMQ_PASSWORD

#### FastAPI相关

这部分的环境变量只有选择使用FastAPI直接监听回调函数时才需要设置。

* WECHAT_FASTAPI_PORT
* SSL_KEYFILE_PATH
* SSL_CERTIFILE_PATH

WECHAT_FASTAPI_PORT是FastAPI监听的端口，比如8080

SSL_KEYFILE_PATH和SSL_CERTIFILE_PATH是用来设置为HTTPS访问FastAPI服务，

因此需要域名和SSL证书。将环境变量SSL_KEYFILE_PATH设置为`.com.key`证书文件的路径，将SSL_CERTIFILE_PATH设置为`.com_bundle.crt`的路径。

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


## TODO

目前完成了从RabbitMQ数据库接受微信消息，然后做简单处理。
也完成了对发送客服消息的用户数据的保存，文本消息的保存

后续还有许多工作需要做：

- [x] 增强服务的健壮性
- [x] 完成[欢迎语](https://kf.weixin.qq.com/api/doc/path/95123)的发送
* 增加对用户发送的各类消息进行解析，包括：
    - [x] 文本
    - [ ] 如果是url，则爬去其中内容 
    - [ ] 公众号文章
    - [ ] 图片
    - [ ] 语音
    - [ ] 视频
    - [ ] 文件
        - [ ] 如果是PDF文件
    - [ ] 聊天记录
* 完成`UPLOAD_FILE`的HTTP请求（改请求与其它请求的差别在于，链接中需要指定TYPE，目前设计无法指定TYPE）

除此之外，还有：

- [x] 接入数据库（需先完成数据库设计）
* 接入DeepSeek（可以选择豆包或DeepSeek官方）
* 接入RAG，可以参考如下项目：
    * [LangChain](https://github.com/langchain-ai/langchain)
    * [Dify](https://github.com/langgenius/dify/blob/main/README_CN.md)
    * [FastGPT](https://github.com/labring/FastGPT)
