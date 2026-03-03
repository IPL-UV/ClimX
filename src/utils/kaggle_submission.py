from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
import xarray as xr


# ClimX leaderboard indices.
#
# NOTE: In our generated index datasets, indices are split into two xarrays:
# - yearly indices (12 variables, yearly time axis)
# - monthly indices (3 variables, monthly time axis)
#
# The Kaggle submission format code below supports either, and can infer which set
# to use from the provided xarray object.

# Monthly indices (as provided by `true_mon_idx` / `model_mon_idx`).
CLIMX_MONTHLY_INDEX_COLUMNS: tuple[str, ...] = (
    "TXx",
    "TNn",
    "Rx5day",
)

# Yearly indices (as provided by `true_year_idx` / `model_year_idx`).
CLIMX_YEARLY_INDEX_COLUMNS: tuple[str, ...] = (
    "SU",
    "TR",
    "FD",
    "ID",
    "WSDI",
    "CSDI",
    "GSL",
    "CDD",
    "CWD",
    # Precip tail index: some assets use `R95p` (observed in this repo);
    # older text/docs may refer to `R95pTOT`. We canonicalize to `R95p`.
    "R95p",
    "R10mm",
    "SDII",
)

# All indices in canonical order (monthly + yearly) = 15 targets.
CLIMX_INDEX_COLUMNS: tuple[str, ...] = (
    "TXx",
    "TNn",
    "SU",
    "TR",
    "FD",
    "ID",
    "WSDI",
    "CSDI",
    "GSL",
    "Rx5day",
    "CDD",
    "CWD",
    "R95p",
    "R10mm",
    "SDII",
)


def _available_index_names(obj: xr.Dataset | xr.DataArray, *, index_dim: str) -> list[str]:
    if isinstance(obj, xr.Dataset):
        return [str(v) for v in obj.data_vars]
    if not isinstance(obj, xr.DataArray):
        raise TypeError(f"Expected xarray Dataset or DataArray, got {type(obj)}")
    if index_dim not in obj.coords:
        return []
    return [str(x) for x in obj.coords[index_dim].values.tolist()]


def _names_contain_all(names: set[str], required: Sequence[str]) -> bool:
    """
    Membership check with a small alias for the `R95p` vs `R95pTOT` naming mismatch.
    """
    for c in required:
        if c in names:
            continue
        if c == "R95p" and "R95pTOT" in names:
            continue
        if c == "R95pTOT" and "R95p" in names:
            continue
        return False
    return True


def infer_climx_index_columns(
    obj: xr.Dataset | xr.DataArray,
    *,
    index_dim: str = "index",
) -> tuple[str, ...]:
    """
    Infer which ClimX index set (monthly/yearly/full) is represented by `obj`.
    """
    names = set(_available_index_names(obj, index_dim=index_dim))

    # Prefer the full set when possible.
    if _names_contain_all(names, CLIMX_INDEX_COLUMNS):
        return CLIMX_INDEX_COLUMNS
    if _names_contain_all(names, CLIMX_YEARLY_INDEX_COLUMNS):
        return CLIMX_YEARLY_INDEX_COLUMNS
    if _names_contain_all(names, CLIMX_MONTHLY_INDEX_COLUMNS):
        return CLIMX_MONTHLY_INDEX_COLUMNS

    raise ValueError(
        "Could not infer ClimX index set from object. "
        f"Available names={sorted(names)}; expected one of: "
        f"monthly={list(CLIMX_MONTHLY_INDEX_COLUMNS)}, "
        f"yearly={list(CLIMX_YEARLY_INDEX_COLUMNS)}, "
        f"all={list(CLIMX_INDEX_COLUMNS)}."
    )


