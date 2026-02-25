import logging
import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)

def log_transform(data, variables, epsilon=1e-3, max_exponent=12, reverse=False):
    """
    Apply or reverse log transformation to specified variables.
    """
    data_transformed = data.copy()
    for var in variables:
        if not reverse:
            # Clip data at epsilon before log transform to avoid log of negative values, which creates NaNs.
            clipped_data = np.maximum(data_transformed[var], 0)
            data_transformed[var] = np.log(clipped_data + epsilon)
            logger.info(f"Log-transformed {var} with epsilon={epsilon}")
        else:
            # Clip data to max_exponent
            data_transformed[var] = np.minimum(data_transformed[var], max_exponent)
            data_transformed[var] = np.exp(data_transformed[var]) - epsilon
            # Ensure the result is non-negative
            data_transformed[var] = np.maximum(data_transformed[var], 0)
            logger.info(f"Reversed log-transform for {var} with epsilon={epsilon}")
    return data_transformed

def scale_variables(data, scaling_params_config, reverse=False):
    """
    Scale or unscale variables using global scaling parameters.
    """
    data_scaled = data.copy()
    for var, params in scaling_params_config.items():
        if var in data_scaled:
            if params['method'] == 'standardize':
                if 'mean' not in params or 'std' not in params:
                    logger.warning(f"Scaling parameters (mean/std) for '{var}' not found. Skipping scaling.")
                    continue
                
                mean = params['mean']
                std = params['std']

                if not reverse:
                    # Handle division by zero: where std is 0, the standardized value should be 0.
                    if std > 0:
                        data_scaled[var] = (data_scaled[var] - mean) / std
                    else:
                        data_scaled[var] = data_scaled[var] - mean
                    logger.info(f"Scaled {var} using standardize method")
                else:
                    data_scaled[var] = data_scaled[var] * std + mean
                    logger.info(f"Unscaled {var} using standardize method")
            else:
                logger.error(f"Unsupported scaling method: {params['method']}")
    return data_scaled


def monthly_climatology_to_daily(climatology: xr.Dataset, time: xr.DataArray) -> xr.Dataset:
    """Interpolate monthly climatology onto daily time axis. Extracted to avoid redundant computation."""
    climatology_mean = climatology.sel(stat='mean')
    month_13 = climatology_mean.sel(month=1).assign_coords(month=13)
    month_0 = climatology_mean.sel(month=12).assign_coords(month=0)
    climatology_padded = xr.concat([month_0, climatology_mean, month_13], dim='month')

    dayofyear = time.dt.dayofyear
    days_in_each_year = time.groupby("time.year").map(lambda arr: arr.dt.dayofyear.max())
    days_in_year = days_in_each_year.sel(year=time.dt.year).reset_coords(drop=True)
    target_month_coord = (dayofyear - 1) / (days_in_year - 1) * 11 + 1

    clim_interp_padded = climatology_padded.interp(month=target_month_coord, method='cubic')
    
    return clim_interp_padded


def _stationarize_single_scenario(data, climatology, reverse=False, stationarization_mode='monthly', daily_climatology=None):
    """Helper function to de-stationarize or re-stationarize a single scenario."""
    if 'monthly' in  stationarization_mode:
        

        '''if 'month' not in climatology.dims:
            raise ValueError("Stationarization mode is 'monthly' but climatology lacks 'month' dimension.")
    
        if daily_climatology is None:
            logger.info("Monthly climatology detected. Interpolating to daily resolution...")
            daily_climatology = _monthly_climatology_to_daily(climatology, data.time)'''
    
        if not reverse:
            processed_data = data - climatology.drop_vars(['month', 'stat'], errors='ignore')
        else:
            processed_data = data + climatology.drop_vars(['month', 'stat'], errors='ignore')
            
    elif stationarization_mode == 'daily':
        if 'dayofyear' not in climatology.dims:
            raise ValueError("Stationarization mode is 'daily' but climatology lacks 'dayofyear' dimension.")
        logger.info("Daily climatology detected.")
        climatology_mean = climatology.sel(stat='mean').drop_vars('stat')
        if not reverse:
            processed_data = data.groupby('time.dayofyear') - climatology_mean
        else:
            processed_data = data.groupby('time.dayofyear') + climatology_mean
    else:
        raise ValueError(f"Unsupported stationarization_mode: '{stationarization_mode}'")
    
    return processed_data.drop_vars('dayofyear', errors='ignore')


