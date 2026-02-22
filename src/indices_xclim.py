"""
Climate index implementations that leverage xclim's indices module.

Assumptions:
    * ``xclim`` and its dependencies (pint, cf-xarray, etc.) are installed in
      the active environment.
    * Input datasets carry CF-compliant metadata (especially ``units``) so that
      xclim can handle conversions automatically.
"""

from __future__ import annotations

import operator
from pathlib import Path
from typing import Callable, Dict, Hashable, Optional, Tuple, Union

import numpy as np
import xarray as xr
import xclim
import xclim.indices as xci
from xclim.indices import run_length as rl

from .index_metadata import INDEX_METADATA_OVERRIDES

# Conversion factor from kg m-2 s-1 to mm/day
KG_M2_S_TO_MM_DAY = 86400

DEFAULT_BASE_PERIOD: Tuple[str, str] = ("1961-01-01", "1990-12-31")
HistoricalData = Union[Path, str, xr.Dataset]

_BASELINE_CACHE: Dict[Path, xr.Dataset] = {}
_PERCENTILE_CACHE: Dict[Tuple[Hashable, str, float, Tuple[str, str], int], xr.DataArray] = {}


# --------------------------------------------------------------------------------------
# Helper utilities
# --------------------------------------------------------------------------------------
def _ensure_var(ds: xr.Dataset, var: str) -> xr.DataArray:
    if var == "tas" and "tas" not in ds:
        return (_ensure_var(ds, "tasmax") + _ensure_var(ds, "tasmin")) / 2.0
    if var not in ds:
        raise ValueError(f"Variable '{var}' not found in dataset.")
    return ds[var]


def _tasmax(ds: xr.Dataset) -> xr.DataArray:
    da = _ensure_var(ds, "tasmax")
    units = da.attrs.get("units")

    if not isinstance(units, str) or not units:
        # If "units" is missing, not a string, or is an empty string, set it to "K"
        da.attrs["units"] = "K"

    return da


def _tasmin(ds: xr.Dataset) -> xr.DataArray:
    da = _ensure_var(ds, "tasmin")
    units = da.attrs.get("units")

    if not isinstance(units, str) or not units:
        # If "units" is missing, not a string, or is an empty string, set it to "K"
        da.attrs["units"] = "K"

    return da


def _tas(ds: xr.Dataset) -> xr.DataArray:
    da = _ensure_var(ds, "tas")
    units = da.attrs.get("units")

    if not isinstance(units, str) or not units:
        # If "units" is missing, not a string, or is an empty string, set it to "K"
        da.attrs["units"] = "K"

    return da


def _pr(ds: xr.Dataset) -> xr.DataArray:
    da =  _ensure_var(ds, "pr")
    units = da.attrs.get("units")

    if not isinstance(units, str) or not units:
        # If "units" is missing, not a string, or is an empty string, set it to "kg m-2 s-1"
        da.attrs["units"] = "kg m-2 s-1"

    return da


def _precip_mm_day(ds: xr.Dataset, var: str = "pr") -> xr.DataArray:
    da = _ensure_var(ds, var)
    units = da.attrs.get("units", "").lower()
    if units in ("mm/day", "mm d-1", "mm"):
        return da
    converted = da * KG_M2_S_TO_MM_DAY
    converted.attrs["units"] = "mm/day"
    return converted


def _baseline_source_key(source: HistoricalData) -> Hashable:
    if isinstance(source, xr.Dataset):
        # xarray.Dataset is not hashable; id() is stable for the lifetime of the object.
        return ("dataset", id(source))
    resolved = Path(source).resolve()
    return ("path", resolved)


def _open_baseline_dataset(source: HistoricalData) -> xr.Dataset:
    if isinstance(source, xr.Dataset):
        return source

    resolved = Path(source).resolve()
    if resolved not in _BASELINE_CACHE:
        if resolved.suffix == ".zarr" or resolved.is_dir():
            ds = xr.open_zarr(resolved, consolidated=True)
        else:
            ds = xr.open_dataset(resolved)
        _BASELINE_CACHE[resolved] = ds
    return _BASELINE_CACHE[resolved]


