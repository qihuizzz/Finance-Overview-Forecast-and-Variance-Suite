from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def _home_page_path() -> str:
    if Path("Home.py").exists():
        return "Home.py"
    if Path("app.py").exists():
        return "app.py"
    return "Home.py"


def sidebar_nav(current: str, section_title: str | None = None):
    st.markdown(
        """
        <style>
        div[data-testid="stSidebarNav"] { display: none !important; }
        section[data-testid="stSidebarNav"] { display: none !important; }
        div[data-testid="stSidebarNavItems"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    routes = {
        "Home": _home_page_path(),
        "Overview": "pages/01_Finance_Executive_Overview.py",
        "Forecast": "pages/02_Product_Forecast_Scenarios.py",
        "Variance": "pages/03_Cost_Variance_Drivers.py",
    }
    order = ["Home", "Overview", "Forecast", "Variance"]

    if "_ofv_nav_ph" not in st.session_state:
        st.session_state["_ofv_nav_ph"] = st.sidebar.empty()
    if "_ofv_section_ph" not in st.session_state:
        st.session_state["_ofv_section_ph"] = st.sidebar.empty()

    nav_ph = st.session_state["_ofv_nav_ph"]
    sec_ph = st.session_state["_ofv_section_ph"]

    nav_ph.empty()
    sec_ph.empty()

    with nav_ph.container():
        idx = order.index(current) if current in order else 0
        choice = st.radio(
            label="Navigate",
            options=order,
            index=idx,
            label_visibility="collapsed",
        )
        if choice != current:
            st.switch_page(routes[choice])
            st.stop()
        st.divider()

    sec_container = sec_ph.container()
    if section_title:
        sec_container.markdown(f"#### {section_title}")
        sec_container.caption("Filters")
    return sec_container


def fmt_money(x) -> str:
    try:
        if x is None:
            return "NA"
        if pd.isna(x):
            return "NA"
        return f"${float(x):,.0f}"
    except Exception:
        return "NA"


def fmt_pct(x) -> str:
    try:
        if x is None:
            return "NA"
        if pd.isna(x):
            return "NA"
        return f"{float(x) * 100:,.1f}%"
    except Exception:
        return "NA"


def kpi_row(items) -> None:
    if not items:
        return
    cols = st.columns(len(items))
    for c, it in zip(cols, items):
        c.metric(it.get("label", ""), it.get("value", ""), it.get("delta"))


def line_multi(
    df: pd.DataFrame,
    x_col: str,
    y_cols: list[str],
    title: str,
    y_title: str,
) -> None:
    if df is None or df.empty:
        st.info("No data to plot")
        return

    fig = go.Figure()
    for col in y_cols:
        if col in df.columns:
            fig.add_trace(go.Scatter(x=df[x_col], y=df[col], mode="lines+markers", name=col))

    fig.update_layout(
        title=title,
        xaxis_title=x_col,
        yaxis_title=y_title,
        height=360,
        legend_title_text="",
        margin=dict(l=10, r=10, t=60, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def stacked_bar(
    df: pd.DataFrame,
    x_col: str,
    y_cols: list[str],
    title: str,
    y_title: str,
) -> None:
    if df is None or df.empty:
        st.info("No data to plot")
        return

    fig = go.Figure()
    for col in y_cols:
        if col in df.columns:
            fig.add_trace(go.Bar(x=df[x_col], y=df[col], name=col))

    fig.update_layout(
        barmode="stack",
        title=title,
        xaxis_title=x_col,
        yaxis_title=y_title,
        height=360,
        legend_title_text="",
        margin=dict(l=10, r=10, t=60, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def variance_bridge(df: pd.DataFrame, label_col: str, value_col: str, title: str) -> None:
    if df is None or df.empty:
        st.info("No data to plot")
        return
    if label_col not in df.columns or value_col not in df.columns:
        st.info("Missing required columns for bridge")
        return

    labels = df[label_col].astype(str).tolist()
    values = pd.to_numeric(df[value_col], errors="coerce").fillna(0.0).tolist()

    fig = go.Figure(
        go.Waterfall(
            orientation="v",
            x=labels,
            y=values,
            measure=["relative"] * len(values),
        )
    )
    fig.update_layout(
        title=title,
        height=420,
        margin=dict(l=10, r=10, t=60, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def heatmap(df: pd.DataFrame, title: str) -> None:
    if df is None or df.empty:
        st.info("No data to plot")
        return

    fig = px.imshow(df, aspect="auto", title=title)
    fig.update_layout(margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig, use_container_width=True)