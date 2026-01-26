import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from ofv.data import find_data_dir, load_tables
from ofv.ui import sidebar_nav, kpi_row

st.set_page_config(page_title="Finance Executive Overview", layout="wide")

filters = sidebar_nav(current="Overview", section_title="Finance Executive Overview")
st.title("Finance Executive Overview")

data_dir = find_data_dir()
if not data_dir:
    st.error("Cannot find folder findata in the repo root")
    st.stop()

tables = load_tables(data_dir)
if "dashboard_exec_overview" not in tables:
    st.error("Missing table dashboard_exec_overview")
    st.stop()

df_raw = tables["dashboard_exec_overview"].copy()
if "month" not in df_raw.columns:
    st.error("dashboard_exec_overview must include column month")
    st.stop()

df_raw["month"] = df_raw["month"].astype(str)
df_raw["month_dt"] = pd.to_datetime(df_raw["month"], format="%Y-%m", errors="coerce")
df_raw = df_raw[df_raw["month_dt"].notna()].sort_values("month_dt").reset_index(drop=True)
df_raw["quarter"] = df_raw["month_dt"].dt.to_period("Q").astype(str)
df_raw["year"] = df_raw["month_dt"].dt.year.astype(int)

months = sorted(df_raw["month"].dropna().unique().tolist())
if not months:
    st.error("No months found in dashboard_exec_overview")
    st.stop()

month_to_idx = {m: i for i, m in enumerate(months)}
df_raw["month_idx"] = df_raw["month"].map(month_to_idx)

quarters = sorted(df_raw["quarter"].dropna().unique().tolist())
years = sorted(df_raw["year"].dropna().unique().tolist())

METRICS = {
    "Revenue": {"base": "revenue", "kind": "flow", "fmt": "money", "unit": "USD"},
    "COGS": {"base": "cogs", "kind": "flow", "fmt": "money", "unit": "USD"},
    "Margin": {"base": "gross_margin", "kind": "flow", "fmt": "money", "unit": "USD"},
    "OpEx": {"base": "opex", "kind": "flow", "fmt": "money", "unit": "USD"},
    "CapEx": {"base": "capex", "kind": "flow", "fmt": "money", "unit": "USD"},
    "Cash": {"base": "cash", "kind": "stock", "fmt": "money", "unit": "USD"},
    "Inventory": {"base": "inventory", "kind": "stock", "fmt": "money", "unit": "USD"},
    "Units": {"base": "units", "kind": "flow", "fmt": "int", "unit": "Units"},
    "Bookings": {"base": "bookings", "kind": "flow", "fmt": "money", "unit": "USD"},
    "Backlog": {"base": "backlog", "kind": "stock", "fmt": "money", "unit": "USD"},
}

GROUPS = [
    ("Profit and loss", ["Revenue", "COGS", "Margin"]),
    ("Spend and investment", ["OpEx", "CapEx"]),
    ("Liquidity and working capital", ["Cash", "Inventory"]),
    ("Demand", ["Units", "Bookings", "Backlog"]),
]


def c_plan(b: str) -> str:
    return f"plan_{b}"


def c_perf(b: str) -> str:
    return f"actual_{b}"


def c_fcst(b: str) -> str:
    return f"forecast_{b}"


def na_series(n: int) -> pd.Series:
    return pd.Series([pd.NA] * n)


