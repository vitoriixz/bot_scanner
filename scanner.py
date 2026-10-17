

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
    data = yf.download(["SPY", "QQQ"], period="1y", progress=False)["Close"]
    regime_status = []
    for etf in ["SPY", "QQQ"]:
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
    """Etapa 1: Pré-filtra ações líquidas e em forte alta no trimestre via Finviz."""
    foverview = Overview()
    filters_dict = {
        "Price": "Over $10",
        "Average Volume": "Over 1M",
        "Performance": "Quarter +20%",
        "20-Day Simple Moving Average": "Price above SMA20",
        "50-Day Simple Moving Average": "Price above SMA50",
        "200-Day Simple Moving Average": "Price above SMA200",
    }
    foverview.set_filter(filters_dict=filters_dict)
    df = foverview.screener_view()
    if df is None or df.empty:
        return []
    return df["Ticker"].tolist()

def analyze_qullamaggie_setup(tickers):
    """Etapa 2: Calcula ADR%, Médias e Bandeira Estreita (Tight Flag) no Pandas."""
    if not tickers:
        return []
    
    raw = yf.download(tickers, period="6mo", group_by="ticker", threads=True, progress=False)
    approved = []

    for ticker in tickers:
        try:
            df = raw[ticker].dropna() if len(tickers) > 1 else raw.dropna()
            if len(df) < 60:
                continue

            close = df["Close"]
            high = df["High"]
            low = df["Low"]
            vol = df["Volume"]

            # 1. Cálculo de Médias (EMA 10, EMA 20, SMA 50)
            ema10 = close.ewm(span=10, adjust=False).mean()
            ema20 = close.ewm(span=20, adjust=False).mean()
            sma50 = close.rolling(50).mean()

            c_now = close.iloc[-1]
            e10_now = ema10.iloc[-1]
            e20_now = ema20.iloc[-1]
            s50_now = sma50.iloc[-1]

            if not (c_now >= e20_now and e10_now > e20_now and e20_now > s50_now):
                continue

            # 2. Cálculo do ADR% de 20 dias (Volatilidade mínima de 4% ao dia)
            daily_range_pct = ((high / low) - 1.0) * 100
            adr20 = daily_range_pct.rolling(20).mean().iloc[-1]
            if adr20 < 4.0:
                continue

            # 3. Retorno de 3 meses (63 pregões)
            ret_3m = ((c_now / close.iloc[-63]) - 1.0) * 100

            # 4. Filtro da "Bandeira Estreita" (Tight Flag nos últimos 5 dias)
            high_5d = high.iloc[-5:].max()
            low_5d = low.iloc[-5:].min()
            range_5d_pct = ((high_5d - low_5d) / c_now) * 100

            vol_5d = vol.iloc[-5:].mean()
            vol_20d = vol.iloc[-20:].mean()
            is_tight = (range_5d_pct <= (adr20 * 2.0)) and (vol_5d < (vol_20d * 0.85))

            if is_tight:
                stop_dist_pct = ((high_5d - low_5d) / high_5d) * 100
                approved.append({
                    "ticker": ticker,
                    "close": round(c_now, 2),
                    "trigger": round(high_5d, 2),
                    "stop": round(low_5d, 2),
                    "stop_pct": round(stop_dist_pct, 1),
                    "adr": round(adr20, 1),
                    "ret_3m": round(ret_3m, 1)
                })
        except Exception:
            continue

    approved.sort(key=lambda x: x["ret_3m"], reverse=True)
    return approved[:8]

def send_telegram_report(regime, setups):
    """Envia o relatório formatado para o seu Telegram."""
    msg = f"📊 *Scanner Qullamaggie (Fechamento NY)*\n\n"
    msg += f"*Regime de Mercado:*\n{regime}\n"
    msg += "----------------------------------\n"

    if not setups:
        msg += "Nenhuma ação passou no filtro de *Tight Flag* hoje. Paciência paga!"
    else:
        msg += f"🔥 *Top {len(setups)} Bandeiras Estreitas (VCP):*\n\n"
        for s in setups:
            tv_link = f"https://www.tradingview.com/chart/?symbol={s['ticker']}"
            msg += (
                f"🔹 *[{s['ticker']}]({tv_link})* | Alta 3M: `+{s['ret_3m']}%` | ADR: `{s['adr']}%`\n"
                f"   • Fechamento: `${s['close']}`\n"
                f"   • Gatilho (Topo 5d): `${s['trigger']}`\n"
                f"   • Stop (Fundo 5d): `${s['stop']}` (`-{s['stop_pct']}%`)\n\n"
            )

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload, timeout=10)

if __name__ == "__main__":
    print("Rodando scanner de mercado...")
    regime = check_market_regime()
    candidates = get_momentum_candidates()
    setups = analyze_qullamaggie_setup(candidates)
    send_telegram_report(regime, setups)
    print("Relatório enviado com sucesso para o Telegram!")