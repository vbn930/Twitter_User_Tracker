#written in python ver 3.10.11
#used lib : tweepy, pandas
#pyinstaller -n "Twitter Crawler ver.2.0" --clean --onefile main.py

import tweepy
import time
import datetime
import pandas as pd
import shutil
import os
from Utility import Logger
from Utility import client_manager as c_manager

#사용자 명을 이용해 트윗 크롤링을 위한 user id 생성
def get_uids(client_manager, screen_names, logger):
    while True:
        try:
            client = client_manager.clients[0].client
            user_datas = client.get_users(usernames=screen_names)
            uids = [user_data.id for user_data in user_datas.data]
            break
        except tweepy.errors.TooManyRequests as e:
            logger.log(log_level="Event", log_msg=f"트위터 API에 한번에 요청할수 있는 제한 횟수를 넘겨 15분간 대기 합니다")
            time.sleep(60 * 15)
        except Exception as e:
            logger.log(log_level="Error", log_msg=f"다음과 같은 오류가 발생하여 프로그램을 종료합니다. : {e}")
            return list()
    return uids

#생성된 uid 를 이용해 사용자의 최근 일주일간 업로드 트윗 정보를 크롤링 (리트윗과 답변 게시물은 제외 하고 크롤링)
def get_recent_user_tweets_data(client_manager, uid, username, data, result_data, logger):
    while True:
        try:
            client = client_manager.clients[0].client
            #일주일 전 트윗을 가져오기 위해 start_time을 지정. (API의 시간 단위가 UTC 이므로 한국 시간과 맞추기 위해 -9h)
            start_time = datetime.datetime.now() - datetime.timedelta(weeks=1, hours=9)
            tweet_datas = client.get_users_tweets(uid, tweet_fields=["public_metrics","created_at","referenced_tweets"], 
                start_time=start_time, exclude=["retweets", "replies"], max_results=100).data
            if tweet_datas is None:
                logger.log(log_level="Event", log_msg=f"계정 \'{username}\'의 최근 일주일간 업로드 한 트윗이 존재하지 않습니다.")
                result_data["계정 이름"].append(username)
                result_data["게시물 수"].append(0)
                return True
            logger.log(log_level="Event", log_msg=f"계정 \'{username}\'의 최근 일주일간 업로드 한 트윗 {len(tweet_datas)}개를 발견했습니다!")
            result_data["계정 이름"].append(username)
            result_data["게시물 수"].append(len(tweet_datas))
            for tweet_data in tweet_datas:
                #retweet_count 는 API 가 받아오는 값과 실제 RT 값이 차이가 나는데 아마 API가 정보를 받아오는 시간이 다른걸로 추정
                #API의 시간 단위가 UTC 이므로 한국 시간과 맞추기 위해 +9h
                created_time = tweet_data.created_at + datetime.timedelta(hours=9)
                logger.log(log_level="Debug", log_msg=f"계정 \'{username}\'의 {created_time} 에 업로드한 트윗 크롤링 완료")
                data["작성 날짜"].append(created_time.strftime('%Y-%m-%d %H:%M:%S'))
                data["트윗 내용"].append(tweet_data.text)
                data["RT 수"].append(tweet_data.public_metrics['retweet_count'])
                data["좋아요 수"].append(tweet_data.public_metrics['like_count'])
                data["인용 수"].append(tweet_data.public_metrics['quote_count'])
                data["댓글 수"].append(tweet_data.public_metrics['reply_count'])
                
                get_retweeters_info(client_manager, username, tweet_data.id, data, logger)
            break
        except tweepy.errors.TooManyRequests as e:
            logger.log(log_level="Event", log_msg=f"트위터 API에 한번에 요청할수 있는 제한 횟수를 넘겨 15분간 대기 합니다")
            time.sleep(60 * 15)
        except Exception as e:
            logger.log(log_level="Error", log_msg=f"다음과 같은 오류가 발생하여 계정 {username}의 크롤링을 건너 뜁니다. : {e}")
            return False
    return True

