import os
import json
import requests
import pytz  # pytz 모듈 추가
from datetime import datetime

# 오늘 날짜를 KST 기준으로 가져오는 함수 (YYYY-MM-DD)
def get_today_date():
    kst = pytz.timezone('Asia/Seoul')
    today_date = datetime.now(kst)
    return today_date.strftime('%Y-%m-%d')

# 토큰 갱신 함수
def refresh_access_token():
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": os.environ.get("KAKAO_REST_API_KEY"),  # 카카오 REST API 키
        "refresh_token": os.environ.get("KAKAO_REFRESH_TOKEN")  # 카카오 리프레시 토큰
    }
    
    response = requests.post(url, data=data)
    if response.status_code == 200:
        tokens = response.json()
        new_token = tokens['access_token']
        print("새로운 액세스 토큰:", new_token)
        return new_token
    else:
        raise Exception(f"토큰 갱신 실패: {response.status_code}, {response.text}")

# GitHub raw URL에서 JSON 데이터를 가져오는 함수
def fetch_schedule_data(api_url):
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()  # HTTP 에러 발생 시 예외 처리
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch data: {e}")

# 카카오톡 메시지 템플릿 생성 함수
def create_message(today_str, schedule_data):
    # 변경하고 싶은 단어를 사전으로 정의
    replacements = {
        "(주)": "[주]",
        "(야)": "[야]",
        "(숙)": "[숙]",
        "(비)": "[비]"
    }

    # 텍스트 내에서 사전에 따라 단어를 대체하는 함수
    def replace_words(text):
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    # 주간 근무자 텍스트 생성
    day_shift = "\n".join([
        replace_words(f"• {worker['파트']} - {worker['이름']} ({worker['근무']})")
        for worker in schedule_data.get('day_shift', [])
    ])
    
    # 야간 근무자 텍스트 생성
    night_shift = "\n".join([
        replace_words(f"• {worker['파트']} - {worker['이름']} ({worker['근무']})")
        for worker in schedule_data.get('night_shift', [])
    ])
    
    # 휴가 근무자 텍스트 생성
    vacation_shift = "\n".join([
        replace_words(f"• {worker['파트']} - {worker['이름']} ({worker['근무']})")
        for worker in schedule_data.get('vacation_shift', [])
    ])
    
    # 최종 메시지 생성
    return (
        f"📅 {today_str} 관제SO팀 근무자 정보\n\n"
        f"☀️ 주간 근무자\n"
        f"{day_shift if day_shift else '   → 주간 근무자가 없습니다!'}\n\n"
        f"🌙 야간 근무자\n"
        f"{night_shift if night_shift else '   → 야간 근무자가 없습니다!'}\n\n"
        f"🌴 휴가 근무자\n"
        f"{vacation_shift if vacation_shift else '   → 휴가 근무자가 없습니다!'}"
    )

# 카카오톡 메시지를 전송하는 함수
def send_kakao_message(message):
    token = os.environ.get("KAKAO_ACCESS_TOKEN")  # Lambda 환경변수에 저장한 카카오 액세스 토큰
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "template_object": json.dumps({
            "object_type": "text",
            "text": message,
            "link": {
                "web_url": "https://rsw-pages.streamlit.app/",
                "mobile_web_url": "https://rsw-pages.streamlit.app/"
            },
            "button_title": "확인"
        })
    }
    
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        print("✅ 메시지 전송 성공")
    elif response.status_code == 401:
        print("토큰 만료 혹은 오류 발생, 토큰 갱신 시도...")
        new_token = refresh_access_token()
        headers["Authorization"] = f"Bearer {new_token}"
        re_response = requests.post(url, headers=headers, data=data)
        if re_response.status_code == 200:
            print("✅ 메시지 전송 성공 (재시도)")
        else:
            raise Exception(f"❌ 메시지 전송 실패: {re_response.status_code}, {re_response.text}")
    else:
        raise Exception(f"❌ 메시지 전송 실패: {response.status_code}, {response.text}")

# Lambda 엔트리 포인트 함수
def lambda_handler(event, context):
    try:
        today_date = get_today_date()  # 예: "2025-02-08"
        team_name = "관제SO팀"
        year_month = today_date[:7]      # 예: "2025-02"
        
        # GitHub raw 컨텐츠 파일 URL 생성
        api_url = f"https://raw.githubusercontent.com/devkylo/RSW/main/team_today_schedules/{team_name}/{year_month}/{today_date}_schedule.json"
        
        # JSON 데이터 가져오기
        schedule_data = fetch_schedule_data(api_url)
        
        # 메시지 생성 및 카카오톡 전송
        message = create_message(today_date, schedule_data)
        send_kakao_message(message)
        
        return {"statusCode": 200, "body": "메시지 전송 완료"}
    
    except Exception as e:
        print(f"❌ 에러 발생: {str(e)}")
        return {"statusCode": 500, "body": str(e)}
