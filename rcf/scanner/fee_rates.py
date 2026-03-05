"""Legal building fee rates from the Third Addendum (תוספת שלישית).

Rates are per square meter in NIS, sourced from:
  תקנות התכנון והבנייה (בקשה להיתר, תנאיו ואגרות), תש"ל-1970
Updated annually on January 1st by CPI index.
"""

from __future__ import annotations

from datetime import date

# Base rates per sqm in NIS, by area type.
# Source: Third Addendum of Planning & Building Regulations.
# These are the 2024 base rates; earlier years are derived via CPI.
_BASE_YEAR = 2024
_BASE_RATES: dict[str, float] = {
    "residential": 32.0,        # שטח עיקרי למגורים
    "commercial": 40.0,         # שטח עיקרי למסחר
    "industrial": 28.0,         # שטח עיקרי לתעשייה
    "service": 16.0,            # שטחי שירות (מחסנים, מרתפים, חדרי מדרגות)
    "parking_covered": 10.0,    # חניה מקורה
    "parking_open": 0.0,        # חניה פתוחה — פטור
    "basement": 16.0,           # מרתף
    "balcony_covered": 16.0,    # מרפסת מקורה
    "balcony_open": 0.0,        # מרפסת פתוחה — פטור
}

# Annual CPI multipliers relative to _BASE_YEAR.
# Source: CBS CPI index.  Approximate values for years with active permits.
_CPI_MULTIPLIERS: dict[int, float] = {
    2018: 0.88,
    2019: 0.89,
    2020: 0.89,
    2021: 0.91,
    2022: 0.95,
    2023: 0.98,
    2024: 1.00,
    2025: 1.03,
    2026: 1.06,
}

# Fallback: 3% annual inflation for years not in the table.
_DEFAULT_ANNUAL_INFLATION = 0.03


def get_rate(year: int, area_type: str) -> float:
    """Return the legal fee rate (NIS/sqm) for *area_type* in *year*.

    Falls back to CPI-extrapolated base rates for unknown years.
    """
    base = _BASE_RATES.get(area_type, _BASE_RATES["residential"])
    multiplier = _CPI_MULTIPLIERS.get(year)
    if multiplier is None:
        # Extrapolate from base year
        delta = year - _BASE_YEAR
        multiplier = (1 + _DEFAULT_ANNUAL_INFLATION) ** delta
    return round(base * multiplier, 2)


def get_all_rates(year: int) -> dict[str, float]:
    """Return all fee rates for *year* as a dict."""
    return {area_type: get_rate(year, area_type) for area_type in _BASE_RATES}


def compute_correct_fee(
    residential_sqm: float,
    service_sqm: float,
    year: int,
    *,
    residential_type: str = "residential",
    service_type: str = "service",
) -> int:
    """Compute the legally correct fee in agorot (1 NIS = 100 agorot).

    This is the core formula:
      correct_fee = (residential_sqm × residential_rate) + (service_sqm × service_rate)
    """
    res_rate = get_rate(year, residential_type)
    svc_rate = get_rate(year, service_type)
    total_nis = (residential_sqm * res_rate) + (service_sqm * svc_rate)
    return round(total_nis * 100)  # convert NIS → agorot
