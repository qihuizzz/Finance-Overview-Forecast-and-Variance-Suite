import streamlit as st
import pandas as pd

from ofv.data import find_data_dir, load_tables
from ofv.ui import sidebar_nav, variance_bridge, fmt_money, heatmap

st.set_page_config(page_title="Cost Variance Drivers", layout="wide")

filters = sidebar_nav(current="Variance", section_title="Cost Variance Drivers")
st.title("Cost Variance Drivers")

data_dir = find_data_dir()
if not data_dir:
    st.error("Cannot find folder findata in the repo root")
    st.stop()

tables = load_tables(data_dir)
if "dashboard_cost_var_bridge" not in tables or "dashboard_cost_var_detail" not in tables:
    st.error("Missing required tables dashboard_cost_var_bridge or dashboard_cost_var_detail")
    st.stop()

bridge = tables["dashboard_cost_var_bridge"].copy()
detail = tables["dashboard_cost_var_detail"].copy()


def _as_str(s: pd.Series) -> pd.Series:
    return s.astype(str)


def _to_month_dt(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype(str), format="%Y-%m", errors="coerce")


def _dedupe_keep_order(items: list) -> list:
    seen = set()
    out = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _disp(x) -> str:
    try:
        return str(x).replace("_", " ").strip()
    except Exception:
        return str(x)


def _ensure_cols(df: pd.DataFrame, cols: list[str], fill_value=0.0) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c not in out.columns:
            out[c] = fill_value
    return out


def _periodize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "month" in out.columns:
        out["month"] = _as_str(out["month"])
        out["month_dt"] = _to_month_dt(out["month"])
        out = out[out["month_dt"].notna()].copy()
        out["quarter"] = out["month_dt"].dt.to_period("Q").astype(str)
        out["year"] = out["month_dt"].dt.year.astype(int).astype(str)
    return out


bridge = _periodize(bridge)
detail = _periodize(detail)

if bridge.empty or "month" not in bridge.columns:
    st.info("No data available to render this dashboard yet")
    st.stop()

products = sorted(bridge["product_name"].dropna().unique().tolist()) if "product_name" in bridge.columns else []
if not products:
    st.info("No data available to render this dashboard yet")
    st.stop()


with filters:
    # 1) Product on top + All
    product_sel = st.selectbox("Product", ["All"] + products, index=0)

    # product-filtered bridge for driver list + period options
    bf = bridge.copy()
    if product_sel != "All" and "product_name" in bf.columns:
        bf = bf[bf["product_name"] == product_sel].copy()

    # 2) Driver under product (moved here)
    drivers_all = sorted(bf["driver"].dropna().unique().tolist()) if "driver" in bf.columns else []
    driver_sel = st.selectbox("Driver", ["All"] + drivers_all, index=0) if drivers_all else "All"

    # 3) View under driver
    view_level = st.selectbox("View", ["Month", "Quarter", "Year"], index=0)

    # period choices
    months = sorted(bf["month"].dropna().unique().tolist()) if "month" in bf.columns else []
    quarters = sorted(bf["quarter"].dropna().unique().tolist()) if "quarter" in bf.columns else []
    years = sorted(bf["year"].dropna().unique().tolist()) if "year" in bf.columns else []

    if view_level == "Month":
        if not months:
            st.error("No months found for current product")
            st.stop()
        period_col = "month"
        period_sel = st.selectbox("Month", months, index=max(0, len(months) - 1))
    elif view_level == "Quarter":
        if not quarters:
            st.error("No quarters found for current product")
            st.stop()
        period_col = "quarter"
        period_sel = st.selectbox("Quarter", quarters, index=max(0, len(quarters) - 1))
    else:
        if not years:
            st.error("No years found for current product")
            st.stop()
        period_col = "year"
        period_sel = st.selectbox("Year", years, index=max(0, len(years) - 1))


# ---- build b0/d0 first (FIX ordering bug) ----
b0 = bridge[bridge[period_col] == period_sel].copy()
d0 = detail[detail[period_col] == period_sel].copy()

# filter product
if product_sel != "All" and "product_name" in b0.columns:
    b0 = b0[b0["product_name"] == product_sel].copy()
if product_sel != "All" and "product_name" in d0.columns:
    d0 = d0[d0["product_name"] == product_sel].copy()

# filter driver
if driver_sel != "All" and "driver" in b0.columns:
    b0 = b0[b0["driver"] == driver_sel].copy()
if driver_sel != "All" and "driver" in d0.columns:
    d0 = d0[d0["driver"] == driver_sel].copy()

if b0.empty:
    st.info("No bridge rows for current filters")
    st.stop()

# numeric safety
b0 = _ensure_cols(b0, ["variance_amount"], fill_value=0.0)
b0["variance_amount"] = pd.to_numeric(b0["variance_amount"], errors="coerce").fillna(0.0)

d0 = _ensure_cols(d0, ["variance_amount", "price_variance", "volume_variance"], fill_value=0.0)
for c in ["variance_amount", "price_variance", "volume_variance"]:
    d0[c] = pd.to_numeric(d0[c], errors="coerce").fillna(0.0)

# Mix = total - price - volume
d0["mix_variance"] = d0["variance_amount"] - d0["price_variance"] - d0["volume_variance"]

# aggregate bridge to driver
b_driver = (
    b0.groupby("driver", as_index=False)
    .agg(variance_amount=("variance_amount", "sum"))
    .copy()
)

