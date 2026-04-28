import yfinance as yf
import requests
import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import google.generativeai as genai

# ── 환경변수에서 API 키 가져오기 ──────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GMAIL_USER        = os.environ.get("GMAIL_USER")
GMAIL_PASSWORD    = os.environ.get("GMAIL_PASSWORD")
RECIPIENTS        = os.environ.get("RECIPIENTS", "").split(",")

# ── 1. 미국 시장 데이터 수집 ──────────────────────────
def fetch_us_market():
    tickers = {
        "다우":    "^DJI",
        "나스닥":  "^IXIC",
        "S&P500": "^GSPC",
        "WTI":    "CL=F",
        "달러인덱스": "DX-Y.NYB",
        "원달러환율":  "KRW=X",
        "미국채10Y":  "^TNX",
    }
    result = {}
    for name, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="2d")
            if len(hist) >= 2:
                prev  = hist["Close"].iloc[-2]
                close = hist["Close"].iloc[-1]
                pct   = (close - prev) / prev * 100
                result[name] = {"price": round(close, 2), "pct": round(pct, 2)}
            elif len(hist) == 1:
                close = hist["Close"].iloc[-1]
                result[name] = {"price": round(close, 2), "pct": 0.0}
        except Exception as e:
            result[name] = {"price": "N/A", "pct": 0.0}
    return result

# ── 2. 국내 시장 데이터 수집 (직전 거래일) ────────────
def fetch_kr_market():
    tickers = {
        "코스피": "^KS11",
        "코스닥": "^KQ11",
    }
    result = {}
    for name, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="2d")
            if len(hist) >= 2:
                prev  = hist["Close"].iloc[-2]
                close = hist["Close"].iloc[-1]
                pct   = (close - prev) / prev * 100
                result[name] = {"price": round(close, 2), "pct": round(pct, 2)}
            elif len(hist) == 1:
                close = hist["Close"].iloc[-1]
                result[name] = {"price": round(close, 2), "pct": 0.0}
        except Exception as e:
            result[name] = {"price": "N/A", "pct": 0.0}
    return result

# ── 3. Claude AI로 시황 분석 생성 ─────────────────────
def generate_report(us, kr):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
아래는 오늘의 시장 데이터입니다.
박병창 마켓 인사이드 스타일로 시황 분석 리포트를 작성해주세요.

[미국 시장]
{json.dumps(us, ensure_ascii=False, indent=2)}

[한국 시장 - 직전 거래일]
{json.dumps(kr, ensure_ascii=False, indent=2)}

작성 형식:
1. 전일 해외 시장 흐름 및 특징 (3~5줄)
2. 전일 국내 시장 흐름 및 특징 (3~5줄)
3. 오늘 시황 전망 및 투자 대응 (3~5줄)

간결하고 핵심만 담아주세요.
"""
    response = model.generate_content(prompt)
    return response.text

# ── 4. HTML 리포트 생성 ───────────────────────────────
def build_html(us, kr, analysis):
    today = datetime.now().strftime("%Y년 %m월 %d일")

    def fmt(data, key):
        d = data.get(key, {})
        price = d.get("price", "N/A")
        pct   = d.get("pct", 0)
        color = "#e53e3e" if pct >= 0 else "#3182ce"
        sign  = "+" if pct >= 0 else ""
        return f'<span style="color:{color}">{price} ({sign}{pct}%)</span>'

    analysis_html = analysis.replace("\n", "<br>")

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>마켓 인사이드 {today}</title>
<style>
  body {{ font-family: 'Apple SD Gothic Neo', sans-serif; max-width: 800px;
          margin: 0 auto; padding: 20px; background: #f7f7f7; color: #222; }}
  h1   {{ font-size: 24px; border-bottom: 3px solid #222; padding-bottom: 8px; }}
  h2   {{ font-size: 18px; background: #222; color: #fff;
          padding: 8px 14px; border-radius: 4px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 20px;
           margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  table {{ width: 100%; border-collapse: collapse; }}
  td, th {{ padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 15px; }}
  th    {{ font-weight: 600; color: #555; }}
  .analysis {{ line-height: 1.9; font-size: 15px; }}
  .date {{ color: #888; font-size: 14px; }}
</style>
</head>
<body>
<h1>📊 마켓 인사이드</h1>
<p class="date">{today} 발행</p>

<div class="card">
  <h2>🇺🇸 미국 시장</h2>
  <table>
    <tr><th>지수/지표</th><th>현재가</th></tr>
    <tr><td>다우</td><td>{fmt(us,"다우")}</td></tr>
    <tr><td>나스닥</td><td>{fmt(us,"나스닥")}</td></tr>
    <tr><td>S&amp;P500</td><td>{fmt(us,"S&P500")}</td></tr>
    <tr><td>WTI 유가</td><td>{fmt(us,"WTI")}</td></tr>
    <tr><td>달러인덱스</td><td>{fmt(us,"달러인덱스")}</td></tr>
    <tr><td>원달러환율</td><td>{fmt(us,"원달러환율")}</td></tr>
    <tr><td>미국채 10년</td><td>{fmt(us,"미국채10Y")}</td></tr>
  </table>
</div>

<div class="card">
  <h2>🇰🇷 국내 시장 (직전 거래일)</h2>
  <table>
    <tr><th>지수</th><th>현재가</th></tr>
    <tr><td>코스피</td><td>{fmt(kr,"코스피")}</td></tr>
    <tr><td>코스닥</td><td>{fmt(kr,"코스닥")}</td></tr>
  </table>
</div>

<div class="card">
  <h2>📝 시황 분석 및 전망</h2>
  <div class="analysis">{analysis_html}</div>
</div>

</body>
</html>"""
    return html

# ── 5. Gmail 발송 ─────────────────────────────────────
def send_email(html_content, today):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 마켓 인사이드 {today}"
    msg["From"]    = GMAIL_USER
    msg["To"]      = ", ".join(RECIPIENTS)
    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENTS, msg.as_string())
    print("✅ 메일 발송 완료")

# ── 6. HTML 파일로 저장 (GitHub Pages용) ─────────────
def save_html(html_content):
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("✅ index.html 저장 완료")

# ── 메인 실행 ─────────────────────────────────────────
if __name__ == "__main__":
    today = datetime.now().strftime("%Y년 %m월 %d일")
    print("📡 데이터 수집 중...")
    us   = fetch_us_market()
    kr   = fetch_kr_market()
    print("🤖 AI 분석 중...")
    analysis = generate_report(us, kr)
    print("📄 HTML 생성 중...")
    html = build_html(us, kr, analysis)
    save_html(html)
    print("📧 메일 발송 중...")
    send_email(html, today)
    print("🎉 완료!")
