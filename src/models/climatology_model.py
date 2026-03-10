
import logging
import xarray as xr
import json
from tqdm import tqdm 
import numpy as np
import inspect

from .emulator import Emulator
from .. import metrics as M
from .. import indices_xclim as I
from ..visualization import utils as V

from src.data_preprocessing.preprocessing_utils import compute_climatology

# Set up logging
logger = logging.getLogger(__name__)

class ClimatologyBaseline(Emulator):
    """
    A baseline model that computes the historical means for each
    pixel in the spatial grid.
    """
    def __init__(self, climatology_path='./preprocessing_data_lite/climatology_lite.nc'):
        self.target_vars =  ['tas', 'tasmax', 'tasmin', 'pr', 'huss', 'psl', 'sfcWind']
        self.climatology_path = climatology_path

    def fit(self, X_train, y_train, trainer_params, load_into_memory=False, **kwargs):

        self.climatology = xr.open_dataset(self.climatology_path)
        
        
    def predict(self, X_test, load_into_memory=False):
        """
        Makes predictions using the historical means.

        Args:
            X_test (xr.Dataset): Forcing variables for the test period.
            load_into_memory (bool): If True, load all data into memory before prediction.
        Returns:
            xr.Dataset: Predicted target variables.
        """

        pred_period = xr.date_range(start="2014-11-01 12:00:00", end="2101-02-01 12:00:00", freq="D", calendar="noleap", use_cftime=True)
        pred_period_monthly = xr.date_range(start="2015-01-01", end="2101-01-01", freq="MS", calendar="noleap", use_cftime=True)
        selector = xr.DataArray(pred_period_monthly.month, dims=["time"], coords=[pred_period_monthly])

        interpolated_vars = []
        for var in self.target_vars:
            tmp_interpolated_var = self.climatology.sel(stat='mean')[var].sel(month=selector).interp(time=pred_period, method="cubic")
            tmp_interpolated_var.name = var
            interpolated_vars.append(tmp_interpolated_var)

        baseline_preds = xr.merge(interpolated_vars)
        baseline_preds = baseline_preds.sel(time=slice("2015-01-01 12:00:00", "2100-12-30 12:00:00"))

        return baseline_preds


    def save(self, path, format=None):
        """
        Saves the historical statistics

        Args:
            path (str): Path to save the model.
            format (str, optional): Format to use ('pkl' or 'nc').
                                   If None, inferred from file extension.
        """
        logger.info(f"Saving climatology to {path}...")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.climatology.to_netcdf(path)

    def load(self, path):
        """
        Loads the historical statistics.

        Args:
            path (str): Path to load the statistics from.
        """
        self.climatology = xr.open_dataset(path)

    def evaluate(self, X_test, metadata, results_path, predictions_path, historical_data_path, TARGET_VARIABLES=None, LOAD_PREDICTIONS=False, compute_indices=True):
        """
        Evaluates the model and saves metrics and predictions.
        """
        if not LOAD_PREDICTIONS:
            logger.info("Making predictions...")
            y_pred = self.predict(X_test)

            logger.info(f"Saving predictions to {predictions_path}...")
            predictions_path.parent.mkdir(parents=True, exist_ok=True)
            y_pred.to_zarr(predictions_path, mode='w')
        
        else:
            logger.info(f"Loading predictions from {predictions_path}...")
            y_pred = xr.open_zarr(predictions_path, chunks={'time': 365})
            
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
            logger.info("Calculating and evaluating indices...")
            bar = tqdm(I.SELECTED_INDICES.items(), desc="Calculating indices")
            for name, func in bar:
                bar.set_description(f"Indices: {name}")
                index_pred = _call_index_function(func, y_pred_for_indices, name)
                indices_pred[name] = index_pred

        else:
            logger.info("Indices skipped due to compute_indices=False")

        return y_pred, indices_pred