def _percentile_threshold(
    var_name: str,
    quantile: float,
    historical_data_path: HistoricalData,
    base_period: Tuple[str, str],
    window: int = 5,
) -> xr.DataArray:
    cache_key = (_baseline_source_key(historical_data_path), var_name, quantile, base_period, window)
    if cache_key in _PERCENTILE_CACHE:
        return _PERCENTILE_CACHE[cache_key]

    ds_hist = _open_baseline_dataset(historical_data_path)
    if var_name not in ds_hist:
        raise ValueError(f"Variable '{var_name}' not available in baseline dataset {historical_data_path}")

    da = ds_hist[var_name].sel(time=slice(base_period[0], base_period[1]))
    percentile = xclim.core.calendar.percentile_doy(da, window=window, per=quantile)
    percentile = percentile.squeeze("percentiles", drop=True)
    percentile.attrs["percentile"] = quantile
    percentile.name = "percentile_threshold"
    _PERCENTILE_CACHE[cache_key] = percentile
    return percentile


def _align_dayofyear(da: xr.DataArray, threshold: xr.DataArray) -> xr.DataArray:
    day_lookup = da["time"].dt.dayofyear
    return threshold.sel(dayofyear=day_lookup)


def _maybe_rechunk_time(da: xr.DataArray, target_chunk: int) -> xr.DataArray:
    if target_chunk <= 0 or "time" not in da.dims:
        return da
    if not hasattr(da.data, "chunks"):
        return da
    try:
        time_chunks = da.chunks[da.get_axis_num("time")]
    except Exception:
        return da
    if len(time_chunks) <= 1:
        return da
    return da.chunk({"time": target_chunk})


def _pr_total_above_percentile(
    pr: xr.DataArray,
    threshold_doy: xr.DataArray,
    *,
    freq: str,
    rechunk_time: int = 365,
) -> xr.DataArray:
    pr = _maybe_rechunk_time(pr, rechunk_time)
    threshold_doy = threshold_doy.chunk({"dayofyear": -1}) if hasattr(threshold_doy.data, "chunks") else threshold_doy

    # Avoid materializing an explicit (time, lat, lon, ...) threshold array via `.sel(dayofyear=...)`.
    # GroupBy applies the 1D day-of-year threshold to each day group.
    mask = pr.groupby("time.dayofyear") > threshold_doy
    wet = pr.where(mask)
    out = wet.resample(time=freq).sum(dim="time")
    out.attrs.update({"units": pr.attrs.get("units", "")})
    return out


def _spell_stat_from_mask(mask: xr.DataArray, min_length: int, reduce: str = "sum") -> xr.DataArray:
    years = np.unique(mask["time"].dt.year.values)
    outputs = []
    for year in years:
        subset = mask.sel(time=mask["time"].dt.year == year)
        if subset.time.size == 0:
            continue
        if reduce == "sum":
            stat = rl.windowed_run_count(subset, window=min_length, dim="time")
        elif reduce == "max":
            stat = rl.longest_run(subset, dim="time")
        elif reduce == "count":
            stat = rl.windowed_run_events(subset, window=min_length, dim="time")         
        else:
            raise ValueError(f"Unsupported reduce mode '{reduce}'")
        stat = stat.expand_dims(time=[np.datetime64(f"{int(year)}-01-01", "ns")])
        outputs.append(stat.rename(None))
    if not outputs:
        template = mask.isel(time=0, drop=True) * np.nan
        return template.expand_dims(time=[]).rename(None)
    return xr.concat(outputs, dim="time")


def _monthly_rolling_zscore(series: xr.DataArray, scale_months: int, name: str) -> xr.DataArray:
    rolled = series.rolling(time=scale_months, min_periods=scale_months).sum()
    mean = rolled.mean("time")
    std = rolled.std("time")
    std_nonzero = std.where(std != 0)
    zscore = (rolled - mean) / std_nonzero
    return zscore.rename(name)


def _estimate_pet(ds: xr.Dataset) -> xr.DataArray:
    tasmax = _tasmax_c(ds)
    tasmin = _tasmin_c(ds)
    tasmean = (tasmax + tasmin) / 2.0
    delta = (tasmax - tasmin).clip(min=0)
    pet = 0.0023 * (tasmean + 17.8) * np.sqrt(delta)
    pet.attrs["units"] = "mm/day"
    return pet


