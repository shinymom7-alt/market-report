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

def generate_report(us