def ensure_numeric(df_in: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df_in.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


num_cols: list[str] = []
for meta in METRICS.values():
    b = meta["base"]
    for c in [c_plan(b), c_perf(b), c_fcst(b)]:
        if c in df_raw.columns:
            num_cols.append(c)
df_raw = ensure_numeric(df_raw, list(dict.fromkeys(num_cols)))


def fmt_money_no_parens(x) -> str:
    try:
        if x is None or pd.isna(x):
            return "NA"
        v = float(x)
        sign = "-" if v < 0 else ""
        v = abs(v)
        return f"{sign}${v:,.0f}"
    except Exception:
        return "NA"


def fmt_int(x) -> str:
    try:
        if x is None or pd.isna(x):
            return "NA"
        return f"{int(round(float(x))):,}"
    except Exception:
        return "NA"


def fmt_by_metric(metric: str, x) -> str:
    if METRICS[metric]["fmt"] == "int":
        return fmt_int(x)
    return fmt_money_no_parens(x)


def last_non_null(s: pd.Series):
    s2 = s.dropna()
    return s2.iloc[-1] if len(s2) else pd.NA


def series_plan(df_in: pd.DataFrame, metric: str) -> pd.Series:
    b = METRICS[metric]["base"]
    s = df_in.get(c_plan(b), na_series(len(df_in)))
    return pd.to_numeric(s, errors="coerce")


def series_perf(df_in: pd.DataFrame, metric: str, cutoff_idx: int) -> pd.Series:
    b = METRICS[metric]["base"]
    s = df_in.get(c_perf(b), na_series(len(df_in)))
    s = pd.to_numeric(s, errors="coerce")
    m = df_in["month_idx"] <= cutoff_idx
    return s.where(m)


def series_fcst(df_in: pd.DataFrame, metric: str) -> pd.Series:
    b = METRICS[metric]["base"]
    s = df_in.get(c_fcst(b), na_series(len(df_in)))
    return pd.to_numeric(s, errors="coerce")


def series_estimate(df_in: pd.DataFrame, metric: str, cutoff_idx: int) -> pd.Series:
    p = series_plan(df_in, metric)
    a = series_perf(df_in, metric, cutoff_idx)
    f = series_fcst(df_in, metric)
    est = a.copy()
    est = est.where(est.notna(), f)
    est = est.where(est.notna(), p)
    return est


def make_title(metric: str, view: str, focus_month: str | None, focus_q: str | None, focus_year: int | None) -> str:
    unit = METRICS[metric]["unit"]
    if view == "Month" and focus_month:
        return f"{metric} — {unit} | {focus_month} | Plan vs Performance vs Forecast"
    if view == "Quarter" and focus_q:
        return f"{metric} — {unit} | {focus_q} | Plan vs Performance vs Forecast"
    if view == "Year" and focus_year is not None:
        return f"{metric} — {unit} | {focus_year} | Plan vs Performance vs Forecast"
    return f"{metric} — {unit} | Plan vs Performance vs Forecast"


def make_line_fig(x, plan, performance, forecast, title: str, y_title: str):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=plan, mode="lines+markers", name="Plan"))
    fig.add_trace(go.Scatter(x=x, y=performance, mode="lines+markers", name="Performance"))
    fig.add_trace(go.Scatter(x=x, y=forecast, mode="lines+markers", name="Forecast"))
    fig.update_layout(
        title=title,
        height=340,
        legend_title_text="",
        margin=dict(l=10, r=10, t=60, b=10),
    )
    fig.update_xaxes(title_text="")
    fig.update_yaxes(title_text=y_title)
    return fig


def render_two_per_row(figs: list[go.Figure | None]):
    for i in range(0, len(figs), 2):
        c1, c2 = st.columns(2)
        if figs[i] is not None:
            c1.plotly_chart(figs[i], use_container_width=True)
        else:
            c1.empty()
        if i + 1 < len(figs) and figs[i + 1] is not None:
            c2.plotly_chart(figs[i + 1], use_container_width=True)
        else:
            c2.empty()


