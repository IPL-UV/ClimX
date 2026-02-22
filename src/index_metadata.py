INDEX_METADATA_OVERRIDES = {
    "FD": {"description": "Frost Days", "unit": "days"},
    "TNLT2": {"description": "Days with Tmin below 2°C", "unit": "days"},
    "TNLTM2": {"description": "Days with Tmin below −2°C", "unit": "days"},
    "TNLTM20": {"description": "Days with Tmin below −20°C", "unit": "days"},
    "SU": {"description": "Summer Days (Tmax ≥ 25°C)", "unit": "days"},
    "ID": {"description": "Ice Days (Tmax < 0°C)", "unit": "days"},
    "TR": {"description": "Tropical Nights (Tmin ≥ 20°C)", "unit": "days"},
    "GSL": {"description": "Growing Season Length", "unit": "days"},
    "TXX": {"description": "Monthly Max of Daily Tmax", "unit": "°C"},
    "TNX": {"description": "Monthly Max of Daily Tmin", "unit": "°C"},
    "TXN": {"description": "Monthly Min of Daily Tmax", "unit": "°C"},
    "TNN": {"description": "Monthly Min of Daily Tmin", "unit": "°C"},
    "TMM": {"description": "Mean Daily Temperature", "unit": "°C"},
    "TXM": {"description": "Mean Daily Tmax", "unit": "°C"},
    "TNM": {"description": "Mean Daily Tmin", "unit": "°C"},
    "TN10P": {"description": "Cool Nights (Tmin < 10th pct)", "unit": "%"},
    "TX10P": {"description": "Cool Days (Tmax < 10th pct)", "unit": "%"},
    "TN90P": {"description": "Warm Nights (Tmin > 90th pct)", "unit": "%"},
    "TX90P": {"description": "Warm Days (Tmax > 90th pct)", "unit": "%"},
    "WSDI": {"description": "Warm Spell Duration Index", "unit": "days"},
    "WSDID": {"description": "User-defined Warm Spell Duration", "unit": "days"},
    "CSDI": {"description": "Cold Spell Duration Index", "unit": "days"},
    "CSDID": {"description": "User-defined Cold Spell Duration", "unit": "days"},
    "TXGT50P": {"description": "Days Above Median Tmax", "unit": "%"},
    "TX95T": {"description": "95th Percentile Tmax Threshold", "unit": "°C"},
    "TMGE5": {"description": "Days with Mean Temp ≥ 5°C", "unit": "days"},
    "TMLT5": {"description": "Days with Mean Temp < 5°C", "unit": "days"},
    "TMGE10": {"description": "Days with Mean Temp ≥ 10°C", "unit": "days"},
    "TMLT10": {"description": "Days with Mean Temp < 10°C", "unit": "days"},
    "TXGE30": {"description": "Days with Tmax ≥ 30°C", "unit": "days"},
    "TXGE35": {"description": "Days with Tmax ≥ 35°C", "unit": "days"},
    "TXDTND": {"description": "Consecutive Hot Days & Nights", "unit": "days"},
    "TXBDTNBD": {"description": "Consecutive Cold Days & Nights", "unit": "days"},
    "HDDHEATN": {"description": "Heating Degree Days", "unit": "°C·days"},
    "CDDCOLDN": {"description": "Cooling Degree Days", "unit": "°C·days"},
    "GDDGROWN": {"description": "Growing Degree Days", "unit": "°C·days"},
    "DTR": {"description": "Daily Temperature Range", "unit": "°C"},
    "RX1DAY": {"description": "Max 1-day Precipitation", "unit": "mm"},
    "RX5DAY": {"description": "Max 5-day Precipitation", "unit": "mm"},
    "RXDDAY": {"description": "Max N-day Precipitation", "unit": "mm"},
    "SPI": {"description": "Standardized Precipitation Index", "unit": ""},
    "SPEI": {"description": "Standardized Precip-Evap Index", "unit": ""},
    "SDII": {"description": "Simple Daily Intensity Index", "unit": "mm day⁻¹"},
    "R10MM": {"description": "Days with Precip ≥10mm", "unit": "days"},
    "R20MM": {"description": "Days with Precip ≥20mm", "unit": "days"},
    "RNNMM": {"description": "Days with Precip ≥NNmm", "unit": "days"},
    "CDD": {"description": "Consecutive Dry Days", "unit": "days"},
    "CWD": {"description": "Consecutive Wet Days", "unit": "days"},
    "R95P": {"description": "Total Precip above 95th pct", "unit": "mm"},
    "R99P": {"description": "Total Precip above 99th pct", "unit": "mm"},
    "PRCPTOT": {"description": "Total Wet-day Precipitation", "unit": "mm"},
}

_HEATWAVE_METHODS = {
    "TX90": "Tmax > 90th pct",
    "TN90": "Tmin > 90th pct",
    "EHF": "Excess Heat Factor",
}

for metric in ["HWN", "HWF", "HWD", "HWM", "HWA"]:
    for method, description in _HEATWAVE_METHODS.items():
        INDEX_METADATA_OVERRIDES[f"{metric}_{method}"] = {
            "description": f"{metric} ({description})",
            "unit": "days" if metric in {"HWN", "HWF", "HWD"} else "°C",
        }

for metric in ["CWN", "CWF", "CWD_ECF", "CWM", "CWA"]:
    INDEX_METADATA_OVERRIDES[metric] = {
        "description": metric.replace("_", " ").upper(),
        "unit": "days" if metric in {"CWN", "CWF", "CWD_ECF"} else "°C",
    }

