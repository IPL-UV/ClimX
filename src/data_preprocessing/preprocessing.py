from time import time
import xarray as xr
import numpy as np
import logging
import json
from pathlib import Path
import cftime
import pandas as pd

from .preprocessing_utils import log_transform, scale_variables, upsample_forcing_to_daily, stationarize, compute_climatology

logger = logging.getLogger(__name__)

TARGET_VARIABLES = ["huss", "pr", "psl", "sfcWind", "tas", "tasmax", "tasmin"]
FORCING_VARIABLES = ["BC_AX", "BC_N", "SO2", "SO4_PR", "OM_NI", "CO2_LBC", "N2O_LBC", "CH4_LBC", "CFC11eq_LBC", "CF2CL2_LBC"]
LOG_TRANSFORM_INFO = {
        "pr": {
            "epsilon": 1e-06
        },
        "huss": {
            "epsilon": 1e-06
        },
        "BC_AX": {
            "epsilon": 1e-06
        },
        "BC_N": {
            "epsilon": 1e-06
        },
        "SO2": {
            "epsilon": 1e-06
        },
        "SO4_PR": {
            "epsilon": 1e-06
        },
        "OM_NI": {
            "epsilon": 1e-06
        }
}


def preprocess_train(ds, preprocessing_path: Path, version: str, scaling_params_path: Path = None, load_into_memory: bool = True, stationarization_mode: str = 'monthly'):
    """
    Preprocesses the dataset for the model.
    """
    ds_hist = ds.hist
    ds = ds.train

    # Drop time_month and time_year dimensions/coordinates if they exist
    ds_hist = ds_hist.drop_vars(['time_month', 'time_year'], errors='ignore')

    # Then drop any remaining dimensions by selecting index 0 if they somehow remain
    if 'time_month' in ds_hist.dims:
        ds_hist = ds_hist.isel(time_month=0, drop=True)
    if 'time_year' in ds_hist.dims:
        ds_hist = ds_hist.isel(time_year=0, drop=True)


    if scaling_params_path is not None:
        with open(scaling_params_path, 'r') as f:
            scaling_params_data = json.load(f)
            scaling_params_config = scaling_params_data['scaling_params']
            target_vars = scaling_params_data['target_variables']
            forcing_vars = scaling_params_data['forcing_variables']
            log_transform_info = scaling_params_data.get('_log_transform_info', {})
    else:
        scaling_params_config = None
        target_vars = TARGET_VARIABLES
        forcing_vars = FORCING_VARIABLES
        log_transform_info = LOG_TRANSFORM_INFO
        scaling_params_path = preprocessing_path / f'scaling_parameters_{version}.json'

    # Separate forcing variables by their time dimension and availability
    available_yearly_forcings = [v for v in forcing_vars if v in ds and ('time_year' in ds[v].dims or 'year' in ds[v].dims)]
    available_monthly_forcings = [v for v in forcing_vars if v in ds and 'time_month' in ds[v].dims]
    available_daily_forcings = [v for v in forcing_vars if v in ds and 'time' in ds[v].dims]

    logger.info(f"All forcing variables from config: {forcing_vars}")
    logger.info(f"Available yearly forcings found in dataset: {available_yearly_forcings}")
    logger.info(f"Available monthly forcings found in dataset: {available_monthly_forcings}")
    logger.info(f"Available daily forcings found in dataset: {available_daily_forcings}")

    # Upsample yearly forcings to daily resolution
    ds_daily_from_yearly_list = []
    if available_yearly_forcings:
        for var in available_yearly_forcings:
            source_time_dim = 'time_year' if 'time_year' in ds[var].dims else 'year'
            logger.info(f"Upsampling '{var}' from '{source_time_dim}' dimension.")
            upsampled_var = upsample_forcing_to_daily(ds, [var], source_time_dim)
            ds_daily_from_yearly_list.append(upsampled_var)
    
    ds_daily_from_yearly = xr.merge(ds_daily_from_yearly_list) if ds_daily_from_yearly_list else xr.Dataset()

    # Upsample monthly forcings to daily resolution
    if available_monthly_forcings:
        ds_daily_from_monthly = upsample_forcing_to_daily(ds, available_monthly_forcings, 'time_month')
    else:
        ds_daily_from_monthly = xr.Dataset()

    X = xr.merge([ds[available_daily_forcings], ds_daily_from_yearly, ds_daily_from_monthly])
    
    # Drop time_month and time_year dimensions/coordinates if they exist
    # First try to drop as variables/coordinates
    X = X.drop_vars(['time_month', 'time_year'], errors='ignore')
    
    # Then drop any remaining dimensions by selecting index 0 if they somehow remain
    if 'time_month' in X.dims:
        X = X.isel(time_month=0, drop=True)
    if 'time_year' in X.dims:
        X = X.isel(time_year=0, drop=True)

    logger.info(f"Variables in X before stationarization: {sorted(list(X.data_vars))}")

    if load_into_memory:
        X = X.compute()

    y = ds[target_vars]
    
    # Apply log transform to both target and forcing variables as specified
    X_transformed, y_transformed = X, y
    del X, y

    if log_transform_info:
        # Get a unique list of variables to transform across X and y
        vars_to_transform = sorted(list(set(X_transformed.variables)| set(y_transformed.variables)))
        
        for var in vars_to_transform:
            if var in log_transform_info:
                info = log_transform_info[var]
                if var in X_transformed:
                    X_transformed = log_transform(X_transformed, [var], epsilon=info['epsilon'])
                if var in y_transformed:
                    y_transformed = log_transform(y_transformed, [var], epsilon=info['epsilon'])
    
    # Compute climatology if not computed yet
    climatology_path = preprocessing_path / f"climatology_{version}.nc"
    if climatology_path.exists():
        logger.info(f"Loading climatology from {climatology_path}...")
        climatology = xr.open_dataset(climatology_path).load()
    else:
        
        climatology_path.parent.mkdir(parents=True, exist_ok=True)
        # The historical data should not have a forcing_scenario dimension.
        # If it does, it's likely a remnant of pre-processing. Select the first index and drop the coord.
        if 'forcing_scenario' in ds_hist.dims:
            logger.warning("Found 'forcing_scenario' dimension in historical data. Selecting first scenario and dropping dimension.")
            ds_hist = ds_hist.isel(forcing_scenario=0, drop=True)

        # Select only available variables for log transform
        available_log_vars = [var for var in LOG_TRANSFORM_INFO.keys() if var in ds_hist]
        logger.info(f"Applying log transform to {available_log_vars}")
        # Clip data at 0 before log transform to avoid log of negative values, which creates NaNs.
        for var in available_log_vars:
            info = log_transform_info[var]
            ds_hist = log_transform(ds_hist, [var], epsilon=info['epsilon'])

        log_transform_info = {var: {'epsilon': epsilon} for var, epsilon in LOG_TRANSFORM_INFO.items()}

        if stationarization_mode != 'none':
            target_climatology = compute_climatology(ds_hist[target_vars], stationarization_mode)

            climatologies = [target_climatology]
            logger.info("Computing monthly climatology for daily forcing variables...")
            forcing_ds = ds_hist[FORCING_VARIABLES]
            # if np.issubdtype(forcing_ds.time_month.dtype, np.number):
            #     forcing_ds = xr.decode_cf(forcing_ds)
            forcing_climatology = compute_climatology(forcing_ds, 'monthly')
            
            climatologies.append(forcing_climatology)

            climatology = xr.merge(climatologies)

            logger.info(f"Saving climatology to {climatology_path}...")
            climatology.to_netcdf(climatology_path)
        else:
            climatology = xr.Dataset()

    # Release large source datasets after climatology has been handled.
    del ds, ds_hist

    # Stationarize data 
    if stationarization_mode != 'none':
        if 'monthly' in stationarization_mode:
            logger.info("Monthly climatology: precomputing daily interpolation once for all forcing_scenario values...")
            from src.data_preprocessing.preprocessing_utils import monthly_climatology_to_daily
            climatology = monthly_climatology_to_daily(climatology, X_transformed.time)

        logger.info(f"De-stationarizing variables using {stationarization_mode} climatology...")  
        X_anomalies = stationarize(X_transformed, climatology, reverse=False, stationarization_mode=stationarization_mode)
        del X_transformed
        y_anomalies = stationarize(y_transformed, climatology, reverse=False, stationarization_mode=stationarization_mode)
        del y_transformed
        
    else:
        logger.info("Skipping de-stationarization.")
        X_anomalies = X_transformed
        y_anomalies = y_transformed
    
    X_anomalies = X_anomalies.astype(np.float32).chunk({'time': 30, 'lat': -1, 'lon': -1})
    y_anomalies = y_anomalies.astype(np.float32).chunk({'time': 30, 'lat': -1, 'lon': -1})

    # Drop time_month and time_year dimensions/coordinates if they exist
    # First try to drop as variables/coordinates
    X_anomalies = X_anomalies.drop_vars(['time_month', 'time_year'], errors='ignore')
    
    # Then drop any remaining dimensions by selecting index 0 if they somehow remain
    if 'time_month' in X_anomalies.dims:
        X_anomalies = X_anomalies.isel(time_month=0, drop=True)
    if 'time_year' in X_anomalies.dims:
        X_anomalies = X_anomalies.isel(time_year=0, drop=True)
        
    # Compute scaling params if not computed yet
    if scaling_params_config is None :
        logger.info('Computing scaling parameters...')
        # Enforce exact coordinate alignment; fail loudly if X/y don't match in time/space.
        all_data = xr.merge([X_anomalies, y_anomalies], join='exact', compat='no_conflicts')
        from .preprocessing_utils import compute_scaling_params
        scaling_values = compute_scaling_params(all_data, target_vars, forcing_vars, 
                                               aerosol_vars=['BC_AX', 'BC_N', 'SO2', 'SO4_PR', 'OM_NI'],
                                               log_transform_info=log_transform_info)
        
        scaling_methods = {var: {'method': 'standardize'} for var in (target_vars + forcing_vars) if var in all_data}
        for var, values in scaling_values.items():
            if var in scaling_methods:
                scaling_methods[var].update(values)

        # Merge into existing JSON instead of overwriting other config fields.
        scaling_params_data = {}
        scaling_params_data['scaling_params'] = scaling_methods
        scaling_params_data['target_variables'] = target_vars
        scaling_params_data['forcing_variables'] = forcing_vars
        scaling_params_data['_log_transform_info'] = log_transform_info

        logger.info(f"Saving scaling parameters config to {scaling_params_path}...")
        with open(scaling_params_path, 'w') as f:
            json.dump(scaling_params_data, f, indent=4)
        del all_data

        # Use the newly computed config for the remaining preprocessing steps.
        scaling_params_config = scaling_params_data['scaling_params']

    logger.info("Scaling variables...")
    y_scaled = scale_variables(y_anomalies, scaling_params_config)
    X_scaled = scale_variables(X_anomalies, scaling_params_config)

    del X_anomalies, y_anomalies

    if load_into_memory:
        X_scaled = X_scaled.compute()
        y_scaled = y_scaled.compute()

    logger.info("Adding seasonal features...")
    seasonal_phase = 2 * np.pi * X_scaled.time.dt.dayofyear / 365.25
    X_scaled['sin_doy'] = np.sin(seasonal_phase).expand_dims({'lat': X_scaled.lat, 'lon': X_scaled.lon})
    X_scaled['cos_doy'] = np.cos(seasonal_phase).expand_dims({'lat': X_scaled.lat, 'lon': X_scaled.lon})
    X_scaled['sin_doy'] = X_scaled['sin_doy'].transpose(..., 'time', 'lat', 'lon')
    X_scaled['cos_doy'] = X_scaled['cos_doy'].transpose(..., 'time', 'lat', 'lon')
     
    logger.info(f"Final variables in X_scaled: {sorted(list(X_scaled.data_vars))}")
    
    if load_into_memory:
         X_scaled = X_scaled.compute()

    metadata = {
        'climatology_path': str(climatology_path),
        'scaling_params_path': str(scaling_params_path),
        'scaling_params': scaling_params_data, # Save the original config
        'stationarization_mode': stationarization_mode
    }
    
    return X_scaled, y_scaled, metadata 

