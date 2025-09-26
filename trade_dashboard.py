# trade_dashboard.py
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="TopstepX Trade Dashboard", layout="wide")

# ---------- Data loading (robust) ----------
DATA_DIR = Path(__file__).parent / "data"
DEFAULT_PATHS = [
    DATA_DIR / "trades.csv",
    Path(__file__).parent / "TOPSTEP_TRADE_DATA 0425-09-25.csv",
]

@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    return _prep(df)

@st.cache_data
def _prep(df: pd.DataFrame) -> pd.DataFrame:
    # Normalize columns used below
    for c in ["EnteredAt", "ExitedAt", "TradeDay"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    if "PnL" in df.columns:
        df["PnL"] = pd.to_numeric(df["PnL"], errors="coerce")
    if "Fees" in df.columns:
        df["Fees"] = pd.to_numeric(df["Fees"], errors="coerce")
    # Derived
    if "EnteredAt" in df.columns and "ExitedAt" in df.columns:
        df["TradeDuration"] = (df["ExitedAt"] - df["EnteredAt"]).dt.total_seconds()
    if "PnL" in df.columns and "Fees" in df.columns:
        df["NetPnL"] = df["PnL"] - df["Fees"]
    else:
        df["NetPnL"] = df.get("PnL", pd.Series(np.nan, index=df.index))
    if "TradeDay" not in df.columns and "EnteredAt" in df.columns:
        df["TradeDay"] = df["EnteredAt"].dt.floor("D")
    return df

st.title("TopstepX Trade Dashboard")

uploaded = st.file_uploader("Upload your trade CSV", type=["csv"])
df = None
if uploaded is not None:
    df = _prep(pd.read_csv(uploaded))
else:
    for p in DEFAULT_PATHS:
        if p.exists():
            df = load_csv(p)
            st.caption(f"Loaded default data from: `{p.name}`")
            break

if df is None or len(df) == 0:
    st.warning("No data loaded. Upload a CSV or add one to the repo (e.g., data/trades.csv).")
    st.stop()

# ---------- KPIs (top row) ----------
baseline_date = (
    df["TradeDay"].dropna().min().date()
    if "TradeDay" in df.columns and df["TradeDay"].notna().any()
    else (df["EnteredAt"].dropna().dt.date.min() if "EnteredAt" in df.columns else None)
)
days_opened = (pd.Timestamp("today").date() - baseline_date).days if baseline_date else np.nan
total_trades = len(df)
wins = (df["PnL"] > 0).sum() if "PnL" in df.columns else np.nan
win_rate = (wins / df["PnL"].notna().sum() * 100) if "PnL" in df.columns and df["PnL"].notna().any() else np.nan
cum_pnl = df["NetPnL"].sum() if "NetPnL" in df.columns else np.nan

c1, c2, c3, c4 = st.columns(4)
c1.metric("Days Opened", f"{int(days_opened):,}" if pd.notna(days_opened) else "–")
c2.metric("Total Trades", f"{total_trades:,}")
c3.metric("Win Rate", f"{win_rate:.1f}%" if pd.notna(win_rate) else "–")
c4.metric("Cumulative P&L", f"{cum_pnl:,.2f}" if pd.notna(cum_pnl) else "–")
st.caption("Days Opened = Today minus earliest TradeDay (or EnteredAt). KPIs update on refresh.")

# ---------- Filters ----------
with st.sidebar:
    st.header("Filters")
    # Date range
    min_date = df["TradeDay"].min().date() if "TradeDay" in df.columns else df["EnteredAt"].min().date()
    max_date = df["TradeDay"].max().date() if "TradeDay" in df.columns else df["EnteredAt"].max().date()
    date_range = st.date_input("Date range", (min_date, max_date), min_value=min_date, max_value=max_date)

    # Contract filter
    contracts = sorted(df["ContractName"].dropna().unique().tolist()) if "ContractName" in df.columns else []
    chosen = st.multiselect("Contracts", options=contracts, default=contracts[:5] if contracts else [])

# Apply filters
mask = pd.Series(True, index=df.index)
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    date_col = "TradeDay" if "TradeDay" in df.columns else "EnteredAt"
    mask &= df[date_col].between(start, end)
if "ContractName" in df.columns and chosen:
    mask &= df["ContractName"].isin(chosen)

df_f = df.loc[mask].copy()

# ---------- Overview table ----------
st.subheader("Trades Overview")
st.dataframe(df_f.head(100), use_container_width=True)

# ---------- Charts ----------
st.subheader("Performance")

# Equity curve (cumulative NetPnL over time)
if "NetPnL" in df_f.columns and "TradeDay" in df_f.columns:
    daily = (
        df_f.groupby(df_f["TradeDay"].dt.date, dropna=True)["NetPnL"]
        .sum()
        .rename("DailyNetPnL")
        .to_frame()
        .sort_index()
    )
    daily["EquityCurve"] = daily["DailyNetPnL"].cumsum()
    fig_eq = px.line(daily, y="EquityCurve", labels={"index":"Date", "EquityCurve":"Equity"}, title="Equity Curve")
    st.plotly_chart(fig_eq, use_container_width=True)

# Daily PnL bars
if "NetPnL" in df_f.columns and "TradeDay" in df_f.columns:
    fig_bar = px.bar(daily, y="DailyNetPnL", labels={"index":"Date", "DailyNetPnL":"Daily Net P&L"}, title="Daily Net P&L")
    st.plotly_chart(fig_bar, use_container_width=True)

# Win rate by contract
if "PnL" in df_f.columns and "ContractName" in df_f.columns and not df_f.empty:
    by_contract = (
        df_f.assign(win=df_f["PnL"] > 0)
        .groupby("ContractName")
        .agg(trades=("PnL", "count"), win_rate=("win", "mean"))
        .sort_values("trades", ascending=False)
        .head(15)
    )
    by_contract["win_rate"] *= 100
    fig_wr = px.bar(by_contract, x=by_contract.index, y="win_rate",
                    labels={"x":"Contract", "win_rate":"Win Rate (%)"},
                    title="Win Rate by Contract (Top 15)")
    st.plotly_chart(fig_wr, use_container_width=True)
