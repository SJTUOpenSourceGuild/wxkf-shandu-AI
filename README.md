## 简介

本项目主要是实现微信客服的接入。具体来说，就是监听用户发给客服的信息，完成信息的自动处理和回复。

项目正常运行，需要设置如下环境变量

**微信客服**相关
* WECHAT_TOKEN
* WECHAT_AESKEY
* WECHAT_CORP_ID
* WECHAT_SECRET
* WECHAT_FASTAPI_PORT

**HTTPS**相关

* SSL_KEYFILE_PATH
* SSL_CERTIFILE_PATH

**RabbitMQ**相关

* RABBITMQ_HOST
* RABBITMQ_PORT
* RABBITMQ_USERNAME
* RABBITMQ_PASSWORD


其中前面4个都是从[微信客服](https://kf.weixin.qq.com/)处获得，也就是需要开通*微信客服*并且**完成企业认证**。

具体获取方式如下：

首先需要获取企业ID，*微信客服*开通完成后就可以在[企业信息](https://kf.weixin.qq.com/kf/frame#/corpinfo)处看到企业ID了，将*WECHAT_CORP_ID*环境变量设置为企业ID。

然后来获取TOKEN和EncodingAESKey，两者是在**配置回调**的时候自行填写或者随机生成的，获得后分别设志伟WECHAT_TOKEN和WECHAT_AESKEY两个环境变量

配置回调完成后（具体配置方法见下文），就可以获得Secret了，设置为WECHAT_SECRET环境变量。在配置回调过程中，填写的URL必须是https（不确定），因此需要域名和SSL证书。将环境变量SSL_KEYFILE_PATH设置为`.com.key`证书文件的路径，将SSL_CERTIFILE_PATH设置为`.com_bundle.crt`的路径。


另外服务使用了RabbitMQ消息队列，因此需要指定RabbitMQ服务器及用户密码

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

目前只是完成了最基础的一些功能：

* 回调配置
* 获取消息
* 发送消息

利用上述功能可以简单完成微信客服配置以及用户发送消息是自动回复的功能。但过程中经常会发生错误，例如：

* 如果回调是由时间（而非消息）触发的，比如*用户进入会话事件*，就会导致程序退出

后续还有许多工作需要做：

* 增强服务的健壮性
* 完成`UPLOAD_FILE`的HTTP请求（改请求与其它请求的差别在于，链接中需要指定TYPE，目前设计无法指定TYPE）
* 完成[欢迎语](https://kf.weixin.qq.com/api/doc/path/95123)的发送
* 增加对用户发送的各类消息进行解析，包括：
    * 文本
        * 如果是url，则爬去其中内容 
    * 图片
    * 语音
    * 视频
    * 文件
        * 如果是PDF文件
    * 聊天记录

除此之外，还有：

* 接入数据库（需先完成数据库设计）
* 接入DeepSeek（可以选择豆包或DeepSeek官方）
* 接入RAG，可以参考如下项目：
    * [LangChain](https://github.com/langchain-ai/langchain)
    * [Dify](https://github.com/langgenius/dify/blob/main/README_CN.md)
    * [FastGPT](https://github.com/labring/FastGPT)