def _temp_in_celsius(da: xr.DataArray) -> xr.DataArray:
    units = da.attrs.get("units", "").lower()
    if units in ("degc", "celsius", "°c"):
        return da
    if units in ("kelvin", "k", "K", ""):
        converted = da - 273.15
        converted.attrs["units"] = "degC"
        return converted
    if units in ("degf", "fahrenheit"):
        converted = (da - 32.0) * 5.0 / 9.0
        converted.attrs["units"] = "degC"
        return converted
    return da


def _tasmax_c(ds: xr.Dataset) -> xr.DataArray:
    return _temp_in_celsius(_ensure_var(ds, "tasmax"))


def _tasmin_c(ds: xr.Dataset) -> xr.DataArray:
    return _temp_in_celsius(_ensure_var(ds, "tasmin"))

# --------------------------------------------------------------------------------------
# Generic builders
# --------------------------------------------------------------------------------------
def _threshold_count_index(
    name: str,
    var: str,
    thresh: str,
    op: str,
    default_freq: str = "YS",
) -> Callable[[xr.Dataset], xr.DataArray]:
    def _func(ds: xr.Dataset, freq: str = default_freq, **_) -> xr.DataArray:
        data = _ensure_var(ds, var)
        out = xci.generic.threshold_count(data, threshold=thresh, op=op, freq=freq)
        return out.rename(name)

    return _func


def _percentile_fraction_index(
    name: str,
    var: str,
    quantile: float,
    op: str,
) -> Callable[[xr.Dataset], xr.DataArray]:
    def _func(
        ds: xr.Dataset,
        historical_data_path: Optional[Path] = None,
        base_period: Tuple[str, str] = DEFAULT_BASE_PERIOD,
        freq: str = "YS",
        window: int = 5,
        **_,
    ) -> xr.DataArray:
        if historical_data_path is None:
            raise ValueError(f"{name} requires 'historical_data_path'.")
        data = _ensure_var(ds, var)
        threshold = _percentile_threshold(var, quantile, historical_data_path, base_period, window)
        aligned = _align_dayofyear(data, threshold)
        count = xci.generic.threshold_count(data, op=op, threshold=aligned, freq=freq)
        total = data.resample(time=freq).count()
        frac = (count / total) * 100
        return frac.rename(name)

    return _func


def _warm_spell_index(
    name: str,
    quantile: float,
    comparator: str,
    window_days: int,
) -> Callable[[xr.Dataset], xr.DataArray]:
    def _func(
        ds: xr.Dataset,
        historical_data_path: Optional[Path] = None,
        base_period: Tuple[str, str] = DEFAULT_BASE_PERIOD,
        freq: str = "YS",
        window: int = 5,
        **_,
    ) -> xr.DataArray:
        if historical_data_path is None:
            raise ValueError(f"{name} requires 'historical_data_path'.")
        var = "tasmax" if comparator == ">" else "tasmin"
        data = _ensure_var(ds, var)

        # xclim run-length helpers are much more reliable when the time dimension
        # is a single dask chunk. Rechunk only when needed.
        if hasattr(data.data, "chunks") and 'time' in data.dims:
            time_chunks = data.chunks[data.get_axis_num('time')]
            if len(time_chunks) > 1:
                data = data.chunk({'time': -1})
        threshold = _align_dayofyear(
            data,
            _percentile_threshold(var, quantile, historical_data_path, base_period, window),
        )
        if hasattr(threshold.data, "chunks") and 'time' in threshold.dims:
            time_chunks = threshold.chunks[threshold.get_axis_num('time')]
            if len(time_chunks) > 1:
                threshold = threshold.chunk({'time': -1})
        op = operator.gt if comparator == ">" else operator.lt
        mask = op(data, threshold)
        annual = _spell_stat_from_mask(mask, window_days, reduce="sum")
        return annual.rename(name)

    return _func


