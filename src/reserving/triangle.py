"""Loss development triangles.

A triangle is held as a pandas DataFrame:

* index   = origin period (accident year), integers
* columns = development age (1, 2, ..., n), integers
* values  = cumulative amounts, NaN where not yet observed

The class is a thin wrapper so that the actuarial operations (link ratios,
latest diagonal, cutting back to an earlier valuation date) live in one place
and are tested once.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Triangle:
    values: pd.DataFrame
    name: str = ""

    # ------------------------------------------------------------------ build
    @classmethod
    def from_long(
        cls,
        df: pd.DataFrame,
        origin: str,
        dev: str,
        value: str,
        name: str = "",
    ) -> "Triangle":
        """Build from long format (one row per origin x development age)."""
        wide = df.pivot_table(index=origin, columns=dev, values=value, aggfunc="sum")
        wide = wide.sort_index().sort_index(axis=1).astype(float)
        wide.index.name, wide.columns.name = "origin", "dev"
        return cls(wide, name)

    @classmethod
    def from_incremental(cls, incr: pd.DataFrame, name: str = "") -> "Triangle":
        cum = incr.cumsum(axis=1).where(incr.notna())
        return cls(cum.astype(float), name)

    # -------------------------------------------------------------- properties
    @property
    def origins(self) -> pd.Index:
        return self.values.index

    @property
    def ages(self) -> pd.Index:
        return self.values.columns

    @property
    def shape(self) -> tuple[int, int]:
        return self.values.shape

    def copy(self) -> "Triangle":
        return Triangle(self.values.copy(), self.name)

    # ------------------------------------------------------------- operations
    def incremental(self) -> pd.DataFrame:
        v = self.values
        inc = v.diff(axis=1)
        inc.iloc[:, 0] = v.iloc[:, 0]
        return inc

    def latest_diagonal(self) -> pd.Series:
        """Most recent observed cumulative value for each origin."""
        v = self.values
        return v.apply(lambda r: r.dropna().iloc[-1] if r.notna().any() else np.nan, axis=1)

    def latest_age(self) -> pd.Series:
        v = self.values
        return v.apply(lambda r: r.dropna().index[-1] if r.notna().any() else np.nan, axis=1)

    def link_ratios(self) -> pd.DataFrame:
        """Age-to-age factors. Column labelled by the *starting* age."""
        v = self.values
        lr = v.iloc[:, 1:].values / v.iloc[:, :-1].values
        out = pd.DataFrame(lr, index=v.index, columns=v.columns[:-1])
        return out.replace([np.inf, -np.inf], np.nan)

    def calendar_period(self) -> pd.DataFrame:
        """Calendar year of each cell (origin + age - 1)."""
        o = np.asarray(self.origins)[:, None]
        a = np.asarray(self.ages)[None, :]
        return pd.DataFrame(o + a - 1, index=self.origins, columns=self.ages)

    def as_at(self, valuation: int) -> "Triangle":
        """Cut back to what was known at the end of calendar year `valuation`.

        Origins after the valuation year are dropped; cells whose calendar year
        is after the valuation are set to NaN. Used for back-testing.
        """
        cal = self.calendar_period()
        v = self.values.where(cal <= valuation)
        v = v.loc[v.index <= valuation]
        v = v.loc[:, v.notna().any()]
        return Triangle(v, f"{self.name} as at {valuation}")

    def upper(self) -> "Triangle":
        """Keep only the observed (upper-left) part of a full square."""
        return self.as_at(int(self.origins.max()))

    def __truediv__(self, other) -> pd.DataFrame:
        o = other.values if isinstance(other, Triangle) else other
        return self.values / o

    def __repr__(self) -> str:  # pragma: no cover - display only
        return f"Triangle({self.name!r}, origins={list(self.origins)}, ages={list(self.ages)})\n{self.values}"
