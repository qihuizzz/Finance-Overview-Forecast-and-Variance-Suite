import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ofv.data import find_data_dir, load_tables
from ofv.ui import sidebar_nav, fmt_money, fmt_pct


def _get_table(tables: dict, candidates: list[str]) -> pd.DataFrame | None:
    for name in candidates:
        if name in tables:
            return tables[name].copy()
    return None


def _to_month_dt(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype(str), format="%Y-%m", errors="coerce")


def _two_per_row(figs: list[go.Figure | None]) -> None:
    for i in range(0, len(figs), 2):
        cols = st.columns(2)
        left = figs[i] if i < len(figs) else None
        right = figs[i + 1] if i + 1 < len(figs) else None

        if left is not None:
            cols[0].plotly_chart(left, use_container_width=True)
        else:
            cols[0].empty()

        if right is not None:
            cols[1].plotly_chart(right, use_container_width=True)
        else:
            cols[1].empty()


def _line_one(df: pd.DataFrame, x: str, y: str, title: str, y_title: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df[x], y=df[y], mode="lines+markers", name=title))
    fig.update_layout(
        title=title,
        height=360,
        legend_title_text="",
        margin=dict(l=10, r=10, t=60, b=10),
    )
    fig.update_xaxes(title_text="")
    fig.update_yaxes(title_text=y_title)
    return fig


def _line_multi_scenarios(df: pd.DataFrame, x: str, y: str, scenario_col: str, title: str, y_title: str) -> go.Figure:
    fig = go.Figure()
    for s in sorted(df[scenario_col].dropna().unique().tolist()):
        v = df[df[scenario_col] == s].sort_values(x)
        fig.add_trace(go.Scatter(x=v[x], y=v[y], mode="lines+markers", name=str(s)))
    fig.update_layout(
        title=title,
        height=360,
        legend_title_text="",
        margin=dict(l=10, r=10, t=60, b=10),
    )
    fig.update_xaxes(title_text="")
    fig.update_yaxes(title_text=y_title)
    return fig


def _band_chart(periods: list[str], p10: list[float], p50: list[float], p90: list[float], title: str, y_title: str) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(go.Scatter(x=periods, y=p50, mode="lines+markers", name="P50"))
    fig.add_trace(
        go.Scatter(
            x=periods,
            y=p90,
            mode="lines",
            name="P90",
            line=dict(width=0),
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=periods,
            y=p10,
            mode="lines",
            name="P10",
            fill="tonexty",
            line=dict(width=0),
            showlegend=False,
        )
    )

    fig.update_layout(
        title=title,
        height=360,
        legend_title_text="",
        margin=dict(l=10, r=10, t=60, b=10),
    )
    fig.update_xaxes(title_text="")
    fig.update_yaxes(title_text=y_title)
    return fig


