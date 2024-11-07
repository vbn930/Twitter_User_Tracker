import tweepy
import time
import datetime
import pandas as pd
from Utility import Logger
from dataclasses import dataclass
from functools import cmp_to_key

@dataclass
class Account:
    ID: str
    PW: str
    token: str

@dataclass
class TweepyClient:
    client: tweepy.Client
    name: str

    #마지막으로 클라이언트를 사용하여 rate limit에 도달한 시간
    #아래 변수는 리트윗 유저 요청 함수만을 위한 변수
    last_used_time: datetime.datetime

class ClientManager:
    def __init__(self, logger):
        self.logger = logger
        self.accounts = list()
        self.clients = list()
        self.get_account_from_setting_file()
        self.create_clients()
    
    #account_setting 파일에서 계정 정보외 API 키 받아오는 함수
    def get_account_from_setting_file(self):
        account_data = pd.read_csv("./account_setting.csv")

        ids = account_data["ID"].to_list()
        pws = account_data["PW"].to_list()
        tokens = account_data["Token"].to_list()

        for id, pw, token in zip(ids, pws, tokens):
            self.accounts.append(Account(id, pw, token))
    
    def cmp_limit_time(self,x, y):
        if x == None and y == None:
            return 0
        elif x == None:
            return -1
        elif y == None:
            return 0
        else:
            return 1
    
    #마지막으로 사용한 시간을 기준으로 클라이언트를 정렬
    def sort_clients_by_limit_time(self):
        self.clients.sort(key=cmp_to_key(self.cmp_limit_time))
        
    def create_clients(self):
        for account in self.accounts:
            self.clients.append(TweepyClient(tweepy.Client(account.token), account.ID, None))
            self.logger.log(log_level="Event", log_msg=f"계정 {account.ID}의 클라이언트 생성 완료!")
        self.logger.log(log_level="Event", log_msg=f"총 {self.get_client_count()}개의 클라이언트 생성 완료!")

    def get_client_count(self):
        return len(self.clients)