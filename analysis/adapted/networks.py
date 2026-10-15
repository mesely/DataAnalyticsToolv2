"""Pinned PoliEco numeric kernels. Dense similarity is bounded to <=60 items by caller."""
import pandas as pd
import numpy as np

def zscore_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy().astype(float)
    std = out.std(axis=0).replace(0, 1.0)
    out = (out - out.mean(axis=0)) / std
    return out.fillna(0.0)


def compute_gatekeeper_scores(membership: pd.DataFrame, adj: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
    plus_idx = np.where(membership["community"].to_numpy() == 1)[0]
    minus_idx = np.where(membership["community"].to_numpy() == -1)[0]
    rows = []
    for i, row in membership.reset_index(drop=True).iterrows():
        vals = adj[i]
        pos_to_plus = float(np.clip(vals[plus_idx], 0, None).sum()) if len(plus_idx) else 0.0
        pos_to_minus = float(np.clip(vals[minus_idx], 0, None).sum()) if len(minus_idx) else 0.0
        neg_to_plus = float(np.abs(np.clip(vals[plus_idx], None, 0)).sum()) if len(plus_idx) else 0.0
        neg_to_minus = float(np.abs(np.clip(vals[minus_idx], None, 0)).sum()) if len(minus_idx) else 0.0
        total_pos_cross = pos_to_plus + pos_to_minus
        total_neg_cross = neg_to_plus + neg_to_minus
        reach_plus = pos_to_plus + neg_to_plus
        reach_minus = pos_to_minus + neg_to_minus
        pos_balance = min(pos_to_plus, pos_to_minus) / (total_pos_cross + 1e-9)
        neg_balance = min(neg_to_plus, neg_to_minus) / (total_neg_cross + 1e-9)
        reach_balance = min(reach_plus, reach_minus) / (reach_plus + reach_minus + 1e-9)
        neutral_bonus = 1.15 if int(row["community"]) == 0 else 1.0
        gatekeeper_score = np.log1p((reach_plus + reach_minus) * 25.0) * reach_balance * neutral_bonus
        cross_pressure = np.log1p(total_neg_cross * 25.0) * neg_balance
        rows.append(
            {
                "speaker": row["speaker"],
                "party": row["party"],
                "community": int(row["community"]),
                "community_label": row["community_label"],
                "total_mentions": float(row["total_mentions"]),
                "pos_to_plus": pos_to_plus,
                "pos_to_minus": pos_to_minus,
                "neg_to_plus": neg_to_plus,
                "neg_to_minus": neg_to_minus,
                "reach_plus": reach_plus,
                "reach_minus": reach_minus,
                "positive_bridge_balance": pos_balance,
                "signed_reach_balance": reach_balance,
                "gatekeeper_score": float(gatekeeper_score),
                "cross_pressure": float(cross_pressure),
            }
        )
    scores = pd.DataFrame(rows).sort_values("gatekeeper_score", ascending=False).reset_index(drop=True)
    party_summary = (
        scores.groupby("party", as_index=False)
        .agg(
            avg_gatekeeper_score=("gatekeeper_score", "mean"),
            median_gatekeeper_score=("gatekeeper_score", "median"),
            avg_cross_pressure=("cross_pressure", "mean"),
            n_speakers=("speaker", "nunique"),
        )
        .sort_values("avg_gatekeeper_score", ascending=False)
        .reset_index(drop=True)
    )
    return scores, party_summary


def build_sparse_signed_graph(mat: pd.DataFrame, k_pos: int = 8, k_neg: int = 8) -> tuple[np.ndarray, np.ndarray]:
    z_mat = zscore_frame(mat)
    x = z_mat.to_numpy(dtype=float)
    norm = np.linalg.norm(x, axis=1)
    norm[norm == 0] = 1.0
    x = x / norm[:, None]
    sim = x @ x.T
    np.fill_diagonal(sim, 0.0)
    n = sim.shape[0]
    sparse = np.zeros_like(sim)
    for i in range(n):
        row = sim[i]
        pos_idx = np.where(row > 0)[0]
        neg_idx = np.where(row < 0)[0]
        if len(pos_idx):
            pick = pos_idx[np.argsort(row[pos_idx])[-min(k_pos, len(pos_idx)):]]
            sparse[i, pick] = row[pick]
        if len(neg_idx):
            pick = neg_idx[np.argsort(row[neg_idx])[:min(k_neg, len(neg_idx))]]
            sparse[i, pick] = row[pick]
    sparse = 0.5 * (sparse + sparse.T)
    np.fill_diagonal(sparse, 0.0)
    return sparse, x