def annualize_monthly_indices_to_yearly(
    monthly: xr.Dataset | xr.DataArray,
    *,
    time_dim: str = "time",
) -> xr.Dataset:
    """
    Aggregate the 3 monthly indices into annual indices (one value per year).

    This is useful when Kaggle expects a *single* annual index dataset with 15 targets,
    but you currently have 12 yearly indices + 3 monthly indices.

    Aggregation choices follow the natural ETCCDI-style semantics:
    - TXx (monthly max of daily max temperature) -> annual TXx = max over months
    - TNn (monthly min of daily min temperature) -> annual TNn = min over months
    - Rx5day (monthly max 5-day precip) -> annual Rx5day = max over months
    """
    ds = ensure_indices_dataset(monthly, index_columns=CLIMX_MONTHLY_INDEX_COLUMNS)

    if time_dim not in ds.dims:
        raise ValueError(f"Expected monthly indices to have dim {time_dim!r}; dims={list(ds.dims)}")

    # Ensure time is datetime-like for .groupby('time.year') even if stored as object.
    try:
        ds = ds.assign_coords({time_dim: pd.to_datetime(ds[time_dim].values)})
    except Exception:
        # If conversion fails, leave as-is; groupby may still work if dtype is datetime64.
        pass

    # Aggregate each variable individually to avoid DatasetGroupBy indexing issues
    reduced_vars = {}
    agg_map = {"TXx": "max", "TNn": "min", "Rx5day": "max"}
    for var, method in agg_map.items():
        if var in ds.data_vars:
            da = ds[var]
            g_var = da.groupby(f"{time_dim}.year")
            if method == "max":
                reduced_vars[var] = g_var.max(time_dim)
            else:
                reduced_vars[var] = g_var.min(time_dim)

    out = xr.Dataset(reduced_vars)

    # groupby creates a 'year' dimension; convert it to the expected annual 'time' axis
    # at Jan 1st of each year (to match the yearly dataset convention used elsewhere).
    if "year" in out.dims:
        years = [int(y) for y in out["year"].values.tolist()]
        out = out.rename({"year": time_dim})
        out = out.assign_coords({time_dim: np.array([np.datetime64(f"{y:04d}-01-01", "ns") for y in years])})

    return out


def merge_yearly_and_monthly_indices(
    yearly: xr.Dataset | xr.DataArray,
    monthly: xr.Dataset | xr.DataArray,
    *,
    annualize_monthly: bool = True,
    time_dim: str = "time",
) -> xr.Dataset:
    """
    Combine 12 yearly-index variables with 3 monthly-index variables into one Dataset.

    If `annualize_monthly=True`, the monthly dataset is aggregated to yearly first, so the
    result is a single annual dataset with 15 index variables (CLIMX_INDEX_COLUMNS).
    """
    yearly_ds = ensure_indices_dataset(yearly, index_columns=CLIMX_YEARLY_INDEX_COLUMNS)

    if annualize_monthly:
        monthly_annual = annualize_monthly_indices_to_yearly(monthly, time_dim=time_dim)
        # Align time coordinates (inner join) to avoid year mismatches.
        yearly_ds, monthly_annual = xr.align(yearly_ds, monthly_annual, join="inner")
        merged = xr.merge([yearly_ds, monthly_annual], compat="no_conflicts")
        return merged[list(CLIMX_INDEX_COLUMNS)]

    monthly_ds = ensure_indices_dataset(monthly, index_columns=CLIMX_MONTHLY_INDEX_COLUMNS)
    merged = xr.merge([yearly_ds, monthly_ds], compat="no_conflicts")
    return merged


def indices_pair_to_kaggle_dataframe(
    *,
    yearly: xr.Dataset | xr.DataArray,
    monthly: xr.Dataset | xr.DataArray,
    annualize_monthly: bool = True,
    grid: KaggleGridSpec | None = None,
    sort_coords: bool = True,
) -> pd.DataFrame:
    """
    Convenience wrapper to produce a *single* Kaggle dataframe from (yearly, monthly) index xarrays.

    By default, monthly indices are aggregated to yearly, yielding 15 annual targets.
    """
    merged = merge_yearly_and_monthly_indices(
        yearly, monthly, annualize_monthly=annualize_monthly
    )
    return indices_xr_to_kaggle_dataframe(
        merged, grid=grid, index_columns=CLIMX_INDEX_COLUMNS, sort_coords=sort_coords
    )

