"""Database tables for the VayuKavach data pipeline.

Rule: missing data is stored as rows (value NULL, status 'missing', plus a reason),
never skipped, so completeness and gap analysis can work on it later.
"""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Pollutants measured at stations (India National AQI set).
POLLUTANTS = ("pm25", "pm10", "no2", "so2", "co", "o3", "nh3")
# Model-only extras (Open-Meteo CAMS). co2 is context only, never part of India's AQI.
MODEL_POLLUTANTS = (*POLLUTANTS, "dust", "co2")
READING_STATUSES = ("ok", "missing", "excluded_over_999")
STATION_SOURCES = ("cpcb", "openaq")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class District(Base):
    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(128))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)


class Station(Base):
    __tablename__ = "stations"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_stations_source_external_id"),
        CheckConstraint(_in("source", STATION_SOURCES), name="ck_stations_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(16))
    # CPCB: station name as published; OpenAQ: location id.
    external_id: Mapped[str] = mapped_column(String(256))
    name: Mapped[str] = mapped_column(String(256))
    city: Mapped[str | None] = mapped_column(String(128))
    state: Mapped[str | None] = mapped_column(String(128))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # True for regulatory monitors (all CPCB; OpenAQ isMonitor), False for low-cost sensors.
    is_reference: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Sensor(Base):
    """One instrument at a station (OpenAQ). Locations keep retired sensors next to live
    ones, so collectors read only sensors whose datetime_last is recent."""

    __tablename__ = "sensors"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_sensors_source_external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(16))
    external_id: Mapped[str] = mapped_column(String(64))
    pollutant: Mapped[str] = mapped_column(String(8))
    unit: Mapped[str | None] = mapped_column(String(16))  # as published, e.g. ppb
    datetime_first: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    datetime_last: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Reading(Base):
    __tablename__ = "readings"
    __table_args__ = (
        UniqueConstraint("station_id", "hour", "pollutant", name="uq_readings_station_hour_pol"),
        CheckConstraint(_in("pollutant", POLLUTANTS), name="ck_readings_pollutant"),
        CheckConstraint(_in("status", READING_STATUSES), name="ck_readings_status"),
        CheckConstraint(
            "(status = 'missing' AND value IS NULL) OR (status <> 'missing' AND value IS NOT NULL)",
            name="ck_readings_value_matches_status",
        ),
        Index("ix_readings_hour", "hour"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"))
    hour: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # UTC, truncated to hour
    pollutant: Mapped[str] = mapped_column(String(8))
    value: Mapped[float | None] = mapped_column(Float)
    # ug/m3 (mg/m3 for CO) for concentrations; 'aqi_subindex' for CPCB's real-time feed.
    unit: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str | None] = mapped_column(String(64))  # why a value is missing
    source: Mapped[str] = mapped_column(String(16))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ModelAir(Base):
    """Open-Meteo CAMS model values for a grid cell (Estimated, never Measured)."""

    __tablename__ = "model_air"
    __table_args__ = (
        UniqueConstraint("lat", "lon", "hour", "pollutant", name="uq_model_air_cell_hour_pol"),
        CheckConstraint(_in("pollutant", MODEL_POLLUTANTS), name="ck_model_air_pollutant"),
        Index("ix_model_air_district_hour", "district_id", "hour"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"))
    lat: Mapped[float] = mapped_column(Float)  # grid cell centre returned by Open-Meteo
    lon: Mapped[float] = mapped_column(Float)
    hour: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    pollutant: Mapped[str] = mapped_column(String(8))
    value: Mapped[float | None] = mapped_column(Float)  # NULL when the model has no value
    unit: Mapped[str] = mapped_column(String(16))
    model_run: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_forecast: Mapped[bool] = mapped_column(Boolean)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Weather(Base):
    """Hourly Open-Meteo weather per district (model analysis for past hours)."""

    __tablename__ = "weather"
    __table_args__ = (UniqueConstraint("district_id", "hour", name="uq_weather_district_hour"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id", ondelete="CASCADE"))
    hour: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    temperature: Mapped[float | None] = mapped_column(Float)  # degC
    apparent_temperature: Mapped[float | None] = mapped_column(Float)  # degC
    humidity: Mapped[float | None] = mapped_column(Float)  # %
    dew_point: Mapped[float | None] = mapped_column(Float)  # degC
    wind_speed: Mapped[float | None] = mapped_column(Float)  # km/h
    wind_gusts: Mapped[float | None] = mapped_column(Float)  # km/h
    wind_direction: Mapped[float | None] = mapped_column(Float)  # degrees
    pressure: Mapped[float | None] = mapped_column(Float)  # hPa, mean sea level
    cloud_cover: Mapped[float | None] = mapped_column(Float)  # %
    precipitation: Mapped[float | None] = mapped_column(Float)  # mm
    precipitation_probability: Mapped[float | None] = mapped_column(Float)  # %
    visibility: Mapped[float | None] = mapped_column(Float)  # m
    uv_index: Mapped[float | None] = mapped_column(Float)
    weather_code: Mapped[int | None] = mapped_column(Integer)  # WMO code
    boundary_layer_height: Mapped[float | None] = mapped_column(Float)  # m
    is_forecast: Mapped[bool] = mapped_column(Boolean)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WeatherDaily(Base):
    """Daily Open-Meteo weather per district (sun, UV, highs and lows)."""

    __tablename__ = "weather_daily"
    __table_args__ = (
        UniqueConstraint("district_id", "date", name="uq_weather_daily_district_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date)  # local date, Asia/Kolkata
    weather_code: Mapped[int | None] = mapped_column(Integer)
    temperature_max: Mapped[float | None] = mapped_column(Float)
    temperature_min: Mapped[float | None] = mapped_column(Float)
    apparent_temperature_max: Mapped[float | None] = mapped_column(Float)
    apparent_temperature_min: Mapped[float | None] = mapped_column(Float)
    sunrise: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sunset: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    daylight_duration: Mapped[float | None] = mapped_column(Float)  # seconds
    uv_index_max: Mapped[float | None] = mapped_column(Float)
    precipitation_sum: Mapped[float | None] = mapped_column(Float)  # mm
    precipitation_probability_max: Mapped[float | None] = mapped_column(Float)  # %
    is_forecast: Mapped[bool] = mapped_column(Boolean)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FetchLog(Base):
    __tablename__ = "fetch_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    errors: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # running | ok | failed | skipped
    status: Mapped[str] = mapped_column(String(16), default="running", server_default="running")
    detail: Mapped[str | None] = mapped_column(Text)


class StationDayCompleteness(Base):
    """Share of expected hourly readings that arrived, per station, pollutant and IST day."""

    __tablename__ = "station_day_completeness"
    __table_args__ = (
        UniqueConstraint("station_id", "date", "pollutant", name="uq_station_day_pollutant"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date, index=True)
    pollutant: Mapped[str] = mapped_column(String(8))
    expected: Mapped[int] = mapped_column(Integer)
    received: Mapped[int] = mapped_column(Integer)
    excluded: Mapped[int] = mapped_column(Integer)
    pct: Mapped[float] = mapped_column(Float)
    longest_gap_hours: Mapped[int] = mapped_column(Integer)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DailyCitySummary(Base):
    """Official vs measured vs shadow AQI, completeness and gap flags per district and IST day.

    official_*: from CPCB's published sub-indices (data.gov.in feed).
    measured_*: our India AQI from reported concentrations only (values >= 999 dropped,
                as CPCB does).
    shadow_*:   our India AQI with missing station-hours estimated (Estimated, never official).
    """

    __tablename__ = "daily_city_summary"
    __table_args__ = (UniqueConstraint("district_id", "date", name="uq_daily_city_summary"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date, index=True)
    is_partial_day: Mapped[bool] = mapped_column(Boolean)  # today, still in progress
    hours_covered: Mapped[int] = mapped_column(Integer)

    official_aqi: Mapped[int | None] = mapped_column(Integer)
    official_hour: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    official_stations: Mapped[int] = mapped_column(Integer, default=0)

    measured_aqi: Mapped[int | None] = mapped_column(Integer)
    measured_main_pollutant: Mapped[str | None] = mapped_column(String(8))
    measured_stations: Mapped[int] = mapped_column(Integer, default=0)

    shadow_aqi: Mapped[int | None] = mapped_column(Integer)
    shadow_aqi_low: Mapped[int | None] = mapped_column(Integer)
    shadow_aqi_high: Mapped[int | None] = mapped_column(Integer)
    shadow_main_pollutant: Mapped[str | None] = mapped_column(String(8))
    shadow_stations: Mapped[int] = mapped_column(Integer, default=0)
    filled_hours: Mapped[int] = mapped_column(Integer, default=0)  # station-pollutant-hours
    unfilled_hours: Mapped[int] = mapped_column(Integer, default=0)
    shadow_mae_pm25: Mapped[float | None] = mapped_column(Float)  # ug/m3, hold-out validation
    shadow_validation_n: Mapped[int] = mapped_column(Integer, default=0)

    completeness_pct: Mapped[float | None] = mapped_column(Float)
    expected_readings: Mapped[int] = mapped_column(Integer, default=0)
    received_readings: Mapped[int] = mapped_column(Integer, default=0)
    stations_total: Mapped[int] = mapped_column(Integer, default=0)
    stations_silent: Mapped[int] = mapped_column(Integer, default=0)  # silent 3+ hours
    city_silent_hours: Mapped[int] = mapped_column(Integer, default=0)  # >= 25% silent
    max_share_silent: Mapped[float | None] = mapped_column(Float)

    gap_bias_flag: Mapped[bool | None] = mapped_column(Boolean)
    gap_bias_diff_pp: Mapped[float | None] = mapped_column(Float)
    polluted_missing_pct: Mapped[float | None] = mapped_column(Float)
    clean_missing_pct: Mapped[float | None] = mapped_column(Float)
    gap_bias_level_source: Mapped[str | None] = mapped_column(String(16))  # cams | stations

    excluded_count: Mapped[int] = mapped_column(Integer, default=0)
    near_limit_count: Mapped[int] = mapped_column(Integer, default=0)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CityHourAqi(Base):
    """Hour-by-hour city AQI (running index at the end of each hour).

    official_*: CPCB published sub-indices (Measured).  measured_*: our AQI from reported
    station concentrations (Measured).  shadow_*: with missing station-hours estimated
    (Estimated).  cams_*: India AQI from the CAMS model, incl. forecast hours (Estimated).
    """

    __tablename__ = "city_hour_aqi"
    __table_args__ = (UniqueConstraint("district_id", "hour", name="uq_city_hour_aqi"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id", ondelete="CASCADE"))
    hour: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    official_aqi: Mapped[int | None] = mapped_column(Integer)
    official_main_pollutant: Mapped[str | None] = mapped_column(String(8))
    official_stations: Mapped[int] = mapped_column(Integer, default=0)
    measured_aqi: Mapped[int | None] = mapped_column(Integer)
    measured_main_pollutant: Mapped[str | None] = mapped_column(String(8))
    measured_stations: Mapped[int] = mapped_column(Integer, default=0)
    shadow_aqi: Mapped[int | None] = mapped_column(Integer)
    shadow_aqi_low: Mapped[int | None] = mapped_column(Integer)
    shadow_aqi_high: Mapped[int | None] = mapped_column(Integer)
    cams_aqi: Mapped[int | None] = mapped_column(Integer)
    cams_main_pollutant: Mapped[str | None] = mapped_column(String(8))
    is_forecast: Mapped[bool] = mapped_column(Boolean, default=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CityDailyAqi(Base):
    """Daily city AQI used to train and score forecasts.

    Station AQI = highest sub-index of that day's mean concentrations (a pollutant needs
    >= 16 observed hours; >= 3 pollutants incl. PM); city AQI = mean of valid station AQIs.
    Backfilled from OpenAQ daily aggregates, then derived nightly from stored hourly readings.
    """

    __tablename__ = "city_daily_aqi"
    __table_args__ = (UniqueConstraint("district_id", "date", name="uq_city_daily_aqi"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date, index=True)
    aqi: Mapped[int | None] = mapped_column(Integer)
    stations: Mapped[int] = mapped_column(Integer, default=0)
    pm25: Mapped[float | None] = mapped_column(Float)  # city mean of station daily means
    pm10: Mapped[float | None] = mapped_column(Float)
    no2: Mapped[float | None] = mapped_column(Float)
    so2: Mapped[float | None] = mapped_column(Float)
    co: Mapped[float | None] = mapped_column(Float)  # mg/m3
    o3: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DistrictDailyFeatures(Base):
    """Daily CAMS and weather per district: history (reanalysis) and forecast days."""

    __tablename__ = "district_daily_features"
    __table_args__ = (UniqueConstraint("district_id", "date", name="uq_district_daily_features"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date, index=True)
    cams_pm25: Mapped[float | None] = mapped_column(Float)
    cams_pm10: Mapped[float | None] = mapped_column(Float)
    cams_no2: Mapped[float | None] = mapped_column(Float)
    cams_so2: Mapped[float | None] = mapped_column(Float)
    cams_co: Mapped[float | None] = mapped_column(Float)  # mg/m3
    cams_o3: Mapped[float | None] = mapped_column(Float)
    temperature_mean: Mapped[float | None] = mapped_column(Float)
    humidity_mean: Mapped[float | None] = mapped_column(Float)
    wind_mean: Mapped[float | None] = mapped_column(Float)
    precipitation_sum: Mapped[float | None] = mapped_column(Float)
    blh_mean: Mapped[float | None] = mapped_column(Float)
    is_forecast: Mapped[bool] = mapped_column(Boolean, default=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AqiForecastDaily(Base):
    """Served daily AQI forecasts (latest issue wins in the API)."""

    __tablename__ = "aqi_forecast_daily"
    __table_args__ = (
        UniqueConstraint("district_id", "issue_date", "target_date", name="uq_aqi_forecast_daily"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id", ondelete="CASCADE"))
    issue_date: Mapped[date] = mapped_column(Date)
    target_date: Mapped[date] = mapped_column(Date, index=True)
    lead_days: Mapped[int] = mapped_column(Integer)
    low: Mapped[int | None] = mapped_column(Integer)
    median: Mapped[int | None] = mapped_column(Integer)
    high: Mapped[int | None] = mapped_column(Integer)
    # cams_corrected (days 1-5) | cams_raw (fallback) | outlook (days 6-10)
    method: Mapped[str] = mapped_column(String(24))
    model_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ForecastModel(Base):
    __tablename__ = "forecast_model"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # bias | outlook
    version: Mapped[str] = mapped_column(String(64), unique=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    train_rows: Mapped[int] = mapped_column(Integer)
    metrics: Mapped[dict] = mapped_column(JSON)
    beats_baseline: Mapped[bool] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)
