import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import xarray as xr
import logging
import numpy as np
import gc
from scipy.interpolate import CubicSpline
from ..data_preprocessing.preprocessing import log_transform

# Set up logging
logger = logging.getLogger(__name__)

def periodic_spline_1d(y, x, x_new):
    """
    Helper for periodic spline interpolation.

    Args:
        y (np.ndarray): The y-values of the data points.
        x (np.ndarray): The x-values of the data points.
        x_new (np.ndarray): The x-values for which to compute the interpolated y-values.

    Returns:
        np.ndarray: The interpolated y-values.
    """
    spline = CubicSpline(x, y, bc_type='periodic')
    return spline(x_new)

def plot_spatial_maps(data_arrays, titles, save_path, common_cbar=False, specific_cbar_for_error=False):
    """
    Plots spatial maps of one or more data arrays.
    """
    if not isinstance(data_arrays, list):
        data_arrays = [data_arrays]
    if not isinstance(titles, list):
        titles = [titles]

    # --- Robustness Fix ---
    # Filter out any non-spatial data arrays *before* any plotting logic.
    valid_plots = []
    for i, da in enumerate(data_arrays):
        if 'lon' in da.coords and 'lat' in da.coords and da.ndim == 2:
            valid_plots.append({'da': da, 'title': titles[i]})
        else:
            logger.warning(
                f"Data array for '{titles[i]}' is not a 2D spatial plot. "
                f"Skipping map. Got dimensions: {da.dims}"
            )
            
    if not valid_plots:
        return

    data_arrays = [p['da'] for p in valid_plots]
    titles = [p['title'] for p in valid_plots]
    n_plots = len(data_arrays)

    fig, axes = plt.subplots(1, n_plots, figsize=(9*n_plots, 6), 
                           subplot_kw={'projection': ccrs.PlateCarree()},
                           constrained_layout=True)
    if n_plots == 1:
        axes = [axes]

    mappables = []
    
    # Determine color scales
    if specific_cbar_for_error and n_plots > 1:
        # Common scale for all but the last plot (the error plot)
        vmin_common = min(da.min().compute().item() for da in data_arrays[:-1] if da.ndim == 2)
        vmax_common = max(da.max().compute().item() for da in data_arrays[:-1] if da.ndim == 2)
        cmap_common = 'viridis'

        # Specific scale for the error plot
        error_da = data_arrays[-1]
        error_min = error_da.min().compute().item()
        error_max = error_da.max().compute().item()
        error_abs_max = max(abs(error_min), abs(error_max))
        vmin_error, vmax_error = -error_abs_max, error_abs_max
        cmap_error = 'RdBu_r'

        scales = [(vmin_common, vmax_common, cmap_common)] * (n_plots - 1) + [(vmin_error, vmax_error, cmap_error)]
    elif common_cbar:
        valid_arrays = [da for da in data_arrays if da.ndim == 2]
        vmin = min(da.min().compute().item() for da in valid_arrays)
        vmax = max(da.max().compute().item() for da in valid_arrays)
        if vmin < 0 and vmax > 0:
            abs_max = max(abs(vmin), abs(vmax))
            vmin, vmax = -abs_max, abs_max
            cmap = 'RdBu_r'
        else:
            cmap = 'viridis'
        scales = [(vmin, vmax, cmap)] * n_plots
    else:
        scales = [None] * n_plots

    for i, da in enumerate(data_arrays):
        
        # Determine plotting scales
        if scales[i] is None:
            # Individual scales if no common scale is set
            da_min = da.min().compute().item()
            da_max = da.max().compute().item()
            if 'Error' in titles[i] or 'error' in titles[i].lower() or 'diff' in titles[i].lower():
                abs_max = max(abs(da_min), abs(da_max))
                plot_vmin, plot_vmax = -abs_max, abs_max
                plot_cmap = 'RdBu_r'
            else:
                plot_vmin, plot_vmax = da_min, da_max
                plot_cmap = 'viridis'
        elif specific_cbar_for_error and i == n_plots - 1 and n_plots > 1:
            plot_vmin, plot_vmax, plot_cmap = scales[-1]
        else:
            plot_vmin, plot_vmax, plot_cmap = scales[i]

        im = da.plot.pcolormesh(ax=axes[i], transform=ccrs.PlateCarree(), 
                                vmin=plot_vmin, vmax=plot_vmax, 
                                cmap=plot_cmap, add_colorbar=False)
        mappables.append(im)
        axes[i].coastlines()
        axes[i].gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False)
        axes[i].set_title(titles[i])
    
    # Add colorbars
    if common_cbar:
        fig.colorbar(mappables[-1], ax=axes.ravel().tolist(), orientation='vertical', shrink=0.6, pad=0.1)
    else:
        # individual colorbars
        for i, mappable in enumerate(mappables):
            fig.colorbar(mappable, ax=axes[i], orientation='vertical', shrink=0.6, pad=0.1)

    plt.savefig(save_path, bbox_inches='tight')
    logger.info(f"Saved plot to {save_path}")
    plt.close(fig)

