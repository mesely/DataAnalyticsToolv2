"""Pure kernels adapted from PoliEco build_economic_shock_study.py at c1705e7.
Retail adapters are outside this module; no political IO or ideology assumptions.
"""
import pandas as pd
import numpy as np
from .networks import zscore_frame


def stage_months(event_month: str, pre: int = 3, post: int = 3) -> dict[str, list[str]]:
    event = pd.Period(event_month, freq="M")
    return {
        "pre": [str(event - i) for i in range(pre, 0, -1)],
        "shock": [str(event)],
        "post": [str(event + i) for i in range(1, post + 1)],
    }

def build_party_affinity(mat: pd.DataFrame) -> pd.DataFrame:
    if mat.empty or len(mat) < 2:
        return pd.DataFrame()
    z = zscore_frame(mat.astype(float))
    norm = np.linalg.norm(z.to_numpy(dtype=float), axis=1)
    norm[norm == 0] = 1.0
    unit = z.div(norm, axis=0)
    sim = unit.to_numpy(dtype=float) @ unit.to_numpy(dtype=float).T
    arr = np.array(sim, dtype=float, copy=True)
    np.fill_diagonal(arr, 0.0)
    out = pd.DataFrame(arr, index=mat.index, columns=mat.index)
    return out

def owner_concentration_hhi(summary: pd.DataFrame) -> float:
    if summary.empty or "agenda_share" not in summary.columns:
        return np.nan
    shares = summary["agenda_share"].to_numpy(dtype=float)
    return float(np.square(shares).sum())

def negative_edge_share(affinity: pd.DataFrame) -> float:
    if affinity.empty:
        return np.nan
    pos_mass = 0.0
    neg_mass = 0.0
    for i in range(len(affinity.index)):
        for j in range(i + 1, len(affinity.columns)):
            val = float(affinity.iloc[i, j])
            if val < 0:
                neg_mass += abs(val)
            else:
                pos_mass += abs(val)
    total = pos_mass + neg_mass
    return float(neg_mass / total) if total > 0 else np.nan
