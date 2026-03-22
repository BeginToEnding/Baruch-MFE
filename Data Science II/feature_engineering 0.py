# feature_engineering.py

import glob

import os
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple, Set
import re

import numpy as np
import pandas as pd


EPS = 1e-12
MU_TRIPOWER = (0.8023805748753304) ** (-3)
DATE_COL = "Date"
ID_COL = "ID"

Y_COL = "y_raw"
Y_NORM_COL = "y_norm"
EST_VOL_COL = "EST_VOL"
MDV_COL = "MDV_63"

# =========================================================
# basic helpers
# =========================================================
def ensure_dir(path: str) -> None:
    """Create directory if it does not already exist."""
    os.makedirs(path, exist_ok=True)


def _standardize_id_col(df: pd.DataFrame) -> pd.DataFrame:
    """Unify security identifier column name to 'ID'."""
    df = df.copy()
    if "Id" in df.columns and "ID" not in df.columns:
        df = df.rename(columns={"Id": "ID"})
    return df


def _cs_zscore(x: pd.Series) -> pd.Series:
    """Cross-sectional z-score with safe handling of near-zero std."""
    mu = x.mean()
    sd = x.std(ddof=0)
    if pd.isna(sd) or sd < EPS:
        return pd.Series(0.0, index=x.index)
    return (x - mu) / sd


def _winsorize_clip(x: pd.Series, lower: Optional[float] = None, upper: Optional[float] = None) -> pd.Series:
    """Simple clip-based winsorization."""
    y = x.copy()
    if lower is not None:
        y = y.clip(lower=lower)
    if upper is not None:
        y = y.clip(upper=upper)
    return y


def _winsorize_quantile(x: pd.Series, q_low: float = 0.01, q_high: float = 0.99) -> pd.Series:
    """Quantile-based winsorization."""
    if x.notna().sum() == 0:
        return x.copy()
    lo = x.quantile(q_low)
    hi = x.quantile(q_high)
    return x.clip(lower=lo, upper=hi)


def _safe_div(a, b, eps: float = EPS):
    """Safe division to avoid zero denominator issues."""
    return a / (b + eps)


def _finite_mean_scaled(s: pd.Series, scale: float = 1.0) -> float:
    """Mean over finite values only; avoids numpy 'mean of empty slice' warnings."""
    a = np.asarray(s, dtype=float)
    m = np.isfinite(a)
    if not np.any(m):
        return float("nan")
    return scale * float(np.mean(a[m]))


def _finite_std_scaled(s: pd.Series, scale: float = 1.0, ddof: int = 0) -> float:
    """Std over finite values only; avoids numpy ddof warnings when no valid points."""
    a = np.asarray(s, dtype=float)
    a = a[np.isfinite(a)]
    n = int(a.size)
    if n == 0:
        return float("nan")
    if n <= ddof:
        return float("nan")
    return scale * float(np.std(a, ddof=ddof))


# =========================================================
# data loading
# =========================================================

# ====== EDIT PATHS ======
DATA_DIR_DAILY = "./data_daily"      # e.g. contains dat.20100104.csv ...
DATA_DIR_INTRA = "./data_intraday"   # e.g. contains 20100104.csv ...

# ====== DAILY ======
def load_daily(start: str = None, end: str = None, input_dir=DATA_DIR_DAILY):
    """Load daily files and optionally filter by date range."""
    files = sorted(glob.glob(os.path.join(input_dir, "dat.*.csv")))
    if start: files = [f for f in files if os.path.basename(f)[4:12] >= start]
    if end:   files = [f for f in files if os.path.basename(f)[4:12] <= end]
    
    df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"].astype(str), format="%Y%m%d")
    df = df.sort_values(["Date", "ID"]).reset_index(drop=True)
    return df

# ====== INTRADAY ======
def load_intraday(start: str = None, end: str = None, input_dir=DATA_DIR_INTRA):
    """Load intraday files and reconstruct the intraday timestamp grid."""
    files = sorted(glob.glob(os.path.join(input_dir, "*.csv")))
    files = [f for f in files if not os.path.basename(f).startswith("dat.")]
    if start: files = [f for f in files if os.path.splitext(os.path.basename(f))[0] >= start]
    if end:   files = [f for f in files if os.path.splitext(os.path.basename(f))[0] <= end]

    df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)

    if "ID" not in df.columns and "Id" in df.columns:
        df = df.rename(columns={"Id": "ID"})
    
    # Parse trading date
    df["Date"] = pd.to_datetime(df["Date"].astype(str), format="%Y%m%d")
    
    # Reconstruct 15-minute timestamp using per-day per-ID row order
    df["snapshot_idx"] = df.groupby(["Date", "ID"]).cumcount()

    base = pd.Timedelta(hours=9, minutes=45)                 # 09:45
    df["Timestamp"] = pd.Timestamp("2000-01-01") + base + df["snapshot_idx"] * pd.Timedelta(minutes=15)
    
    df = df.sort_values(["Date", "ID", "Timestamp"]).reset_index(drop=True)
    return df

# =========================================================
# rolling state
# =========================================================
def make_empty_rolling_state(lookback: int = 20) -> Dict:
    """Initialize rolling state for features that need history."""
    return {
        "lookback": lookback,
        "vol_profile": defaultdict(lambda: deque(maxlen=lookback)),
        "last_seen_idx": {},   # ID -> date index
        "prev_shares_adj_factor": {},  # ID -> last seen SharesAdjFactor
        "last_rev_split_idx": {},      # ID -> date index of last reverse split
    }

# =========================================================
# daily preprocessing
# =========================================================
def build_daily_adjusted(daily_df: pd.DataFrame) -> pd.DataFrame:
    """
    Input raw daily file for a single date.
    Output daily_T with adjusted fields used by feature construction.
    """
    daily_df = _standardize_id_col(daily_df).copy()

    req = [
        "Date", "ID", "Open", "High", "Low", "Close", "Volume",
        "PxAdjFactor", "SharesAdjFactor", "EST_VOL", "MDV_63",
        "FREE_FLOAT_PERCENTAGE"
    ]

    # Build adjusted OHLC and adjusted daily dollar volume
    daily_df["Open_adj"] = daily_df["Open"] * daily_df["PxAdjFactor"]
    daily_df["High_adj"] = daily_df["High"] * daily_df["PxAdjFactor"]
    daily_df["Low_adj"] = daily_df["Low"] * daily_df["PxAdjFactor"]
    daily_df["Close_adj"] = daily_df["Close"] * daily_df["PxAdjFactor"]

    daily_df["Volume_adj_day"] = daily_df["Volume"] * daily_df["SharesAdjFactor"]
    daily_df["DV_adj_day"] = daily_df["Volume_adj_day"] * daily_df["Close_adj"]
    daily_df.rename(columns={"FREE_FLOAT_PERCENTAGE": "FFP"}, inplace=True)
    
    keep_cols = [
        "Date", "ID", "SYMBOL", "MIC",
        "EST_VOL", "MDV_63", "FFP",
        "PxAdjFactor", "SharesAdjFactor",
        "Open_adj", "High_adj", "Low_adj", "Close_adj",
        "Volume_adj_day", "DV_adj_day",
    ]
    keep_cols = [c for c in keep_cols if c in daily_df.columns]
    return daily_df[keep_cols].copy()


