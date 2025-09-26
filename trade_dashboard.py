from pathlib import Path
import streamlit as st
import pandas as pd

st.set_page_config(page_title="TopstepX Trade Dashboard", layout="wide")

# Define possible default CSV locations
DATA_DIR = Path(__file__).parent / "data"
DEFAULT_PATHS = [
    DATA_DIR / "trades.csv",  # recommended path
    Path(__file__).parent / "TOPSTEP_TRADE_DATA 0425-09-25.csv",  # your current filename
    DATA_DIR / "IBIT_vol.csv"  # if you want to load this instead
]

@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)

st.title("TopstepX Trade Dashboard")

uploaded = st.file_uploader("Upload your trade CSV", type=["csv"])

df = None
if uploaded is not None:
    df = pd.read_csv(uploaded)
else:
    for p in DEFAULT_PATHS:
        if p.exists():
            df = load_csv(p)
            st.caption(f"Loaded default data from: `{p.name}`")
            break

if df is None:
    st.warning("No CSV found in the repo. Please upload a CSV to continue.")
    st.stop()

# Preview data
st.subheader("Trades Overview")
st.dataframe(df.head(50), use_container_width=True)

# ... add your charts, KPIs, etc. here ...
