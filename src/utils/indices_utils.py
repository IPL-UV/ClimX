import pandas as pd
import cftime
import datetime
from pathlib import Path
import xarray as xr
import numpy as np

def unify_calendar(da, calendar_type="standard"):
    """
    Convert the 'time' coordinate of a DataArray or Dataset to a consistent type.

    Parameters:
        da : xarray.DataArray or xarray.Dataset
        calendar_type : str
            "standard" (default): convert times to numpy.datetime64
            "noleap": convert times to cftime.DatetimeNoLeap

    Returns:
        xarray.DataArray or Dataset with unified time coordinate.
    """

    da = da.copy()
    times = da["time"].values
    new_times = []

    for t in times:
        # --- 1) cftime objects ---
        if isinstance(t, cftime.datetime):
            if calendar_type == "standard":
                # convert manually to python datetime
                new_times.append(datetime.datetime(t.year, t.month, t.day))
            else:  # keep as cftime
                new_times.append(cftime.DatetimeNoLeap(t.year, t.month, t.day))

        # --- 2) pandas.Timestamp ---
        elif isinstance(t, pd.Timestamp):
            if calendar_type == "noleap":
                new_times.append(cftime.DatetimeNoLeap(t.year, t.month, t.day))
            else:
                new_times.append(t.to_pydatetime())

        # --- 3) numpy.datetime64 ---
        elif isinstance(t, np.datetime64):
            dt = pd.to_datetime(t)
            if calendar_type == "noleap":
                new_times.append(cftime.DatetimeNoLeap(dt.year, dt.month, dt.day))
            else:
                new_times.append(dt.to_pydatetime())

        # --- 4) fallback: keep value ---
        else:
            new_times.append(t)

    # Write back with correct dtype
    if calendar_type == "standard":
        da["time"] = np.array(new_times, dtype="datetime64[ns]")
    else:
        da["time"] = new_times  # must remain object for cftime
    return da


def format_indices(indices_pred, model_type, DATA_VERSION, save_indices=True):

    for index_name in indices_pred.keys():
        indices_pred[index_name] = unify_calendar(indices_pred[index_name])

        if index_name in ['TXx', 'Rx5day']:
            indices_pred[index_name] = indices_pred[index_name].resample(time='YS').max()
        if index_name == 'TNn':
            indices_pred[index_name] = indices_pred[index_name].resample(time='YS').min()

    results_path = Path(f"results_{DATA_VERSION}")
    results_path.mkdir(exist_ok=True)

    # Save indices 
    if True:
        time_vals = indices_pred[list(indices_pred.keys())[0]].time
        for k, v in indices_pred.items():
            if 'forcing_scenario' in v.dims:
                indices_pred[k] = v.isel(forcing_scenario=0, drop=True)
        dataset_indices_pred = xr.Dataset(
            {k: v for k, v in indices_pred.items()})
        dataset_indices_pred.to_netcdf(results_path / f"{model_type}_indices.nc", engine='netcdf4')
    
    return indices_pred