def _select_indices_with_aliases(ds: xr.Dataset, index_columns: Sequence[str]) -> xr.Dataset:
    """
    Select requested indices from a Dataset, allowing `R95p` <-> `R95pTOT` aliasing.
    Returns a Dataset whose variable names match `index_columns`.
    """
    src_vars: list[str] = []
    rename_map: dict[str, str] = {}
    for c in index_columns:
        if c in ds.data_vars:
            src_vars.append(c)
            continue
        if c == "R95p" and "R95pTOT" in ds.data_vars:
            src_vars.append("R95pTOT")
            rename_map["R95pTOT"] = "R95p"
            continue
        if c == "R95pTOT" and "R95p" in ds.data_vars:
            src_vars.append("R95p")
            rename_map["R95p"] = "R95pTOT"
            continue
        raise ValueError(f"Prediction dataset missing required index variable: {c!r}")

    out = ds[src_vars]
    if rename_map:
        out = out.rename(rename_map)
    # Ensure final variable order matches requested order.
    return out[list(index_columns)]


@dataclass(frozen=True)
class KaggleGridSpec:
    """Describes how an xarray submission should be flattened."""

    time_dim: str
    lat_dim: str
    lon_dim: str
    row_id_column: str = "row_id"

    def dims_order(self) -> tuple[str, str, str]:
        return (self.time_dim, self.lat_dim, self.lon_dim)


def _infer_dim(ds: xr.Dataset | xr.DataArray, candidates: Sequence[str]) -> str:
    for d in candidates:
        if d in ds.dims:
            return d
    raise ValueError(f"Could not infer dimension from candidates={list(candidates)}; dims={list(ds.dims)}")


def infer_kaggle_grid_spec(obj: xr.Dataset | xr.DataArray) -> KaggleGridSpec:
    """
    Infer common ClimX dimension names for annual index maps.

    We try a few common conventions:
    - time: 'time', 'time_year', 'year'
    - spatial: ('lat','lon') or ('y','x')
    """
    time_dim = _infer_dim(obj, ("time", "time_year", "year"))
    if "lat" in obj.dims and "lon" in obj.dims:
        lat_dim, lon_dim = "lat", "lon"
    elif "y" in obj.dims and "x" in obj.dims:
        lat_dim, lon_dim = "y", "x"
    else:
        raise ValueError(f"Could not infer spatial dims; expected (lat,lon) or (y,x). dims={list(obj.dims)}")
    return KaggleGridSpec(time_dim=time_dim, lat_dim=lat_dim, lon_dim=lon_dim)