def get_retweeters_info(client_manager, username, tweet_id, data, logger):
    
    is_crawling_end = False
    next_page_token = None
    user_cnt = 0
    usernames = [] #트위터 사용자 이름
    screenames = [] #트위터 아이디 (@xxx 의 형태)
    #모든 리트윗 유저 정보를 받아올때 까지 반복
    while is_crawling_end == False:
        #클라이언트들을 마지막 사용 시간을 기준으로 정렬
        client_manager.sort_clients_by_limit_time()

        #제일 마지막에 사용한 클라이언트를 사용
        curr_client = client_manager.clients[0]
        logger.log(log_level="Event", log_msg=f"이번 요청에 사용하는 클라이언트는 {curr_client.name}의 클라이언트 입니다.")
        
        #last_used_time이 None이라면 대기시간 없이 사용 가능
        if curr_client.last_used_time == None:
            try:
                #대기 안하는 리미트는 최대 5번 (리트윗 유저의 개수와 상관없이 한번의 요청당 15분 대기 (한번에 가져올수 있는 개수는 대략 400개))
                #만약 리트윗이 400회가 넘는다면 클라이언트를 교체하면서 크롤링
                #5페이지씩 클라이언트를 교체하면서 크롤링
                for retweeters in tweepy.Paginator(curr_client.client.get_retweeters, tweet_id, max_results=100, limit=5, pagination_token=next_page_token):
                    
                    #만약 retweeters.data 가 None이라면 모든 유저 정보를 다 받아온 상태
                    if retweeters.data != None:
                        for retweeter in retweeters.data:
                            usernames.append(retweeter.name)
                            screenames.append(retweeter.username)
                        user_cnt += len(retweeters.data)
                        next_page_token = retweeters.meta.get('next_token', None)
                    else:
                        is_crawling_end = True
                
                #크롤링 후 사용한 클라이언트의 마지막 사용시간 업데이트
                curr_client.last_used_time = datetime.datetime.now()

            #last_used_time이 None인데 요청 대기시간이 존재한다면 기본적으로 15분 대기
            except tweepy.errors.TooManyRequests as e:
                curr_client.last_used_time = datetime.datetime.now()
                logger.log(log_level="Event", log_msg=f"트위터 API에 한번에 요청할수 있는 제한 횟수를 넘겨 15분간 대기 합니다")
                time.sleep(60 * 15)
                #대기 후 현재 클라이언트 상태를 사용 가능하도록 업데이트
                curr_client.last_used_time = None

        #last_used_time이 None이 아니라면 현재 시간과 마지막 사용시간을 비교해 대기시간 결정
        else:
            delta_time = int((datetime.datetime.now() - curr_client.last_used_time).total_seconds())
            remain_time = 16 - ((delta_time % 3600) // 60)
            logger.log(log_level="Debug", log_msg=f"트위터 API 요청까지 남은시간 : {remain_time}")
            if remain_time > 0:
                logger.log(log_level="Event", log_msg=f"트위터 API에 한번에 요청할수 있는 제한 횟수를 넘겨 {remain_time}분간 대기 합니다")
                time.sleep(60 * remain_time)
            
            #대기 후 현재 클라이언트 상태를 사용 가능하도록 업데이트
            curr_client.last_used_time = None
    
    #유저 정보 리스트를 문자열 한줄로 변환 후 저장
    usernames_str = ", ".join(usernames)
    screenames_str = ", ".join(screenames)
    data["리트윗 유저 이름"].append(usernames_str)
    data["리트윗 유저 아이디"].append(screenames_str)

    logger.log(log_level="Event", log_msg=f"계정 \'{username}\'의 {tweet_id} 트윗의 리트윗 유저 목록 {user_cnt}개 크롤링 완료")
    return

def save_excel_datas(data, dir_path, file_name, logger):
    data_frame = pd.DataFrame(data)
    data_frame.to_excel(f"{dir_path}/{file_name}.xlsx", index=False)
    return

def create_data():
    data = dict()
    data["작성 날짜"] = []
    data["트윗 내용"] = []
    data["RT 수"] = []
    data["좋아요 수"] = []
    data["인용 수"] = []
    data["댓글 수"] = []
    data["리트윗 유저 이름"] = []
    data["리트윗 유저 아이디"] = []
    return data


def main():
    #로거 모드 설정
    logger = Logger.Logger("Build")
    logger.log(log_level="Event", log_msg=f"=Twitter Crawler ver.2.0=")
    
    #엑셀 파일 이름에 사용할 현재 날짜
    now = datetime.datetime.now()
    year = f"{now.year}"
    month = "%02d" % now.month
    day = f"{now.day}"
    file_name = year + month + day

    #엑셀 파일을 저장 할 폴더 생성
    os.makedirs(f"./{file_name}", exist_ok=True)

    #최종 결과 엑셀 데이터 초기화
    result_data = dict()
    result_data["계정 이름"] = []
    result_data["게시물 수"] = []

    #크롤링 할 사용자 정보 setting 파일에서 받아오기
    user_data = pd.read_csv("./setting.csv")
    user_names = user_data["username"].to_list()
    logger.log(log_level="Event", log_msg=f"크롤링 대상 사용자 : {user_names} 설정 완료")

    #account_setting.csv 에서 받아온 계정 정보로 클라이언트들 생성
    client_manager = c_manager.ClientManager(logger)

    uids = get_uids(client_manager, user_names, logger)

    for i in range(len(uids)):
        data = create_data()
        if get_recent_user_tweets_data(client_manager, uids[i], user_names[i], data, result_data, logger):
            #사용자마다 엑셀 파일 저장 후 초기화 해줌
            save_excel_datas(data, f"./{file_name}", f"{user_names[i]}_{file_name}", logger)
        data.clear()
    
    #최종 크롤링 결과 저장
    save_excel_datas(result_data, f"./{file_name}", f"result_data_{file_name}", logger)

    logger.log(log_level="Event", log_msg="엔터키를 눌러 프로그램을 종료 해주세요!")
    exit_program = input("")
    return

if __name__ == "__main__":
    main()