# --------------------------------------------------------------------------------------
# Individual indices (threshold-based)
# --------------------------------------------------------------------------------------
fd = _threshold_count_index("FD", "tasmin", 273.15, "<")
tnlt2 = _threshold_count_index("TNlt2", "tasmin", 275.15, "<")
tnltm2 = _threshold_count_index("TNltm2", "tasmin", 271.15, "<")
tnltm20 = _threshold_count_index("TNltm20", "tasmin", 253.15, "<")
su = _threshold_count_index("SU", "tasmax", 298.15, ">")
id_days = _threshold_count_index("ID", "tasmax", 273.15, "<")
tr = _threshold_count_index("TR", "tasmin", 293.15, ">")
def _mean_threshold_count(name: str, thresh: float, op: str) -> Callable[[xr.Dataset], xr.DataArray]:
    def _func(ds: xr.Dataset, freq: str = "YS", **_) -> xr.DataArray:
        data = _tas(ds)
        out = xci.generic.threshold_count(data, threshold=thresh, op=op, freq=freq)
        return out.rename(name)

    return _func


tmge5 = _mean_threshold_count("TMge5", 278.15, ">=")
tmlt5 = _mean_threshold_count("TMlt5", 278.15, "<")
tmge10 = _mean_threshold_count("TMge10", 283.15, ">=")
tmlt10 = _mean_threshold_count("TMlt10", 283.15, "<")
txge30 = _threshold_count_index("TXge30", "tasmax", 303.15, ">=")
txge35 = _threshold_count_index("TXge35", "tasmax", 308.15, ">=")


# --------------------------------------------------------------------------------------
# Percentile / spell based indices
# --------------------------------------------------------------------------------------
txgt50p = _percentile_fraction_index("TXgt50p", "tasmax", 50.0, ">")
tn10p = _percentile_fraction_index("TN10p", "tasmin", 10.0, "<")
tx10p = _percentile_fraction_index("TX10p", "tasmax", 10.0, "<")
tn90p = _percentile_fraction_index("TN90p", "tasmin", 90.0, ">")
tx90p = _percentile_fraction_index("TX90p", "tasmax", 90.0, ">")
wsdi = _warm_spell_index("WSDI", 90.0, ">", 6)
wsdid = _warm_spell_index("WSDId", 90.0, ">", 4)
csdi = _warm_spell_index("CSDI", 10.0, "<", 6)
csdid = _warm_spell_index("CSDId", 10.0, "<", 4)


# --------------------------------------------------------------------------------------
# Direct xclim calls for standard ETCCDI metrics
# --------------------------------------------------------------------------------------
def gsl(
    ds: xr.Dataset,
    thresh: str = "5 degC",
    freq: str = "YS",
    **_,
) -> xr.DataArray:
    return xci.growing_season_length(tas=_tas(ds), thresh=thresh, freq=freq).rename("GSL")


def txx(ds: xr.Dataset, freq: str = "MS", **_) -> xr.DataArray:
    return xci.tx_max(tasmax=_tasmax(ds), freq=freq).rename("TXx")


def tnx(ds: xr.Dataset, freq: str = "MS", **_) -> xr.DataArray:
    return xci.tn_max(tasmin=_tasmin(ds), freq=freq).rename("TNx")


def txn(ds: xr.Dataset, freq: str = "MS", **_) -> xr.DataArray:
    return xci.tx_min(tasmax=_tasmax(ds), freq=freq).rename("TXn")


def tnn(ds: xr.Dataset, freq: str = "MS", **_) -> xr.DataArray:
    return xci.tn_min(tasmin=_tasmin(ds), freq=freq).rename("TNn")


def tmm(ds: xr.Dataset, freq: str = "MS", **_) -> xr.DataArray:
    return _tas(ds).resample(time=freq).mean().rename("TMm")


def txm(ds: xr.Dataset, freq: str = "MS", **_) -> xr.DataArray:
    return xci.tx_mean(tasmax=_tasmax(ds), freq=freq).rename("TXm")


def tnm(ds: xr.Dataset, freq: str = "MS", **_) -> xr.DataArray:
    return xci.tn_mean(tasmin=_tasmin(ds), freq=freq).rename("TNm")


def tx95t(
    ds: xr.Dataset,
    historical_data_path: Optional[Path] = None,
    base_period: Tuple[str, str] = DEFAULT_BASE_PERIOD,
    window: int = 5,
    **_,
) -> xr.DataArray:
    if historical_data_path is None:
        raise ValueError("TX95t requires 'historical_data_path'.")
    threshold = _percentile_threshold("tasmax", 95.0, historical_data_path, base_period, window)
    return threshold.rename("TX95t")