def ensure_indices_dataset(
    pred: xr.Dataset | xr.DataArray,
    *,
    index_columns: Sequence[str] | None = CLIMX_INDEX_COLUMNS,
    index_dim: str = "index",
) -> xr.Dataset:
    """
    Convert a prediction object into a Dataset with one variable per index.

    Supported inputs:
    - Dataset with variables named like 'TXx', 'CDD', ...
    - DataArray with an 'index' (or custom) dimension whose coordinate values name the indices.
    """
    if index_columns is None:
        index_columns = infer_climx_index_columns(pred, index_dim=index_dim)

    if isinstance(pred, xr.Dataset):
        # Backwards-compatible behavior: if the default (all indices) was requested but the
        # dataset actually corresponds to a known subset (monthly/yearly), infer it.
        if index_columns == CLIMX_INDEX_COLUMNS:
            try:
                inferred = infer_climx_index_columns(pred, index_dim=index_dim)
            except Exception:
                inferred = CLIMX_INDEX_COLUMNS
            index_columns = inferred
        return _select_indices_with_aliases(pred, index_columns)

    if not isinstance(pred, xr.DataArray):
        raise TypeError(f"Expected xarray Dataset or DataArray, got {type(pred)}")

    if index_dim not in pred.dims:
        raise ValueError(f"Prediction DataArray must have dim {index_dim!r}. dims={list(pred.dims)}")

    if index_dim not in pred.coords:
        raise ValueError(f"Prediction DataArray must have coord {index_dim!r} naming indices.")

    # Backwards-compatible behavior: if the default (all indices) was requested but the
    # array actually corresponds to a known subset (monthly/yearly), infer it.
    if index_columns == CLIMX_INDEX_COLUMNS:
        try:
            inferred = infer_climx_index_columns(pred, index_dim=index_dim)
        except Exception:
            inferred = CLIMX_INDEX_COLUMNS
        index_columns = inferred

    index_values = [str(x) for x in pred.coords[index_dim].values.tolist()]
    names = set(index_values)
    if not _names_contain_all(names, index_columns):
        missing = [
            c
            for c in index_columns
            if c not in names
            and not (c == "R95p" and "R95pTOT" in names)
            and not (c == "R95pTOT" and "R95p" in names)
        ]
        raise ValueError(f"Prediction DataArray is missing required indices in coord {index_dim!r}: {missing}")

    # Select indices, allowing aliasing via a rename if needed.
    select_values: list[str] = []
    rename_map: dict[str, str] = {}
    for c in index_columns:
        if c in names:
            select_values.append(c)
        elif c == "R95p" and "R95pTOT" in names:
            select_values.append("R95pTOT")
            rename_map["R95pTOT"] = "R95p"
        elif c == "R95pTOT" and "R95p" in names:
            select_values.append("R95p")
            rename_map["R95p"] = "R95pTOT"

    ds = pred.sel({index_dim: select_values}).to_dataset(dim=index_dim)
    if rename_map:
        ds = ds.rename(rename_map)
    # Ensure variable names are exactly the index names (xarray uses coord values for names).
    ds = ds.rename({str(v): str(v) for v in ds.data_vars})
    return ds[list(index_columns)]


def indices_xr_to_kaggle_dataframe(
    pred: xr.Dataset | xr.DataArray,
    *,
    grid: KaggleGridSpec | None = None,
    index_columns: Sequence[str] | None = CLIMX_INDEX_COLUMNS,
    sort_coords: bool = True,
    fill_na_with_zero: bool = False,
) -> pd.DataFrame:
    """
    Flatten an xarray prediction of annual index maps into a Kaggle submission DataFrame.

    Output schema:
    - row_id column named by grid.row_id_column (default: 'row_id')
    - one column per index in `index_columns` (default: the 15 ClimX indices)

    The row_id is generated as 0..N-1 in a deterministic order:
    time-major, then latitude, then longitude (after optional coordinate sorting).
    """
    ds = ensure_indices_dataset(pred, index_columns=index_columns)

    if fill_na_with_zero:
        ds = ds.fillna(0.0)

    # If index_columns was None or a default that got inferred, align the local variable.
    if index_columns is None or index_columns == CLIMX_INDEX_COLUMNS:
        index_columns = tuple(ds.data_vars)
    if grid is None:
        grid = infer_kaggle_grid_spec(ds)

    # Keep only required variables and (optionally) sort coordinates for determinism.
    ds = ds[list(index_columns)]
    if sort_coords:
        for d in grid.dims_order():
            # Sort only if this coordinate exists and is sortable.
            if d in ds.coords:
                try:
                    ds = ds.sortby(d)
                except Exception:
                    # If sorting fails (e.g., unsortable dtype), keep original order.
                    pass

    # Stack into rows: (time, lat, lon) -> row
    stacked = ds.to_array("variable").transpose("variable", *grid.dims_order()).stack(
        row=grid.dims_order()
    )
    # stacked dims: variable x row
    arr = stacked.transpose("row", "variable").values  # shape: (N, n_vars)
    if arr.ndim != 2 or arr.shape[1] != len(index_columns):
        raise RuntimeError(f"Unexpected stacked array shape: {arr.shape}")

    df = pd.DataFrame(arr, columns=list(index_columns))
    if fill_na_with_zero:
        df = df.fillna(0.0)
    df.insert(0, grid.row_id_column, np.arange(len(df), dtype=np.int64))
    return df