# =========================================================
# intraday preprocessing
# =========================================================
def build_intraday_15m_adjusted(
    intra_T: pd.DataFrame,
    daily_T: pd.DataFrame,
    daily_Tm1: pd.DataFrame,
) -> pd.DataFrame:
    """
    Convert one-day raw intraday cumulative file into adjusted 15m bars.

    Returned columns include:
      - Timestamp
      - bar_no
      - CumReturnRaw / CumReturnResid
      - r_raw / r_resid
      - P_adj
      - V_adj_cum / V_adj
      - DV_adj
      - DV_adj_cum
    """
    intra_T = _standardize_id_col(intra_T).copy()

    out = intra_T.copy()
    shares_map = daily_T.set_index("ID")["SharesAdjFactor"]
    open_map = daily_T.set_index("ID")["Open_adj"]

    out["SharesAdjFactor"] = out["ID"].map(shares_map)
    out["Open_adj"] = out["ID"].map(open_map)
    
    if daily_Tm1 is None:
        out["PrevClose_adj"] = np.nan
    else:
        # Previous adjusted close is the base price for today's cumulative return path
        prev_close_map = daily_Tm1.set_index("ID")["Close_adj"]
        out["PrevClose_adj"] = out["ID"].map(prev_close_map)
    
    # Reconstruct adjusted intraday price path
    out["P_adj"] = out["PrevClose_adj"] * (1.0 + out["CumReturnRaw"])

    # Convert cumulative volume into adjusted bar volume
    out["V_adj_cum"] = out["CumVolume"] * out["SharesAdjFactor"]

    g = out.groupby("ID", sort=False)

    out["V_adj"] = g["V_adj_cum"].diff()
    first_mask = g.cumcount().eq(0)
    out.loc[first_mask, "V_adj"] = out.loc[first_mask, "V_adj_cum"]

    # Convert cumulative returns into 15-minute bar returns
    prev_raw = g["CumReturnRaw"].shift(1).fillna(0.0)
    prev_resid = g["CumReturnResid"].shift(1).fillna(0.0)
    out["r_raw"] = (1.0 + out["CumReturnRaw"]) / (1.0 + prev_raw) - 1.0
    out["r_resid"] = (1.0 + out["CumReturnResid"]) / (1.0 + prev_resid) - 1.0

    # Use average price over the bar to compute adjusted dollar volume
    out["P_adj_prev"] = g["P_adj"].shift(1)
    out.loc[first_mask, "P_adj_prev"] = out.loc[first_mask, "Open_adj"]

    out["DV_adj"] = out["V_adj"] * (out["P_adj"] + out["P_adj_prev"]) * 0.5
    out["DV_adj_cum"] = g["DV_adj"].cumsum()
    
    out["bar_no"] = g.cumcount() + 1

    keep_cols = [
        "Date", "ID", "Time", "Timestamp", "bar_no",
        "CumReturnRaw", "CumReturnResid",
        "r_raw", "r_resid",
        "PrevClose_adj", "P_adj", "P_adj_prev",
        "V_adj_cum", "V_adj", "DV_adj", "DV_adj_cum",
    ]
    return out[keep_cols]


# =========================================================
# target
# =========================================================
def build_target_y_norm(
    intra_T: pd.DataFrame,
    intra_Tm1: pd.DataFrame,
    daily_Tm1: pd.DataFrame,
    t1530: str = "15:30:00",
    t1600: str = "16:00:00",
) -> pd.DataFrame:
    """Build normalized target from yesterday 15:30 to today 15:30."""
    if intra_Tm1 is None or daily_Tm1 is None:
        return pd.DataFrame(columns=["Date", "ID", "y_raw", "y_norm"])

    t1530_clock = pd.Timestamp(f"2000-01-01 {t1530}")
    t1600_clock = pd.Timestamp(f"2000-01-01 {t1600}")

    # Use maps instead of repeated merges for speed
    r1530_tm1 = (
        intra_Tm1.loc[intra_Tm1["Timestamp"] == t1530_clock, ["ID", "CumReturnResid"]]
        .drop_duplicates("ID")
        .set_index("ID")["CumReturnResid"]
    )
    r1600_tm1 = (
        intra_Tm1.loc[intra_Tm1["Timestamp"] == t1600_clock, ["Date", "ID", "CumReturnResid"]]
        .drop_duplicates("ID")
        .set_index("ID")
    )
    r1530_t = (
        intra_T.loc[intra_T["Timestamp"] == t1530_clock, ["ID", "CumReturnResid"]]
        .drop_duplicates("ID")
        .set_index("ID")["CumReturnResid"]
    )

    y = r1600_tm1.rename(columns={"CumReturnResid": "r_1600_Tm1"}).copy()
    y["r_1530_Tm1"] = y.index.map(r1530_tm1)
    y["r_1530_T"] = y.index.map(r1530_t)
    
    y["y_raw"] = (1.0 + y["r_1600_Tm1"]) / (1.0 + y["r_1530_Tm1"]) * (1.0 + y["r_1530_T"]) - 1.0

    daily_map = daily_Tm1[["Date", "ID", "EST_VOL"]].drop_duplicates("ID").set_index("ID")
    y["EST_VOL"] = y.index.map(daily_map["EST_VOL"])
    y["y_norm"] = _safe_div(y["y_raw"], y["EST_VOL"])

    y = y.reset_index()
    return y[["Date", "ID", "y_raw", "y_norm"]]


# =========================================================
# feature internals
# =========================================================
def _extract_1530_snapshot(intra_T: pd.DataFrame, t1530_clock: pd.Timestamp) -> pd.DataFrame:
    """Extract the 15:30 snapshot used by several features."""
    cols = [
        "Date", "ID", "Timestamp", "bar_no",
        "CumReturnRaw", "CumReturnResid",
        "P_adj", "V_adj_cum", "DV_adj_cum",
    ]
    return intra_T.loc[intra_T["Timestamp"] == t1530_clock, cols]


def _intraday_profile_to_1530(intra_L: pd.DataFrame) -> pd.DataFrame:
    """Build intraday volume profile up to 15:30."""
    x = intra_L[["ID", "Timestamp", "bar_no", "V_adj"]].copy()
    total = x.groupby("ID", sort=False)["V_adj"].transform("sum")
    x["vol_share"] = _safe_div(x["V_adj"], total)
    return x


def _pivot_profile_24(profile_long: pd.DataFrame) -> pd.DataFrame:
    """Pivot the long profile table into 24 bar-wise volume shares."""
    prof = profile_long.pivot(index="ID", columns="bar_no", values="vol_share").sort_index(axis=1)
    # ensure exactly bars 1..24 exist
    for k in range(1, 25):
        if k not in prof.columns:
            prof[k] = 0.0
    prof = prof[[k for k in range(1, 25)]]
    prof.columns = [f"share_{k:02d}" for k in range(1, 25)]
    prof = prof.fillna(0.0)
    prof.index.name = "ID"
    return prof.reset_index()


def _compute_range_and_drawdown(intra_L: pd.DataFrame) -> pd.DataFrame:
    """Compute intraday range and max drawdown up to 15:30."""
    x = intra_L[["ID", "P_adj"]].copy()
    g = x.groupby("ID", sort=False)["P_adj"]

    out = pd.DataFrame(index=g.size().index)
    first = g.first()
    out["range"] = (g.max() - g.min()) / (first + EPS)

    x["cummax"] = x.groupby("ID", sort=False)["P_adj"].cummax()
    x["drawdown"] = (x["cummax"] - x["P_adj"]) / (x["cummax"] + EPS)
    out["max_drawdown"] = x.groupby("ID", sort=False)["drawdown"].max()

    out.index.name = "ID"
    return out.reset_index()


def _compute_up_minus_down_risk(
    intra_L: pd.DataFrame,
    r_col: str = "r_resid",
) -> pd.DataFrame:
    """Measure asymmetry between positive and negative return variation."""
    x = intra_L[["ID", r_col]].copy()
    x["up_var"] = x[r_col].clip(lower=0.0) ** 2
    x["dn_var"] = (-x[r_col].clip(upper=0.0)) ** 2

    agg = x.groupby("ID", sort=False)[["up_var", "dn_var"]].sum()
    agg["up_minus_down_risk_L"] = (agg["up_var"] - agg["dn_var"]) / (agg["up_var"] + agg["dn_var"] + EPS)
    return agg[["up_minus_down_risk_L"]].reset_index()


def _compute_tga_directional_asymmetry(
    intra_L: pd.DataFrame,
    r_col: str = "r_resid",
) -> pd.DataFrame:
    """Directional trend asymmetry based on weighted positive vs negative returns."""
    rows = []
    for sid, g in intra_L.groupby("ID", sort=False):
        r = g[r_col].to_numpy(dtype=float)
        if r.size == 0:
            rows.append((sid, np.nan))
            continue

        r_pos = np.where(r > 0.0, r, 0.0)
        r_neg_abs = np.where(r < 0.0, -r, 0.0)

        w = np.arange(1, len(r) + 1, dtype=float)
        denom_w = w.sum()
        mean_abs = np.mean(np.abs(r))

        tga_u = np.dot(w, r_pos) / (denom_w + EPS) / (mean_abs + EPS)
        tga_d = np.dot(w, r_neg_abs) / (denom_w + EPS) / (mean_abs + EPS)
        rows.append((sid, tga_u - tga_d))

    return pd.DataFrame(rows, columns=["ID", "tga_directional_asymmetry_L"])