def period_row(metric: str, view: str, focus_month: str | None, focus_q: str | None, focus_year: int | None, cutoff_idx: int) -> dict:
    kind = METRICS[metric]["kind"]

    if view == "Month":
        if not focus_month:
            return {"plan": pd.NA, "performance": pd.NA, "forecast": pd.NA, "estimate": pd.NA, "vs_plan": pd.NA}
        d = df_raw[df_raw["month"] == focus_month].copy()
        if len(d) == 0:
            return {"plan": pd.NA, "performance": pd.NA, "forecast": pd.NA, "estimate": pd.NA, "vs_plan": pd.NA}
        plan_v = series_plan(d, metric).iloc[0]
        perf_v = series_perf(d, metric, cutoff_idx).iloc[0]
        fcst_v = series_fcst(d, metric).iloc[0]
        est_v = series_estimate(d, metric, cutoff_idx).iloc[0]
        vs_plan = (float(est_v) - float(plan_v)) if (pd.notna(est_v) and pd.notna(plan_v)) else pd.NA
        return {"plan": plan_v, "performance": perf_v, "forecast": fcst_v, "estimate": est_v, "vs_plan": vs_plan}

    if view == "Quarter":
        if not focus_q:
            return {"plan": pd.NA, "performance": pd.NA, "forecast": pd.NA, "estimate": pd.NA, "vs_plan": pd.NA}
        d = df_raw[df_raw["quarter"] == focus_q].copy().sort_values("month_dt").reset_index(drop=True)

        plan_s = series_plan(d, metric)
        perf_s = series_perf(d, metric, cutoff_idx)
        fcst_s = series_fcst(d, metric)
        est_s = series_estimate(d, metric, cutoff_idx)

        if kind == "flow":
            plan_v = plan_s.sum(min_count=1)
            perf_v = perf_s.sum(min_count=1)
            fcst_v = fcst_s.sum(min_count=1)
            est_v = est_s.sum(min_count=1)
        else:
            plan_v = last_non_null(plan_s)
            perf_v = last_non_null(perf_s)
            fcst_v = last_non_null(fcst_s)
            est_v = last_non_null(est_s)

        vs_plan = (float(est_v) - float(plan_v)) if (pd.notna(est_v) and pd.notna(plan_v)) else pd.NA
        return {"plan": plan_v, "performance": perf_v, "forecast": fcst_v, "estimate": est_v, "vs_plan": vs_plan}

    if view == "Year":
        if focus_year is None:
            return {"plan": pd.NA, "performance": pd.NA, "forecast": pd.NA, "estimate": pd.NA, "vs_plan": pd.NA}
        d = df_raw[df_raw["year"] == int(focus_year)].copy().sort_values("month_dt").reset_index(drop=True)

        plan_s = series_plan(d, metric)
        perf_s = series_perf(d, metric, cutoff_idx)
        fcst_s = series_fcst(d, metric)
        est_s = series_estimate(d, metric, cutoff_idx)

        if kind == "flow":
            plan_v = plan_s.sum(min_count=1)
            perf_v = perf_s.sum(min_count=1)
            fcst_v = fcst_s.sum(min_count=1)
            est_v = est_s.sum(min_count=1)
        else:
            plan_v = last_non_null(plan_s)
            perf_v = last_non_null(perf_s)
            fcst_v = last_non_null(fcst_s)
            est_v = last_non_null(est_s)

        vs_plan = (float(est_v) - float(plan_v)) if (pd.notna(est_v) and pd.notna(plan_v)) else pd.NA
        return {"plan": plan_v, "performance": perf_v, "forecast": fcst_v, "estimate": est_v, "vs_plan": vs_plan}

    return {"plan": pd.NA, "performance": pd.NA, "forecast": pd.NA, "estimate": pd.NA, "vs_plan": pd.NA}


