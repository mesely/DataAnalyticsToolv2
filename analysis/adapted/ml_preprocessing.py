"""Adapted from mesely Influencer notebook b217890, cells63 and66.

The source loops over log columns then MinMax scales. Here fit is separate,
inside every fold, schema comes from training only, and signed log supports
negative domain values. No validation/test fit_transform. Original notebook
and exact cells are retained in docs/phases/ML_SOURCE_INVENTORY.json.
"""

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from analysis.preparation import column_type


def apply_log_transform(df, columns):
    df = df.copy()
    for col in columns:
        df[col] = np.sign(df[col]) * np.log1p(np.abs(df[col]))
    return df


class FoldPreprocessor(TransformerMixin, BaseEstimator):
    def fit(self, X, y=None):
        self.columns_ = list(X.columns)
        self.numeric_ = [
            c
            for c in X
            if column_type(
                X[c].dropna().astype(str).str.strip().loc[lambda x: x != ""].tolist()
            )[0]
            in ("integer", "number")
        ]
        self.categorical_ = [c for c in X if c not in self.numeric_]
        frame = self._coerce(X)
        self.log_columns_ = [c for c in self.numeric_ if abs(frame[c].skew()) > 1]
        frame = apply_log_transform(frame, self.log_columns_)
        self.transformer_ = ColumnTransformer(
            [
                (
                    "numeric",
                    Pipeline(
                        [
                            (
                                "missing",
                                SimpleImputer(
                                    strategy="median", keep_empty_features=True
                                ),
                            ),
                            ("scale", MinMaxScaler()),
                        ]
                    ),
                    self.numeric_,
                ),
                (
                    "category",
                    Pipeline(
                        [
                            (
                                "missing",
                                SimpleImputer(
                                    strategy="most_frequent", keep_empty_features=True
                                ),
                            ),
                            (
                                "encode",
                                OneHotEncoder(
                                    handle_unknown="ignore",
                                    max_categories=24,
                                    sparse_output=False,
                                ),
                            ),
                        ]
                    ),
                    self.categorical_,
                ),
            ],
            remainder="drop",
            sparse_threshold=0,
        )
        self.transformer_.fit(frame)
        return self

    def _coerce(self, X):
        frame = X[self.columns_].copy().replace("", np.nan)
        for c in self.numeric_:
            frame[c] = pd.to_numeric(frame[c], errors="coerce").replace(
                [np.inf, -np.inf], np.nan
            )
        for c in self.categorical_:
            frame[c] = frame[c].map(lambda v: np.nan if pd.isna(v) else str(v))
        return frame

    def transform(self, X):
        return self.transformer_.transform(
            apply_log_transform(self._coerce(X), self.log_columns_)
        )


def log_mse_like_counts(y_true, y_pred):
    """Source cell66, now guarded. Inputs must be original nonnegative scale."""
    y_true, y_pred = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
    if (
        not np.isfinite(y_true).all()
        or not np.isfinite(y_pred).all()
        or (y_true < 0).any()
        or (y_pred < 0).any()
    ):
        raise ValueError("Log MSE requires finite nonnegative original-scale values.")
    log_y_true, log_y_pred = np.log1p(y_true), np.log1p(y_pred)
    return float(np.mean((log_y_true - log_y_pred) ** 2))