def txdtnd(
    ds: xr.Dataset,
    historical_data_path: Optional[Path] = None,
    base_period: Tuple[str, str] = DEFAULT_BASE_PERIOD,
    window_days: int = 2,
    **_,
) -> xr.DataArray:
    if historical_data_path is None:
        raise ValueError("TXdTNd requires 'historical_data_path'.")
    tasmax = _tasmax(ds)
    tasmin = _tasmin(ds)
    tx_thresh = _align_dayofyear(tasmax, _percentile_threshold("tasmax", 95.0, historical_data_path, base_period))
    tn_thresh = _align_dayofyear(tasmin, _percentile_threshold("tasmin", 95.0, historical_data_path, base_period))
    mask = (tasmax > tx_thresh) & (tasmin > tn_thresh)
    def count_window(group):
        consecutive = group.copy()
        for i in range(1, window_days):
            consecutive &= group.shift(time=i, fill_value=False)
        return consecutive.sum(dim="time")
    return mask.groupby("time.year").map(count_window).rename({"year": "time"}).rename("TXdTNd")

def txbdtnd(
    ds: xr.Dataset,
    historical_data_path: Optional[Path] = None,
    base_period: Tuple[str, str] = DEFAULT_BASE_PERIOD,
    window_days: int = 2,
    **_,
) -> xr.DataArray:
    if historical_data_path is None:
        raise ValueError("TXbdTNbd requires 'historical_data_path'.")
    tasmax = _tasmax(ds)
    tasmin = _tasmin(ds)
    tx_thresh = _align_dayofyear(tasmax, _percentile_threshold("tasmax", 5.0, historical_data_path, base_period))
    tn_thresh = _align_dayofyear(tasmin, _percentile_threshold("tasmin", 5.0, historical_data_path, base_period))
    mask = (tasmax < tx_thresh) & (tasmin < tn_thresh)
    def count_window(group):
        consecutive = group.copy()
        for i in range(1, window_days):
            consecutive &= group.shift(time=i, fill_value=False)
        return consecutive.sum(dim="time")
    return mask.groupby("time.year").map(count_window).rename({"year": "time"}).rename("TXbdTNbd")  


def hddheatn(ds: xr.Dataset, thresh: str = "18 degC", freq: str = "YS", **_) -> xr.DataArray:
    return xci.heating_degree_days(tas=_tas(ds), thresh=thresh, freq=freq).rename("HDDheatn")


def cddcoldn(ds: xr.Dataset, thresh: str = "18 degC", freq: str = "YS", **_) -> xr.DataArray:
    return xci.cooling_degree_days(tas=_tas(ds), thresh=thresh, freq=freq).rename("CDDcoldn")


def gddgrown(ds: xr.Dataset, thresh: str = "10 degC", freq: str = "YS", **_) -> xr.DataArray:
    return xci.growing_degree_days(tas=_tas(ds), thresh=thresh, freq=freq).rename("GDDgrown")


def dtr(ds: xr.Dataset, freq: str = "YS", **_) -> xr.DataArray:
    return xci.daily_temperature_range(tasmax=_tasmax(ds), tasmin=_tasmin(ds), freq=freq).rename("DTR")


def rx1day(ds: xr.Dataset, freq: str = "MS", **_) -> xr.DataArray:
    pr = _precip_mm_day(ds)
    return xci.max_1day_precipitation_amount(pr=pr, freq=freq).rename("Rx1day")


def rx5day(ds: xr.Dataset, freq: str = "MS", **_) -> xr.DataArray:
    pr = _precip_mm_day(ds)
    return xci.max_n_day_precipitation_amount(pr=pr, window=5, freq=freq).rename("Rx5day")


def rxdday(ds: xr.Dataset, window_days: int = 7, freq: str = "MS", **_) -> xr.DataArray:
    pr = _precip_mm_day(ds)
    return xci.max_n_day_precipitation_amount(pr=pr, window=window_days, freq=freq).rename("RXdday")


def spi(ds: xr.Dataset, scale_months: int = 3, var: str = "pr", **_) -> xr.DataArray:
    monthly = _precip_mm_day(ds, var).resample(time="MS").sum("time")
    return _monthly_rolling_zscore(monthly, scale_months, name="SPI")