def _compute_negative_illiquidity_L(
    intra_L: pd.DataFrame,
    daily_T1: pd.DataFrame,
    r_col: str = "r_resid",
) -> pd.DataFrame:
    """Negative-return illiquidity over the long intraday window."""
    x = intra_L[["ID", r_col, "DV_adj"]].copy()

    neg_mask = x[r_col] < 0.0
    x["neg_abs_r"] = np.where(neg_mask, np.abs(x[r_col]), np.nan)
    x["neg_dv"] = np.where(neg_mask, x["DV_adj"], np.nan)

    agg = x.groupby("ID", sort=False)[["neg_abs_r", "neg_dv"]].sum(min_count=1)

    mdv_map = daily_T1.drop_duplicates("ID").set_index("ID")["MDV_63"]
    agg["MDV_63"] = agg.index.map(mdv_map)

    agg["negative_illiquidity_L"] = agg["neg_abs_r"] / (EPS + agg["neg_dv"] / agg["MDV_63"])

    return agg[["negative_illiquidity_L"]].reset_index()


def _compute_yesterday_tail_vpr(
    intra_Tm1: pd.DataFrame,
    daily_Tm1: pd.DataFrame,
    t1530_clock: pd.Timestamp,
) -> pd.DataFrame:
    """Compute yesterday's tail dollar-volume participation ratio."""
    if intra_Tm1 is None or daily_Tm1 is None:
        return pd.DataFrame(columns=["ID", "yday_tail_vpr"])

    # 1) Intraday tail DV from 15:30 to 16:00
    agg_1530_1600 = (
        intra_Tm1.loc[intra_Tm1["Timestamp"] > t1530_clock, ["ID", "DV_adj"]]
        .groupby("ID", sort=False)["DV_adj"]
        .sum()
    )

    # 2) Full-day intraday DV from the intraday file
    agg_intra_full = (
        intra_Tm1.groupby("ID", sort=False)["DV_adj"]
        .sum()
    )

    # 3) Combine with daily total: tail = intraday(15:30-16:00) + (daily_full - intraday_full)
    y = daily_Tm1[["ID", "MDV_63", "DV_adj_day"]].copy()
    y["DV_1530_1600"] = y["ID"].map(agg_1530_1600).fillna(0.0)
    y["DV_intraday_full"] = y["ID"].map(agg_intra_full).fillna(0.0)
    y["DV_tail_1530_close"] = y["DV_1530_1600"] + (y["DV_adj_day"] - y["DV_intraday_full"])

    y["yday_tail_vpr"] = _safe_div(y["DV_tail_1530_close"], y["MDV_63"])

    return y[["ID", "yday_tail_vpr"]]


def _compute_prevday_cumret_resid_1600(intra_Tm1: pd.DataFrame) -> pd.DataFrame:
    """Extract previous day's cumulative residual return at 16:00."""
    if intra_Tm1 is None:
        return pd.DataFrame(columns=["ID", "prev_cumret_resid_1600"])

    t1600 = pd.Timestamp("2000-01-01 16:00:00")
    x = intra_Tm1.loc[intra_Tm1["Timestamp"] == t1600, ["ID", "CumReturnResid"]].copy()
    x = x.rename(columns={"CumReturnResid": "prev_cumret_resid_1600"})
    return x


def _compute_days_since_reverse_split(
    daily_T: pd.DataFrame,
    date_idx: int,
    rolling_state: Dict,
    min_periods: int,
) -> pd.DataFrame:
    """
    Track reverse splits via SharesAdjFactor and compute days since last reverse split.

    A reverse split is detected when today's SharesAdjFactor increases relative to the
    last seen SharesAdjFactor for the same ID. The feature is the number of days since
    that last detected split, capped to 0 when there was no reverse split in the
    past `min_periods` days.
    """
    shares_map = rolling_state["prev_shares_adj_factor"]
    last_split = rolling_state["last_rev_split_idx"]

    rows = []
    for row in daily_T.itertuples(index=False):
        sid = row.ID
        shares_today = getattr(row, "SharesAdjFactor", None)
        prev_shares = shares_map.get(sid)

        # If SharesAdjFactor on T (this date) is greater than the last seen
        # SharesAdjFactor, interpret this as a morning-of-T reverse split.
        if prev_shares is not None and shares_today is not None and shares_today > prev_shares + EPS:
            last_split[sid] = date_idx

        if shares_today is not None:
            shares_map[sid] = shares_today

        last_idx = last_split.get(sid)
        if last_idx is None:
            days = 0
        else:
            diff = date_idx - last_idx
            days = diff if diff <= min_periods else 0

        rows.append((sid, days))

    return pd.DataFrame(rows, columns=["ID", "days_since_rev_split"])


def _compute_frighten_stats_L(
    intra_L: pd.DataFrame,
    r_col: str = "r_resid",
) -> pd.DataFrame:
    """
    frighten_mean_L / frighten_std_L on the long window up to 15:30.
    """
    x = intra_L[["ID", "Timestamp", r_col, "DV_adj"]].copy()

    # Cross-sectional market return weighted by DV_adj at each timestamp
    x["_num"] = x[r_col] * x["DV_adj"]
    g = x.groupby("Timestamp", sort=False)
    r_mkt_num = g["_num"].sum()
    r_mkt_den = g["DV_adj"].sum(min_count=1)
    r_mkt = r_mkt_num / (r_mkt_den + EPS)

    x["r_mkt"] = x["Timestamp"].map(r_mkt)

    x["fright_raw"] = np.abs(x[r_col] - x["r_mkt"]) / (
        np.abs(x[r_col]) + np.abs(x["r_mkt"]) + 0.1
    )

    g = x.groupby("ID", sort=False)
    x["fright"] = x["fright_raw"] - (
        g["fright_raw"].shift(1) + g["fright_raw"].shift(2)
    ) / 2.0
    x["fright"] = x["fright"].where(x["fright"] > 0.0, 0.0)

    x["fright_x_raw"] = x["fright"] * x[r_col]

    agg = x.groupby("ID", sort=False).agg(
        frighten_mean_L=("fright_x_raw", lambda s: _finite_mean_scaled(s, 1e6)),
        frighten_std_L=("fright_x_raw", lambda s: _finite_std_scaled(s, 1e6, 0)),
    )
    return agg.reset_index()



def _compute_amount_dir_15m(
    intra_L: pd.DataFrame,
    r_col: str = "r_resid",
) -> pd.DataFrame:
    """
    amount_dir_15m = mean(DV_adj * sign(r_resid)) / mean(DV_adj)
    """
    x = intra_L[["ID", r_col, "DV_adj"]].copy()
    x["signed_dv"] = x["DV_adj"] * np.sign(x[r_col])

    agg = x.groupby("ID", sort=False).agg(
        signed_dv_mean=("signed_dv", "mean"),
        dv_mean=("DV_adj", "mean"),
    )
    agg["amount_dir_15m"] = agg["signed_dv_mean"] / (agg["dv_mean"] + EPS)
    return agg[["amount_dir_15m"]].reset_index()


def _compute_umd_family_L(
    intra_L: pd.DataFrame,
    r_col: str = "r_resid",
) -> pd.DataFrame:
    """
    Compute:
      - r2_umd_inv_mean
      - r2_umdvol_inv_mean
      - r1_umdvol_mean
      - r1_umdvol_std
    """
    x = intra_L[["ID", r_col, "V_adj"]].copy()
    x["dV"] = x.groupby("ID", sort=False)["V_adj"].diff()

    g = 100.0 * np.log1p(x[r_col].clip(lower=-0.999999))
    g2 = g.abs() + 1e-4

    pos = (g > 0.0).astype(float)
    neg = (g < 0.0).astype(float)
    vol_up = (x["dV"] > 0.0).astype(float)
    vol_dn = (x["dV"] < 0.0).astype(float)

    x["pos_inv"] = pos / g2
    x["neg_inv"] = neg / g2
    x["up_inv"] = vol_up / g2
    x["dn_inv"] = vol_dn / g2
    x["g_up"] = g * vol_up
    x["g_dn"] = g * vol_dn

    agg = x.groupby("ID", sort=False).agg(
        pos_mean=("pos_inv", "mean"),
        neg_mean=("neg_inv", "mean"),
        up_mean=("up_inv", "mean"),
        dn_mean=("dn_inv", "mean"),
        gup_mean=("g_up", "mean"),
        gdn_mean=("g_dn", "mean"),
        gup_std=("g_up", lambda s: np.nanstd(s, ddof=0)),
        gdn_std=("g_dn", lambda s: np.nanstd(s, ddof=0)),
    )

    agg["r1_umd_inv_mean"] = 1e-4 * (agg["pos_mean"] - agg["neg_mean"])
    agg["r1_umdvol_inv_mean"] = 1e-4 * (agg["up_mean"] - agg["dn_mean"])
    agg["r1_umdvol_mean"] = agg["gup_mean"] - agg["gdn_mean"]
    agg["r1_umdvol_std"] = agg["gup_std"] - agg["gdn_std"]

    return agg[
        [
            "r1_umd_inv_mean",
            "r1_umdvol_inv_mean",
            "r1_umdvol_mean",
            "r1_umdvol_std",
        ]
    ].reset_index()


