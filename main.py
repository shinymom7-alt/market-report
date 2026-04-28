import yfinance as yf
import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from groq import Groq

GROQ_API_KEY   = os.environ.get("GROQ_API_KEY")
GMAIL_USER     = os.environ.get("GMAIL_USER")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD")
RECIPIENTS     = os.environ.get("RECIPIENTS", "").split(",")

def fetch_us_market():
    tickers = {
        "다우":       "^DJI",
        "나스닥":     "^IXIC",
        "S&P500":    "^GSPC",
        "WTI":       "CL=F",
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
        except:
            result[name] = {"price": "N/A", "pct": 0.0}
    return result

def fetch_kr_market():
    tickers = {"코스피": "^KS11", "코스닥": "^KQ11"}
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
        except:
            result[name] = {"price": "N/A", "pct": 0.0}
    return result

def generate_report(us, kr):
    client = Groq(api_key=GROQ_API_KEY)
    prompt = f"""당신은 한국 증권방송의 시황 전문가입니다. 아래 데이터를 바탕으로 박병창 마켓 인사이드 스타일의 시황 분석을 작성하세요.

[미국 시장 데이터]
{json.dumps(us, ensure_ascii=False, indent=2)}

[한국 시장 데이터 - 직전 거래일]
{json.dumps(kr, ensure_ascii=False, indent=2)}

아래 형식으로 작성하되, 각 항목을 구체적이고 전문적으로 3~5줄씩 작성하세요.
숫자를 반드시 언급하고, 시장 흐름의 원인과 의미를 분석해주세요.
절대 일본어나 중국어를 섞지 말고 한국어로만 작성하세요.

===전일 해외 시장 흐름 및 특징===
(미국 3대 지수 등락, WTI/달러/국채수익률 주요 변동, 특징적 종목/섹터, 시장 흐름 원인 분석)

===전일 국내 시장 흐름 및 특징===
(코스피/코스닥 등락, 수급 동향, 주요 강세/약세 섹터, 특징적 흐름)

===오늘 시황 전망 및 투자 대응===
(오늘 예상 흐름, 주목할 이슈, 구체적 투자 대응 전략)
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.7
    )
    return response.choices[0].message.content

def parse_analysis(text):
    sections = {"해외": "", "국내": "", "전망": ""}
    current = None
    lines = []
    for line in text.split("\n"):
        if "전일 해외" in line or "해외 시장" in line:
            if current and lines:
                sections[current] = "<br>".join([l for l in lines if l.strip()])
            current = "해외"
            lines = []
        elif "전일 국내" in line or "국내 시장" in line:
            if current and lines:
                sections[current] = "<br>".join([l for l in lines if l.strip()])
            current = "국내"
            lines = []
        elif "시황 전망" in line or "투자 대응" in line or "오늘" in line and "전망" in line:
            if current and lines:
                sections[current] = "<br>".join([l for l in lines if l.strip()])
            current = "전망"
            lines = []
        elif current and line.strip() and "===" not in line:
            lines.append(line.strip())
    if current and lines:
        sections[current] = "<br>".join([l for l in lines if l.strip()])
    return sections

def fmt_val(data, key):
    d = data.get(key, {})
    price = d.get("price", "N/A")
    pct   = d.get("pct", 0)
    color = "#c0392b" if pct >= 0 else "#2471a3"
    sign  = "+" if pct >= 0 else ""
    if key == "원달러환율" and price != "N/A":
        price = f"{price:,.0f}원" if isinstance(price, float) else price
    elif key == "미국채10Y":
        price = f"{price}%" if price != "N/A" else price
    elif key == "달러인덱스":
        price = f"{price}" if price != "N/A" else price
    elif key == "WTI":
        price = f"${price}" if price != "N/A" else price
    return f'<span style="font-size:15px;font-weight:500;color:{color}">{price}</span><br><span style="font-size:12px;color:{color}">{sign}{pct}%</span>'

def fmt_kr(data, key):
    d = data.get(key, {})
    price = d.get("price", "N/A")
    pct   = d.get("pct", 0)
    color = "#c0392b" if pct >= 0 else "#2471a3"
    sign  = "+" if pct >= 0 else ""
    return f'<span style="font-size:16px;font-weight:500;color:{color}">{price:,.2f}P</span><br><span style="font-size:12px;color:{color}">{sign}{pct}%</span>'

def build_html(us, kr, analysis):
    today    = datetime.now().strftime("%Y년 %m월 %d일")
    weekdays = ["월","화","수","목","금","토","일"]
    weekday  = weekdays[datetime.now().weekday()]
    sections = parse_analysis(analysis)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>마켓 인사이드 {today}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;background:#f4f4f4;color:#222;padding:20px}}
  .wrap{{max-width:780px;margin:0 auto}}
  .header{{background:#111;color:#fff;padding:20px 24px;border-radius:10px 10px 0 0;margin-bottom:2px}}
  .header h1{{font-size:22px;font-weight:700;letter-spacing:-0.5px}}
  .header .sub{{font-size:13px;color:#aaa;margin-top:4px}}
  .card{{background:#fff;padding:20px 24px;margin-bottom:2px}}
  .card:last-child{{border-radius:0 0 10px 10px}}
  .card-title{{font-size:14px;font-weight:700;background:#222;color:#fff;display:inline-block;padding:4px 12px;border-radius:4px;margin-bottom:16px}}
  .index-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px}}
  .macro-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:4px}}
  .idx-box{{background:#f8f8f8;border-radius:8px;padding:10px 14px}}
  .idx-name{{font-size:12px;color:#888;margin-bottom:6px}}
  .divider{{height:1px;background:#f0f0f0;margin:14px 0}}
  .kr-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:14px}}
  .kr-box{{background:#f8f8f8;border-radius:8px;padding:14px 18px;text-align:center}}
  .kr-name{{font-size:13px;color:#666;margin-bottom:8px;font-weight:600}}
  .analysis-section{{margin-bottom:14px}}
  .analysis-label{{font-size:11px;font-weight:700;color:#888;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px}}
  .analysis-text{{font-size:14px;line-height:1.9;color:#333;background:#f8f8f8;padding:14px 16px;border-radius:8px;border-left:3px solid #222}}
  .footer{{font-size:11px;color:#bbb;text-align:right;margin-top:10px}}
</style>
</head>
<body>
<div class="wrap">

<div class="header">
  <h1>📊 마켓 인사이드</h1>
  <div class="sub">{today} {weekday}요일 · 자동 생성 리포트</div>
</div>

<div class="card">
  <div class="card-title">🇺🇸 전일 미국 시장</div>
  <div class="index-grid">
    <div class="idx-box"><div class="idx-name">다우존스</div>{fmt_val(us,"다우")}</div>
    <div class="idx-box"><div class="idx-name">나스닥</div>{fmt_val(us,"나스닥")}</div>
    <div class="idx-box"><div class="idx-name">S&amp;P 500</div>{fmt_val(us,"S&P500")}</div>
  </div>
  <div class="macro-grid">
    <div class="idx-box"><div class="idx-name">WTI 유가</div>{fmt_val(us,"WTI")}</div>
    <div class="idx-box"><div class="idx-name">달러인덱스</div>{fmt_val(us,"달러인덱스")}</div>
    <div class="idx-box"><div class="idx-name">원달러환율</div>{fmt_val(us,"원달러환율")}</div>
    <div class="idx-box"><div class="idx-name">미국채 10년</div>{fmt_val(us,"미국채10Y")}</div>
  </div>
  <div class="divider"></div>
  <div class="analysis-section">
    <div class="analysis-label">해외 시장 특징</div>
    <div class="analysis-text">{sections["해외"] if sections["해외"] else analysis.split("===")[2] if len(analysis.split("===")) > 2 else analysis[:500]}</div>
  </div>
</div>

<div class="card">
  <div class="card-title">🇰🇷 전일 국내 시장</div>
  <div class="kr-grid">
    <div class="kr-box"><div class="kr-name">코스피</div>{fmt_kr(kr,"코스피")}</div>
    <div class="kr-box"><div class="kr-name">코스닥</div>{fmt_kr(kr,"코스닥")}</div>
  </div>
  <div class="analysis-section">
    <div class="analysis-label">국내 시장 특징</div>
    <div class="analysis-text">{sections["국내"] if sections["국내"] else "국내 시장 분석 데이터를 불러오는 중입니다."}</div>
  </div>
</div>

<div class="card">
  <div class="card-title">📋 오늘 시황 전망 및 투자 대응</div>
  <div class="analysis-section">
    <div class="analysis-text">{sections["전망"] if sections["전망"] else "전망 데이터를 불러오는 중입니다."}</div>
  </div>
</div>

<div class="footer">데이터 출처: yfinance · AI 분석: Groq (llama-3.3-70b) · {today} 자동 발행</div>
</div>
</body>
</html>"""
    return html

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

def save_html(html_content):
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("✅ index.html 저장 완료")

if __name__ == "__main__":
    today = datetime.now().strftime("%Y년 %m월 %d일")
    print("📡 데이터 수집 중...")
    us = fetch_us_market()
    kr = fetch_kr_market()
    print("🤖 AI 분석 중...")
    analysis = generate_report(us, kr)
    print("📄 HTML 생성 중...")
    html = build_html(us, kr, analysis)
    save_html(html)
    print("📧 메일 발송 중...")
    send_email(html, today)
    print("🎉 완료!")