def group_table_rows(view: str, focus_month: str | None, focus_q: str | None, focus_year: int | None, cutoff_idx: int, metrics: list[str]) -> pd.DataFrame:
    rows_num: list[dict] = []
    for m in metrics:
        r = period_row(m, view, focus_month, focus_q, focus_year, cutoff_idx)
        rows_num.append(
            {
                "Metric": m,
                "Plan": r["plan"],
                "Performance": r["performance"],
                "Forecast": r["forecast"],
                "Vs plan": r["vs_plan"],
            }
        )

    t_num = pd.DataFrame(rows_num)

    t_disp = pd.DataFrame()
    t_disp["Metric"] = t_num["Metric"]
    for col in ["Plan", "Performance", "Forecast", "Vs plan"]:
        t_disp[col] = pd.Series(
            [fmt_by_metric(m, v) for m, v in zip(t_num["Metric"], t_num[col])],
            dtype="object",
        )
    return t_disp


def quarter_of_month_str(m: str) -> str | None:
    try:
        dt = pd.to_datetime(m, format="%Y-%m", errors="coerce")
        if pd.isna(dt):
            return None
        return dt.to_period("Q").strftime("%YQ%q")
    except Exception:
        return None


def year_of_month_str(m: str) -> int | None:
    try:
        dt = pd.to_datetime(m, format="%Y-%m", errors="coerce")
        if pd.isna(dt):
            return None
        return int(dt.year)
    except Exception:
        return None


actual_rev_months = (
    df_raw.loc[df_raw.get("actual_revenue").notna(), "month"].tolist()
    if "actual_revenue" in df_raw.columns
    else []
)
default_perf_through = actual_rev_months[-1] if actual_rev_months else months[min(5, len(months) - 1)]
default_focus_month = default_perf_through if default_perf_through in months else months[-1]
default_focus_q = quarter_of_month_str(default_focus_month)
default_focus_year = year_of_month_str(default_focus_month) if years else None
if default_focus_year is None and years:
    default_focus_year = years[-1]

section = st.radio(
    "Section",
    ["KPIs", "Trends"],
    horizontal=True,
    label_visibility="collapsed",
    key="exec_overview_section",
)

with filters:
    view_mode = st.selectbox("View", ["Month", "Quarter", "Year"], index=0)

    focus_month = None
    focus_q = None
    focus_year = None

    if section == "KPIs":
        if view_mode == "Month":
            focus_month = st.selectbox("Focus month", months, index=months.index(default_focus_month))
        elif view_mode == "Quarter":
            if not quarters:
                st.error("No quarters found in data")
                st.stop()
            focus_q = st.selectbox("Focus quarter", quarters, index=quarters.index(default_focus_q) if default_focus_q in quarters else len(quarters) - 1)
        else:
            if not years:
                st.error("No years found in data")
                st.stop()
            focus_year = st.selectbox("Focus year", years, index=years.index(default_focus_year) if default_focus_year in years else len(years) - 1)

        perf_through = default_perf_through
    else:
        perf_through = st.selectbox(
            "Performance available through",
            months,
            index=months.index(default_perf_through),
            help="Use performance values through this month. Later months will use forecast for the headline value.",
        )

cutoff_idx = month_to_idx.get(perf_through, month_to_idx[months[-1]])

if section == "KPIs":
    if view_mode == "Quarter":
        if focus_q:
            d_q = df_raw[df_raw["quarter"] == focus_q].copy().sort_values("month_dt").reset_index(drop=True)
            if len(d_q):
                focus_month = d_q["month"].dropna().iloc[-1]
    if view_mode == "Year":
        if focus_year is not None:
            d_y = df_raw[df_raw["year"] == int(focus_year)].copy().sort_values("month_dt").reset_index(drop=True)
            if len(d_y):
                focus_month = d_y["month"].dropna().iloc[-1]
else:
    focus_month = perf_through
    focus_q = quarter_of_month_str(perf_through)
    focus_year = year_of_month_str(perf_through)