def plot_timeseries(data_arrays, labels, title, save_path):
    """
    Plots one or more time series on the same axes.

    Args:
        data_arrays (list of xr.DataArray): The time series arrays to plot.
        labels (list of str): A list of labels for each time series.
        title (str): The title for the plot.
        save_path (Path): The path to save the plot.
    """
    plt.figure(figsize=(18, 9))
    for da, label in zip(data_arrays, labels):
        da.plot(label=label)
    
    plt.title(title)
    plt.xlabel("Time")
    plt.ylabel("Value")
    plt.grid(True)
    plt.legend()
    
    plt.savefig(save_path, bbox_inches='tight')
    logger.info(f"Saved plot to {save_path}")
    plt.close()

def plot_stationarity_check(raw_data, anomaly_data, climatology_path, variables, lat, lon, save_dir, log_transform_vars, log_transform_epsilon):
    """
    Visualizes the effect of de-stationarization for a given list of variables and a location.
    Plots the raw data, the climatology, and the resulting anomaly.
    Handles log-transformation for specified variables and upsamples forcings for comparison.
    """
    save_dir.mkdir(parents=True, exist_ok=True)

    with xr.open_dataset(climatology_path) as climatology:
        for variable in variables:
            if variable not in raw_data or variable not in anomaly_data:
                logger.warning(f"Variable '{variable}' not found in raw or anomaly datasets. Skipping.")
                continue
            
            # Select the timeseries for a specific location
            raw_ts_original = raw_data[variable].sel(lat=lat, lon=lon, method='nearest').load()
            anomaly_ts = anomaly_data[variable].sel(lat=lat, lon=lon, method='nearest').load()

            # --- Handle different time coordinates in raw data (e.g., for aerosols) ---
            target_time_axis = anomaly_ts.time
            raw_ts = raw_ts_original
            if 'time' not in raw_ts.dims:
                source_time_dim = None
                if 'time_month' in raw_ts.dims:
                    source_time_dim = 'time_month'
                elif 'time_year' in raw_ts.dims:
                    source_time_dim = 'time_year'
                
                if source_time_dim:
                    logger.info(f"Upsampling '{variable}' from '{source_time_dim}' to daily for plotting.")
                    raw_ts = raw_ts.ffill(dim=source_time_dim).reindex(
                        {source_time_dim: target_time_axis.values}, method='ffill'
                    ).bfill(dim=source_time_dim).rename({source_time_dim: 'time'})
                else:
                    logger.warning(f"'{variable}' does not have a recognized time dimension. Skipping plot.")
                    continue

            # --- Get climatology on the same daily time axis ---
            daily_climatology_ts = None
            if variable in climatology:
                clim_var = climatology[variable].sel(lat=lat, lon=lon, method='nearest').load()
                if 'forcing_scenario' in clim_var.dims:
                    clim_var = clim_var.squeeze('forcing_scenario', drop=True)
                if 'stat' in clim_var.dims:
                    clim_var = clim_var.sel(stat='mean')
                
                if 'month' in clim_var.dims:
                    month_13 = clim_var.sel(month=1).assign_coords(month=13)
                    month_0 = clim_var.sel(month=12).assign_coords(month=0)
                    climatology_padded = xr.concat([month_0, clim_var, month_13], dim='month')
                    
                    dayofyear = raw_ts.time.dt.dayofyear
                    days_in_each_year = raw_ts.time.groupby("time.year").map(lambda arr: arr.dt.dayofyear.max())
                    days_in_year = days_in_each_year.sel(year=raw_ts.time.dt.year).reset_coords(drop=True)
                    target_month_coord = (dayofyear - 1) / (days_in_year - 1) * 11 + 1
                    
                    daily_climatology_ts = climatology_padded.interp(month=target_month_coord, method='cubic').drop_vars('month')
                elif 'dayofyear' in clim_var.dims:
                    daily_climatology_ts = clim_var.rename({'dayofyear':'time'}).reindex({'time': raw_ts.time.dt.dayofyear}, method='pad')
                
                if daily_climatology_ts is not None and variable in log_transform_vars:
                    temp_ds = xr.Dataset({variable: daily_climatology_ts})
                    daily_climatology_ts = log_transform(temp_ds, [variable], epsilon=log_transform_epsilon)[variable]

            # --- Plotting ---
            fig, axes = plt.subplots(2, 1, figsize=(20, 12), sharex=True)
            
            # Plot raw data and climatology on top axis
            y_label = "Value"
            raw_ts.plot(ax=axes[0], label='Raw Data (transformed if applicable)')
            if daily_climatology_ts is not None:
                daily_climatology_ts.plot(ax=axes[0], label='Climatology (transformed if applicable)', linestyle='--')
            axes[0].set_title(f'Raw Data vs. Climatology for {variable} at ({lat}, {lon})')
            axes[0].set_ylabel(y_label)
            axes[0].legend()
            axes[0].grid(True)
            
            # Plot anomaly on bottom axis
            anomaly_ts.plot(ax=axes[1], label='Anomaly (De-stationarized)')
            axes[1].axhline(0, color='gray', linestyle='--')
            axes[1].set_title(f'De-stationarized Anomaly for {variable}')
            axes[1].set_xlabel("Time")
            axes[1].set_ylabel("Anomaly")
            axes[1].legend()
            axes[1].grid(True)
            
            plt.tight_layout()
            save_path = save_dir / f'stationarity_check_{variable}_{lat}_{lon}.png'
            plt.savefig(save_path, bbox_inches='tight')
            logger.info(f"Saved stationarity check plot to {save_path}")
            plt.close(fig)