def make_time_based_usage(
    ds: xr.Dataset | xr.DataArray,
    *,
    private_from_year: int = 3000,
    grid: KaggleGridSpec | None = None,
    sort_coords: bool = True,
) -> np.ndarray:
    """
    Generate a flat ``Usage`` array ("Public" / "Private") for a solution CSV.

    Rows are assigned in the same time-major order that
    ``indices_xr_to_kaggle_dataframe`` produces.  Any time step whose year is
    **strictly less than** ``private_from_year`` is labelled ``"Public"``; the
    rest are ``"Private"``.

    Parameters
    ----------
    ds:
        The xarray object that will be passed to ``write_kaggle_submission_csv``.
    private_from_year:
        First year (inclusive) whose rows are labelled ``"Private"``.
        Default is 3000, meaning **all rows are Public** unless you override it
        (e.g. ``private_from_year=2071`` to make the last 30 years private).
    grid:
        Spatial/time dimension spec.  Inferred when ``None``.
    sort_coords:
        Should match the ``sort_coords`` flag used in the CSV writer so that
        the row order is identical.
    """
    if grid is None:
        grid = infer_kaggle_grid_spec(ds)
    if sort_coords:
        for d in grid.dims_order():
            if d in ds.coords:
                try:
                    ds = ds.sortby(d)
                except Exception:
                    pass
    time_coords = ds.coords[grid.time_dim].values
    n_lat = ds.sizes[grid.lat_dim]
    n_lon = ds.sizes[grid.lon_dim]
    # Extract the year from each time coordinate robustly.
    years = pd.DatetimeIndex(time_coords).year
    usage_per_time = ["Public" if y < private_from_year else "Private" for y in years]
    # Repeat each time-step label for every (lat, lon) cell — time-major order.
    return np.array([label for label in usage_per_time for _ in range(n_lat * n_lon)])


def _build_submission_dataframe(
    pred: xr.Dataset | xr.DataArray,
    *,
    grid: KaggleGridSpec | None,
    index_columns: Sequence[str] | None,
    sort_coords: bool,
    include_row_id: bool,
    cast_integer_columns: bool,
    usage: str | Sequence[str] | None,
    stacklevel_offset: int = 0,
) -> pd.DataFrame:
    """
    Shared DataFrame builder used by both CSV and Parquet writers.

    Handles NaN-filling, float16→float64 upcast, integer casting, row_id
    stripping, and Usage column insertion. ``stacklevel_offset`` lets callers
    shift warning stack levels so warnings point at the public API call site.
    """
    import warnings

    df = indices_xr_to_kaggle_dataframe(
        pred,
        grid=grid,
        index_columns=index_columns,
        sort_coords=sort_coords,
        fill_na_with_zero=False,
    )
    value_cols = [c for c in df.columns if c != "row_id"]

    # Upcast low-precision floats (e.g. float16) to float64 to avoid overflow
    # in subsequent round() / comparison operations.
    for col in value_cols:
        if pd.api.types.is_float_dtype(df[col]) and df[col].dtype != np.float64:
            df[col] = df[col].astype(np.float64)

    null_cols = [c for c in value_cols if df[c].isnull().any()]
    if null_cols:
        warnings.warn(
            f"Submission contains NaN values in {len(null_cols)} target column(s) "
            f"({null_cols}); replacing with 0.0.",
            stacklevel=2 + stacklevel_offset,
        )
        df[null_cols] = df[null_cols].fillna(0.0)

    # Cast whole-number float columns to int64 (smaller on disk, cleaner output).
    if cast_integer_columns:
        for col in value_cols:
            s = df[col]
            if pd.api.types.is_float_dtype(s) and (s == s.astype(np.int64)).all():
                df[col] = s.astype(np.int64)

    # Optionally drop the row_id column.
    if not include_row_id and "row_id" in df.columns:
        df = df.drop(columns=["row_id"])

    # Insert Usage column (required for solution/GT files) right after row_id.
    if usage is not None:
        if isinstance(usage, str):
            usage_values: np.ndarray = np.full(len(df), usage)
        else:
            usage_values = np.asarray(usage)
        if len(usage_values) != len(df):
            raise ValueError(
                f"usage array length ({len(usage_values)}) does not match "
                f"number of rows ({len(df)})."
            )
        insert_pos = 1 if (include_row_id and "row_id" in df.columns) else 0
        df.insert(insert_pos, "Usage", usage_values)

    return df


