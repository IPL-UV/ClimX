import os
os.environ.setdefault("HDF5_USE_FILE_LOCKING", "FALSE")

from pathlib import Path
from src.utils.logging_utils import setup_logger, logging
setup_logger(logging.INFO)

logger = logging.getLogger(__name__)

data_path = Path('data/')
DATA_VERSION = 'lite' # Options: 'lite', 'full'

# --- Load the dataset ---
from src.utils.hugging_face_utils import open_climx_virtual_datasets
dataset = open_climx_virtual_datasets(data_path, DATA_VERSION)

# --- Preprocess the data (id needed) ---
from src.data_preprocessing.preprocessing import preprocess_test

preprocessing_path = Path(f"preprocessing_data_{DATA_VERSION}/") 


X_test, metadata_test = preprocess_test(
        dataset, 
        preprocessing_path=preprocessing_path,
        version='lite',
        scaling_params_path=preprocessing_path / f'scaling_params_{DATA_VERSION}.json',
        load_into_memory=True
)
import numpy as np
X_test = X_test.astype(np.float32).chunk({'time': 30, 'lat': -1, 'lon': -1})
print("Saving X_test...")
encoding = {var: {'zlib': False, '_FillValue': None} for var in X_test.data_vars}

X_test.to_netcdf(preprocessing_path / "X_test.nc", encoding=encoding, compute=False)