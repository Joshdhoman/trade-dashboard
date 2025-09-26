
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
from datetime import date, datetime, timezone

st.set_page_config(page_title="Trade EDA Dashboard", layout="wide")

st.title("📊 Trade EDA Dashboard")

# --- Data loading ---
@st.cache_data
def load_csv(path: str):
    df = pd.read_csv(path)
    # Convert types
    for col in ["EnteredAt", "ExitedAt", "TradeDay"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    if "TradeDuration" in df.columns:
        df["TradeDuration"] = pd.to_timedelta(df["TradeDuration"], errors="coerce")
        df["DurationMinutes"] = df["TradeDuration"].dt.total_seconds() / 60
    # Feature engineering
    if "EnteredAt" in df.columns:
        df["EntryHour"] = df["EnteredAt"].dt.hour
        df["EntryDate"] = df["EnteredAt"].dt.date
    if "TradeDay" in df.columns and df["TradeDay"].notna().any():
        baseline_date = df["TradeDay"].dt.date.min()
    else:
        baseline_date = df["EnteredAt"].dt.date.min()
    df["DaysSinceFirstTrade"] = (df["EnteredAt"].dt.date - baseline_date).apply(lambda x: x.days if pd.notna(x) else np.nan)
    # Clean PnL fallback
    if "PnL" in df.columns:
        df["PnL"] = pd.to_numeric(df["PnL"], errors="coerce")
    return df

# Path input or file uploader
st.sidebar.header("Data")
default_path = st.sidebar.text_input("CSV path (optional)", value="trades_export (3).csv")
uploaded = st.sidebar.file_uploader("...or upload your CSV", type=["csv"])

if uploaded is not None:
    df = pd.read_csv(uploaded)
    # redo conversions after upload
    for col in ["EnteredAt", "ExitedAt", "TradeDay"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    if "TradeDuration" in df.columns:
        df["TradeDuration"] = pd.to_timedelta(df["TradeDuration"], errors="coerce")
        df["DurationMinutes"] = df["TradeDuration"].dt.total_seconds() / 60
    if "EnteredAt" in df.columns:
        df["EntryHour"] = df["EnteredAt"].dt.hour
        df["EntryDate"] = df["EnteredAt"].dt.date
    if "TradeDay" in df.columns and df["TradeDay"].notna().any():
        baseline_date = df["TradeDay"].dt.date.min()
    else:
        baseline_date = df["EnteredAt"].dt.date.min()
    df["DaysSinceFirstTrade"] = (df["EnteredAt"].dt.date - baseline_date).apply(lambda x: x.days if pd.notna(x) else np.nan)
    if "PnL" in df.columns:
        df["PnL"] = pd.to_numeric(df["PnL"], errors="coerce")
else:
    df = load_csv(default_path)

if df is None or len(df) == 0:
    st.warning("No data loaded. Enter a valid path or upload a CSV.")
    st.stop()

# --- KPI Bar ---
# Days Opened (updates every day): today - earliest trading date
baseline = df["TradeDay"].dt.date.min() if "TradeDay" in df.columns and df["TradeDay"].notna().any() else df["EnteredAt"].dt.date.min()
today = date.today()
days_opened = (today - baseline).days if pd.notna(baseline) else np.nan

total_trades = len(df)
win_rate = np.nan
if "PnL" in df.columns:
    wins = (df["PnL"] > 0).sum()
    total_trades_nonnull = df["PnL"].notna().sum()
    win_rate = (wins / total_trades_nonnull * 100.0) if total_trades_nonnull > 0 else np.nan
    cum_pnl = df["PnL"].sum()
else:
    cum_pnl = np.nan

col1, col2, col3, col4 = st.columns(4)
col1.metric("Days Opened", f"{int(days_opened) if pd.notna(days_opened) else '—'}")
col2.metric("Total Trades", f"{total_trades}")
col3.metric("Win Rate", f"{win_rate:.1f}%" if pd.notna(win_rate) else "—")
col4.metric("Cumulative PnL", f"{cum_pnl:,.2f}" if pd.notna(cum_pnl) else "—")

st.caption("‘Days Opened’ = Today minus your earliest TradeDay (or EnteredAt if TradeDay missing). It updates automatically when you reload the app.")

# --- Filters ---
st.sidebar.header("Filters")
min_date = df["EnteredAt"].min().date() if "EnteredAt" in df.columns and df["EnteredAt"].notna().any() else today
max_date = df["EnteredAt"].max().date() if "EnteredAt" in df.columns and df["EnteredAt"].notna().any() else today
date_range = st.sidebar.date_input("Date range", (min_date, max_date), min_value=min_date, max_value=max_date)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    mask = (df["EnteredAt"].dt.date >= start) & (df["EnteredAt"].dt.date <= end)
    dff = df.loc[mask].copy()
else:
    dff = df.copy()

contract_list = sorted(dff["ContractName"].dropna().unique().tolist()) if "ContractName" in dff.columns else []
chosen_contracts = st.sidebar.multiselect("Contract(s)", options=contract_list, default=contract_list[:5] if contract_list else [])
if chosen_contracts:
    dff = dff[dff["ContractName"].isin(chosen_contracts)]

# --- Equity curve ---
st.subheader("Equity Curve")
if "PnL" in dff.columns and "EnteredAt" in dff.columns:
    dff_sorted = dff.sort_values("EnteredAt")
    dff_sorted["CumPnL"] = dff_sorted["PnL"].cumsum()
    fig = px.line(dff_sorted, x="EnteredAt", y="CumPnL", markers=False, title="Cumulative PnL over Time")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("PnL or EnteredAt not found for equity curve.")

# --- PnL by Weekday & Hour ---
st.subheader("PnL by Weekday / Hour")
left, right = st.columns(2)
if "PnL" in dff.columns and "TradeDay" in dff.columns:
    tmp = dff.copy()
    tmp["Weekday"] = tmp["TradeDay"].dt.day_name()
    weekday_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    tmp["Weekday"] = pd.Categorical(tmp["Weekday"], categories=weekday_order, ordered=True)
    g1 = tmp.groupby("Weekday", dropna=False)["PnL"].mean().reset_index()
    fig1 = px.bar(g1, x="Weekday", y="PnL", title="Average PnL by Weekday")
    left.plotly_chart(fig1, use_container_width=True)
else:
    left.info("Need PnL and TradeDay for weekday chart.")

if "PnL" in dff.columns and "EntryHour" in dff.columns:
    g2 = dff.groupby("EntryHour", dropna=False)["PnL"].mean().reset_index()
    fig2 = px.bar(g2, x="EntryHour", y="PnL", title="Average PnL by Entry Hour")
    right.plotly_chart(fig2, use_container_width=True)
else:
    right.info("Need PnL and EntryHour for hour chart.")

# --- PnL by Contract ---
st.subheader("PnL by Contract")
if "PnL" in dff.columns and "ContractName" in dff.columns:
    g3 = dff.groupby("ContractName", dropna=False)["PnL"].mean().reset_index().sort_values("PnL", ascending=False)
    fig3 = px.bar(g3, x="ContractName", y="PnL", title="Average PnL by Contract")
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("Need PnL and ContractName for this chart.")

# --- Raw table ---
st.subheader("Data Preview")
st.dataframe(dff.head(50))
