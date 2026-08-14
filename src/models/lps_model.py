import torch
import xarray as xr
import numpy as np
from pathlib import Path
import logging

from .emulator import Emulator

# Set up logging
logger = logging.getLogger(__name__)


def fit_lps_model(X_train, y_train, tas_ds=None, lat_name='lat', **kwargs):
    """
    Fits an LPSModel using the provided training data, similar to fit_linear_model.

    Args:
        X_train (xr.DataArray or xr.Dataset): Forcing variables (must include CO2)
        y_train (xr.DataArray or xr.Dataset): Target variable(s)
        tas_ds (xr.DataArray, optional): Surface air temperature, dims (time, lat, lon)
        lat_name (str): Name of latitude dimension
    Returns:
        LPSBaseline: Fitted model instance
    """
    model = LPSBaseline()
    model.fit(
        X_train=X_train,
        y_train=y_train,
        lat_name=lat_name,
        **kwargs,
    )
    return model


class LPSBaseline(Emulator):
    """
    Linear Pattern Scaling Model implemented in PyTorch.
    Predicts global mean tas from CO2, then predicts climate variable from predicted tas.
    """

    def __init__(self):
        self.w_local = torch.nn.Parameter(torch.tensor(0.0))
        self.b_local = torch.nn.Parameter(torch.tensor(0.0))
        self.W_global = torch.nn.Parameter(torch.tensor(0.0))
        self.B_global = torch.nn.Parameter(torch.tensor(0.0))
        self.device = torch.device('cpu')
        self.co2_var = None
        self.tas_var = None
        self.lat_name = None
        self.lon_name = None
        self._spatial_template = None

    @staticmethod
    def _iter_lstsq_sample_chunks(A, b, sample_chunk_size):
        """
        Yield sample chunks for batched least-squares accumulation.

        Args:
            A (torch.Tensor): Shape (batch, n_samples, n_features)
            b (torch.Tensor): Shape (batch, n_samples, ...)
            sample_chunk_size (int): Number of samples per chunk
        """
        n_samples = A.shape[1]
        for start in range(0, n_samples, sample_chunk_size):
            end = min(start + sample_chunk_size, n_samples)
            yield A[:, start:end, :], b[:, start:end, ...]

    @staticmethod
    def _solve_lstsq_with_sample_batching(A, b, sample_chunk_size):
        """
        Solve batched least squares by accumulating normal equations in chunks.

        Args:
            A (torch.Tensor): Shape (batch, n_samples, n_features)
            b (torch.Tensor): Shape (batch, n_samples, n_rhs)
            sample_chunk_size (int): Number of samples per chunk
        Returns:
            torch.Tensor: Solution with shape (batch, n_features, n_rhs)
        """
        if sample_chunk_size is None or sample_chunk_size <= 0:
            return torch.linalg.lstsq(A, b).solution

        batch_size = A.shape[0]
        n_features = A.shape[2]
        n_rhs = b.shape[2]
        device = A.device
        dtype = A.dtype

        AtA = torch.zeros(batch_size, n_features, n_features, device=device, dtype=dtype)
        Atb = torch.zeros(batch_size, n_features, n_rhs, device=device, dtype=dtype)

        loader = LPSBaseline._iter_lstsq_sample_chunks(A=A, b=b, sample_chunk_size=sample_chunk_size)
        for A_chunk, b_chunk in loader:
            At = A_chunk.transpose(-1, -2)
            AtA += At @ A_chunk
            Atb += At @ b_chunk

        return torch.linalg.lstsq(AtA, Atb).solution

    @staticmethod
    def _transpose_target(da, lat_name="lat", lon_name="lon", sample_dim="sample"):
        """
        Ensure a target DataArray has dimension order (sample, lat, lon)
        before converting to NumPy.
        """
        expected_dims = [sample_dim, lat_name, lon_name]
        missing_dims = [dim for dim in expected_dims if dim not in da.dims]
        if missing_dims:
            raise ValueError(
                f"Expected dims {expected_dims}, but missing {missing_dims}. Found dims: {da.dims}"
            )
        return da.transpose(sample_dim, lat_name, lon_name)

    @staticmethod
    def _transpose_co2(da, sample_dim="sample", lat_name="lat", lon_name="lon"):
        """
        Ensure CO2 has sample first. If lat/lon are present, keep them after sample.
        """
        ordered_dims = [sample_dim]
        for dim in (lat_name, lon_name):
            if dim in da.dims:
                ordered_dims.append(dim)
        remaining_dims = [dim for dim in da.dims if dim not in ordered_dims]
        ordered_dims.extend(remaining_dims)
        return da.transpose(*ordered_dims)

    def fit(
        self,
        X_train,
        y_train,
        co2_var="CO2_LBC",
        tas_var="tas",
        lat_name="lat",
        lon_name="lon",
        use_cuda=False,
        batch_samples=False,
        sample_chunk_size=2048,
        scenario_dim="forcing_scenario",
        **kwargs,
    ):
        """
        Fit the model parameters using training data.
        Flattens scenarios and stacks variables.
        Args:
            X_train (xr.Dataset or xr.DataArray): Forcing variables (must include CO2)
            y_train (xr.Dataset or xr.DataArray): Target variables
            co2_var (str): Name of CO2 variable in X_train
            tas_var (str): Name of tas variable in y_train
            lat_name (str): Name of latitude dimension
            scenario_dim (str): Name of scenario dimension to flatten
            variable_dim (str): Name of variable dimension to stack
        """
        logger.info("Starting LPSModel fit (multi-scenario, multi-variable)...")

        self.target_vars = list(y_train.data_vars)
        self.co2_var = co2_var
        self.tas_var = tas_var
        self.lat_name = lat_name
        self.lon_name = lon_name

        # Flatten scenarios for X and y by stacking scenario and time dimensions
        X_train_stacked = X_train.stack(sample=(scenario_dim, 'time'))
        y_train_stacked = y_train.stack(sample=(scenario_dim, 'time'))

        # Extract CO2 timeseries from a single pixel (lat=0, lon=0) across all samples
        co2_da = self._transpose_co2(
            X_train_stacked[co2_var],
            sample_dim="sample",
            lat_name=lat_name,
            lon_name=lon_name,
        )
        if lat_name in co2_da.dims and lon_name in co2_da.dims:
            co2_gm_train_np = co2_da.isel({lat_name: 0, lon_name: 0}).values.astype(np.float32)
        else:
            co2_gm_train_np = co2_da.values.astype(np.float32)

        # Extract tas and compute global mean using latitude-weighted average
        tas_da = self._transpose_target(
            y_train_stacked[tas_var],
            lat_name=lat_name,
            lon_name=lon_name,
            sample_dim="sample",
        )
        lat = tas_da[lat_name].values.astype(np.float32)
        weights = np.cos(np.deg2rad(lat))
        weights = weights / weights.sum()

        tas_stacked_vals = tas_da.values.astype(np.float32)  # (sample, lat, lon)
        n_samples, n_lat, n_lon = tas_stacked_vals.shape
        weights_2d = np.repeat(weights[:, np.newaxis], n_lon, axis=1)  # (lat, lon)
        tas_gm_train_np = np.average(tas_stacked_vals, axis=(1, 2), weights=weights_2d)  # (sample,)

        # Extract all target variables and reshape to (n_variables, sample, lat*lon)
        y_train_list = []
        for var in self.target_vars:
            var_da = self._transpose_target(
                y_train_stacked[var],
                lat_name=lat_name,
                lon_name=lon_name,
                sample_dim="sample",
            )
            var_vals = var_da.values.astype(np.float32)  # (sample, lat, lon)
            var_vals_flat = var_vals.reshape(n_samples, n_lat * n_lon)  # (sample, lat*lon)
            y_train_list.append(var_vals_flat)

        y_train_np = np.stack(y_train_list, axis=0)  # (n_variables, sample, lat*lon)

        # Convert to torch tensors
        co2_gm_train_torch = torch.from_numpy(co2_gm_train_np).float()
        tas_gm_train_torch = torch.from_numpy(tas_gm_train_np).float()
        y_train_torch = torch.from_numpy(y_train_np).float()

        # Store dimensions for prediction
        self._n_pixels = y_train_np.shape[2]
        self._n_variables = y_train_np.shape[0]
        self._lat_size = n_lat
        self._lon_size = n_lon

        if use_cuda and torch.cuda.is_available():
            self.device = torch.device("cuda")
            co2_gm_train_torch = co2_gm_train_torch.to(self.device)
            tas_gm_train_torch = tas_gm_train_torch.to(self.device)
            y_train_torch = y_train_torch.to(self.device)
        else:
            self.device = torch.device("cpu")

        # Fit global model: tas_gm = W_global * co2_gm + B_global
        logger.info("Fitting global model: tas_gm from CO2...")
        A_global = torch.stack([co2_gm_train_torch, torch.ones_like(co2_gm_train_torch)], dim=1)
        b_global = tas_gm_train_torch.unsqueeze(1)
        if batch_samples:
            A_global_batched = A_global.unsqueeze(0)
            b_global_batched = b_global.unsqueeze(0)
            solution_global = self._solve_lstsq_with_sample_batching(
                A=A_global_batched,
                b=b_global_batched,
                sample_chunk_size=sample_chunk_size,
            ).squeeze(0)
        else:
            solution_global = torch.linalg.lstsq(A_global, b_global).solution
        self.W_global.data = solution_global[0, 0]
        self.B_global.data = solution_global[1, 0]

        # Fit local model: y = w_local * tas_gm + b_local
        # Reshape for regression: (n_variables, n_samples, n_pixels)
        logger.info("Fitting local model: variables from tas_gm...")
        n_var = y_train_torch.shape[0]

        # Repeat tas_gm_train_torch 7 times in dimension 0: (n_samples,) -> (n_variables, n_samples)
        tas_gm_repeated = tas_gm_train_torch.unsqueeze(0).repeat(n_var, 1)  # (n_variables, n_samples)

        # Create A_local: (n_variables, n_samples, 2)
        A_local = torch.stack([tas_gm_repeated, torch.ones_like(tas_gm_repeated)], dim=2)  # (n_variables, n_samples, 2)

        if batch_samples:
            solution_local = self._solve_lstsq_with_sample_batching(
                A=A_local,
                b=y_train_torch,
                sample_chunk_size=sample_chunk_size,
            )
        else:
            solution_local = torch.linalg.lstsq(A_local, y_train_torch).solution

        self.w_local.data = solution_local[:, 0, :]
        self.b_local.data = solution_local[:, 1, :]

        logger.info("LPSModel fit complete.")

    def predict(self, X, *, target_vars: list[str] | None = None, variable_dim="data_vars"):
        """
        Predict climate variable(s) from CO2 input.
        Args:
            X (xr.Dataset or xr.DataArray): Forcing variables (must include CO2)
            variable_dim (str): Name of variable dimension in output
        Returns:
            xr.DataArray: Predicted variable(s), dims (time, lat, lon, variable)
        """
        logger.info("Predicting climate variable(s) from CO2 input...")

        # Extract CO2 from a single pixel, matching fit() behavior
        co2_da = self._transpose_co2(
            X[self.co2_var],
            sample_dim="time",
            lat_name=self.lat_name,
            lon_name=self.lon_name,
        )
        if self.lat_name in co2_da.dims and self.lon_name in co2_da.dims:
            co2_gm = co2_da.isel({self.lat_name: 0, self.lon_name: 0}).values.astype(np.float32)
        else:
            co2_gm = co2_da.values.astype(np.float32)

        co2_gm_tensor = torch.from_numpy(co2_gm).float().to(self.device)

        # Predict global mean tas: tas_gm = W_global * co2_gm + B_global
        tas_gm_pred = self.W_global * co2_gm_tensor + self.B_global

        # Compute local predictions: y_pred = w_local * tas_gm + b_local
        # Get dimensions stored during fit
        n_samples = co2_gm_tensor.shape[0]
        n_lat = X.sizes[self.lat_name]
        n_lon = X.sizes[self.lon_name]
        n_pixels = n_lat * n_lon
        try:
            n_variables = len(self.target_vars)
        except Exception:
            logging.warning("target_vars not set, defaulting to ['tas', 'tasmax', 'tasmin', 'pr', 'huss', 'psl', 'sfcWind'] variables")
            self.target_vars = ['tas', 'tasmax', 'tasmin', 'pr', 'huss', 'psl', 'sfcWind']
            n_variables = len(self.target_vars)

        # Expand tensors for broadcasting, matching fit() structure
        # w_local: (n_variables, n_pixels) -> (n_variables, n_pixels, 1)
        # tas_gm_pred: (n_samples,) -> (1, n_samples)
        w_local_expanded = self.w_local.unsqueeze(2)  # (n_variables, n_pixels, 1)
        tas_gm_expanded = tas_gm_pred.unsqueeze(0)  # (1, n_samples)
        b_local_expanded = self.b_local.unsqueeze(2)  # (n_variables, n_pixels, 1)

        # Compute y_pred: (n_variables, n_pixels, n_samples)
        y_pred = w_local_expanded * tas_gm_expanded + b_local_expanded

        y_pred_np = y_pred.detach().cpu().numpy()
        y_pred_np = np.transpose(y_pred_np, (0, 2, 1))  # (n_variables, n_samples, n_pixels)

        # Reshape from (n_variables, n_samples, n_pixels) to (n_variables, n_samples, n_lat, n_lon)
        y_pred_spatial = y_pred_np.reshape(n_variables, n_samples, n_lat, n_lon)

        # Transpose to (n_samples, n_lat, n_lon, n_variables)
        y_pred_final = np.transpose(y_pred_spatial, (1, 2, 3, 0))

        coords = {
            'time': X.time,
            self.lat_name: X[self.lat_name],
            self.lon_name: X[self.lon_name],
        }
        pred_ds = xr.Dataset(
            {
                var: (('time', self.lat_name, self.lon_name), y_pred_final[..., i])
                for i, var in enumerate(self.target_vars)
            },
            coords=coords
        )
        return pred_ds

    def save(self, path):
        logger.info(f"Saving LPSModel parameters to {path}...")
        torch.save({
            'w_local': self.w_local.data,
            'b_local': self.b_local.data,
            'W_global': self.W_global.data,
            'B_global': self.B_global.data,
            'co2_var': self.co2_var,
            'tas_var': self.tas_var,
            'lat_name': self.lat_name,
            'lon_name': self.lon_name,
            'target_vars': getattr(self, 'target_vars', None),
        }, path)
        logger.info("LPSModel parameters saved.")

    def load(self, path):
        logger.info(f"Loading LPSModel parameters from {path}...")
        params = torch.load(path)
        self.w_local.data = params['w_local']
        self.b_local.data = params['b_local']
        self.W_global.data = params['W_global']
        self.B_global.data = params['B_global']
        self.co2_var = params.get('co2_var', 'CO2_LBC')
        self.tas_var = params.get('tas_var', 'tas')
        self.lat_name = params.get('lat_name', 'lat')
        self.lon_name = params.get('lon_name', 'lon')
        self.target_vars = params.get('target_vars', None)
        logger.info("LPSModel parameters loaded.")