def write_kaggle_submission_csv(
    pred: xr.Dataset | xr.DataArray,
    out_csv: str | Path,
    *,
    grid: KaggleGridSpec | None = None,
    index_columns: Sequence[str] | None = CLIMX_INDEX_COLUMNS,
    sort_coords: bool = True,
    float_format: str | None = None,
    decimal_places: int = 6,
    include_row_id: bool = True,
    cast_integer_columns: bool = True,
    usage: str | Sequence[str] | None = None,
) -> Path:
    """
    Write a Kaggle submission CSV for ClimX from an xarray prediction.

    NaN values in target columns are replaced with 0.0 with a warning.

    Parameters
    ----------
    decimal_places:
        Number of decimal places for float columns (default 6). Trailing zeros
        are stripped automatically (e.g. ``0.6`` not ``0.600000``). Ignored
        when ``float_format`` is provided explicitly.
    include_row_id:
        Whether to include the ``row_id`` column (default True).
    cast_integer_columns:
        Cast whole-number float columns to int64 (default True).
    usage:
        ``Usage`` column for solution/GT CSVs (``"Public"`` / ``"Private"`` /
        ``"Ignored"``). Use :func:`make_time_based_usage` for a year-based
        split. Leave ``None`` for participant submission files.

    Returns the written path.
    """
    df = _build_submission_dataframe(
        pred,
        grid=grid,
        index_columns=index_columns,
        sort_coords=sort_coords,
        include_row_id=include_row_id,
        cast_integer_columns=cast_integer_columns,
        usage=usage,
        stacklevel_offset=1,
    )

    # Round remaining float columns; Python's default repr strips trailing zeros.
    value_cols = [c for c in df.columns if c not in ("row_id", "Usage")]
    for col in value_cols:
        if pd.api.types.is_float_dtype(df[col]):
            df[col] = df[col].round(decimal_places)
    effective_float_format = float_format  # None → natural repr, no trailing zeros

    validate_kaggle_submission_dataframe(
        df, index_columns=None, require_row_id=include_row_id, has_usage=usage is not None
    )
    out_path = Path(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, float_format=effective_float_format)
    return out_path


