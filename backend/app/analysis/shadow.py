"""Shadow AQI: estimate missing station-hours from nearby stations that did report.

estimate = sum(w_i * (v_i + m_target - m_i)) / sum(w_i),  w_i = 1 / d_i^2,  d_i <= 15 km
where v_i is a reporting neighbour's value and m is the CAMS model value at each location
(the model term shifts each neighbour to the target's conditions; 0 when model data is
missing). Real readings are never overwritten. The method is validated by hiding real
readings and estimating them (MAE in ug/m3), and that error is the +/- band.

The shadow AQI is shown NEXT TO the official figure as an estimate, never instead of it.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

RADIUS_KM = 15.0
POWER = 2.0
HOLDOUT_FRACTION = 0.10
MIN_DISTANCE_KM = 0.1  # co-located stations: avoid dividing by ~0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class Neighbour:
    distance_km: float
    value: float
    model: float | None = None


def idw_estimate(
    neighbours: Iterable[Neighbour],
    target_model: float | None = None,
    radius_km: float = RADIUS_KM,
    power: float = POWER,
) -> float | None:
    """Inverse-distance-weighted estimate, or None if no neighbour within the radius."""
    num = den = 0.0
    for nb in neighbours:
        if nb.distance_km > radius_km or nb.value is None or math.isnan(nb.value):
            continue
        shift = 0.0
        if (
            target_model is not None
            and nb.model is not None
            and not (math.isnan(target_model) or math.isnan(nb.model))
        ):
            shift = target_model - nb.model
        w = 1.0 / max(nb.distance_km, MIN_DISTANCE_KM) ** power
        num += w * (nb.value + shift)
        den += w
    if den == 0:
        return None
    return max(num / den, 0.0)


def distance_matrix(coords: Mapping[int, tuple[float, float]]) -> pd.DataFrame:
    ids = list(coords)
    data = [[haversine_km(*coords[a], *coords[b]) for b in ids] for a in ids]
    return pd.DataFrame(data, index=ids, columns=ids)


def fill_missing(
    values: pd.DataFrame,
    coords: Mapping[int, tuple[float, float]],
    model: pd.DataFrame | None = None,
    radius_km: float = RADIUS_KM,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fill NaN cells of an (hour x station) frame. Returns (filled, was_filled mask).

    Estimates use only real readings from the same hour; cells that cannot be estimated
    (no reporting neighbour within the radius) stay NaN.
    """
    filled = values.copy()
    mask = pd.DataFrame(False, index=values.index, columns=values.columns)
    stations = [s for s in values.columns if s in coords]
    dist = distance_matrix({s: coords[s] for s in stations})
    for hour, row in values.iterrows():
        real = row.dropna()
        if real.empty:
            continue
        for target in row.index[row.isna()]:
            if target not in dist.index:
                continue
            target_model = _model_at(model, hour, target)
            nbs = [
                Neighbour(float(dist.at[target, s]), float(v), _model_at(model, hour, s))
                for s, v in real.items()
                if s in dist.columns and s != target
            ]
            est = idw_estimate(nbs, target_model, radius_km)
            if est is not None:
                filled.at[hour, target] = est
                mask.at[hour, target] = True
    return filled, mask


def _model_at(model: pd.DataFrame | None, hour, station) -> float | None:
    if model is None or station not in model.columns or hour not in model.index:
        return None
    value = model.at[hour, station]
    return None if pd.isna(value) else float(value)


@dataclass(frozen=True)
class Validation:
    mae: float | None  # mean absolute error, same unit as the values
    bias: float | None  # mean (estimate - truth)
    n: int  # held-out readings that could be estimated
    n_held_out: int


def validate_holdout(
    values: pd.DataFrame,
    coords: Mapping[int, tuple[float, float]],
    model: pd.DataFrame | None = None,
    fraction: float = HOLDOUT_FRACTION,
    seed: int = 42,
    radius_km: float = RADIUS_KM,
) -> Validation:
    """Hide `fraction` of real readings, estimate them from the rest, report the error."""
    real = values.stack().dropna()
    if real.empty:
        return Validation(None, None, 0, 0)
    rng = np.random.default_rng(seed)
    k = max(1, int(round(len(real) * fraction)))
    picked = real.index[rng.choice(len(real), size=min(k, len(real)), replace=False)]
    hidden = values.copy()
    for hour, station in picked:
        hidden.at[hour, station] = np.nan
    filled, mask = fill_missing(hidden, coords, model, radius_km)
    errors = [filled.at[h, s] - real.loc[(h, s)] for h, s in picked if mask.at[h, s]]
    if not errors:
        return Validation(None, None, 0, len(picked))
    errs = np.array(errors, dtype=float)
    return Validation(float(np.abs(errs).mean()), float(errs.mean()), len(errs), len(picked))
