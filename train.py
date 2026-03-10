from pathlib import Path
import os

# Prevent common HDF5/netCDF deadlocks on shared filesystems (NFS/Lustre).
os.environ.setdefault("HDF5_USE_FILE_LOCKING", "FALSE")

import xarray as xr

from src.utils.logging_utils import setup_logger, logging
setup_logger(logging.INFO)

logger = logging.getLogger(__name__)

data_path = Path('data/')
DATA_VERSION = 'lite' # Options: 'lite', 'full'

# --- Load the dataset ---
from src.utils.hugging_face_utils import open_climx_virtual_datasets
dataset = open_climx_virtual_datasets(data_path, DATA_VERSION)

# --- Preprocess the data (id needed) ---
from src.data_preprocessing.preprocessing import preprocess_train

precomputed = False
preprocessing_path = Path(f"preprocessing_data_{DATA_VERSION}/")

if not precomputed:
    X_train, y_train, metadata = preprocess_train(
            dataset, 
            preprocessing_path=preprocessing_path,
            version=DATA_VERSION,
            scaling_params_path=None
    )
else:
    X_train = xr.open_dataset(preprocessing_path / 'X_train.nc')
    y_train = xr.open_dataset( preprocessing_path / 'y_train.nc')


# Define model to train
model_type = 'nn' # implemented options in models/: climatology, nn, gnn 

# Instantiate the appropriate model
if model_type == 'climatology':
    from src.models.climatology_model import ClimatologyBaseline
    emulator = ClimatologyBaseline()
    model_path = Path(f'models_{DATA_VERSION}') / f'{model_type}.nc'
    
elif model_type == 'nn':
    from src.models.nn_model import NNBaseline
    # NN model requires parameters at initialization
    model_params = {
        'n_lat': 192, # This should match the subsampled data
        'n_lon': 288, # This should match the subsampled data
        'n_forcing_vars': 12,
        'n_target_vars': 7,
        'learning_rate': 1e-3,
    }
    model_path = Path(f'models_{DATA_VERSION}') / f'{model_type}'
    trainer_params = {'max_epochs': 5, 'model_path': model_path} 

    emulator = NNBaseline(model_params)

elif model_type == 'gnn':
    pass
else:
    raise ValueError(f"Unknown model type: {model_type}")

print(f"Using '{model_type}' model. Model will be saved to: {model_path}")

# Fit the model
FIT_MODEL = True 

# Fit and save the model
if FIT_MODEL:
    emulator.fit(X_train, y_train, trainer_params=trainer_params)
    emulator.save(model_path)
    print(f"'{model_type}' model trained and saved to {model_path}")
else:
    # Load the model
    emulator.load(model_path)
    print(f"'{model_type}' model loaded from {model_path}")

# Plot the loss
if hasattr(emulator, 'plot_loss'):
    emulator.plot_loss()