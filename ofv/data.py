from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
import streamlit as st


REQUIRED_TABLES = [
    "dashboard_exec_overview",
    "dashboard_new_product_scen",
    "dashboard_cost_var_bridge",
    "dashboard_cost_var_detail",
]


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def find_data_dir() -> Path | None:
    root = project_root()
    p = root / "findata"
    if p.exists() and p.is_dir():
        return p
    return None


def _pick_best_source(data_dir: Path) -> Tuple[str, Path]:
    xlsx = sorted(data_dir.glob("*.xlsx"))
    if xlsx:
        preferred = [p for p in xlsx if "Finance_Overview" in p.name or "Forecast" in p.name or "Variance" in p.name]
        return "excel", preferred[0] if preferred else xlsx[0]

    csv = sorted(data_dir.glob("*.csv"))
    if csv:
        return "csv", data_dir

    raise FileNotFoundError("No xlsx or csv files found in findata")


def _load_from_excel(xlsx_path: Path) -> Dict[str, pd.DataFrame]:
    xls = pd.ExcelFile(xlsx_path)
    tables: Dict[str, pd.DataFrame] = {}
    for sheet in xls.sheet_names:
        tables[sheet] = pd.read_excel(xlsx_path, sheet_name=sheet)
    return tables


def _load_from_csv_folder(data_dir: Path) -> Dict[str, pd.DataFrame]:
    tables: Dict[str, pd.DataFrame] = {}
    for p in data_dir.glob("*.csv"):
        tables[p.stem] = pd.read_csv(p)
    return tables


def _validate_tables(tables: Dict[str, pd.DataFrame]) -> None:
    missing = [t for t in REQUIRED_TABLES if t not in tables]
    if missing:
        raise ValueError(f"Missing required tables: {missing}")


@st.cache_data(show_spinner=False)
def load_tables(data_dir: Path) -> Dict[str, pd.DataFrame]:
    source_type, source_path = _pick_best_source(data_dir)

    if source_type == "excel":
        tables = _load_from_excel(source_path)
    else:
        tables = _load_from_csv_folder(source_path)

    _validate_tables(tables)
    return tables