def plot_climatology(climatology_path, variables, lat, lon, save_dir):
    """
    Visualizes the climatology for a given list of variables and a location.
    If the climatology is monthly, it interpolates to daily.
    """
    save_dir.mkdir(parents=True, exist_ok=True)

    with xr.open_dataset(climatology_path) as climatology:
        for variable in variables:
            if variable not in climatology:
                logger.error(f"Variable {variable} not found in climatology file.")
                continue

            clim_var = climatology[variable].load()

            if 'forcing_scenario' in clim_var.dims:
                clim_var = clim_var.squeeze('forcing_scenario', drop=True)

            if 'stat' in clim_var.dims:
                clim_var = clim_var.sel(stat='mean')

            if 'month' in clim_var.dims:
                logger.info(f"Monthly climatology for {variable}. Interpolating to daily resolution...")
                
                # Append Jan data at the end to make it periodic
                periodic_clim = xr.concat([clim_var, clim_var.sel(month=1)], dim='month')
                periodic_clim['month'] = np.arange(1, 14)

                dayofyear_coord = np.arange(1, 366)
                target_month_coord = (dayofyear_coord - 1) / 365.0 * 12 + 1
                
                daily_climatology = xr.apply_ufunc(
                    periodic_spline_1d,
                    periodic_clim,
                    kwargs={'x': periodic_clim.month.values, 'x_new': target_month_coord},
                    input_core_dims=[['month']],
                    output_core_dims=[['dayofyear']],
                    exclude_dims={'month'},
                    vectorize=True,
                    dask='parallelized'
                ).assign_coords(dayofyear=dayofyear_coord)
            
            elif 'dayofyear' in clim_var.dims:
                daily_climatology = clim_var
            else:
                logger.error(f"Climatology for {variable} must have 'month' or 'dayofyear' dimension.")
                continue

            clim_ts = daily_climatology.sel(lat=lat, lon=lon, method='nearest')
            
            plt.figure(figsize=(18, 9))
            clim_ts.plot()
            
            plt.title(f"Daily Climatology for {variable} at ({lat}, {lon})")
            plt.xlabel("Day of Year")
            plt.ylabel("Value")
            plt.grid(True)
            
            save_path = save_dir / f'{variable}_{lat}_{lon}.png'
            plt.savefig(save_path, bbox_inches='tight')
            logger.info(f"Saved climatology plot to {save_path}")
            
            # Force garbage collection to free up memory
            plt.cla()
            plt.clf()
            plt.close('all')
            gc.collect() 