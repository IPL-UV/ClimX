from abc import ABC, abstractmethod
import inspect
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
from tqdm.auto import tqdm
from pathlib import Path
import xarray as xr

from ..visualization import utils as V
from ..data_preprocessing.preprocessing_utils import scale_variables, log_transform, stationarize
from .. import metrics as M
from .. import indices_xclim as I

logger = logging.getLogger(__name__)

class Emulator(ABC):
    """Abstract base class for all climate emulators."""

    @abstractmethod
    def fit(self, X_train, y_train, *args, **kwargs):
        """Train the model."""
        pass

    @abstractmethod
    def predict(self, X, *args, **kwargs):
        """Make predictions."""
        pass

    @abstractmethod
    def save(self, path):
        """Save the model."""
        pass

    @abstractmethod
    def load(self, path):
        """Load the model."""
        pass

    def evaluate(
        self,
        X_test,
        metadata,
        results_path,
        predictions_path,
        historical_data_path,
        TARGET_VARIABLES,
        LOAD_PREDICTIONS=False,
        compute_indices=True,
    ):
        """
        Evaluates the model and saves metrics and predictions.
        """

        if not LOAD_PREDICTIONS:
            logger.info("Making predictions...")
            y_pred_anomalies_scaled = self.predict(X_test, target_vars=TARGET_VARIABLES)

            logger.info("Reversing preprocessing for predictions...")
            
            # Unscale the variables
            scaling_params_config = metadata['scaling_params']['scaling_params']
            y_pred_anomalies = scale_variables(y_pred_anomalies_scaled, scaling_params_config, reverse=True)

            # Reverse stationarization if needed
            stationarization_mode = metadata.get('stationarization_mode', 'monthly')
            if stationarization_mode != 'none':
                climatology_path = Path(metadata['climatology_path'])
                if not climatology_path.exists():
                    raise FileNotFoundError(f"Climatology file not found at {climatology_path}")
                climatology = xr.open_dataset(climatology_path)
                y_pred_log_transformed = stationarize(
                    y_pred_anomalies, climatology, reverse=True, stationarization_mode=stationarization_mode
                )

                if 'time_month' in y_pred_log_transformed.dims:
                    y_pred_log_transformed = y_pred_log_transformed.isel(time_month=0, drop=True)
                if 'time_year' in y_pred_log_transformed.dims:
                    y_pred_log_transformed = y_pred_log_transformed.isel(time_year=0, drop=True)
                if 'month' in y_pred_log_transformed.dims:
                    y_pred_log_transformed = y_pred_log_transformed.isel(month=0, drop=True)
                if 'stat' in y_pred_log_transformed.dims:
                    y_pred_log_transformed = y_pred_log_transformed.isel(stat=0, drop=True)
            else:
                y_pred_log_transformed = y_pred_anomalies

            # Reverse log transform if needed
            log_transform_info = metadata['scaling_params'].get('_log_transform_info', {})
            y_pred = y_pred_log_transformed
            if log_transform_info:
                for var, info in log_transform_info.items():
                    if var in y_pred:
                        y_pred = log_transform(y_pred, [var], epsilon=info['epsilon'], reverse=True)
            else: 
                logger.error("No log transform info found in metadata")

            y_pred = y_pred.astype(np.float32).chunk({'time': 365})
            for var in y_pred.variables:
                y_pred[var].encoding.clear()
            logger.info(f"Saving predictions to {predictions_path}...")
            predictions_path.parent.mkdir(parents=True, exist_ok=True)
            y_pred.to_zarr(predictions_path, mode='w')
        else:
            logger.info(f"Loading predictions from {predictions_path}...")
            y_pred = xr.open_zarr(predictions_path, chunks={'time': 365})
        

        # Compute indices from predictions
        def _call_index_function(func, dataset, index_name):
            try:
                params = inspect.signature(func).parameters
            except (ValueError, TypeError):
                params = {}

            kwargs = {}
            if "historical_data_path" in params:
                if historical_data_path is None:
                    raise ValueError(
                        f"Index '{index_name}' requires 'historical_data_path' but none was provided."
                    )
                kwargs["historical_data_path"] = historical_data_path
            return func(dataset, **kwargs)

        def _strip_forcing_scenario(ds):
            if 'forcing_scenario' in ds.dims:
                ds = ds.isel(forcing_scenario=0, drop=True)
            if 'forcing_scenario' in ds.coords:
                ds = ds.drop_vars('forcing_scenario')
            return ds

        y_pred_for_indices = _strip_forcing_scenario(y_pred)

        indices_pred = {}
        if compute_indices:
            logger.info("Calculating indices...")
            bar = tqdm(I.SELECTED_INDICES.items(), desc="Calculating indices")
            for name, func in bar:    
                bar.set_description(f"Indices: {name}")
                index_pred = _call_index_function(func, y_pred_for_indices, name)
                indices_pred[name] = index_pred   
        else:
            logger.info("Indices skipped due to compute_indices=False")
    
        return y_pred, indices_pred

    def visualize(self, y_pred, indices_pred, save_dir, variables_to_plot, time_index, lat, lon):
        """
        Visualizes the model's predictions (no ground truth comparison).

        Produces a single plot per requested item (prediction only).
        """
        logger.info("Visualizing results...")
        save_dir.mkdir(parents=True, exist_ok=True)

        # Plot spatial maps and time series
        for var in variables_to_plot['y']:
            if var not in y_pred:
                continue

            # Select the data for the specific time index for plotting
            pred_da_time = y_pred[var].isel(time=time_index)

            if 'forcing_scenario' in pred_da_time.dims and pred_da_time.sizes['forcing_scenario'] == 1:
                pred_da = pred_da_time.squeeze('forcing_scenario')
            else:
                pred_da = pred_da_time

            # Check if data is now 2D before proceeding with spatial plots
            if pred_da.ndim != 2:
                logger.warning(
                    f"Cannot create spatial map for '{var}' because data is not 2D after time selection. "
                    f"Pred dims: {pred_da.dims}. Skipping map."
                )
            else:
                try:
                    date_str = pd.to_datetime(str(pred_da.time.values)).strftime('%Y-%m-%d')
                except Exception:
                    date_str = str(pred_da.time.values).split('T')[0]

                V.plot_spatial_maps(
                    [pred_da],
                    ['Prediction'],
                    save_dir / f"result_map_{var}_{date_str}.png",
                )

            pred_ts = y_pred[var].sel(lat=lat, lon=lon, method='nearest')
            if 'forcing_scenario' in pred_ts.dims:
                if pred_ts.sizes.get('forcing_scenario', 0) == 1:
                    pred_ts = pred_ts.squeeze('forcing_scenario')
                else:
                    pred_ts = pred_ts.isel(forcing_scenario=0)
            V.plot_timeseries(
                [pred_ts], ['Prediction'],
                f"Time Series for {var} at ({lat}, {lon})",
                save_dir / f"result_timeseries_{var}_{lat}_{lon}.png")
            
        logger.info(f"Visualizations of predictions saved to {save_dir}")

        logger.info("Visualizing indices...")

        for index_name in variables_to_plot['indices']:
            if index_name not in indices_pred:
                continue

            if 'forcing_scenario' in indices_pred[index_name].dims and indices_pred[index_name].sizes['forcing_scenario'] == 1:
                indices_pred[index_name] = indices_pred[index_name].squeeze('forcing_scenario')
            elif 'forcing_scenario' in indices_pred[index_name].dims:
                indices_pred[index_name] = indices_pred[index_name].isel(forcing_scenario=0)

            # Plot spatial map
            if 'lat' in indices_pred[index_name].coords or 'lon' in indices_pred[index_name].coords:
                if 'time' in indices_pred[index_name].coords:
                    pred_index_map = indices_pred[index_name].isel(time=time_index)
                else:
                    pred_index_map = indices_pred[index_name]
               
                if 'time' in pred_index_map.coords:
                    try:
                        date_str = pd.to_datetime(str(pred_index_map.time.values)).strftime('%Y-%m-%d')
                    except Exception:
                        date_str = str(pred_index_map.time.values).split('T')[0]
                else:
                    date_str = "static"

                V.plot_spatial_maps(
                    [pred_index_map],
                    ['Prediction'],
                    save_dir / f"index_map_{index_name}_{date_str}.png",
                )

            # Plot time series
            if 'time' in indices_pred[index_name].coords:
                if 'lat' in indices_pred[index_name].coords or 'lon' in indices_pred[index_name].coords:
                    pred_ts = indices_pred[index_name].sel(lat=lat, lon=lon, method='nearest')
                else:
                    pred_ts = indices_pred[index_name]

                if 'forcing_scenario' in pred_ts.dims:
                    if pred_ts.sizes.get('forcing_scenario', 0) == 1:
                        pred_ts = pred_ts.squeeze('forcing_scenario')
                    else:
                        pred_ts = pred_ts.isel(forcing_scenario=0)
                
                V.plot_timeseries(
                [pred_ts], ['Prediction'],
                f"Time Series for {index_name} at ({lat}, {lon})",
                save_dir / f"index_timeseries_{index_name}_{lat}_{lon}.png")
        
        logger.info(f"Visualizations of indices saved to {save_dir}")
                    

                
            

            