def stationarize(data, climatology, reverse=False, stationarization_mode='monthly'):
    """
    De-stationarizes or re-stationarizes variables by subtracting or adding climatology.

    Args:
        data (xr.Dataset): The data to process.
        climatology (xr.Dataset): The climatology data.
        reverse (bool): If False, de-stationarizes (subtracts climatology).
                        If True, re-stationarizes (adds climatology).
        stationarization_mode (str): The mode of stationarization ('monthly' or 'daily').
    """
    # The climatology is from historical data and should be applicable to all scenarios.
    # If 'forcing_scenario' is present, select the first index and drop the coordinate.
    if 'forcing_scenario' in climatology.dims:
        climatology = climatology.isel(forcing_scenario=0, drop=True)

    # Identify variables common to both data and climatology to avoid dropping variables
    common_vars = [var for var in data.data_vars if var in climatology.data_vars]
    data_to_stationarize = data[common_vars]

    data_to_keep = data.drop_vars(common_vars)
    
    logger.info(f"Variables to be stationarized: {common_vars}")
    logger.info(f"Variables to be kept without stationarization: {list(data_to_keep.data_vars)}")

    if not common_vars:
        logger.warning("No common variables found between data and climatology. Returning original data.")
        return data

    change_stationarization_mode = False
    if 'forcing_scenario' in data.dims:
        scenario_results = []
        
        # Precompute daily climatology once (shared time axis across scenarios)
        precomputed_daily = None
        for scenario in data.forcing_scenario.values:
            scenario_data = data_to_stationarize.sel(forcing_scenario=scenario)
            
            scenario_processed = _stationarize_single_scenario(
                scenario_data, climatology, reverse=reverse, stationarization_mode=stationarization_mode,
                daily_climatology=precomputed_daily
            )
            logger.info(f"Stationarized scenario '{scenario}': sizes={dict(scenario_processed.sizes)}")
            scenario_results.append(scenario_processed)
        
        stationarized_part = xr.concat(scenario_results, dim='forcing_scenario')
        stationarized_part = stationarized_part.assign_coords(forcing_scenario=data.forcing_scenario)
    else:
        stationarized_part = _stationarize_single_scenario(
            data_to_stationarize, climatology, reverse=reverse, stationarization_mode=stationarization_mode
        )

    logger.info("Merging stationarized data...")
    return xr.merge([stationarized_part, data_to_keep])


def upsample_forcing_to_daily(ds, forcing_vars, source_time_dim):
    """Upsample forcing variables to daily resolution.

    Important: `interp()` will produce NaNs outside the source time range by default.
    Those NaNs often lead to very expensive `ffill/bfill` passes over the full daily cube.
    We therefore extrapolate at the ends to avoid introducing gaps.
    """
    downsampled_forcings = ds[forcing_vars]

    try:
        resampled_ds = downsampled_forcings.interp(
            {source_time_dim: ds.time.values},
            method='linear',
            kwargs={'fill_value': 'extrapolate'},
        )
    except TypeError:
        # Older xarray versions may not accept `kwargs` here.
        resampled_ds = downsampled_forcings.interp(
            {source_time_dim: ds.time.values},
            method='linear',
        )

    return resampled_ds.rename({source_time_dim: 'time'})


def compute_climatology(ds: xr.Dataset, method: str = 'monthly'):
    """
    Computes climatology from a dataset.

    The structure of the returned climatology depends on the `method`:
    - 'monthly': Returns a Dataset with dimensions ('month', 'lat', 'lon', 'stat').
                 The 'stat' coordinate holds 'mean' and 'std'.
    - 'daily':   Returns a Dataset with dimensions ('dayofyear', 'lat', 'lon', 'stat').
                 This contains both mean and std.

    Args:
        ds (xr.Dataset): The dataset from which to compute the climatology.
        method (str): The method to use, either 'daily' or 'monthly'.

    Returns:
        xr.Dataset: The computed climatology.
    """
    if method == 'monthly':
        logger.info("Computing monthly climatology (mean and std)...")
        climatology_mean = ds.groupby('time.month').mean('time')
        climatology_std = ds.groupby('time.month').std('time')
        climatology_mean = climatology_mean.fillna(0)
        climatology_std = climatology_std.fillna(1)
        climatology_std = climatology_std.where(climatology_std != 0, 1)
        climatology = xr.concat(
            [climatology_mean.expand_dims(dim='stat'), climatology_std.expand_dims(dim='stat')],
            dim='stat'
        ).assign_coords(stat=['mean', 'std'])
    elif method == 'daily':
        logger.info("Computing daily climatology (mean and std)...")
        climatology_mean = ds.groupby('time.dayofyear').mean('time')
        climatology_std = ds.groupby('time.dayofyear').std('time')
        climatology_mean = climatology_mean.fillna(0)
        climatology_std = climatology_std.fillna(1)
        climatology_std = climatology_std.where(climatology_std != 0, 1)
        climatology = xr.concat(
            [climatology_mean.expand_dims(dim='stat'), climatology_std.expand_dims(dim='stat')],
            dim='stat'
        ).assign_coords(stat=['mean', 'std'])
    else:
        raise ValueError(f"Unsupported climatology method: '{method}'")
    return climatology


def compute_scaling_params(ds: xr.Dataset, target_vars: list[str], forcing_vars: list[str], 
                             aerosol_vars: list[str], log_transform_info: dict, aerosol_threshold: float = 0.1,
                             std_epsilon: float = 1e-9):
    """
    Computes global scaling parameters (mean and std) for variables.
    For aerosol variables, it ignores near-zero values to get more stable scaling parameters.
    For other variables, it ignores exact zero values.
    It correctly handles whether the aerosol data has been log-transformed or not.
    """
    all_vars = target_vars + forcing_vars
    
    logging.info("Computing scaling parameters for variables...")
    
    # Compute stats only for required variables (more efficient)
    ds_subset = ds[all_vars]
    means = ds_subset.mean(skipna=True)
    stds = ds_subset.std(skipna=True)

    # Extract scaling parameters
    scaling_params = {}
    for var in all_vars:
        mean_val = float(means[var].values.item())
        std_val = float(stds[var].values.item())
        scaling_params[var] = {'mean': mean_val, 'std': std_val}
        logging.info(f"Variable '{var}': mean={mean_val}, std={std_val}")
    return scaling_params