# driver order by abs impact
b_driver = b_driver.sort_values("variance_amount", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)
driver_order_raw = _dedupe_keep_order(b_driver["driver"].astype(str).tolist())
driver_order_disp = [_disp(x) for x in driver_order_raw]

# bridge plot df
plot_df = b_driver.copy()
plot_df["label"] = plot_df["driver"].astype(str).map(_disp)
plot_df["label"] = pd.Categorical(plot_df["label"], categories=_dedupe_keep_order(driver_order_disp), ordered=True)
plot_df = plot_df.sort_values("label").reset_index(drop=True)

plot_df2 = plot_df.rename(columns={"variance_amount": "value"})[["label", "value"]].copy()

# decomposition aggregated to driver
decomp = (
    d0.groupby("driver", as_index=False)
    .agg(
        price=("price_variance", "sum"),
        volume=("volume_variance", "sum"),
        mix=("mix_variance", "sum"),
    )
    .copy()
)
decomp["driver_disp"] = decomp["driver"].astype(str).map(_disp)
decomp["driver_disp"] = pd.Categorical(decomp["driver_disp"], categories=_dedupe_keep_order(driver_order_disp), ordered=True)
decomp = decomp.sort_values("driver_disp").reset_index(drop=True)

# table on right ordered by driver then abs variance
if "account_name" not in d0.columns:
    d0["account_name"] = "NA"

tbl = (
    d0.groupby(["driver", "account_name"], as_index=False)
    .agg(
        variance=("variance_amount", "sum"),
        price=("price_variance", "sum"),
        volume=("volume_variance", "sum"),
        mix=("mix_variance", "sum"),
    )
    .copy()
)

tbl["driver_disp"] = tbl["driver"].astype(str).map(_disp)
tbl["driver_disp"] = pd.Categorical(tbl["driver_disp"], categories=_dedupe_keep_order(driver_order_disp), ordered=True)

# FIX: do not use key on categorical
tbl["abs_variance"] = tbl["variance"].abs()
tbl = tbl.sort_values(["driver_disp", "abs_variance"], ascending=[True, False]).reset_index(drop=True)
tbl = tbl.drop(columns=["abs_variance"])

tbl_show = tbl.rename(columns={"driver_disp": "Driver", "account_name": "Account"}).copy()
for c in ["variance", "price", "volume", "mix"]:
    tbl_show[c] = tbl_show[c].map(fmt_money)
tbl_show = tbl_show.rename(columns={"variance": "Variance", "price": "Price", "volume": "Volume", "mix": "Mix"})
tbl_show = tbl_show[["Driver", "Account", "Variance", "Price", "Volume", "Mix"]]

st.markdown("## Bridge and decomposition")

# row 1: bridge left half only
row1_l, row1_r = st.columns(2)
with row1_l:
    st.subheader("Variance bridge")
    title_txt = f"Variance bridge | {product_sel} | {period_sel}"
    variance_bridge(plot_df2, "label", "value", title_txt)
with row1_r:
    st.empty()

# row 2: decomposition left, table right
row2_l, row2_r = st.columns(2)
with row2_l:
    st.subheader("Price vs volume decomposition")
    if decomp.empty:
        st.info("No detail rows for current filters")
    else:
        import plotly.graph_objects as go

        x = decomp["driver_disp"].astype(str).tolist()
        fig = go.Figure()
        fig.add_trace(go.Bar(x=x, y=decomp["price"].tolist(), name="Price"))
        fig.add_trace(go.Bar(x=x, y=decomp["volume"].tolist(), name="Volume"))
        fig.add_trace(go.Bar(x=x, y=decomp["mix"].tolist(), name="Mix"))

        fig.update_layout(
            barmode="stack",
            height=420,
            legend_title_text="",
            margin=dict(l=10, r=10, t=60, b=10),
            title="Price volume mix decomposition",
        )
        fig.update_xaxes(title_text="")
        fig.update_yaxes(title_text="Amount")
        st.plotly_chart(fig, use_container_width=True)

with row2_r:
    st.subheader("Detail")
    if tbl_show.empty:
        st.info("No detail rows for current filters")
    else:
        st.dataframe(tbl_show, use_container_width=True, hide_index=True)

st.markdown("## Variance heatmap")

h_l, h_r = st.columns(2)
with h_l:
    try:
        if {"product_name", "driver", "month", "variance_amount"}.issubset(bridge.columns):
            base_heat = bridge.copy()
            if product_sel != "All" and "product_name" in base_heat.columns:
                base_heat = base_heat[base_heat["product_name"] == product_sel].copy()
            if driver_sel != "All" and "driver" in base_heat.columns:
                base_heat = base_heat[base_heat["driver"] == driver_sel].copy()

            base_heat = _ensure_cols(base_heat, ["variance_amount"], fill_value=0.0)
            base_heat["variance_amount"] = pd.to_numeric(base_heat["variance_amount"], errors="coerce").fillna(0.0)

            heat = base_heat.pivot_table(
                index="driver",
                columns="month",
                values="variance_amount",
                aggfunc="sum",
                fill_value=0.0,
            )

            # align driver order
            heat_idx = [str(i) for i in heat.index.tolist()]
            ordered = _dedupe_keep_order(driver_order_raw + [x for x in heat_idx if x not in driver_order_raw])
            heat = heat.reindex(ordered)
            heat.index = [_disp(x) for x in heat.index.tolist()]

            heatmap(heat, f"Variance by driver and month | {product_sel}")
        else:
            st.info("Heatmap not available because required columns are missing")
    except Exception:
        st.info("Heatmap not available for current data")

with h_r:
    st.empty()