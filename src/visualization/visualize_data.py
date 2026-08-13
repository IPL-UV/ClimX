import xarray as xr
from pathlib import Path
import argparse
import logging
import pandas as pd
import re

from . import utils as V

# Set up logging
logger = logging.getLogger(__name__)


def _windows_safe_filename_component(value):
    """Return a filename component that is valid on Windows, macOS, and Linux."""
    component = re.sub(r'[<>:"/\\|?*]', '-', str(value))
    return component.rstrip(' .')

def visualize_data(data_path, save_dir, variables_to_plot, scenario, time_index, lat, lon):
    """
    Visualizes climate data by plotting maps and time series.
    """
    logger.info(f"Loading data from {data_path}...")
    ds = xr.open_zarr(data_path, consolidated=True)
    # Decode CF times to handle cftime objects and non-standard calendars.
    ds = xr.decode_cf(ds)
    
    for var in variables_to_plot:
        if var not in ds:
            logger.warning(f"Variable '{var}' not found in the dataset. Skipping.")
            continue
        
        da = ds[var]
        if 'forcing_scenario' in da.dims:
            # Select the scenario, taking the first index if coordinates are not unique.
            da = da.sel(forcing_scenario=scenario)
            if 'forcing_scenario' in da.dims:
                da = da.isel(forcing_scenario=0)

        # --- Plot spatial map at a given time step ---
        if 'lat' in da.dims and 'lon' in da.dims:
            # Select time step and handle different time coordinate names
            if 'time' in da.dims:
                time_coord = 'time'
            elif 'time_month' in da.dims:
                time_coord = 'time_month'
            else:
                logger.warning(f"No recognizable time dimension for spatial plot of '{var}'. Skipping.")
                continue
                
            da_snapshot = da.isel({time_coord: time_index})
            
            # Use a robust way to get the date string
            try:
                cftime_obj = da_snapshot[time_coord].values
                date_str = f"{cftime_obj.year}-{cftime_obj.month:02d}-{cftime_obj.day:02d}"
            except AttributeError:
                date_str = str(da_snapshot[time_coord].values).split('T')[0]

            title = f'{var} for {scenario} at {date_str}'
            safe_date = _windows_safe_filename_component(date_str)
            save_path = save_dir / f"data_map_{var}_{scenario}_{safe_date}.png"
            V.plot_spatial_maps([da_snapshot], [title], save_path)
        else:
            logger.info(f"Variable '{var}' is not spatial. Skipping map plot.")
            
        # --- Plot time series for a specific location ---
        if 'lat' in ds.dims and 'lon' in ds.dims:
            point_ds = ds.sel(lat=lat, lon=lon, method='nearest')
            point_da = point_ds[var].sel(forcing_scenario=scenario)
            if 'forcing_scenario' in point_da.dims:
                point_da = point_da.isel(forcing_scenario=0)
        else:
            # For non-spatial data, plot the global time series
            point_da = ds[var].sel(forcing_scenario=scenario)
            if 'forcing_scenario' in point_da.dims:
                point_da = point_da.isel(forcing_scenario=0)

        # Ensure there is a time dimension to plot
        time_dim_name = None
        for dim in ['time', 'time_month', 'time_year']:
            if dim in point_da.dims:
                time_dim_name = dim
                break

        if time_dim_name:
            # No conversion needed; xarray and matplotlib handle cftime natively.
            title = f'Time series of {var} at (lat={lat}, lon={lon}) for {scenario}'
            save_path = save_dir / f"data_timeseries_{var}_{scenario}_{lat}_{lon}.png"
            V.plot_timeseries([point_da], [var], title, save_path)
        else:
            logger.info(f"Variable '{var}' has no time dimension. Skipping time series plot.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize climate data from a Zarr store.")
    parser.add_argument('--data_path', type=str,
                        default='/data/users/climate_challenge/final/NorESM2-MM_r1i1p1f1_with_forcing_4x4_subsampled.zarr',
                        help='Path to the input (subsampled) Zarr dataset.')
    parser.add_argument('--save_dir', type=str, default='results/', help='Directory to save the plots.')
    parser.add_argument('--vars', nargs='+', default=['tas', 'pr'], help='List of variables to plot.')
    parser.add_argument('--scenario', type=str, default='ssp126', help='The climate scenario to plot.')
    parser.add_argument('--time_index', type=int, default=0, help='The integer index of the time step to plot for maps.')
    parser.add_argument('--lat', type=float, default=40.0, help='Latitude for time series plot.')
    parser.add_argument('--lon', type=float, default=-95.0, help='Longitude for time series plot.')

    args = parser.parse_args()

    data_input_path = Path(args.data_path)
    save_directory = Path('ClimateEmulation') / args.save_dir
    save_directory.mkdir(parents=True, exist_ok=True)
    
    visualize_data(data_input_path, save_directory, args.vars, args.scenario, args.time_index, args.lat, args.lon)
