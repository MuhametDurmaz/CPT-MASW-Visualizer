"""CSV preparation and a sampling-spacing proxy for marker sizes."""
import io
import numpy as np
import pandas as pd


def read_csv(content, separator="Auto", decimal="."):
    sep = {"Auto": None, "Comma": ",", "Semicolon": ";", "Tab": "\t"}[separator]
    frame = pd.read_csv(io.BytesIO(content), sep=sep, engine="python", decimal=decimal,
                        encoding="utf-8-sig", dtype=str, keep_default_na=False)
    frame.columns = frame.columns.astype(str).str.strip()
    if frame.columns.duplicated().any():
        raise ValueError("Column names must be unique after trimming spaces.")
    return frame


def prepare(frame, columns, decimal=".", categorical=False, id_column=None):
    if len(set(columns[:3])) != 3:
        raise ValueError("Choose three different coordinate columns.")
    selected = frame.loc[:, columns].copy()
    selected.columns = ["x", "y", "z", "value"]
    for col in (["x", "y", "z"] if categorical else selected.columns):
        values = selected[col]
        if decimal == "," and not pd.api.types.is_numeric_dtype(values):
            values = values.astype("string").str.replace(",", ".", regex=False)
        selected[col] = pd.to_numeric(values, errors="coerce")
    valid = np.isfinite(selected[["x", "y", "z"]].to_numpy(dtype=float)).all(axis=1)
    if categorical:
        selected["value"] = selected["value"].astype("string").str.strip()
        valid &= (selected["value"].notna() & selected["value"].ne("") &
                  ~selected["value"].isin(["#REF!", "#VALUE!", "#N/A", "#DIV/0!", "#NUM!", "#NAME?", "#NULL!"])).to_numpy(dtype=bool)
    else:
        valid &= np.isfinite(selected["value"].to_numpy(dtype=float))
    if id_column is not None:
        selected["id"] = frame[id_column].fillna("").astype(str).str.strip()
    return selected.loc[valid].reset_index(drop=True), int((~valid).sum())


def spacing(points):
    """Median nearest-neighbour distance between unique original coordinates."""
    from scipy.spatial import cKDTree
    unique = np.unique(np.asarray(points, dtype=float), axis=0)
    if len(unique) < 2:
        return None
    tree = cKDTree(unique)
    # Bound query work for large files, but keep the full tree for exact neighbours.
    queries = unique if len(unique) <= 20000 else unique[np.linspace(0, len(unique)-1, 20000, dtype=int)]
    distances = tree.query(queries, k=2)[0][:, 1]
    return float(np.median(distances))


def marker_sizes(spacings, base=5.0):
    available = [s for s in spacings if s is not None and s > 0]
    reference = min(available) if available else 1.0
    return [float(np.clip(base * np.sqrt(s / reference), 2, 24))
            if s is not None and s > 0 else float(base) for s in spacings]
