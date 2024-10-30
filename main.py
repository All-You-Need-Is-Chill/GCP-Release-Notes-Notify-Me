import os
import requests
import feedparser
from dotenv import load_dotenv
import google.generativeai as genai
from flask import Request
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import *
from flask import jsonify
from datetime import datetime, timezone, timedelta

# .envファイルの読み込み
load_dotenv()

# API-KEYの設定
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

def summarize_release_notes(request: Request, cloudevent):
    """
    GCPのリリースノートを取得し、要約を生成してメールを送信する
    """
    try:
        # リリースノートの取得と要約
        url = 'https://cloud.google.com/feeds/gcp-release-notes.xml'
        response = requests.get(url)
        feed = feedparser.parse(response.content)

        # 最新のエントリを取得
        latest_entry = feed.entries[0]

        if not(is_today(latest_entry.updated)):
            print("本日の Google Cloud リリースノートはありません")
            send_email("本日の Google Cloud リリースノートはありません", "<a href='https://puzzlega.me/sakuin-tango/'>索引たんご</a>")
            return "本日のリリースノートはありません"

        latest_content = latest_entry.content[0].value
        print(f"latest_content: {latest_content}\n")

        # Gemini APIにリクエストを送り、要約を取得
        prompt = """
            あなたは GCP のリリースノートを要約した HTML メール本文を作成するアシスタントです。
            以下のリリースノートの内容を日本語で説明してください。
            ただし、HTML メールに使用するので、HTML タグは削除しないこと。
            ```リリースノートの内容
            """ + latest_content + """
            ```

            要約した HTML メール作成後、専門用語や固有名詞について、小学生でもわかる説明を HTML メール本文の最後に以下の形式で記載すること。
            ```
            <h2>専門用語と固有名詞の解説</h2>
            <h3>{専門用語や固有名詞}</h3>
            <p>{専門用語や固有名詞の解説}</p>
            ...
            ```
            """

        gemini_response_text, total_token_count = generate_ai_response(prompt)
        send_email("本日の Google Cloud リリースノートです", f"{gemini_response_text}<br><br>消費トークン数: {total_token_count}")

        # 成功した場合はレスポンスを返す
        return jsonify({
            "message": gemini_response_text,
            "token_count": total_token_count
        })
    except Exception as e:
        print(f"error: {e}\n")
        # 例外が発生した場合もエラーメッセージをJSONで返す
        return jsonify({"error": str(e)}), 500

def generate_ai_response(prompt):
    """
    AIの返答を生成する
    """
    gemini = genai.GenerativeModel("gemini-1.5-flash-latest")
    gemini_response = gemini.generate_content(prompt)

    print(f"gemini_response: {gemini_response}\n")

    # Gemini APIのレスポンスをパース
    gemini_response_text = gemini_response.candidates[0].content.parts[0].text.strip()
    total_token_count = gemini_response.usage_metadata.total_token_count

    print(f"gemini_response_text: {gemini_response_text}\n")
    print(f"total_token_count: {total_token_count}\n")
    
    return gemini_response_text, total_token_count

def send_email(email_subject, html_email_body):
    # メールを送信
    try:
        client = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        print(f"subject:{email_subject}")
        print(f"html_content:{html_email_body}")
        sendgrid_response = client.send(
            Mail(
                from_email = os.getenv('FROM_EMAIL_ADDRESS'),
                to_emails = os.getenv('TO_EMAIL_ADDRESS'),
                subject = email_subject,
                html_content = Content("text/html", html_email_body)
            ))
        print(sendgrid_response.status_code)
        print(sendgrid_response.body)
        print(sendgrid_response.headers)
    except Exception as e:
        print(f"error: {e}\n")

def is_today(date_string):
    # 与えられた文字列をdatetimeオブジェクトに変換
    date_obj = datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%S%z")
    # 米国のタイムゾーン (UTC-07:00) を定義
    us_tz = timezone(timedelta(hours=-7))
    # 米国時間に変換
    date_in_us = date_obj.astimezone(us_tz)
    # 今日の米国時間の日付を取得
    today_in_us = datetime.now(us_tz).date()

    print(f"today_in_us:{today_in_us}")
    print(f"date_in_us.date():{date_in_us.date()}")
    # 日付部分だけを比較して今日かどうかを判断
    return date_in_us.date() == today_in_us