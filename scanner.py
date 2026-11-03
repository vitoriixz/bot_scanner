import os
import requests
import pandas as pd
import yfinance as yf
from finvizfinance.screener.overview import Overview

# ==========================================
# CONFIGURAÇÕES SEGURAS (Lê do ambiente do GitHub)
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def check_market_regime():
    """Verifica se SPY e QQQ estão acima da SMA 200 e EMA 20."""
    # threads=False previne o erro 'database is locked' no SQLite do yfinance no GitHub Actions
    data = yf.download(["SPY", "QQQ"], period="1y", progress=False, threads=False)["Close"]
    regime_status = []
    
    for etf in ["SPY", "QQQ"]:
        # Proteção contra falhas na API do Yahoo Finance (dados vazios)
        if etf not in data or data[etf].dropna().empty:
            regime_status.append(f"❓ {etf}: Dados indisponíveis no momento")
            continue
            
        s = data[etf].dropna()
        close = s.iloc[-1]
        sma200 = s.rolling(200).mean().iloc[-1]
        ema20 = s.ewm(span=20, adjust=False).mean().iloc[-1]
        
        if close > sma200 and close > ema20:
            regime_status.append(f"🟢 {etf}: Bullish (Acima EMA20 e SMA200)")
        elif close > sma200:
            regime_status.append(f"🟡 {etf}: Cautela (Abaixo EMA20, Acima SMA200)")
        else:
            regime_status.append(f"🔴 {etf}: Bearish (Abaixo SMA200 - Evitar Compras)")
            
    return "\n".join(regime_status)

def get_momentum_candidates():
    """Etapa 1: Pré-filtra ações líquidas