def _sample_distributions(dist_df: pd.DataFrame, n: int, seed: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)

    req = {"variable", "distribution", "min", "mode", "max"}
    if not req.issubset(set(dist_df.columns)):
        return {}

    d = dist_df.copy()
    d["distribution"] = d["distribution"].astype(str).str.lower().str.strip()

    for c in ["min", "mode", "max"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")

    out: dict[str, np.ndarray] = {}

    for _, r in d.iterrows():
        var = str(r["variable"]).strip()
        dist = str(r["distribution"]).strip()
        vmin = float(r["min"]) if pd.notna(r["min"]) else np.nan
        vmode = float(r["mode"]) if pd.notna(r["mode"]) else np.nan
        vmax = float(r["max"]) if pd.notna(r["max"]) else np.nan

        if var == "" or dist == "" or np.isnan(vmin) or np.isnan(vmode) or np.isnan(vmax):
            continue

        if dist == "triangular":
            out[var] = rng.triangular(vmin, vmode, vmax, size=n)
            continue

        if dist == "discrete":
            vals = sorted(list({vmin, vmode, vmax}))
            if len(vals) == 1:
                out[var] = np.full(n, vals[0])
            elif len(vals) == 2:
                a, b = vals[0], vals[1]
                if vmode == a:
                    p = 0.7
                    out[var] = rng.choice([a, b], size=n, p=[p, 1 - p])
                elif vmode == b:
                    p = 0.7
                    out[var] = rng.choice([a, b], size=n, p=[1 - p, p])
                else:
                    out[var] = rng.choice([a, b], size=n)
            else:
                a, b, c = vals[0], vals[1], vals[2]
                if vmode == b:
                    out[var] = rng.choice([a, b, c], size=n, p=[0.2, 0.6, 0.2])
                elif vmode == a:
                    out[var] = rng.choice([a, b, c], size=n, p=[0.6, 0.2, 0.2])
                elif vmode == c:
                    out[var] = rng.choice([a, b, c], size=n, p=[0.2, 0.2, 0.6])
                else:
                    out[var] = rng.choice([a, b, c], size=n)
            continue

    return out


def _run_monte_carlo(base_df: pd.DataFrame, dist_df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    base = base_df.copy()
    base["month"] = base["month"].astype(str)
    base["month_dt"] = _to_month_dt(base["month"])
    base = base.sort_values("month_dt").reset_index(drop=True)

    for c in ["units", "revenue", "cogs", "gross_margin"]:
        if c not in base.columns:
            base[c] = 0.0
        base[c] = pd.to_numeric(base[c], errors="coerce").fillna(0.0)

    base["asp"] = np.where(base["units"] > 0, base["revenue"] / base["units"], 0.0)
    base["unit_cost"] = np.where(base["units"] > 0, base["cogs"] / base["units"], 0.0)

    draws = _sample_distributions(dist_df, n=n, seed=seed)
    if not draws:
        return pd.DataFrame()

    units_mul = draws.get("units_multiplier", np.ones(n))
    asp_mul = draws.get("asp_multiplier", np.ones(n))
    cost_mul = draws.get("unit_cost_multiplier", np.ones(n))
    delay = draws.get("launch_delay_months", np.zeros(n))

    delay = np.round(delay).astype(int)
    delay = np.clip(delay, 0, 24)

    months = base["month"].tolist()
    t = len(months)

    revenue_runs = np.zeros((n, t), dtype=float)
    cogs_runs = np.zeros((n, t), dtype=float)
    gm_runs = np.zeros((n, t), dtype=float)
    units_runs = np.zeros((n, t), dtype=float)

    base_units = base["units"].to_numpy()
    base_asp = base["asp"].to_numpy()
    base_cost = base["unit_cost"].to_numpy()

    for i in range(n):
        u = base_units * float(units_mul[i])
        a = base_asp * float(asp_mul[i])
        c = base_cost * float(cost_mul[i])

        rev = u * a
        cg = u * c
        gm = rev - cg

        d = int(delay[i])
        if d > 0:
            rev = np.concatenate([np.zeros(d), rev])[:t]
            cg = np.concatenate([np.zeros(d), cg])[:t]
            gm = np.concatenate([np.zeros(d), gm])[:t]
            u = np.concatenate([np.zeros(d), u])[:t]

        revenue_runs[i, :] = rev
        cogs_runs[i, :] = cg
        gm_runs[i, :] = gm
        units_runs[i, :] = u

    def stats(arr: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        p10 = np.nanpercentile(arr, 10, axis=0)
        p50 = np.nanpercentile(arr, 50, axis=0)
        p90 = np.nanpercentile(arr, 90, axis=0)
        mean = np.nanmean(arr, axis=0)
        return p10, p50, p90, mean

    rev_p10, rev_p50, rev_p90, rev_mean = stats(revenue_runs)
    cogs_p10, cogs_p50, cogs_p90, cogs_mean = stats(cogs_runs)
    gm_p10, gm_p50, gm_p90, gm_mean = stats(gm_runs)
    u_p10, u_p50, u_p90, u_mean = stats(units_runs)

    out = pd.DataFrame(
        {
            "month": months,
            "revenue_p10": rev_p10,
            "revenue_p50": rev_p50,
            "revenue_p90": rev_p90,
            "revenue_mean": rev_mean,
            "cogs_p10": cogs_p10,
            "cogs_p50": cogs_p50,
            "cogs_p90": cogs_p90,
            "cogs_mean": cogs_mean,
            "gross_margin_p10": gm_p10,
            "gross_margin_p50": gm_p50,
            "gross_margin_p90": gm_p90,
            "gross_margin_mean": gm_mean,
            "units_p10": u_p10,
            "units_p50": u_p50,
            "units_p90": u_p90,
            "units_mean": u_mean,
        }
    )
    return out


st.set_page_config(page_title="Product Forecast Scenarios", layout="wide")

filters = sidebar_nav(current="Forecast", section_title="Product Forecast Scenarios")

data_dir = find_data_dir()
if not data_dir:
    st.error("Cannot find folder findata in the repo root")
    st.stop()

tables = load_tables(data_dir)

df = _get_table(tables, ["dashboard_new_product_scen", "dashboard_new_product_scenarios"])
if df is None:
    st.error("Missing table dashboard_new_product_scen")
    st.stop()

df["month"] = df["month"].astype(str)
df["month_dt"] = _to_month_dt(df["month"])
df = df.sort_values(["scenario", "month_dt"]).reset_index(drop=True)

scenarios = sorted(df["scenario"].dropna().unique().tolist())
if not scenarios:
    st.error("No scenarios found in dashboard_new_product_scen")
    st.stop()

dist_df = _get_table(tables, ["mc_input_distributions", "mc_input_distribution", "monte_carlo_input_distributions"])

with filters:
    mode = st.selectbox("Mode", ["Single Scenario", "Compare Scenarios", "Monte Carlo"], index=0)

mode_tag = {
    "Single Scenario": "-Single Scenario",
    "Compare Scenarios": "-Compare Scenarios",
    "Monte Carlo": "-Monte Carlo",
}.get(mode, "")

st.title(f"Product Forecast Scenarios {mode_tag}")

if mode == "Single Scenario":
    with filters:
        scenario = st.selectbox("Scenario", scenarios, index=0)

    view = df[df["scenario"] == scenario].sort_values("month_dt").copy()

    for c in ["units", "revenue", "cogs", "gross_margin", "probability_of_mp"]:
        if c not in view.columns:
            view[c] = 0.0
        view[c] = pd.to_numeric(view[c], errors="coerce")

    view["expected_revenue"] = view["revenue"] * view["probability_of_mp"]
    view["expected_gross_margin"] = view["gross_margin"] * view["probability_of_mp"]

    view["quarter"] = view["month_dt"].dt.to_period("Q").astype(str)
    view["year"] = view["month_dt"].dt.year.astype(str)

    with filters:
        view_level = st.selectbox("View", ["Month", "Quarter", "Year"], index=0)

    if view_level == "Month":
        periods = sorted(view["month"].dropna().unique().tolist())
        period_col = "month"
        y_title_amount = "Amount"
        y_title_units = "Units"
        y_title_prob = "Probability"

        with filters:
            focus_period = st.selectbox("Focus month", periods, index=max(0, len(periods) - 1))

        view_agg = view.copy()

    elif view_level == "Quarter":
        periods = sorted(view["quarter"].dropna().unique().tolist())
        period_col = "quarter"
        y_title_amount = "Amount"
        y_title_units = "Units"
        y_title_prob = "Probability"

        with filters:
            focus_period = st.selectbox("Focus quarter", periods, index=max(0, len(periods) - 1))

        view_agg = (
            view.groupby("quarter", as_index=False)
            .agg(
                revenue=("revenue", "sum"),
                cogs=("cogs", "sum"),
                gross_margin=("gross_margin", "sum"),
                units=("units", "sum"),
                probability_of_mp=("probability_of_mp", "mean"),
                expected_revenue=("expected_revenue", "sum"),
                expected_gross_margin=("expected_gross_margin", "sum"),
            )
            .sort_values("quarter")
            .reset_index(drop=True)
        )

    else:
        periods = sorted(view["year"].dropna().unique().tolist())
        period_col = "year"
        y_title_amount = "Amount"
        y_title_units = "Units"
        y_title_prob = "Probability"

        with filters:
            focus_period = st.selectbox("Focus year", periods, index=max(0, len(periods) - 1))

        view_agg = (
            view.groupby("year", as_index=False)
            .agg(
                revenue=("revenue", "sum"),
                cogs=("cogs", "sum"),
                gross_margin=("gross_margin", "sum"),
                units=("units", "sum"),
                probability_of_mp=("probability_of_mp", "mean"),
                expected_revenue=("expected_revenue", "sum"),
                expected_gross_margin=("expected_gross_margin", "sum"),
            )
            .sort_values("year")
            .reset_index(drop=True)
        )

    focus_row = view_agg[view_agg[period_col] == focus_period].iloc[0]

    tab_kpi, tab_trends, tab_table = st.tabs(["KPIs", "Trends", "Table"])

    with tab_kpi:
        st.markdown("### Profit and loss")
        cols = st.columns(3)
        cols[0].metric("Revenue", fmt_money(focus_row.get("revenue")))
        cols[1].metric("COGS", fmt_money(focus_row.get("cogs")))
        cols[2].metric("Gross margin", fmt_money(focus_row.get("gross_margin")))

        st.write("")
        st.markdown("### Demand and probability")
        cols = st.columns(2)
        cols[0].metric("Units", f"{int(round(float(focus_row.get('units', 0.0)))):,}")
        cols[1].metric("Launch probability", fmt_pct(focus_row.get("probability_of_mp")))

        st.write("")
        st.markdown("### Expected value")
        cols = st.columns(2)
        cols[0].metric("Expected revenue", fmt_money(focus_row.get("expected_revenue")))
        cols[1].metric("Expected gross margin", fmt_money(focus_row.get("expected_gross_margin")))

    with tab_trends:
        st.markdown("### Profit and loss")
        _two_per_row(
            [
                _line_one(view_agg, period_col, "revenue", "Revenue", y_title_amount),
                _line_one(view_agg, period_col, "cogs", "COGS", y_title_amount),
            ]
        )
        _two_per_row(
            [
                _line_one(view_agg, period_col, "gross_margin", "Gross margin", y_title_amount),
                _line_one(view_agg, period_col, "units", "Units", y_title_units),
            ]
        )

        st.write("")
        st.markdown("### Probability and expected value")
        _two_per_row(
            [
                _line_one(view_agg, period_col, "probability_of_mp", "Launch probability", y_title_prob),
                _line_one(view_agg, period_col, "expected_revenue", "Expected revenue", y_title_amount),
            ]
        )
        _two_per_row(
            [
                _line_one(view_agg, period_col, "expected_gross_margin", "Expected gross margin", y_title_amount),
                None,
            ]
        )

    with tab_table:
        t = view_agg.copy()
        t = t.rename(columns={period_col: "Period"})
        cols = ["Period"] + [c for c in t.columns if c != "Period"]
        st.dataframe(t[cols], use_container_width=True, hide_index=True)

    st.stop()


if mode == "Compare Scenarios":
    dfc = df.copy()
    for c in ["units", "revenue", "cogs", "gross_margin", "probability_of_mp"]:
        if c not in dfc.columns:
            dfc[c] = 0.0
        dfc[c] = pd.to_numeric(dfc[c], errors="coerce")

    dfc["expected_revenue"] = dfc["revenue"] * dfc["probability_of_mp"]
    dfc["expected_gross_margin"] = dfc["gross_margin"] * dfc["probability_of_mp"]

    dfc["quarter"] = dfc["month_dt"].dt.to_period("Q").astype(str)
    dfc["year"] = dfc["month_dt"].dt.year.astype(str)

    with filters:
        view_level = st.selectbox("View", ["Month", "Quarter", "Year"], index=0)

    if view_level == "Month":
        period_col = "month"
        periods = sorted(dfc["month"].dropna().unique().tolist())
        with filters:
            focus_period = st.selectbox("Focus month", periods, index=max(0, len(periods) - 1))
        dfp = dfc.copy()

    elif view_level == "Quarter":
        period_col = "quarter"
        periods = sorted(dfc["quarter"].dropna().unique().tolist())
        with filters:
            focus_period = st.selectbox("Focus quarter", periods, index=max(0, len(periods) - 1))
        dfp = (
            dfc.groupby(["scenario", "quarter"], as_index=False)
            .agg(
                revenue=("revenue", "sum"),
                cogs=("cogs", "sum"),
                gross_margin=("gross_margin", "sum"),
                units=("units", "sum"),
                probability_of_mp=("probability_of_mp", "mean"),
                expected_revenue=("expected_revenue", "sum"),
                expected_gross_margin=("expected_gross_margin", "sum"),
            )
            .sort_values(["scenario", "quarter"])
            .reset_index(drop=True)
        )

    else:
        period_col = "year"
        periods = sorted(dfc["year"].dropna().unique().tolist())
        with filters:
            focus_period = st.selectbox("Focus year", periods, index=max(0, len(periods) - 1))
        dfp = (
            dfc.groupby(["scenario", "year"], as_index=False)
            .agg(
                revenue=("revenue", "sum"),
                cogs=("cogs", "sum"),
                gross_margin=("gross_margin", "sum"),
                units=("units", "sum"),
                probability_of_mp=("probability_of_mp", "mean"),
                expected_revenue=("expected_revenue", "sum"),
                expected_gross_margin=("expected_gross_margin", "sum"),
            )
            .sort_values(["scenario", "year"])
            .reset_index(drop=True)
        )

    tab_trends, tab_table = st.tabs(["Trends", "Table"])

    with tab_trends:
        st.markdown("### Profit and loss")
        _two_per_row(
            [
                _line_multi_scenarios(dfp, period_col, "revenue", "scenario", "Revenue by scenario", "Amount"),
                _line_multi_scenarios(dfp, period_col, "gross_margin", "scenario", "Gross margin by scenario", "Amount"),
            ]
        )
        _two_per_row(
            [
                _line_multi_scenarios(dfp, period_col, "cogs", "scenario", "COGS by scenario", "Amount"),
                _line_multi_scenarios(dfp, period_col, "units", "scenario", "Units by scenario", "Units"),
            ]
        )

        st.write("")
        st.markdown("### Probability and expected value")
        _two_per_row(
            [
                _line_multi_scenarios(dfp, period_col, "probability_of_mp", "scenario", "Launch probability by scenario", "Probability"),
                _line_multi_scenarios(dfp, period_col, "expected_revenue", "scenario", "Expected revenue by scenario", "Amount"),
            ]
        )
        _two_per_row(
            [
                _line_multi_scenarios(dfp, period_col, "expected_gross_margin", "scenario", "Expected gross margin by scenario", "Amount"),
                None,
            ]
        )

    with tab_table:
        show = dfp.copy()
        show = show.rename(columns={period_col: "Period"})
        cols = ["scenario", "Period"] + [c for c in show.columns if c not in ["scenario", "Period"]]
        st.dataframe(show[cols], use_container_width=True, hide_index=True)

    st.stop()


if mode == "Monte Carlo":
    if dist_df is None or dist_df.empty:
        st.error("Monte Carlo input distribution table not found in tables. Ensure mc_input_distributions.csv is in findata.")
        st.stop()

    base_scenario = "Base" if "Base" in scenarios else scenarios[0]
    with filters:
        scenario = st.selectbox("Baseline scenario", scenarios, index=scenarios.index(base_scenario))
        view_level = st.selectbox("View", ["Month", "Quarter", "Year"], index=0)
        n_sims = st.slider("Simulations", 500, 20000, 3000, 500)
        seed = st.number_input("Seed", value=7, step=1)

    base_view = df[df["scenario"] == scenario].sort_values("month_dt").copy()
    if base_view.empty:
        st.error("Baseline scenario has no rows.")
        st.stop()

    tab_trends, tab_table = st.tabs(["Trends", "Table"])

    with tab_trends:
        run = st.button("Run simulation", use_container_width=True)

        if not run and "mc_results_cache" not in st.session_state:
            st.info("Click Run simulation to generate Monte Carlo results from the input distribution table.")
            st.stop()

        if run:
            mc = _run_monte_carlo(base_view, dist_df, n=int(n_sims), seed=int(seed))
            st.session_state["mc_results_cache"] = mc
        else:
            mc = st.session_state["mc_results_cache"]

        if mc is None or mc.empty:
            st.error("Monte Carlo results are empty. Check inputs in mc_input_distributions.")
            st.stop()

        mc = mc.copy()
        mc["month"] = mc["month"].astype(str)
        mc["month_dt"] = _to_month_dt(mc["month"])
        mc["quarter"] = mc["month_dt"].dt.to_period("Q").astype(str)
        mc["year"] = mc["month_dt"].dt.year.astype(str)

        if view_level == "Month":
            period_col = "month"
            mcv = mc.sort_values("month_dt").reset_index(drop=True)
        elif view_level == "Quarter":
            period_col = "quarter"
            mcv = (
                mc.groupby("quarter", as_index=False)
                .agg(
                    revenue_p10=("revenue_p10", "sum"),
                    revenue_p50=("revenue_p50", "sum"),
                    revenue_p90=("revenue_p90", "sum"),
                    cogs_p10=("cogs_p10", "sum"),
                    cogs_p50=("cogs_p50", "sum"),
                    cogs_p90=("cogs_p90", "sum"),
                    gross_margin_p10=("gross_margin_p10", "sum"),
                    gross_margin_p50=("gross_margin_p50", "sum"),
                    gross_margin_p90=("gross_margin_p90", "sum"),
                    units_p10=("units_p10", "sum"),
                    units_p50=("units_p50", "sum"),
                    units_p90=("units_p90", "sum"),
                )
                .sort_values("quarter")
                .reset_index(drop=True)
            )
        else:
            period_col = "year"
            mcv = (
                mc.groupby("year", as_index=False)
                .agg(
                    revenue_p10=("revenue_p10", "sum"),
                    revenue_p50=("revenue_p50", "sum"),
                    revenue_p90=("revenue_p90", "sum"),
                    cogs_p10=("cogs_p10", "sum"),
                    cogs_p50=("cogs_p50", "sum"),
                    cogs_p90=("cogs_p90", "sum"),
                    gross_margin_p10=("gross_margin_p10", "sum"),
                    gross_margin_p50=("gross_margin_p50", "sum"),
                    gross_margin_p90=("gross_margin_p90", "sum"),
                    units_p10=("units_p10", "sum"),
                    units_p50=("units_p50", "sum"),
                    units_p90=("units_p90", "sum"),
                )
                .sort_values("year")
                .reset_index(drop=True)
            )

        periods = mcv[period_col].astype(str).tolist()

        st.markdown("### Profit and loss")
        _two_per_row(
            [
                _band_chart(periods, mcv["revenue_p10"].tolist(), mcv["revenue_p50"].tolist(), mcv["revenue_p90"].tolist(), "Revenue with P10 to P90 band", "Amount"),
                _band_chart(periods, mcv["cogs_p10"].tolist(), mcv["cogs_p50"].tolist(), mcv["cogs_p90"].tolist(), "COGS with P10 to P90 band", "Amount"),
            ]
        )
        _two_per_row(
            [
                _band_chart(periods, mcv["gross_margin_p10"].tolist(), mcv["gross_margin_p50"].tolist(), mcv["gross_margin_p90"].tolist(), "Gross margin with P10 to P90 band", "Amount"),
                _band_chart(periods, mcv["units_p10"].tolist(), mcv["units_p50"].tolist(), mcv["units_p90"].tolist(), "Units with P10 to P90 band", "Units"),
            ]
        )

    with tab_table:
        mc_show = st.session_state.get("mc_results_cache", pd.DataFrame())
        st.dataframe(mc_show, use_container_width=True, hide_index=True)

    st.stop()