def write_kaggle_submission_parquet(
    pred: xr.Dataset | xr.DataArray,
    out_parquet: str | Path,
    *,
    grid: KaggleGridSpec | None = None,
    index_columns: Sequence[str] | None = CLIMX_INDEX_COLUMNS,
    sort_coords: bool = True,
    include_row_id: bool = True,
    cast_integer_columns: bool = True,
    usage: str | Sequence[str] | None = None,
    compression: str = "snappy",
) -> Path:
    """
    Write a Kaggle submission Parquet file for ClimX from an xarray prediction.

    Parquet is preferred over CSV for large submissions: it is typically
    5–10× smaller, preserves integer/float dtypes natively, and is faster to
    read and write.  Kaggle accepts ``.parquet`` files directly as submissions.

    NaN values in target columns are replaced with 0.0 with a warning.

    Parameters
    ----------
    include_row_id:
        Whether to include the ``row_id`` column (default True).
    cast_integer_columns:
        Cast whole-number float columns to int64 (default True).
    usage:
        ``Usage`` column for solution/GT files. Use :func:`make_time_based_usage`
        for a year-based split. Leave ``None`` for participant submission files.
    compression:
        Parquet compression codec.  ``"snappy"`` (default) gives the best
        speed/size trade-off.  Other options: ``"gzip"``, ``"brotli"``,
        ``"zstd"``, ``None``.

    Returns the written path.
    """
    df = _build_submission_dataframe(
        pred,
        grid=grid,
        index_columns=index_columns,
        sort_coords=sort_coords,
        include_row_id=include_row_id,
        cast_integer_columns=cast_integer_columns,
        usage=usage,
        stacklevel_offset=1,
    )
    validate_kaggle_submission_dataframe(
        df, index_columns=None, require_row_id=include_row_id, has_usage=usage is not None
    )
    out_path = Path(out_parquet)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Write atomically to avoid producing truncated/corrupted files if the
    # process is interrupted mid-write (a common cause of missing Parquet footer).
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    if tmp_path.exists():
        try:
            tmp_path.unlink()
        except Exception:
            # Best-effort cleanup; we'll overwrite below if possible.
            pass

    # Force pyarrow for determinism across environments.
    df.to_parquet(tmp_path, index=False, compression=compression, engine="pyarrow")

    # Basic signature validation: Parquet files begin and end with b"PAR1".
    # If this fails, the file is not a valid parquet file (or is truncated).
    magic = b"PAR1"
    bs = tmp_path.read_bytes()
    if len(bs) < 8 or bs[:4] != magic or bs[-4:] != magic:
        raise OSError(
            "Parquet write produced an invalid file (missing PAR1 magic bytes). "
            "This usually indicates a truncated/corrupted write or a non-parquet output. "
            f"Wrote {tmp_path} ({tmp_path.stat().st_size} bytes)."
        )

    # Ensure pandas/pyarrow can read it back (catches some subtle filesystem issues).
    _ = pd.read_parquet(tmp_path, engine="pyarrow", columns=["row_id"] if include_row_id else None)

    tmp_path.replace(out_path)
    return out_path

def validate_kaggle_submission_dataframe(
    df: pd.DataFrame,
    *,
    row_id_column: str = "row_id",
    usage_column: str = "Usage",
    index_columns: Sequence[str] | None = CLIMX_INDEX_COLUMNS,
    require_row_id: bool = True,
    has_usage: bool = False,
) -> None:
    """
    Lightweight checks to catch common submission format issues locally.

    Parameters
    ----------
    require_row_id:
        When False, the ``row_id`` column is not required (and not checked).
    has_usage:
        When True, a ``Usage`` column is expected and validated.
    """
    if index_columns is None:
        # Validate against whichever known schema the dataframe matches.
        cols = set([str(c) for c in df.columns])
        for cand in (CLIMX_INDEX_COLUMNS, CLIMX_YEARLY_INDEX_COLUMNS, CLIMX_MONTHLY_INDEX_COLUMNS):
            if _names_contain_all(cols, cand):
                index_columns = cand
                break
        else:
            raise ValueError(
                "Could not infer submission index columns; "
                f"found columns={sorted(cols)}."
            )

    required = ([row_id_column] if require_row_id else []) + list(index_columns)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Submission is missing required columns: {missing}")
    allowed = {row_id_column, usage_column, *index_columns}
    extra = [c for c in df.columns if c not in allowed]
    if extra:
        raise ValueError(f"Submission has unexpected extra columns: {extra}")
    if require_row_id and row_id_column in df.columns:
        if not pd.api.types.is_integer_dtype(df[row_id_column]):
            raise ValueError(f"{row_id_column!r} must be integer dtype.")
        if df[row_id_column].isnull().any():
            raise ValueError(f"{row_id_column!r} contains nulls.")
    if has_usage:
        if usage_column not in df.columns:
            raise ValueError(f"Expected {usage_column!r} column but it is missing.")
        valid_usage = {"Public", "Private", "Ignored"}
        bad = set(df[usage_column].unique()) - valid_usage
        if bad:
            raise ValueError(f"{usage_column!r} contains invalid values: {bad}. Must be one of {valid_usage}.")
    if df[list(index_columns)].isnull().any().any():
        raise ValueError("One or more target columns contain nulls.")
    if not np.isfinite(df[list(index_columns)].to_numpy(dtype=np.float64, copy=False)).all():
        raise ValueError("Submission contains NaN or infinite values in target columns.")