def spei(
    ds: xr.Dataset,
    scale_months: int = 3,
    var: str = "pr",
    **_,
) -> xr.DataArray:
    pr = _precip_mm_day(ds, var)
    pet = _estimate_pet(ds)
    balance = (pr - pet).resample(time="MS").sum("time")
    return _monthly_rolling_zscore(balance, scale_months, name="SPEI")


def cdd(ds: xr.Dataset, thresh: str = "1 mm/day", freq: str = "YS", **_) -> xr.DataArray:
    pr = _precip_mm_day(ds)
    return xci.maximum_consecutive_dry_days(pr=pr, thresh=thresh, freq=freq).rename("CDD")


def cwd(ds: xr.Dataset, thresh: str = "1 mm/day", freq: str = "YS", **_) -> xr.DataArray:
    pr = _precip_mm_day(ds)
    return xci.maximum_consecutive_wet_days(pr=pr, thresh=thresh, freq=freq).rename("CWD")


def sdii(ds: xr.Dataset, freq: str = "YS", thresh: str = 1, **_) -> xr.DataArray:
    pr = _precip_mm_day(ds)
    wet = pr.where(pr >= thresh)
    return wet.resample(time=freq).sum() / wet.resample(time=freq).count()


def r10mm(ds: xr.Dataset, freq: str = "YS", **_) -> xr.DataArray:
    pr = _precip_mm_day(ds)
    return xci.wetdays(pr=pr, thresh="10 mm/day", freq=freq).rename("R10mm")


def r20mm(ds: xr.Dataset, freq: str = "YS", **_) -> xr.DataArray:
    pr = _precip_mm_day(ds)
    return xci.wetdays(pr=pr, thresh="20 mm/day", freq=freq).rename("R20mm")


def rnnmm(ds: xr.Dataset, threshold_mm: float = 30.0, freq: str = "YS", **_) -> xr.DataArray:
    thresh = f"{threshold_mm} mm/day"
    pr = _precip_mm_day(ds)
    return xci.wetdays(pr=pr, thresh=thresh, freq=freq).rename("Rnnmm")


def r95p(
    ds: xr.Dataset,
    historical_data_path: Optional[Path] = None,
    base_period: Tuple[str, str] = DEFAULT_BASE_PERIOD,
    freq: str = "YS",
    rechunk_time: int = 365,
    **_,
) -> xr.DataArray:
    if historical_data_path is None:
        raise ValueError("R95p requires 'historical_data_path'.")
    pr = _pr(ds)
    threshold_doy = _percentile_threshold("pr", 95.0, historical_data_path, base_period)
    return _pr_total_above_percentile(pr, threshold_doy, freq=freq, rechunk_time=rechunk_time).rename("R95p")


def r99p(
    ds: xr.Dataset,
    historical_data_path: Optional[Path] = None,
    base_period: Tuple[str, str] = DEFAULT_BASE_PERIOD,
    freq: str = "YS",
    rechunk_time: int = 365,
    **_,
) -> xr.DataArray:
    if historical_data_path is None:
        raise ValueError("R99p requires 'historical_data_path'.")
    pr = _pr(ds)
    threshold_doy = _percentile_threshold("pr", 99.0, historical_data_path, base_period)
    return _pr_total_above_percentile(pr, threshold_doy, freq=freq, rechunk_time=rechunk_time).rename("R99p")


def prcptot(ds: xr.Dataset, freq: str = "YS", thresh: str = "1 mm/day", **_) -> xr.DataArray:
    pr = _pr(ds) * KG_M2_S_TO_MM_DAY
    pr.attrs["units"] = "mm/day"
    return xci.prcptot(pr=pr, thresh=thresh, freq=freq).rename("PRCPTOT")


