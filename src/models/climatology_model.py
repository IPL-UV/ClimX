
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

# Set up logging
logger = logging.getLogger(__name__)

class ClimatologyBaseline(Emulator):
    """
    A baseline model that computes the historical means for each
    pixel in the spatial grid.
    """
    def __init__(self):
        self.historical_path = '/data/users/climate_challenge/final/NorESM2-MM_r1i1p1f1_with_forcing_fix_hist.zarr'
        self.target_vars =  ['tas', 'tasmax', 'tasmin', 'pr', 'huss', 'psl', 'sfcWind']

    def fit(self, X_train, y_train, load_into_memory=False, **kwargs):
        from src.data.process_climatology import compute_climatology

        hist_ds = xr.open_zarr(self.historical_path, consolidated=True)
        target_vars = list(y_train.data_vars)
        monthly_forcing_vars = ['BC_AX', 'BC_N', 'SO2', 'SO4_PR', 'OM_NI']        

        # The historical data should not have a forcing_scenario dimension.
        if 'forcing_scenario' in hist_ds.dims:
            hist_ds = hist_ds.isel(forcing_scenario=0, drop=True)


        target_climatology = compute_climatology(hist_ds[target_vars], 'monthly')

        climatologies = [target_climatology]
        if monthly_forcing_vars:
            logger.info("Computing monthly climatology for monthly forcing variables...")
            forcing_ds = hist_ds[monthly_forcing_vars].rename({'time_month': 'time'})
            if np.issubdtype(forcing_ds.time.dtype, np.number):
                forcing_ds = xr.decode_cf(forcing_ds)
            forcing_climatology = compute_climatology(forcing_ds, 'monthly')
            climatologies.append(forcing_climatology)
        
        self.climatology = xr.merge(climatologies)
        
        
    def predict(self, X_test, load_into_memory=False):
        """
        Makes predictions using the historical means.

        Args:
            X_test (xr.Dataset): Forcing variables for the test period.
            load_into_memory (bool): If True, load all data into memory before prediction.
        Returns:
            xr.Dataset: Predicted target variables.
        """
        self.load('/home/mariag/ClimateEmulation/models/climatology_monthly.nc')
        print(self.climatology)

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

    def evaluate(self, X_test, y_true_raw, metadata, results_path, predictions_path, historical_data_path, LOAD_PREDICTIONS=False, compute_metrics=True, compute_indices=True):
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

        results = {'metrics': {}, 'indices_metrics': {}}
        if compute_metrics:
            logger.info("Calculating metrics...")
            bar = tqdm(y_true_raw.data_vars, desc="Calculating metrics for variables")
            for var in bar:
                if var not in y_pred: continue
                results['metrics'][var] = {}
                for name, func in M.SELECTED_METRICS.items():
                    bar.set_description(f"Metrics for {var}: {name}")
                    #try:
                    if 'anomalies' in name:
                        climatology = xr.open_dataset('/home/mariag/ClimateEmulation/preprocessing_data/climatology.nc')
                        month = y_pred['time'].dt.month
                        pred_anom = (
                            y_pred[var]
                            - climatology[var].sel(stat='mean').sel(month=month)
                        ) / climatology[var].sel(stat='std').sel(month=month)

                        month = y_true_raw['time'].dt.month
                        target_anom = (
                            y_true_raw[var]
                            - climatology[var].sel(stat='mean').sel(month=month)
                        ) / climatology[var].sel(stat='std').sel(month=month)

                        '''import matplotlib.pyplot as plt
                        plt.plot(pred_anom.mean(dim=['lat', 'lon']).values, label='Predicted Anomalies')
                        plt.savefig(f'anomalies_check_{var}_pred.png')
                        plt.close()
                        plt.plot(target_anom.mean(dim=['lat', 'lon']).values, label='True Anomalies')
                        plt.savefig(f'anomalies_check_{var}_true.png')
                        plt.close()
                        results['metrics'][var][name] = func(pred_anom, target_anom).mean().compute().item()'''
                    else:
                        results['metrics'][var][name] = func(y_pred[var], y_true_raw[var]).mean().compute().item()
                        '''import matplotlib.pyplot as plt
                        plt.plot(y_pred[var].mean(dim=['lat', 'lon']).values, label='Predicted ')
                        plt.savefig(f'anomalies_not_check_{var}_pred.png')
                        plt.close()
                        plt.plot(y_true_raw[var].mean(dim=['lat', 'lon']).values, label='True')
                        plt.savefig(f'anomalies_not_check_{var}_true.png')
                        plt.close()'''
                    #except Exception as e:
                    #    results['metrics'][var][name] = 'error'
                    
        else:
            logger.info("Metrics skipped due to compute_metrics=False")
            
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

        def _scalar(value):
            if hasattr(value, "compute"):
                value = value.compute()
            if hasattr(value, "values"):
                value = value.values
            if hasattr(value, "item"):
                try:
                    value = value.item()
                except ValueError:
                    pass
            if isinstance(value, np.ndarray):
                if value.size == 1:
                    return float(value.ravel()[0])
                raise ValueError("Expected scalar value but received array.")
            return float(value)

        def _strip_forcing_scenario(ds):
            if 'forcing_scenario' in ds.dims:
                ds = ds.isel(forcing_scenario=0, drop=True)
            if 'forcing_scenario' in ds.coords:
                ds = ds.drop_vars('forcing_scenario')
            return ds

        y_true_for_indices = _strip_forcing_scenario(y_true_raw)
        y_pred_for_indices = _strip_forcing_scenario(y_pred)

        if compute_indices:
            logger.info("Calculating and evaluating indices...")
            bar = tqdm(I.SELECTED_INDICES.items(), desc="Calculating indices")
            indices_pred = {}
            indices_true = {}
            for name, func in bar:
                try:
                    bar.set_description(f"Indices: {name}")
                    index_true = _call_index_function(func, y_true_for_indices, name)
                    index_pred = _call_index_function(func, y_pred_for_indices, name)
                    indices_pred[name] = index_pred
                    indices_true[name] = index_true
                    metrics_entry = {}
                    '''if 'time' in index_true.dims:
                        rmse = _scalar(M.pixel_wise_rmse(index_pred, index_true).mean())
                        r2 = _scalar(M.r2_score(index_pred, index_true).mean())
                    else:
                        diff = index_pred - index_true
                        rmse = _scalar(np.sqrt(((diff) ** 2).mean()))
                        ss_res = _scalar(((diff) ** 2).sum())
                        centered = index_true - index_true.mean()
                        ss_tot = _scalar((centered ** 2).sum())
                        if ss_tot == 0:
                            r2 = float("nan")
                        else:
                            r2 = 1 - ss_res / ss_tot
                    metrics_entry['rmse'] = rmse
                    metrics_entry['r2'] = r2'''

                    if 'time' in index_true.dims:
                        mae = _scalar(M.pixel_wise_mae(index_pred, index_true).mean())
                    else:
                        mae = _scalar(np.abs(index_pred - index_true).mean())
                    metrics_entry['mae'] = mae

                    results['indices_metrics'][name] = metrics_entry
                except Exception as e:
                    results['indices_metrics'][name] = {'error': str(e)}
        else:
            logger.info("Indices skipped due to compute_indices=False")
            indices_pred = {}
            indices_true = {}

        def nan_to_none(d):
            if isinstance(d, dict): return {k: nan_to_none(v) for k, v in d.items()}
            if isinstance(d, list): return [nan_to_none(i) for i in d]
            if isinstance(d, float) and np.isnan(d): return None
            return d

        results = nan_to_none(results)

        logger.info(f"Saving results to {results_path}...")
        results_path.parent.mkdir(parents=True, exist_ok=True)
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=4)

        return y_pred, results, indices_pred, indices_true