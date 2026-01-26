import pandas as pd
import streamlit as st

from ofv.data import find_data_dir, load_tables
from ofv.ui import sidebar_nav, fmt_money, fmt_pct

st.set_page_config(
    page_title="Finance Overview, Forecasting and Variance Analysis",
    layout="wide",
)

sidebar_nav(current="Home")

data_dir = find_data_dir()
if not data_dir:
    st.error("Cannot find folder findata in the repo root")
    st.stop()

tables = load_tables(data_dir)

st.markdown(
    """
    <div style="padding: 18px 22px; border-radius: 14px; background: #F6F7FB;">
      <div style="font-size: 44px; font-weight: 800; line-height: 1.1;">
        Finance Overview, Forecasting and Variance Analysis
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Button card styling
st.markdown(
    """
<style>
/* Only affects buttons on this page */
div.stButton > button{
  width: 100%;
  padding: 18px 16px;
  border-radius: 14px;
  border: 1px solid #E5E7EB;
  background: #FFFFFF;
  font-weight: 700;
  font-size: 16px;
  color: #111827;
  height: 64px;
}
div.stButton > button:hover{
  border-color: #D1D5DB;
  background: #F9FAFB;
}
div.stButton > button:focus{
  box-shadow: none;
}
</style>
""",
    unsafe_allow_html=True,
)

st.write("")
c1, c2, c3 = st.columns(3)

def go_page(path: str):
    # Use switch_page if available, fallback to page_link style if not
    if hasattr(st, "switch_page"):
        st.switch_page(path)
    else:
        st.info(f"Navigation not supported in this Streamlit version. Open {path}")

with c1:
    if st.button("Finance Executive Overview", use_container_width=True, key="nav_exec_overview"):
        go_page("pages/01_Finance_Executive_Overview.py")

with c2:
    if st.button("Product Forecast Scenarios", use_container_width=True, key="nav_product_scenarios"):
        go_page("pages/02_Product_Forecast_Scenarios.py")

with c3:
    if st.button("Cost Variance Drivers", use_container_width=True, key="nav_cost_variance"):
        go_page("pages/03_Cost_Variance_Drivers.py")

st.write("")
st.subheader("Snapshot")

df = tables.get("dashboard_exec_overview", pd.DataFrame()).copy()
if df.empty or "month" not in df.columns:
    st.info("No dashboard_exec_overview data found")
else:
    df["month"] = df["month"].astype(str)
    df = df.sort_values("month").reset_index(drop=True)

    latest_row = None
    if "actual_revenue" in df.columns:
        non_null = df[df["actual_revenue"].notna()]
        if len(non_null) > 0:
            latest_row = non_null.iloc[-1]
    if latest_row is None:
        latest_row = df.iloc[-1]

    def fmt_int(x) -> str:
        try:
            if x is None or pd.isna(x):
                return "NA"
            return f"{int(round(float(x))):,}"
        except Exception:
            return "NA"

    # Revenue
    act_rev = latest_row.get("actual_revenue")
    rev_delta = latest_row.get("revenue_variance_to_plan")

    # Gross margin
    act_gm = latest_row.get("actual_gross_margin")
    gm_delta = latest_row.get("gross_margin_variance_to_plan")

    # Units
    act_units = latest_row.get("actual_units")
    units_delta = latest_row.get("units_variance_to_plan")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Latest month", str(latest_row.get("month")))
    k2.metric("Revenue", fmt_money(act_rev), fmt_money(rev_delta))
    k3.metric("Gross margin", fmt_money(act_gm), fmt_money(gm_delta))
    k4.metric("Units", fmt_int(act_units), fmt_int(units_delta))

with st.expander("Data check", expanded=False):
    st.write("Data folder")
    st.code(str(data_dir))
    st.write("Loaded tables")
    for name in sorted(tables.keys()):
        st.write(name)