def _compute_srvj_family_L(
    intra_L: pd.DataFrame,
    r_col: str = "r_resid",
) -> pd.DataFrame:
    """
    Compute SRVJ_W, RTV_L, RVJ_L, RBV_L on the long intraday window.
    """
    x = intra_L[["ID", r_col]].copy()
    x["bp"] = 100.0 * x[r_col]

    g = x.groupby("ID", sort=False)

    # lagged values
    x["bp_l1"] = g["bp"].shift(1)
    x["bp_l2"] = g["bp"].shift(2)

    # RTV_L
    x["rtv_term"] = (
        np.abs(x["bp"]) ** (2.0 / 3.0)
        * np.abs(x["bp_l1"]) ** (2.0 / 3.0)
        * np.abs(x["bp_l2"]) ** (2.0 / 3.0)
    )
    RTV_L = MU_TRIPOWER * x.groupby("ID", sort=False)["rtv_term"].sum(min_count=1)

    # RV_L and RVJ_L
    RV_L = x.groupby("ID", sort=False)["bp"].apply(lambda s: np.nansum(s.to_numpy(dtype=float) ** 2))
    RVJ_L = (RV_L - RTV_L).clip(lower=0.0)

    out = pd.concat(
        [
            RTV_L.rename("RTV_L"),
            RVJ_L.rename("RVJ_L"),
        ],
        axis=1,
    ).reset_index()

    return out


def _compute_pv_corr_L(
    intra_L: pd.DataFrame,
    r_col: str = "r_resid",
) -> pd.DataFrame:
    """
    Correlation between V_adj and residual return over the long window.
    """
    x = intra_L[["ID", "V_adj", r_col]].copy()
    x["vr"] = x["V_adj"] * x[r_col]
    x["v2"] = x["V_adj"] ** 2
    x["r2"] = x[r_col] ** 2

    agg = x.groupby("ID", sort=False).agg(
        n=("V_adj", "count"),
        sum_v=("V_adj", "sum"),
        sum_r=(r_col, "sum"),
        sum_vr=("vr", "sum"),
        sum_v2=("v2", "sum"),
        sum_r2=("r2", "sum"),
    )

    cov = agg["sum_vr"] / agg["n"] - (agg["sum_v"] / agg["n"]) * (agg["sum_r"] / agg["n"])
    var_v = agg["sum_v2"] / agg["n"] - (agg["sum_v"] / agg["n"]) ** 2
    var_r = agg["sum_r2"] / agg["n"] - (agg["sum_r"] / agg["n"]) ** 2

    agg["pv_corr"] = cov / (np.sqrt(var_v.clip(lower=0.0)) * np.sqrt(var_r.clip(lower=0.0)) + EPS)
    return agg[["pv_corr"]].reset_index()


def _compute_intraday_macd_rsi_L(
    intra_L: pd.DataFrame,
    price_col: str = "P_adj",
    fast: int = 4,
    slow: int = 8,
    signal: int = 3,
    rsi_period: int = 6,
) -> pd.DataFrame:
    """
    Intraday MACD and RSI evaluated at 15:30.
    Vectorized version on a Timestamp x ID matrix for speed.
    """
    x = intra_L[["Timestamp", "ID", price_col]].copy()
    px_wide = (
        x.pivot(index="Timestamp", columns="ID", values=price_col)
         .sort_index()
         .astype(float)
    )

    # ---------- MACD on log price ----------
    log_px = np.log(np.maximum(px_wide, EPS))

    ema_fast = log_px.ewm(span=fast, adjust=False, min_periods=fast).mean()
    ema_slow = log_px.ewm(span=slow, adjust=False, min_periods=slow).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False, min_periods=signal).mean()
    macd_hist = macd - macd_signal

    macd_last = macd.iloc[-1]
    macd_signal_last = macd_signal.iloc[-1]
    macd_hist_last = macd_hist.iloc[-1]

    # ---------- RSI on raw price ----------
    dpx = px_wide.diff()

    gain = dpx.clip(lower=0.0)
    loss = (-dpx.clip(upper=0.0))

    avg_gain = gain.ewm(alpha=1.0 / rsi_period, adjust=False, min_periods=rsi_period).mean()
    avg_loss = loss.ewm(alpha=1.0 / rsi_period, adjust=False, min_periods=rsi_period).mean()

    rs = avg_gain / (avg_loss + EPS)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi_last = rsi.iloc[-1]

    out = pd.concat(
        [
            macd_signal_last.rename("intraday_macd_signal"),
            macd_hist_last.rename("intraday_macd_hist"),
            rsi_last.rename("intraday_rsi"),
        ],
        axis=1,
    ).reset_index()

    return out


def _compute_profile_l1_against_past_mean(
    profile_24: pd.DataFrame,
    rolling_state: Dict,
    min_periods: int = 20,
) -> pd.DataFrame:
    """Compare today's volume profile to the rolling mean profile."""
    share_cols = [f"share_{k:02d}" for k in range(1, 25)]
    rows = []

    for row in profile_24.itertuples(index=False):
        sid = row.ID
        today_vec = np.asarray([getattr(row, c) for c in share_cols], dtype=float)

        hist = rolling_state["vol_profile"][sid]
        if len(hist) < min_periods:
            val = np.nan
        else:
            hist_mean = np.mean(np.vstack(hist), axis=0)
            val = float(np.abs(today_vec - hist_mean).sum())

        rows.append((sid, val))

    return pd.DataFrame(rows, columns=["ID", "vol_profile_L1_vs_avg"])


def handle_id_gap(sid, current_idx, rolling_state, max_gap_days=5):
    """Clear rolling profile history if the gap is too large."""
    last_seen = rolling_state["last_seen_idx"].get(sid)
    if last_seen is None:
        return

    gap = current_idx - last_seen
    if gap > max_gap_days:
        rolling_state["vol_profile"][sid].clear()
    