# --------------------------------------------------------------------------------------
# Heatwave / coldwave families (via xclim run-length utilities)
# --------------------------------------------------------------------------------------
def _heatwave_metric(
    metric_name: str,
    var: str,
    quantile: float,
    comparator: Callable[[xr.DataArray, xr.DataArray], xr.DataArray],
    reduce: str,
):
    def _func(
        ds: xr.Dataset,
        historical_data_path: Optional[Path] = None,
        base_period: Tuple[str, str] = DEFAULT_BASE_PERIOD,
        window_days: int = 3,
        **_,
    ) -> xr.DataArray:
        if historical_data_path is None:
            raise ValueError(f"{metric_name} requires 'historical_data_path'.")
        data = _ensure_var(ds, var)
        threshold = _align_dayofyear(data, _percentile_threshold(var, quantile, historical_data_path, base_period))
        mask = comparator(data, threshold)
        if reduce == "count":
            annual = _spell_stat_from_mask(mask, window_days, reduce="count")
        elif reduce == "sum":
            annual = _spell_stat_from_mask(mask, window_days, reduce="sum")
        elif reduce == "max":
            annual = _spell_stat_from_mask(mask, window_days, reduce="max")
        else:
            aggregated = data.where(mask)
            if reduce == "mean":
                annual = aggregated.resample(time="YS").mean("time")
            else:
                annual = aggregated.resample(time="YS").max("time")
        return annual.rename(metric_name)

    return _func


hwn_tx90 = _heatwave_metric("HWN_TX90", "tasmax", 90.0, operator.gt, "count")
hwf_tx90 = _heatwave_metric("HWF_TX90", "tasmax", 90.0, operator.gt, "sum")
hwd_tx90 = _heatwave_metric("HWD_TX90", "tasmax", 90.0, operator.gt, "max")
hwm_tx90 = _heatwave_metric("HWM_TX90", "tasmax", 90.0, operator.gt, "mean")
hwa_tx90 = _heatwave_metric("HWA_TX90", "tasmax", 90.0, operator.gt, "peak")

hwn_tn90 = _heatwave_metric("HWN_TN90", "tasmin", 90.0, operator.gt, "count")
hwf_tn90 = _heatwave_metric("HWF_TN90", "tasmin", 90.0, operator.gt, "sum")
hwd_tn90 = _heatwave_metric("HWD_TN90", "tasmin", 90.0, operator.gt, "max")
hwm_tn90 = _heatwave_metric("HWM_TN90", "tasmin", 90.0, operator.gt, "mean")
hwa_tn90 = _heatwave_metric("HWA_TN90", "tasmin", 90.0, operator.gt, "peak")

hwn_ehf = _heatwave_metric("HWN_EHF", "tas", 90.0, operator.gt, "count")
hwf_ehf = _heatwave_metric("HWF_EHF", "tas", 90.0, operator.gt, "sum")
hwd_ehf = _heatwave_metric("HWD_EHF", "tas", 90.0, operator.gt, "max")
hwm_ehf = _heatwave_metric("HWM_EHF", "tas", 90.0, operator.gt, "mean")
hwa_ehf = _heatwave_metric("HWA_EHF", "tas", 90.0, operator.gt, "peak")


def _coldwave_metric(name: str, quantile: float, reduce: str):
    def _func(
        ds: xr.Dataset,
        historical_data_path: Optional[Path] = None,
        base_period: Tuple[str, str] = DEFAULT_BASE_PERIOD,
        window_days: int = 3,
        **_,
    ) -> xr.DataArray:
        if historical_data_path is None:
            raise ValueError(f"{name} requires 'historical_data_path'.")
        tas = _tasmin(ds)
        threshold = _align_dayofyear(tas, _percentile_threshold("tasmin", quantile, historical_data_path, base_period))
        mask = tas < threshold
        if reduce in {"count", "sum", "max"}:
            mode = reduce if reduce != "count" else "count"
            annual = _spell_stat_from_mask(mask, window_days, reduce=mode)
        elif reduce == "mean":
            annual = tas.where(mask).resample(time="YS").mean("time")
        else:
            annual = tas.where(mask).resample(time="YS").min("time")
        return annual.rename(name)

    return _func


cwn = _coldwave_metric("CWN", 10.0, "count")
cwf = _coldwave_metric("CWF", 10.0, "sum")
cwd_ecf = _coldwave_metric("CWD_ECF", 10.0, "max")
cwm = _coldwave_metric("CWM", 10.0, "mean")
cwa = _coldwave_metric("CWA", 10.0, "peak")


def wheeler_kiladis_filter(data):
    """
    Apply Wheeler-Kiladis filter to the data.
    This is a placeholder for a more complex implementation.
    """
    # Placeholder implementation
    if isinstance(data, xr.DataArray):
        return data.rolling(time=15, center=True).mean()
    else:
        raise TypeError("Input must be an xarray.DataArray")