if section == "KPIs":
    for gname, metrics in GROUPS:
        st.markdown(f"### {gname}")

        items = []
        for m in metrics:
            r = period_row(m, view_mode, focus_month, focus_q, focus_year, cutoff_idx)
            items.append(
                {
                    "label": m,
                    "value": fmt_by_metric(m, r["estimate"]),
                    "delta": fmt_by_metric(m, r["vs_plan"]) if pd.notna(r["vs_plan"]) else None,
                }
            )

        kpi_row(items)

        t_show = group_table_rows(view_mode, focus_month, focus_q, focus_year, cutoff_idx, metrics)
        st.dataframe(t_show, use_container_width=True, hide_index=True)
        st.write("")

else:
    for gname, metrics in GROUPS:
        st.markdown(f"### {gname}")

        figs: list[go.Figure | None] = []
        for m in metrics:
            kind = METRICS[m]["kind"]
            y_title = METRICS[m]["unit"]

            if view_mode == "Month":
                d = df_raw.sort_values("month_dt").reset_index(drop=True)
                x = d["month"]
                plan = series_plan(d, m)
                perf = series_perf(d, m, cutoff_idx)
                fcst = series_fcst(d, m)
                title = make_title(m, "Month", None, None, None)
                figs.append(make_line_fig(x, plan, perf, fcst, title, y_title))

            elif view_mode == "Quarter":
                if not quarters:
                    figs.append(None)
                else:
                    rows = []
                    for qtr in quarters:
                        d = df_raw[df_raw["quarter"] == qtr].copy().sort_values("month_dt").reset_index(drop=True)
                        plan_s = series_plan(d, m)
                        perf_s = series_perf(d, m, cutoff_idx)
                        fcst_s = series_fcst(d, m)

                        if kind == "flow":
                            plan_v = plan_s.sum(min_count=1)
                            perf_v = perf_s.sum(min_count=1)
                            fcst_v = fcst_s.sum(min_count=1)
                        else:
                            plan_v = last_non_null(plan_s)
                            perf_v = last_non_null(perf_s)
                            fcst_v = last_non_null(fcst_s)

                        rows.append({"quarter": qtr, "Plan": plan_v, "Performance": perf_v, "Forecast": fcst_v})

                    qdf = pd.DataFrame(rows)
                    title = make_title(m, "Quarter", None, None, None)
                    figs.append(
                        make_line_fig(
                            qdf["quarter"],
                            pd.to_numeric(qdf["Plan"], errors="coerce"),
                            pd.to_numeric(qdf["Performance"], errors="coerce"),
                            pd.to_numeric(qdf["Forecast"], errors="coerce"),
                            title,
                            y_title,
                        )
                    )

            else:
                if not years:
                    figs.append(None)
                else:
                    rows = []
                    for y in years:
                        d = df_raw[df_raw["year"] == int(y)].copy().sort_values("month_dt").reset_index(drop=True)
                        plan_s = series_plan(d, m)
                        perf_s = series_perf(d, m, cutoff_idx)
                        fcst_s = series_fcst(d, m)

                        if kind == "flow":
                            plan_v = plan_s.sum(min_count=1)
                            perf_v = perf_s.sum(min_count=1)
                            fcst_v = fcst_s.sum(min_count=1)
                        else:
                            plan_v = last_non_null(plan_s)
                            perf_v = last_non_null(perf_s)
                            fcst_v = last_non_null(fcst_s)

                        rows.append({"year": str(y), "Plan": plan_v, "Performance": perf_v, "Forecast": fcst_v})

                    ydf = pd.DataFrame(rows)
                    title = make_title(m, "Year", None, None, None)
                    figs.append(
                        make_line_fig(
                            ydf["year"],
                            pd.to_numeric(ydf["Plan"], errors="coerce"),
                            pd.to_numeric(ydf["Performance"], errors="coerce"),
                            pd.to_numeric(ydf["Forecast"], errors="coerce"),
                            title,
                            y_title,
                        )
                    )

        render_two_per_row(figs)

        t_show = group_table_rows(view_mode, focus_month, focus_q, focus_year, cutoff_idx, metrics)
        st.dataframe(t_show, use_container_width=True, hide_index=True)
        st.write("")