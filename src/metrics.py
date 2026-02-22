import xarray as xr
import numpy as np

def pixel_wise_rmse(y_pred, y_true):
    """
    Calculates the pixel-wise Root Mean Squared Error.

    Args:
        y_pred (xr.DataArray or xr.Dataset): Predicted values.
        y_true (xr.DataArray or xr.Dataset): True values.

    Returns:
        xr.DataArray or xr.Dataset: The RMSE for each pixel.
    """
    return np.sqrt(((y_pred - y_true) ** 2).mean(dim='time'))

def pixel_wise_mae(y_pred, y_true):
    """
    Calculates the pixel-wise Mean Absolute Error.

    Args:
        y_pred (xr.DataArray or xr.Dataset): Predicted values.
        y_true (xr.DataArray or xr.Dataset): True values.

    Returns:
        xr.DataArray or xr.Dataset: The MAE for each pixel.
    """
    return np.abs((y_pred - y_true)).mean(dim='time')

def pixel_wise_r2(y_pred, y_true, dim='time'):
    """
    Calculates the coefficient of determination (R^2) along the specified dimension.
    """
    ss_res = ((y_pred - y_true) ** 2).sum(dim=dim)
    y_true_mean = y_true.mean(dim=dim)
    ss_tot = ((y_true - y_true_mean) ** 2).sum(dim=dim)

    valid = ss_tot != 0
    r2 = xr.where(valid, 1 - (ss_res / ss_tot), 0.0)
    return r2

# Dictionary to access all metric functions
SELECTED_METRICS = {
    'r2': pixel_wise_r2,
    'rmse': pixel_wise_rmse,
    'mae': pixel_wise_mae,
}


