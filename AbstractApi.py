#!/usr/bin/env python
# -*- coding:utf-8 -*-
##
 # Copyright (C) 2018 All rights reserved.
 #   
 # @File AbstractApi.py
 # @Brief 
 # @Author abelzhu, abelzhu@tencent.com
 # @Version 1.0
 # @Date 2018-02-24
 #
 #
 
import os
import re

import json
import requests

DEBUG = False

class ApiException(Exception) :
    def __init__(self, errCode, errMsg) :
        self.errCode = errCode
        self.errMsg = errMsg

class AbstractApi(object) :
    def __init__(self) : 
        return

    def getAccessToken(self) :
        raise NotImplementedError
    def refreshAccessToken(self) :
        raise NotImplementedError

    def getSuiteAccessToken(self) :
        raise NotImplementedError
    def refreshSuiteAccessToken(self) :
        raise NotImplementedError

    def getProviderAccessToken(self) :
        raise NotImplementedError
    def refreshProviderAccessToken(self) :
        raise NotImplementedError

    def httpCall(self, urlType, args=None, urlParamList=[]) : 
        shortUrl = urlType[0]
        method = urlType[1]
        response = {}
        for retryCnt in range(0, 3) :
            if 'POST' == method :
                url = self.__makeUrl(shortUrl)
                url = self.replaceParams(url, urlParamList)
                response = self.__httpPost(url, args)
            elif 'POST-FILE' == method :
                url = self.__makeUrl(shortUrl)
                url = self.replaceParams(url,urlParamList)
                response = self.__post_file(url, args)
            elif 'GET' == method :
                url = self.__makeUrl(shortUrl)
                url = self.replaceParams(url,urlParamList)
                url = self.__appendArgs(url, args)
                response = self.__httpGet(url)
            else : 
                raise ApiException(-1, "unknown method type")

            # check if token expired
            if self.__tokenExpired(response.get('errcode')) :
                self.__refreshToken(shortUrl)
                retryCnt += 1
                continue
            else :
                break

        return self.__checkResponse(response) 

    @staticmethod
    def __appendArgs(url, args) : 
        if args is None :
            return url

        for key, value in args.items() : 
            if '?' in url : 
                url += ('&' + key + '=' + value)
            else :
                url += ('?' + key + '=' + value)
        return url

    @staticmethod
    def __makeUrl(shortUrl) :
        base = "https://qyapi.weixin.qq.com"
        if shortUrl[0] == '/' :
            return base + shortUrl
        else :
            return base + '/' + shortUrl 

    def __appendToken(self, url) : 
        if 'SUITE_ACCESS_TOKEN' in url :
            return url.replace('SUITE_ACCESS_TOKEN', self.getSuiteAccessToken())
        elif 'PROVIDER_ACCESS_TOKEN' in url :
            return url.replace('PROVIDER_ACCESS_TOKEN', self.getProviderAccessToken())
        elif 'ACCESS_TOKEN' in url :
            return url.replace('ACCESS_TOKEN', self.getAccessToken())
        else : 
            return url
    """
    在url中可能存在一些参数需要替换,在请求之前完成替换
    @Params:
        * param_list: list，每个元素为一个tuple，保存替换前和替换后的字符串，格式：[("TYPE", "image")]
    """
    def replaceParams(self, url, param_list):
        for param_tuple in param_list:
            url = url.replace(param_tuple[0],param_tuple[1])
        return url

    def __httpPost(self, url, args) :
        realUrl = self.__appendToken(url)

        if DEBUG is True : 
            print(realUrl,args)

        return requests.post(realUrl, data = json.dumps(args, ensure_ascii = False).encode('utf-8')).json()

    def __httpGet(self, url) :
        realUrl = self.__appendToken(url)

        if DEBUG is True : 
            print(realUrl)

        return requests.get(realUrl).json()

    def __post_file(self, url, media_file):
        realUrl = self.__appendToken(url)
        if DEBUG is True : 
            print(realUrl,args)
        return requests.post(realUrl, files=media_file).json()

    @staticmethod
    def __checkResponse(response):
        errCode = response.get('errcode')
        errMsg = response.get('errmsg')

        if errCode == 0:
            return response 
        else:
            raise ApiException(errCode, errMsg)

    @staticmethod
    def __tokenExpired(errCode) :
        if errCode == 40014 or errCode == 42001 or errCode == 42007 or errCode == 42009 :
            return True
        else :
            return False

    def __refreshToken(self, url) :
        if 'SUITE_ACCESS_TOKEN' in url :
            self.refreshSuiteAccessToken()
        elif 'PROVIDER_ACCESS_TOKEN' in url :
            self.refreshProviderAccessToken()
        elif 'ACCESS_TOKEN' in url :
            self.refreshAccessToken()