def tx_wheeler_kiladis(ds, var='tasmax', **_):
    """
    Calculate the Wheeler-Kiladis filtered maximum temperature.
    
    Args:
        ds (xr.Dataset): Dataset containing the temperature variable.
        var (str): Name of the maximum temperature variable.
        
    Returns:
        xr.DataArray: Filtered maximum temperature.
    """
    if var not in ds:
        raise ValueError(f"Variable '{var}' not found in the dataset.")
    
    filtered_data = wheeler_kiladis_filter(ds[var])
    return filtered_data

# --------------------------------------------------------------------------------------
# Extreme Value Theory 
# --------------------------------------------------------------------------------------
def compute_statistic_return_level(values: xr.DataArray, return_period: int = 100):
    import scipy.stats as st
    data = values[~np.isnan(values)]
    
    c, loc, scale = st.genextreme.fit(data)
    
    p_prob = 1.0 / return_period
    q_prob = 1.0 - p_prob

    return st.genextreme.ppf(q_prob, c, loc=loc, scale=scale)

def fitted_return_level(var: xr.Dataset, return_period: int):
    block_maxima = var.groupby("time.year").max("time").rename({"year": "time"})
    if hasattr(block_maxima.data, "chunks"):
            block_maxima = block_maxima.chunk({"time": -1})
    return xr.apply_ufunc(
        compute_statistic_return_level,
        block_maxima,
        return_period,
        input_core_dims=[["time"], []],  
        vectorize=True,
        keep_attrs=True,
        dask="parallelized", 
        output_dtypes=[float],
    )

def tx50_return_level(ds: xr.Dataset, return_period: int = 50):
    return fitted_return_level(_tasmax(ds), return_period)


def tx100_return_level(ds: xr.Dataset, return_period: int = 100):
    return fitted_return_level(_tasmax(ds), return_period)


def tx200_return_level(ds: xr.Dataset, return_period: int = 200):
    return fitted_return_level(_tasmax(ds), return_period)


def tx500_return_level(ds: xr.Dataset, return_period: int = 500):
    return fitted_return_level(_tasmax(ds), return_period)


def tn50_return_level(ds: xr.Dataset, return_period: int = 50):
    return fitted_return_level(_tasmin(ds), return_period)


def tn100_return_level(ds: xr.Dataset, return_period: int = 100):
    return fitted_return_level(_tasmin(ds), return_period)


def tn200_return_level(ds: xr.Dataset, return_period: int = 200):
    return fitted_return_level(_tasmin(ds), return_period)


def tn500_return_level(ds: xr.Dataset, return_period: int = 500):
    return fitted_return_level(_tasmin(ds), return_period)


def pr50_return_level(ds: xr.Dataset, return_period: int = 50):
    return fitted_return_level(_pr(ds), return_period)


def pr100_return_level(ds: xr.Dataset, return_period: int = 100):
    return fitted_return_level(_pr(ds), return_period)


def pr200_return_level(ds: xr.Dataset, return_period: int = 200):
    return fitted_return_level(_pr(ds), return_period)


def pr500_return_level(ds: xr.Dataset, return_period: int = 500):
    return fitted_return_level(_pr(ds), return_period)

# --------------------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------------------

SELECTED_INDICES: Dict[str, Callable[[xr.Dataset], xr.DataArray]] = {
    "FD": fd,
    "SU": su,
    "ID": id_days,
    "TR": tr,
    "GSL": gsl,
    "TXx": txx,
    "TNn": tnn,
    "WSDI": wsdi,
    "CSDI": csdi,
    "Rx5day": rx5day,
    "CDD": cdd,
    "CWD": cwd,
    "R95p": r95p,
    "SDII": sdii,
    "R10mm": r10mm,
}


def _default_index_description(name: str) -> str:
    return name.replace("_", " ").upper()


INDEX_METADATA_XCLIM: Dict[str, Dict[str, str]] = {}
for key in SELECTED_INDICES.keys():
    override = INDEX_METADATA_OVERRIDES.get(key.upper(), {})
    INDEX_METADATA_XCLIM[key] = {
        "description": override.get("description", _default_index_description(key)),
        "unit": override.get("unit", ""),
    }