def preprocess_test(ds, preprocessing_path: Path, version: str, scaling_params_path: Path = None, load_into_memory: bool = False, stationarization_mode: str = 'monthly'):
    """
    Preprocesses the dataset for the model.
    """
    ds = ds.test_forcings

    with open(scaling_params_path, 'r') as f:
        scaling_params_data = json.load(f)
        scaling_params_config = scaling_params_data['scaling_params']
        target_vars = scaling_params_data['target_variables']
        forcing_vars = scaling_params_data['forcing_variables']
        log_transform_info = scaling_params_data.get('_log_transform_info', {})
    

        # Separate forcing variables by their time dimension and availability
    available_yearly_forcings = [v for v in forcing_vars if v in ds and ('time_year' in ds[v].dims or 'year' in ds[v].dims)]
    available_monthly_forcings = [v for v in forcing_vars if v in ds and 'time_month' in ds[v].dims]
    available_daily_forcings = [v for v in forcing_vars if v in ds and 'time' in ds[v].dims]

    logger.info(f"All forcing variables from config: {forcing_vars}")
    logger.info(f"Available yearly forcings found in dataset: {available_yearly_forcings}")
    logger.info(f"Available monthly forcings found in dataset: {available_monthly_forcings}")
    logger.info(f"Available daily forcings found in dataset: {available_daily_forcings}")

    # Upsample yearly forcings to daily resolution
    ds_daily_from_yearly_list = []
    if available_yearly_forcings:
        for var in available_yearly_forcings:
            source_time_dim = 'time_year' if 'time_year' in ds[var].dims else 'year'
            logger.info(f"Upsampling '{var}' from '{source_time_dim}' dimension.")
            upsampled_var = upsample_forcing_to_daily(ds, [var], source_time_dim)
            ds_daily_from_yearly_list.append(upsampled_var)
    
    ds_daily_from_yearly = xr.merge(ds_daily_from_yearly_list) if ds_daily_from_yearly_list else xr.Dataset()

    # Upsample monthly forcings to daily resolution
    if available_monthly_forcings:
        ds_daily_from_monthly = upsample_forcing_to_daily(ds, available_monthly_forcings, 'time_month')
    else:
        ds_daily_from_monthly = xr.Dataset()

    X = xr.merge([ds[available_daily_forcings], ds_daily_from_yearly, ds_daily_from_monthly])
    
    # Drop time_month and time_year dimensions/coordinates if they exist
    # First try to drop as variables/coordinates
    X = X.drop_vars(['time_month', 'time_year'], errors='ignore')
    
    # Then drop any remaining dimensions by selecting index 0 if they somehow remain
    if 'time_month' in X.dims:
        X = X.isel(time_month=0, drop=True)
    if 'time_year' in X.dims:
        X = X.isel(time_year=0, drop=True)

    logger.info(f"Variables in X before stationarization: {sorted(list(X.data_vars))}")

    if load_into_memory:
        X = X.compute()
    
    # Apply log transform to both target and forcing variables as specified
    X_transformed = X
    del X, ds

    if log_transform_info:
        # Get a unique list of variables to transform across X and y
        vars_to_transform = sorted(list(set(X_transformed.variables)))
        
        for var in vars_to_transform:
            if var in log_transform_info:
                info = log_transform_info[var]
                if var in X_transformed:
                    X_transformed = log_transform(X_transformed, [var], epsilon=info['epsilon'])

    # Compute climatology if not computed yet
    climatology_path = preprocessing_path / f"climatology_{version}.nc"
    if not climatology_path.exists():
        raise FileNotFoundError(
            f"Climatology file not found at {climatology_path}. "
            "Run preprocess_train() first (or provide the correct preprocessing_path/version)."
        )
    logger.info(f"Loading climatology from {climatology_path}...")
    climatology = xr.open_dataset(climatology_path).load()

    # Stationarize data 
    if stationarization_mode != 'none':
        if 'monthly' in stationarization_mode:
            logger.info("Monthly climatology: precomputing daily interpolation once for all forcing_scenario values...")
            from src.data_preprocessing.preprocessing_utils import monthly_climatology_to_daily
            climatology = monthly_climatology_to_daily(climatology, X_transformed.time)

        logger.info('Converting to float32 before de-stationarization')
        X_transformed = X_transformed.astype(np.float32).chunk({'time': 30, 'lat': -1, 'lon': -1})
        logger.info(f"De-stationarizing variables using {stationarization_mode} climatology...")  
        X_anomalies = stationarize(X_transformed, climatology, reverse=False, stationarization_mode=stationarization_mode)
        del X_transformed

        
    else:
        logger.info("Skipping de-stationarization.")
        X_anomalies = X_transformed
        del X_transformed
    
    X_anomalies = X_anomalies.astype(np.float32).chunk({'time': 30, 'lat': -1, 'lon': -1})

    # Drop time_month and time_year dimensions/coordinates if they exist
    # First try to drop as variables/coordinates
    X_anomalies = X_anomalies.drop_vars(['time_month', 'time_year'], errors='ignore')
    
    # Then drop any remaining dimensions by selecting index 0 if they somehow remain
    if 'time_month' in X_anomalies.dims:
        X_anomalies = X_anomalies.isel(time_month=0, drop=True)
    if 'time_year' in X_anomalies.dims:
        X_anomalies = X_anomalies.isel(time_year=0, drop=True)

    logger.info("Scaling variables...")
    X_scaled = scale_variables(X_anomalies, scaling_params_config)

    del X_anomalies

    if load_into_memory:
        X_scaled = X_scaled.compute()

    logger.info("Adding seasonal features...")
    seasonal_phase = 2 * np.pi * X_scaled.time.dt.dayofyear / 365.25
    X_scaled['sin_doy'] = np.sin(seasonal_phase).expand_dims({'lat': X_scaled.lat, 'lon': X_scaled.lon})
    X_scaled['cos_doy'] = np.cos(seasonal_phase).expand_dims({'lat': X_scaled.lat, 'lon': X_scaled.lon})
    X_scaled['sin_doy'] = X_scaled['sin_doy'].transpose(..., 'time', 'lat', 'lon')
    X_scaled['cos_doy'] = X_scaled['cos_doy'].transpose(..., 'time', 'lat', 'lon')
     
    logger.info(f"Final variables in X_scaled: {sorted(list(X_scaled.data_vars))}")
    
    if load_into_memory:
         X_scaled = X_scaled.compute()

    metadata = {
        'climatology_path': str(climatology_path),
        'scaling_params_path': str(scaling_params_path),
        'scaling_params': scaling_params_data, # Save the original config
        'stationarization_mode': stationarization_mode
    }
    
    return X_scaled, metadata 