# =========================================================
# main feature builder
# =========================================================
def build_features_for_date(
    date_idx,
    daily_T: pd.DataFrame,
    daily_Tm1: Optional[pd.DataFrame],
    intra_T: pd.DataFrame,
    intra_Tm1: Optional[pd.DataFrame],
    rolling_state: Dict,
    min_periods: int = 20,
    return_y: bool = True,
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:

    t1530_clock = pd.Timestamp("2000-01-01 15:30:00")
    T0945 = pd.Timestamp("2000-01-01 09:45:00")
    T1100 = pd.Timestamp("2000-01-01 11:00:00")
    T1400 = pd.Timestamp("2000-01-01 14:00:00")
    T1530 = t1530_clock

    # Reuse the <=15:30 slice for all long-window intraday features
    intra_L = intra_T.loc[intra_T["Timestamp"] <= t1530_clock].copy()

    # Base daily cross-section
    feat = daily_T[["Date", "ID", "EST_VOL", "MDV_63", "Open_adj", "Close_adj", "DV_adj_day", "FFP"]].copy()

    # ---------- (1 to 4) Day-of-week one-hot (Mon-Thu; 0 = Monday) ----------
    # dow = daily_T["Date"].dt.dayofweek
    # feat["dow_Mon"] = (dow == 0).astype(int)
    # feat["dow_Tue"] = (dow == 1).astype(int)
    # feat["dow_Wed"] = (dow == 2).astype(int)
    # feat["dow_Thu"] = (dow == 3).astype(int)

    # ---------- 15:30 snapshot ----------
    snap_1530 = _extract_1530_snapshot(intra_T, t1530_clock).rename(
        columns={
            "CumReturnRaw": "cumret_raw_1530",
            "CumReturnResid": "cumret_resid_1530",
            "P_adj": "P_adj_1530",
            "V_adj_cum": "V_adj_cum_1530",
            "DV_adj_cum": "DV_adj_cum_1530",
        }
    ).set_index("ID")

    for c in ["cumret_raw_1530", "cumret_resid_1530", "P_adj_1530", "V_adj_cum_1530", "DV_adj_cum_1530"]:
        feat[c] = feat["ID"].map(snap_1530[c])

    # ---------- 5) intraday dollar VPR ----------
    feat["intraday_dollar_vpr"] = _safe_div(feat["DV_adj_cum_1530"], feat["MDV_63"])

    # ---------- 6) today DV relative to yesterday DV ----------
    if intra_Tm1 is not None:
        yday_dv = intra_Tm1.groupby("ID", sort=False)["DV_adj_cum"].last()
        feat["DV_adj_day_Tm1"] = feat["ID"].map(yday_dv)
        feat["intraday_dollar_rel_to_yday"] = _safe_div(feat["DV_adj_cum_1530"], feat["DV_adj_day_Tm1"])
    else:
        feat["intraday_dollar_rel_to_yday"] = np.nan

    # ---------- 7) volume profile L1 vs past mean ----------
    profile_long = _intraday_profile_to_1530(intra_L)
    # profile_24 = _pivot_profile_24(profile_long)
    # prof_l1 = _compute_profile_l1_against_past_mean(profile_24, rolling_state, min_periods).set_index("ID")
    # feat["vol_profile_L1_vs_avg"] = feat["ID"].map(prof_l1["vol_profile_L1_vs_avg"])

    # # Update rolling volume profile state after today's feature is computed
    # share_cols = [f"share_{k:02d}" for k in range(1, 25)]
    # for row in profile_24.itertuples(index=False):
    #     sid = row.ID
    #     handle_id_gap(sid, date_idx, rolling_state)
    #     vec = np.asarray([getattr(row, c) for c in share_cols], dtype=float)
    #     rolling_state["vol_profile"][sid].append(vec)
    #     rolling_state["last_seen_idx"][sid] = date_idx

    # ---------- 8) volume acceleration ----------
    ts = profile_long["Timestamp"]
    early_mask = (ts >= T0945) & (ts <= T1100)
    late_mask = (ts >= T1400) & (ts <= T1530)

    vol_early = profile_long.loc[early_mask].groupby("ID", sort=False)["V_adj"].sum()
    vol_late = profile_long.loc[late_mask].groupby("ID", sort=False)["V_adj"].sum()
    feat["V_early"] = feat["ID"].map(vol_early)
    feat["V_late"] = feat["ID"].map(vol_late)
    feat["volume_accel"] = _safe_div(feat["V_late"], feat["V_early"])

    # ---------- 9) intraday residual return scaled by volatility ----------
    feat["intraday_resid_ret_vol"] = _safe_div(feat["cumret_resid_1530"], feat["EST_VOL"])

    # ---------- 10) overnight return scaled by volatility ----------
    feat["overnight_ret"] = np.nan
    if daily_Tm1 is not None:
        prev_close = daily_Tm1.set_index("ID")["Close_adj"]
        feat["Close_adj_Tm1"] = feat["ID"].map(prev_close)
        feat["overnight_ret"] = _safe_div(feat["Open_adj"], feat["Close_adj_Tm1"]) - 1.0
        feat["overnight_ret_vol"] = _safe_div(feat["overnight_ret"], feat["EST_VOL"])
    else:
        feat["overnight_ret_vol"] = np.nan

    # ---------- 11) range / 12) drawdown ----------
    rgdd = _compute_range_and_drawdown(intra_L).set_index("ID")
    feat["range"] = feat["ID"].map(rgdd["range"])
    feat["max_drawdown"] = feat["ID"].map(rgdd["max_drawdown"])

    # ---------- 13) up-minus-down risk ----------
    umr = _compute_up_minus_down_risk(intra_L, r_col="r_resid").set_index("ID")
    feat["up_minus_down_risk_L"] = feat["ID"].map(umr["up_minus_down_risk_L"])

    # ---------- 14) tga directional asymmetry ----------
    tga = _compute_tga_directional_asymmetry(intra_L, r_col="r_resid").set_index("ID")
    feat["tga_directional_asymmetry_L"] = feat["ID"].map(tga["tga_directional_asymmetry_L"])

    # ---------- 15) previous day cumulative residual at 16:00 (vol-scaled) ----------
    if intra_Tm1 is not None and daily_Tm1 is not None:
        prev_res = _compute_prevday_cumret_resid_1600(intra_Tm1).set_index("ID")
        feat["prev_cumret_resid_1600"] = feat["ID"].map(prev_res["prev_cumret_resid_1600"])

        est_vol_tm1 = daily_Tm1.drop_duplicates("ID").set_index("ID")["EST_VOL"]
        feat["EST_VOL_Tm1"] = feat["ID"].map(est_vol_tm1)
        feat["prev_cumret_resid_1600"] = _safe_div(
            feat["prev_cumret_resid_1600"], feat["EST_VOL_Tm1"]
        )
    else:
        feat["prev_cumret_resid_1600"] = np.nan

    # ---------- 16) yesterday tail VPR ----------
    no4 = _compute_yesterday_tail_vpr(intra_Tm1, daily_Tm1, t1530_clock).set_index("ID")
    feat["yday_tail_vpr"] = feat["ID"].map(no4["yday_tail_vpr"])

    # ---------- 17) common-factor return scaled by daily volatility ----------
    feat["common_factor_ret_vol"] = _safe_div(
        feat["cumret_raw_1530"] - feat["cumret_resid_1530"],
        feat["EST_VOL"]
    )

    # ---------- 18) negative-return illiquidity ----------
    if daily_Tm1 is not None:
        neg_illiq = _compute_negative_illiquidity_L(intra_L, daily_Tm1, r_col="r_resid").set_index("ID")
        feat["negative_illiquidity_L"] = feat["ID"].map(neg_illiq["negative_illiquidity_L"])
    else:
        feat["negative_illiquidity_L"] = np.nan

    # ---------- 19) days since reverse split ----------
    # days_rs = _compute_days_since_reverse_split(
    #     daily_T=daily_T,
    #     date_idx=date_idx,
    #     rolling_state=rolling_state,
    #     min_periods=min_periods,
    # ).set_index("ID")
    # feat["days_since_rev_split"] = feat["ID"].map(days_rs["days_since_rev_split"])
    
        # ---------- 19) frighten_mean_L / frighten_std_L ----------
    fright = _compute_frighten_stats_L(intra_L, r_col="r_resid").set_index("ID")
    feat["frighten_mean_L"] = feat["ID"].map(fright["frighten_mean_L"])
    feat["frighten_std_L"] = feat["ID"].map(fright["frighten_std_L"])
    
    # ---------- 20) amount_dir_15m ----------
    amount_dir = _compute_amount_dir_15m(intra_L, r_col="r_resid").set_index("ID")
    feat["amount_dir_15m"] = feat["ID"].map(amount_dir["amount_dir_15m"])

    # ---------- 21-23) umd family ----------
    # umd_family = _compute_umd_family_L(intra_L, r_col="r_resid").set_index("ID")
    # feat["r1_umd_inv_mean"] = feat["ID"].map(umd_family["r1_umd_inv_mean"])
    # feat["r1_umdvol_inv_mean"] = feat["ID"].map(umd_family["r1_umdvol_inv_mean"])
    # feat["r1_umdvol_mean"] = feat["ID"].map(umd_family["r1_umdvol_mean"])
    # feat["r1_umdvol_std"] = feat["ID"].map(umd_family["r1_umdvol_std"])

    # ---------- 24) SRVJ_W / RTV_L / RVJ_L / RBV_L ----------
    # jump_family = _compute_srvj_family_L(intra_L, r_col="r_resid").set_index("ID")
    # feat["RTV_L"] = feat["ID"].map(jump_family["RTV_L"])
    # feat["RVJ_L"] = feat["ID"].map(jump_family["RVJ_L"])

    # ---------- 25) pv_corr ----------
    # pv = _compute_pv_corr_L(intra_L, r_col="r_resid").set_index("ID")
    # feat["pv_corr"] = feat["ID"].map(pv["pv_corr"])

    # ---------- 26) intraday MACD / RSI ----------
    tech = _compute_intraday_macd_rsi_L(
        intra_L,
        price_col="P_adj",
        fast=4,
        slow=8,
        signal=3,
        rsi_period=6,
    ).set_index("ID")
    feat["intraday_macd_signal"] = feat["ID"].map(tech["intraday_macd_signal"])
    feat["intraday_macd_hist"] = feat["ID"].map(tech["intraday_macd_hist"])
    feat["intraday_rsi"] = feat["ID"].map(tech["intraday_rsi"])

    # ---------- 27) up-minus-down risk (raw) ----------
    umr_raw = _compute_up_minus_down_risk(intra_L, r_col="r_raw").set_index("ID")
    feat["up_minus_down_risk_L_raw"] = feat["ID"].map(umr_raw["up_minus_down_risk_L"])

    # ---------- 28) tga directional asymmetry (raw) ----------
    # tga_raw = _compute_tga_directional_asymmetry(intra_L, r_col="r_raw").set_index("ID")
    # feat["tga_directional_asymmetry_L_raw"] = feat["ID"].map(tga_raw["tga_directional_asymmetry_L"])

    # ---------- 29) negative-return illiquidity (raw) ----------
    # if daily_Tm1 is not None:
    #     neg_illiq_raw = _compute_negative_illiquidity_L(intra_L, daily_Tm1, r_col="r_raw").set_index("ID")
    #     feat["negative_illiquidity_L_raw"] = feat["ID"].map(neg_illiq_raw["negative_illiquidity_L"])
    # else:
    #     feat["negative_illiquidity_L_raw"] = np.nan

    # ---------- 30) amount_dir_15m (raw) ----------
    # amount_dir_raw = _compute_amount_dir_15m(intra_L, r_col="r_raw").set_index("ID")
    # feat["amount_dir_15m_raw"] = feat["ID"].map(amount_dir_raw["amount_dir_15m"])
    
    # ---------- 31-34) umd family (raw) ----------
    # umd_family_raw = _compute_umd_family_L(intra_L, r_col="r_raw").set_index("ID")
    # feat["r1_umd_inv_mean_raw"] = feat["ID"].map(umd_family_raw["r1_umd_inv_mean"])
    # feat["r1_umdvol_inv_mean_raw"] = feat["ID"].map(umd_family_raw["r1_umdvol_inv_mean"])
    # feat["r1_umdvol_mean_raw"] = feat["ID"].map(umd_family_raw["r1_umdvol_mean"])
    # feat["r1_umdvol_std_raw"] = feat["ID"].map(umd_family_raw["r1_umdvol_std"])

    # ---------- 35) pv_corr (raw) ----------
    # pv_raw = _compute_pv_corr_L(intra_L, r_col="r_raw").set_index("ID")
    # feat["pv_corr_raw"] = feat["ID"].map(pv_raw["pv_corr"])


    feature_cols = [
        "Date", "ID",
        "dow_Mon", "dow_Tue", "dow_Wed", "dow_Thu",
        # "days_since_rev_split",
        "intraday_dollar_vpr",
        "intraday_dollar_rel_to_yday",
        "vol_profile_L1_vs_avg",
        "volume_accel",
        "intraday_resid_ret_vol",
        "overnight_ret_vol",
        "range",
        "max_drawdown",
        "up_minus_down_risk_L",
        "tga_directional_asymmetry_L",
        "prev_cumret_resid_1600",
        "yday_tail_vpr",
        "common_factor_ret_vol",
        "negative_illiquidity_L",
        "frighten_mean_L",
        "frighten_std_L",
        "amount_dir_15m",
        "r1_umd_inv_mean",
        "r1_umdvol_inv_mean",
        "r1_umdvol_mean",
        "r1_umdvol_std",
        "pv_corr",
        "RTV_L",
        "RVJ_L",
        "intraday_macd_signal",
        "intraday_macd_hist",
        "intraday_rsi",
        "up_minus_down_risk_L_raw",
        "tga_directional_asymmetry_L_raw",
        "negative_illiquidity_L_raw",
        "amount_dir_15m_raw",
        "r1_umd_inv_mean_raw",
        "r1_umdvol_inv_mean_raw",
        "r1_umdvol_mean_raw",
        "r1_umdvol_std_raw",
        "pv_corr_raw",
        "EST_VOL",
        "MDV_63",
    ]

    feat = feat[[c for c in feature_cols if c in feat.columns]]

    y_T = None
    if return_y:
        y_T = build_target_y_norm(
            intra_T=intra_T,
            intra_Tm1=intra_Tm1,
            daily_Tm1=daily_Tm1,
        )
    
    return feat, y_T



def build_interaction_features(
    df: pd.DataFrame,
    ts_window: int = 20,
    ts_min_periods: int = 10,
    use_sigmoid_gate: bool = True,
    sigmoid_k: float = 1.5,
) -> pd.DataFrame:
    
    x = df.copy()
    x = x.sort_values(["ID", "Date"]).reset_index(drop=False).rename(columns={"index": "_orig_index"})
    out = pd.DataFrame(index=x.index)

    def _sign(s: pd.Series) -> pd.Series:
        return pd.Series(np.sign(s), index=s.index, dtype=float)

    def _min_abs(a: pd.Series, b: pd.Series) -> pd.Series:
        return pd.concat([a.abs(), b.abs()], axis=1).min(axis=1)

    def _safe_sigmoid(s: pd.Series, k: float = 1.5) -> pd.Series:
        y = (k * s).clip(-8, 8)
        return 1.0 / (1.0 + np.exp(-y))

    def _cs_pct(s: pd.Series) -> pd.Series:
        return s.groupby(x["Date"]).rank(pct=True, method="average")

    def _compute_ts_zscores(frame: pd.DataFrame, cols, by="ID") -> pd.DataFrame:
        g = frame.groupby(by)[cols]
        roll_mean = g.rolling(window=ts_window, min_periods=ts_min_periods).mean()
        roll_std = g.rolling(window=ts_window, min_periods=ts_min_periods).std(ddof=0)

        roll_mean = roll_mean.reset_index(level=0, drop=True)
        roll_std = roll_std.reset_index(level=0, drop=True)

        z = (frame[cols] - roll_mean) / roll_std.replace(0.0, np.nan)
        z.columns = [f"z_{c}" for c in cols]
        return z

    z_cols = [
        "intraday_dollar_vpr",
        "yday_tail_vpr",
        "intraday_dollar_rel_to_yday",
        "max_drawdown",
        "frighten_std_L",
        "volume_accel",
        "range",
    ]
    zdf = _compute_ts_zscores(x, z_cols, by="ID")
    x = pd.concat([x, zdf], axis=1)

    z_intraday_dollar_vpr = x["z_intraday_dollar_vpr"]
    z_yday_tail_vpr = x["z_yday_tail_vpr"]
    z_intraday_dollar_rel_to_yday = x["z_intraday_dollar_rel_to_yday"]
    z_max_drawdown = x["z_max_drawdown"]
    # z_frighten_std_L = x["z_frighten_std_L"]

    cs_pct_abs_intraday_resid_ret_vol = _cs_pct(x["intraday_resid_ret_vol"].abs())

    if use_sigmoid_gate:
        g_flow = _safe_sigmoid(z_intraday_dollar_vpr, sigmoid_k)
        g_drawdown = _safe_sigmoid(z_max_drawdown, sigmoid_k)
        # g_fright_std = _safe_sigmoid(z_frighten_std_L, sigmoid_k)
        g_tail = _safe_sigmoid(z_yday_tail_vpr, sigmoid_k)
        g_rel_yday = _safe_sigmoid(z_intraday_dollar_rel_to_yday, sigmoid_k)
    else:
        g_flow = z_intraday_dollar_vpr.clip(lower=0.0)
        g_drawdown = z_max_drawdown.clip(lower=0.0)
        # g_fright_std = z_frighten_std_L.clip(lower=0.0)
        g_tail = z_yday_tail_vpr.clip(lower=0.0)
        g_rel_yday = z_intraday_dollar_rel_to_yday.clip(lower=0.0)

    out["x_trend_when_flow_high"] = (
        x["intraday_resid_ret_vol"] * g_flow
    )

    out["x_high_flow_no_move"] = (
        g_flow * (1.0 - cs_pct_abs_intraday_resid_ret_vol)
    )

    out["x_tail_flow_continuation"] = 0.5 * (g_tail + g_rel_yday)

    out["x_drawdown_conditioned_rsi"] = (
        (50.0 - x["intraday_rsi"]) * g_drawdown
    )
    
    # out["x_panic_amplified_illiq"] = (
    #     x["negative_illiquidity_L"] * g_fright_std
    # )
    
    # out["x_overnight_intraday_agreement"] = (
    #     _sign(x["overnight_ret_vol"] * x["intraday_resid_ret_vol"]) *
    #     _min_abs(x["overnight_ret_vol"], x["intraday_resid_ret_vol"])
    # )

    out["x_prev_close_followthrough"] = (
        _sign(x["prev_cumret_resid_1600"] * x["intraday_resid_ret_vol"]) *
        _min_abs(x["prev_cumret_resid_1600"], x["intraday_resid_ret_vol"])
    )

    # out["x_jump_vs_continuous_vol"] = (
    #     np.log1p(x["RVJ_L"].clip(lower=0.0)) -
    #     np.log1p(x["RTV_L"].clip(lower=0.0))
    # )

    out["x_frighten_mean_over_std"] = (
        x["frighten_mean_L"] / (x["frighten_std_L"].replace(0.0, np.nan))
    )
    
    # out["x_r1_umdvol_mean_over_std"] = (
    #     x["r1_umdvol_mean"] / (x["r1_umdvol_std"].replace(0.0, np.nan))
    # )
    

    # out["x_r1_umdvol_mean_over_std_raw"] = (
    #     x["r1_umdvol_mean_raw"] / (x["r1_umdvol_std_raw"].replace(0.0, np.nan))
    # )
    
    out = out.replace([np.inf, -np.inf], np.nan)

    out["_orig_index"] = x["_orig_index"].values
    out = out.sort_values("_orig_index").drop(columns="_orig_index")
    out.index = df.index

    return pd.concat([df, out], axis=1)


def _winsorize_clip(x: pd.Series, lower: Optional[float] = None, upper: Optional[float] = None) -> pd.Series:
    """Simple clip-based winsorization."""
    y = x.copy()
    if lower is not None:
        y = y.clip(lower=lower)
    if upper is not None:
        y = y.clip(upper=upper)
    return y


def mad_clip_by_date(
    df: pd.DataFrame,
    feature_cols: list,
    date_col: str = "Date",
    n_mad: float = 5.0,
) -> pd.DataFrame:
    cols = [c for c in feature_cols if c in df.columns]
    if not cols:
        return df.copy()

    out = df.copy()
    
    med = out.groupby(date_col)[cols].transform("median")
    abs_dev = (out[cols] - med).abs()
    mad = abs_dev.groupby(out[date_col])[cols].transform("median")

    mad_safe = mad.mask(mad < 1e-12)

    lower = med - n_mad * mad_safe
    upper = med + n_mad * mad_safe
    
    out[cols] = out[cols].clip(lower=lower, upper=upper, axis=1)
    return out


def winsorize_1_99_by_date(
    df: pd.DataFrame,
    cols,
    date_col: str = "Date",
) -> pd.DataFrame:
    cols = list(cols)

    q01 = df.groupby(date_col)[cols].transform("quantile", 0.01)
    q99 = df.groupby(date_col)[cols].transform("quantile", 0.99)
    
    df[cols] = df[cols].clip(lower=q01, upper=q99, axis=1)
    return df


def add_ts_zscore_all_features(
    df: pd.DataFrame,
    feature_cols: list,
    date_col: str = "Date",
    id_col: str = "ID",
    window: int = 20,
    min_periods: int = 10,
    suffix: str = None,
) -> pd.DataFrame:
    """
    Add 20-day time-series z-score for multiple feature columns at once.

    For each ID and each feature:
        z_t = (x_t - mean_{t-20:t-1}) / std_{t-20:t-1}
    
    using shift(1) to avoid leakage.

    Parameters
    ----------
    df : DataFrame
        Panel dataframe containing Date, ID, and feature columns.
    feature_cols : list
        Feature columns to transform.
    date_col : str
        Date column name.
    id_col : str
        ID column name.
    window : int
        Rolling window length.
    min_periods : int
        Minimum history required.
    suffix : str
        Suffix for newly created columns.

    Returns
    -------
    DataFrame
        Original df with new ts-zscore columns appended.
    """
    out = df.copy()
    out = out.sort_values([id_col, date_col]).reset_index(drop=True)

    eps = 1e-12
    
    # 1) lag all selected features by 1 day to avoid leakage
    x_lag = out.groupby(id_col, sort=False)[feature_cols].shift(1)

    # 2) rolling mean/std for all selected features at once
    roll_mean = (
        x_lag.groupby(out[id_col], sort=False)
        .rolling(window=window, min_periods=min_periods)
        .mean()
        .reset_index(level=0, drop=True)
    )

    roll_std = (
        x_lag.groupby(out[id_col], sort=False)
        .rolling(window=window, min_periods=min_periods)
        .std()
        .reset_index(level=0, drop=True)
    )
    
    # 3) compute z-score for all selected features at once
    z = (out[feature_cols] - roll_mean) / (roll_std + eps)
    if suffix is not None:
        z = z.add_suffix(suffix)
        out = pd.concat([out, z], axis=1)
    else:
        out[feature_cols] = z
    
    return out


# =========================================================
# rolling state update
# =========================================================


def _extract_daily_dates(daily_dir: str) -> Set[str]:
    """Extract available trading dates from daily file names."""
    pat = re.compile(r"^dat\.(\d{8})\.csv$")
    out = set()
    for fn in os.listdir(daily_dir):
        m = pat.match(fn)
        if m:
            out.add(m.group(1))
    return out


def _extract_intraday_dates(intraday_dir: str) -> Set[str]:
    """Extract available trading dates from intraday file names."""
    pat = re.compile(r"^(\d{8})\.csv$")
    out = set()
    for fn in os.listdir(intraday_dir):
        m = pat.match(fn)
        if m:
            out.add(m.group(1))
    return out


def get_trading_dates(
    daily_dir: str,
    intraday_dir: str,
    start_date: str,
    end_date: str,
    use_intersection: bool = True,
) -> List[str]:
    """Get sorted trading dates available in both daily and intraday folders."""
    daily_dates = _extract_daily_dates(daily_dir)
    intra_dates = _extract_intraday_dates(intraday_dir)

    if use_intersection:
        dates = daily_dates & intra_dates
    else:
        dates = daily_dates

    dates = [d for d in dates if start_date <= d <= end_date]
    return sorted(dates)


# =========================================================
# mode1 feature generation
# =========================================================
def run_mode1_feature_generation(
    input_dir: str,
    output_dir: str,
    start_date: str,
    end_date: str,
    normalize_features: bool = True,
    min_periods: int = 20,
    return_y: bool = False,
    save: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame]:

    ensure_dir(output_dir)
    daily_input_dir = os.path.join(input_dir, "data_daily")
    intra_input_dir = os.path.join(input_dir, "data_intraday")

    date_list = get_trading_dates(
        daily_input_dir,
        intra_input_dir,
        start_date,
        end_date,
        use_intersection=True,
    )

    rolling_state = make_empty_rolling_state(lookback=20)

    daily_Tm1 = None
    intra_Tm1 = None

    all_features = []
    all_y = []
    failed_dates = []

    for date_idx, date in enumerate(date_list):
        print(date_idx, date)
        try:
            # Load one trading day of raw data
            raw_daily = load_daily(start=date, end=date, input_dir=daily_input_dir)
            raw_intra = load_intraday(start=date, end=date, input_dir=intra_input_dir)

            daily_T = build_daily_adjusted(raw_daily)

            if daily_Tm1 is not None:
                # On first day, we have no T-1 data, so we skip this day
                intra_T = build_intraday_15m_adjusted(raw_intra, daily_T, daily_Tm1)

                if date_idx > 1:
                    # Even on the second day, we do not have all T-1 needed data. So, start on date_idx=2
                    features_T, y_T = build_features_for_date(
                        date_idx=date_idx,
                        daily_T=daily_T,
                        daily_Tm1=daily_Tm1,
                        intra_T=intra_T,
                        intra_Tm1=intra_Tm1,
                        rolling_state=rolling_state,
                        min_periods=min_periods,
                        return_y=return_y,
                    )

                    all_features.append(features_T)
                    if return_y and y_T is not None:
                        all_y.append(y_T)

                # Update the previous-day cache
                intra_Tm1 = intra_T

            # Move current day data into previous-day cache
            daily_Tm1 = daily_T

        except Exception as exc:
            failed_dates.append((date, str(exc)))
            print(f"[mode1] failed for {date}: {exc}")

    all_features_df = pd.concat(all_features, ignore_index=True) if all_features else pd.DataFrame()
    all_y_df = pd.concat(all_y, ignore_index=True) if return_y and all_y else None

    if all_features_df.empty:
        print("No features generated.")
        return all_features_df, all_y_df
    
    # ---------- winsorization ----------
    clip_map = {
        # participation / activity ratios
        "intraday_dollar_vpr": (0.0, 5.0),
        "intraday_dollar_rel_to_yday": (0.0, 3.0),
        "yday_tail_vpr": (0.0, 3.0),
        "vol_profile_L1_vs_avg": (0.0, 1.0),
        "volume_accel": (0.0, 10.0),

        # vol-scaled / return-like
        "intraday_resid_ret_vol": (-4.0, 4.0),
        "overnight_ret_vol": (-4.0, 4.0),
        "prev_cumret_resid_1600": (-4.0, 4.0),
        "common_factor_ret_vol": (-4.0, 4.0),

        # path / risk shape
        "range": (0.0, 0.5),
        "max_drawdown": (0.0, 0.5),
        "up_minus_down_risk_L": (-1.0, 1.0),
        "tga_directional_asymmetry_L": (-5.0, 5.0),
        "negative_illiquidity_L": (0.0, 0.5),

        # frighten family
        "frighten_mean_L": (-1000.0, 1000.0),
        "frighten_std_L": (0.0, 1000.0),

        # signed flow / asymmetry family
        "amount_dir_15m": (-1.0, 1.0),
        # "r1_umd_inv_mean": (-20.0, 20.0),
        # "r1_umdvol_inv_mean": (-20.0, 20.0),
        # "r1_umdvol_mean": (-2.0, 1.0),
        # "r1_umdvol_std": (-2.0, 3.0),

        # jump / variation family
        # "RTV_L": (0.0, 10.0),
        # "RVJ_L": (0.0, 15.0),

        # correlation / technicals
        # "pv_corr": (-1.0, 1.0),
        "intraday_macd_signal": (-0.05, 0.05),
        "intraday_macd_hist": (-0.03, 0.03),
        "intraday_rsi": (0.0, 100.0),

        # raw return
        "up_minus_down_risk_L_raw": (-1.0, 1.0),
        "tga_directional_asymmetry_L_raw": (-5.0, 5.0),
        "amount_dir_15m_raw": (-1.0, 1.0),
        # "r1_umd_inv_mean_raw": (-3.0, 3.0),
        # "r1_umdvol_inv_mean_raw": (-3.0, 3.0),
        # "r1_umdvol_mean_raw": (-1.5, 1.5),
        # "r1_umdvol_std_raw": (-1.5, 1.5),
        # "pv_corr_raw": (-1.0, 1.0),
    }

    for c, (lo, hi) in clip_map.items():
        if c in all_features_df.columns:
            all_features_df[c] = _winsorize_clip(all_features_df[c], lo, hi)
    
    all_features_df = mad_clip_by_date(
        all_features_df,
        feature_cols=[c for c in all_features_df.columns if c in clip_map],
        date_col=DATE_COL,
        n_mad=5.0,
    )
    
    all_features_df = build_interaction_features(all_features_df)

    # ---------- winsorization for interaction features ----------

    interaction_clip_map = {
        "x_trend_when_flow_high": (-4.0, 4.0),
        "x_prev_close_followthrough": (-4.0, 4.0),
        "x_high_flow_no_move": (0.0, 1.0),
        "x_tail_flow_continuation": (0.0, 1.0),
        "x_drawdown_conditioned_rsi": (-50.0, 50.0),
        "x_frighten_mean_over_std": (-5.0, 5.0),
        # "x_overnight_intraday_agreement": (-4.0, 4.0),
        # "x_panic_amplified_illiq": (0.0, 0.5),
        # "x_jump_vs_continuous_vol": (-3.0, 3.0),
        # "x_r1_umdvol_mean_over_std": (-5.0, 5.0),
        # "x_r1_umdvol_mean_over_std_raw": (-5.0, 5.0),
    }

    for c, (lo, hi) in interaction_clip_map.items():
        if c in all_features_df.columns:
            all_features_df[c] = _winsorize_clip(all_features_df[c], lo, hi)

    all_features_df = mad_clip_by_date(
        all_features_df,
        feature_cols=[c for c in all_features_df.columns if c.startswith("x_")],
        date_col=DATE_COL,
        n_mad=5.0,
    )

    # df = winsorize_1_99_by_date(
    #     df,
    #     cols=[c for c in df.columns if c.startswith("x_")],
    #     date_col=DATE_COL,
    # )

    non_feature_cols = {
        DATE_COL, ID_COL, Y_COL, Y_NORM_COL, EST_VOL_COL, MDV_COL, "year", "month",
    }

    day_of_week_feature_cols = {c for c in all_features_df.columns if c not in non_feature_cols and c.startswith("dow_")}
    # continuous_raw_feature_cols = [c for c in all_features_df.columns if c not in non_feature_cols and c not in day_of_week_feature_cols]
    
    continuous_feature_cols = [c for c in all_features_df.columns if c not in non_feature_cols and c not in day_of_week_feature_cols]
    # ts_zscore_cols = continuous_raw_feature_cols + [
    #     "x_overnight_intraday_agreement",
    #     "x_jump_vs_continuous_vol",
    #     "x_frighten_mean_over_std",
    #     "x_r1_umdvol_mean_over_std",
    #     "x_r1_umdvol_mean_over_std_raw",
    # ]
        
    # all_features_df = add_ts_zscore_all_features(
    #     all_features_df,
    #     feature_cols=ts_zscore_cols,
    #     date_col=DATE_COL,
    #     id_col=ID_COL,
    #     window=20,
    #     min_periods=20,
    #     suffix=None,
    # )
    
    if normalize_features:
        all_features_df[continuous_feature_cols] = (
            all_features_df.groupby(DATE_COL)[continuous_feature_cols]
            .transform(lambda x: (x - x.mean()) / x.std(ddof=0))
        )
    
    all_feature_cols = [
        "overnight_ret_vol",
        "up_minus_down_risk_L",
        "intraday_resid_ret_vol",
        "tga_directional_asymmetry_L",
        "intraday_dollar_rel_to_yday",
        "volume_accel",
        "common_factor_ret_vol",
        "prev_cumret_resid_1600",
        "negative_illiquidity_L",
        "range",
        "max_drawdown",
        # "intraday_dollar_vpr",
        # "vol_profile_L1_vs_avg",
        # "yday_tail_vpr",
        
        'intraday_macd_hist',
        'amount_dir_15m',
        'up_minus_down_risk_L_raw',
        'x_drawdown_conditioned_rsi',
        'x_high_flow_no_move',
        'x_frighten_mean_over_std',
        'x_trend_when_flow_high',
        "x_prev_close_followthrough",
        "x_tail_flow_continuation",
    ]

    all_features_df = all_features_df[[DATE_COL, ID_COL, MDV_COL, EST_VOL_COL] + all_feature_cols]

    if save:
        import pdb; pdb.set_trace()
        for date_str in date_list:
            date = pd.to_datetime(date_str)
            features_T = all_features_df[all_features_df[DATE_COL] == date]
            out_path = os.path.join(output_dir, f"{date_str}.csv")
            features_T.to_csv(out_path, index=False)
            print(f"[mode1] saved features for {date_str}: ({len(features_T)} rows)")

            if return_y and y_T is not None:
                y_T = all_y_df[all_y_df[DATE_COL] == date]
                out_path = os.path.join(output_dir, f"{date_str}_y.csv")
                y_T.to_csv(out_path, index=False)
                print(f"[mode1] saved y for {date_str}: ({len(y_T)} rows)") 
    
    
    if failed_dates:
        print(f"[mode1] failed dates: {failed_dates}")

    return all_features_df, all_y_df
   