"""Check our India AQI against CPCB's published sub-indices.

For each CPCB station-hour-pollutant sub-index in the data.gov.in feed, compute our own
sub-index from the same station's hourly concentrations (OpenAQ mirror), using the CPCB
averaging window that ends with that hour, and compare.

Run:  uv run python -m app.analysis.validate_cpcb [output.md]
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analysis.aqi import sub_index, window_average
from app.analysis.shadow import haversine_km

LINK_MAX_KM = 0.5


def normalise_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().lower()


def link_stations(cpcb: pd.DataFrame, openaq: pd.DataFrame) -> dict[int, int]:
    """CPCB station id -> OpenAQ reference station id (same name, else within 0.5 km)."""
    by_name = {normalise_name(r.name): r.id for r in openaq.itertuples()}
    links = {}
    for r in cpcb.itertuples():
        match = by_name.get(normalise_name(r.name))
        if match is None and pd.notna(r.lat):
            near = [
                (haversine_km(r.lat, r.lon, o.lat, o.lon), o.id)
                for o in openaq.itertuples()
                if pd.notna(o.lat)
            ]
            near = [n for n in near if n[0] <= LINK_MAX_KM]
            match = min(near)[1] if near else None
        if match is not None:
            links[r.id] = match
    return links


@dataclass(frozen=True)
class Comparison:
    rows: pd.DataFrame  # station, hour, pollutant, cpcb, ours, diff

    def by_pollutant(self) -> pd.DataFrame:
        if self.rows.empty:
            return pd.DataFrame()
        g = self.rows.groupby("pollutant")["diff"]
        return pd.DataFrame(
            {
                "n": g.size(),
                "mae_points": g.apply(lambda d: d.abs().mean()).round(1),
                "bias_points": g.mean().round(1),
                "within_5": g.apply(lambda d: (d.abs() <= 5).mean() * 100).round(0),
                "within_10": g.apply(lambda d: (d.abs() <= 10).mean() * 100).round(0),
            }
        )

    def station_aqi(self) -> pd.DataFrame:
        """Station AQI (max sub-index) on both sides, for station-hours with >= 3 pollutants."""
        if self.rows.empty:
            return pd.DataFrame()
        g = self.rows.groupby(["station", "hour"])
        out = pd.DataFrame(
            {"pollutants": g.size(), "cpcb_aqi": g["cpcb"].max(), "our_aqi": g["ours"].max()}
        )
        out = out[out["pollutants"] >= 3].copy()
        out["diff"] = out["our_aqi"] - out["cpcb_aqi"]
        return out


def compare(
    cpcb_subindices: pd.DataFrame, concentrations: pd.DataFrame, links: dict[int, int]
) -> Comparison:
    """cpcb_subindices: station_id, station, hour, pollutant, value (sub-index).
    concentrations: station_id, hour, pollutant, value (ug/m3, CO mg/m3), real values only."""
    out = []
    grouped = {k: g.set_index("hour")["value"] for k, g in concentrations.groupby(
        ["station_id", "pollutant"])}  # fmt: skip
    for r in cpcb_subindices.itertuples():
        oq = links.get(r.station_id)
        series = grouped.get((oq, r.pollutant)) if oq is not None else None
        if series is None:
            continue
        avg = window_average(series, r.pollutant, r.hour + timedelta(hours=1))
        ours = sub_index(r.pollutant, avg)
        if ours is None:
            continue
        out.append((r.station, r.hour, r.pollutant, float(r.value), round(ours)))
    rows = pd.DataFrame(out, columns=["station", "hour", "pollutant", "cpcb", "ours"])
    rows["diff"] = rows["ours"] - rows["cpcb"]
    return Comparison(rows)


def run(session: Session) -> Comparison:
    stations = pd.DataFrame(
        session.execute(
            text(
                "SELECT id, source, name, lat, lon FROM stations WHERE source = 'cpcb'"
                " OR (source = 'openaq' AND is_reference)"
            )  # fmt: skip
        ).all(),
        columns=["id", "source", "name", "lat", "lon"],
    )
    links = link_stations(
        stations[stations.source == "cpcb"], stations[stations.source == "openaq"]
    )
    if not links:
        return Comparison(pd.DataFrame(columns=["station", "hour", "pollutant", "cpcb", "ours",
                                                "diff"]))  # fmt: skip
    cpcb = pd.DataFrame(
        session.execute(
            text(
                "SELECT r.station_id, s.name AS station, r.hour, r.pollutant, r.value"
                " FROM readings r JOIN stations s ON s.id = r.station_id"
                " WHERE s.source = 'cpcb' AND r.status = 'ok' AND r.unit = 'aqi_subindex'"
                " AND r.station_id = ANY(:ids)"
            ),
            {"ids": list(links)},
        ).all(),
        columns=["station_id", "station", "hour", "pollutant", "value"],
    )
    if cpcb.empty:
        return compare(cpcb, cpcb, links)
    cpcb["hour"] = pd.to_datetime(cpcb["hour"], utc=True)
    start = cpcb["hour"].min() - timedelta(hours=25)
    conc = pd.DataFrame(
        session.execute(
            text(
                "SELECT station_id, hour, pollutant, value FROM readings"
                " WHERE station_id = ANY(:ids) AND status = 'ok' AND hour >= :s"
            ),
            {"ids": list(set(links.values())), "s": start.to_pydatetime()},
        ).all(),
        columns=["station_id", "hour", "pollutant", "value"],
    )
    conc["hour"] = pd.to_datetime(conc["hour"], utc=True)
    return compare(cpcb, conc, links)


def report(result: Comparison) -> str:
    lines = [
        "# India AQI vs CPCB published sub-indices",
        "",
        f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC. Our sub-index: CPCB breakpoints on"
        " OpenAQ hourly concentrations (24 h mean, >= 16 h; CO/O3 max 8 h mean).",
        "CPCB: `avg_value` sub-index from the data.gov.in real-time feed, same station and hour.",
        "",
        "## Per pollutant (difference = ours - CPCB, AQI points)",
        "",
    ]
    per = result.by_pollutant()
    if per.empty:
        lines.append("No overlapping station-hours yet.")
        return "\n".join(lines) + "\n"
    lines.append("| Pollutant | n | MAE | Bias | Within ±5 | Within ±10 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for p, r in per.iterrows():
        lines.append(f"| {p} | {r.n} | {r.mae_points} | {r.bias_points} | {r.within_5:.0f}% |"
                     f" {r.within_10:.0f}% |")  # fmt: skip
    st = result.station_aqi()
    lines += ["", "## Station AQI (highest sub-index, station-hours with ≥ 3 pollutants)", ""]
    if st.empty:
        lines.append("None yet.")
    else:
        d = st["diff"]
        lines.append(
            f"{len(st)} station-hours: MAE {d.abs().mean():.1f} points, bias {d.mean():+.1f},"
            f" within ±5: {(d.abs() <= 5).mean() * 100:.0f}%,"
            f" within ±10: {(d.abs() <= 10).mean() * 100:.0f}%."
        )
        lines += ["", "| Station | Hour (IST) | CPCB AQI | Our AQI | Diff |",
                  "| --- | --- | --- | --- | --- |"]  # fmt: skip
        for (station, hour), r in st.head(25).iterrows():
            ist = (hour + timedelta(hours=5, minutes=30)).strftime("%d %b %H:%M")
            lines.append(f"| {station} | {ist} | {r.cpcb_aqi:.0f} | {r.our_aqi:.0f} |"
                         f" {r['diff']:+.0f} |")  # fmt: skip
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    from app.db import SessionLocal

    with SessionLocal() as session:
        text_out = report(run(session))
    if len(argv) > 1:
        Path(argv[1]).parent.mkdir(parents=True, exist_ok=True)
        Path(argv[1]).write_text(text_out, encoding="utf-8")
    print(text_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
