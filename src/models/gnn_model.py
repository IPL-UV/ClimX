import pytorch_lightning as pl
import torch
import torch.nn as nn
from .emulator import Emulator
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
import xarray as xr
import logging
import matplotlib.pyplot as plt
from pytorch_lightning.callbacks import Callback, ModelCheckpoint, EarlyStopping
from torch.utils.data import  Dataset, IterableDataset, get_worker_info
from pathlib import Path
from tqdm import tqdm
import pytorch_lightning as pl
import torch
import torch.nn as nn
from torch_geometric.nn import GCNConv
from torch_geometric.loader import DataLoader as GeoDataLoader
from torch_geometric.loader.cluster import ClusterData, ClusterLoader


torch.set_float32_matmul_precision('medium')
logger = logging.getLogger(__name__)

class GNNDailyIterableDataset(IterableDataset):
    """Fast streaming dataset for daily GNN training.

    Instead of calling xarray .isel() per (t, lat, lon) sample (extremely slow),
    this iterates over time in small chunks and loads all pixels in one go, then
    yields pixel mini-batches.

    Each yielded item is already a batch:
      x: (batch_pixels, n_features, time_chunk)
      y: (batch_pixels, n_targets, time_chunk)
      lat_lon_idx: (batch_pixels,)
    """

    def __init__(
        self,
        X: xr.Dataset,
        y: xr.Dataset,
        time_chunk: int = 10,
        pixel_batch: int = 4096,
        shuffle_time: bool = True,
        dtype: str = 'float32',
        seed: int = 0,
    ):
        super().__init__()
        self.X = X
        self.y = y
        self.time_chunk = int(time_chunk)
        self.pixel_batch = int(pixel_batch)
        self.shuffle_time = bool(shuffle_time)
        self.dtype = str(dtype)
        self.seed = int(seed)

        self.feature_vars = list(self.X.data_vars)
        self.target_vars = list(self.y.data_vars)

        self.n_lat = int(self.X.sizes['lat'])
        self.n_lon = int(self.X.sizes['lon'])
        self.n_sample = int(self.X.sizes['sample'])
        self.n_pixels = self.n_lat * self.n_lon

    def __iter__(self):
        worker = get_worker_info()
        worker_id = 0 if worker is None else int(worker.id)
        num_workers = 1 if worker is None else int(worker.num_workers)

        rng = np.random.default_rng(self.seed + worker_id)

        # Partition time chunks across workers.
        time_starts = np.arange(0, self.n_sample, self.time_chunk, dtype=np.int64)
        time_starts = time_starts[worker_id::num_workers]
        if self.shuffle_time:
            rng.shuffle(time_starts)

        # Embedding index convention: flatten lat-major => lat_idx * n_lon + lon_idx.
        #lat_lon_idx = np.arange(self.n_pixels, dtype=np.int64)

        for t0 in time_starts:
            t1 = int(min(self.n_sample, t0 + self.time_chunk))
            t_len = int(t1 - t0)
            if t_len <= 0:
                continue

            X_block = self.X.isel(sample=slice(t0, t1))
            y_block = self.y.isel(sample=slice(t0, t1))

            # (feature, sample, lat, lon)
            x = (
                X_block.to_array(dim='feature_variable')
                .transpose('feature_variable', 'sample', 'lat', 'lon')
                .values
                .astype(self.dtype, copy=False)
            )
            # (target, sample, lat, lon)
            yt = (
                y_block.to_array(dim='target_variable')
                .transpose('target_variable', 'sample', 'lat', 'lon')
                .values
                .astype(self.dtype, copy=False)
            )

            # -> (pixels, features, time)
            x = x.reshape(x.shape[0], t_len, self.n_pixels).transpose(2, 0, 1)
            # -> (pixels, targets, time)
            yt = yt.reshape(yt.shape[0], t_len, self.n_pixels).transpose(2, 0, 1)

            # Yield pixel mini-batches.
            for p0 in range(0, self.n_pixels, self.pixel_batch):
                p1 = min(self.n_pixels, p0 + self.pixel_batch)
                xb = torch.from_numpy(x[p0:p1]).to(dtype=torch.float32)
                yb = torch.from_numpy(yt[p0:p1]).to(dtype=torch.float32)
                xb = xb.reshape(-1,1,  self.n_lat*self.n_lon, self.feature_vars.__len__()) # (batch_pixels, features, time)
                yb = yb.reshape(-1,1,  self.n_lat*self.n_lon, self.target_vars.__len__()) # (batch_pixels, targets, time)
                #ib = torch.from_numpy(lat_lon_idx[p0:p1]).to(dtype=torch.long)
                yield xb, yb #, ib

    def __len__(self):
        """Return an estimate of number of batches per epoch.

        PyTorch Lightning uses `len(dataloader)` to compute progress/ETA.
        For an IterableDataset this isn't required by PyTorch, but providing it
        makes the progress bar ETA much more accurate.
        """
        n_time_chunks = int((self.n_sample + self.time_chunk - 1) // self.time_chunk)
        n_pixel_batches = int((self.n_pixels + self.pixel_batch - 1) // self.pixel_batch)
        return n_time_chunks * n_pixel_batches

class LossHistoryCallback(Callback):
    def __init__(self):
        super().__init__()
        self.train_losses = []

    def on_train_epoch_end(self, trainer, pl_module):
        loss = trainer.callback_metrics.get('train_loss')
        if loss is not None:
            self.train_losses.append(loss.item())

import torch
import torch.nn as nn
import pytorch_lightning as pl

class ClimateGNN(pl.LightningModule):
    def __init__(self, edge_index, n_forcing_vars, n_target_vars, learning_rate=1e-3):
        super().__init__()
        self.save_hyperparameters()

        # Embedding layer for spatial context
        #self.embedding = nn.Embedding(n_lat * n_lon, embedding_dim)
        
        # Shared linear layers
        # Input size: forcing variables + the spatial embedding
        # self.fc1 = nn.Linear(n_forcing_vars , 128) #+ embedding_dim
        # self.fc2 = nn.Linear(128, 128)
        # self.fc3 = nn.Linear(128, n_target_vars)

        self.register_buffer("edge_index", edge_index)
        self.gcnconv1 = GCNConv(n_forcing_vars, 128)
        self.gcnconv2 = GCNConv(128, 128)
        self.gcnconv3 = GCNConv(128, n_target_vars)
        self.relu = nn.ReLU()
        print("ClimateGNN initialized")

        

    def forward(self, x):
        # x: [batch, features, time]
        # lat_lon_idx: [batch]
        #batch_size, n_features, n_time = x.shape

        # 1. Get spatial embedding: [batch, embedding_dim]
        #emb = self.embedding(lat_lon_idx) 

        # 2. Expand embedding across time: [batch, embedding_dim, time]
        # This gives every time step the same spatial context
        #emb = emb.unsqueeze(-1).repeat(1, 1, n_time)
        #emb = emb.unsqueeze(-1).expand(-1, -1, n_time)

        # 3. Concatenate along the feature dimension (dim=1)
        # Result: [batch, features + embedding_dim, time]
        #x_combined = torch.cat([x, emb], dim=1)

        # 4. Prepare for Linear Layers
        # Linear layers expect features at the end. 
        # Move time to dim 1: [batch, time, features_combined]
        #x_combined = x_combined.transpose(1, 2)

        # 5. Pass through MLP
        # x = self.relu(self.fc1(x_combined))
        # x = self.relu(self.fc2(x))
        # x = self.fc3(x) # Output: [batch, time, target_vars]

        # 6. Transpose back to match original time-last format
        # Result: [batch, target_vars, time]
        
        # Input: [batch, 1, latXlon, input_features]
        #print(x.shape, self.edge_index.shape)
        x = self.relu(self.gcnconv1(x, self.edge_index))
        x = self.relu(self.gcnconv2(x, self.edge_index))
        x = self.gcnconv3(x, self.edge_index)
        # Result: [batch, 1, latXlon, output_features]
        #print(x.shape)

        return x #.transpose(1, 2)

    def training_step(self, batch, batch_idx):
        #x, y, lat_lon_idx = batch
        x, y = batch
        y_hat = self(x) #, lat_lon_idx
        loss = nn.functional.mse_loss(y_hat, y)
        self.log('train_loss', loss, prog_bar=True, on_step=True, on_epoch=True)
        return loss

    def validation_step(self, batch, batch_idx):
        #x, y, lat_lon_idx = batch
        x, y = batch
        y_hat = self(x) #, lat_lon_idx
        loss = nn.functional.mse_loss(y_hat, y)
        self.log('val_loss', loss, prog_bar=True, on_step=True, on_epoch=True)
        return loss

    def configure_optimizers(self):
        return torch.optim.Adam(self.parameters(), lr=self.hparams.learning_rate)

class GNNBaseline(Emulator):
    def __init__(self, model_params):
        self.model = ClimateGNN(**model_params)
        self.trainer = None
        # Add a mapping for lat/lon to index
        #self.lat_lon_to_idx = {}
        self.lat_lon_precision = 6
        self.lat_lon_tolerance = 5e-4
        self.target_vars = None
        self.loss_history_callback = LossHistoryCallback()

    def fit(self, X_train, y_train, trainer_params, **kwargs):
        # Store target variable names
        self.target_vars = list(y_train.data_vars)

        # Prepare validation data (last 20 years)
        X_val = X_train.sel(time=slice('2080-01-01', '2100-12-31'))
        y_val = y_train.sel(time=slice('2080-01-01', '2100-12-31'))

        # Stack forcing_scenario and time into a single 'sample' dimension
        X_val_stacked = X_val.stack(sample=('forcing_scenario', 'time'))
        y_val_stacked = y_val.stack(sample=('forcing_scenario', 'time'))

        # Keep sample chunked so reads are small and sequential.
        X_val_stacked = X_val_stacked.chunk({"sample": trainer_params.get('time_chunk', 10)})
        y_val_stacked = y_val_stacked.chunk({"sample": trainer_params.get('time_chunk', 10)})

        # Prepare train data (first 80 years)
        X_train = X_train.sel(time=slice('2015-01-01', '2080-12-31'))
        y_train = y_train.sel(time=slice('2015-01-01', '2080-12-31'))

        # Stack forcing_scenario and time into a single 'sample' dimension
        X_train_stacked = X_train.stack(sample=('forcing_scenario', 'time'))
        y_train_stacked = y_train.stack(sample=('forcing_scenario', 'time'))

        # Keep sample chunked so reads are small and sequential.
        X_train_stacked = X_train_stacked.chunk({"sample": trainer_params.get('time_chunk', 10)})
        y_train_stacked = y_train_stacked.chunk({"sample": trainer_params.get('time_chunk', 10)})
        n_lat = int(X_train.sizes['lat'])
        n_lon = int(X_train.sizes['lon'])

        # Use the streaming dataset for efficiency.
        train_dataset = GNNDailyIterableDataset(
            X_train_stacked,
            y_train_stacked,
            time_chunk=trainer_params.get('time_chunk', 10),
            pixel_batch=int(trainer_params.get('pixel_batch', n_lat*n_lon*10)),#4096)),
            shuffle_time=True,
        )

        val_dataset = GNNDailyIterableDataset(
            X_val_stacked,
            y_val_stacked,
            time_chunk=trainer_params.get('time_chunk', 10),
            pixel_batch=int(trainer_params.get('pixel_batch', n_lat*n_lon*10)),#4096)),
            shuffle_time=True,
        )

        logger.info(trainer_params)
  
        trainer_params_with_callbacks = trainer_params.copy()
        model_path = trainer_params_with_callbacks.get('model_path')
        model_path = Path(model_path)
        model_path.mkdir(parents=True, exist_ok=True)

        # Prevent Lightning from creating `lightning_logs/version_*`.
        # The default logger is what creates those folders.
        trainer_params_with_callbacks.setdefault('default_root_dir', str(model_path))
        trainer_params_with_callbacks.setdefault('logger', False)

        callbacks = trainer_params_with_callbacks.get('callbacks', [])
        callbacks.append(self.loss_history_callback)
        
        # Add checkpoint callback to save best model based on training loss
        checkpoint_callback = ModelCheckpoint(
            monitor='train_loss_epoch',
            mode='min',
            save_top_k=1,
            dirpath=str(model_path),
            filename='best-model-{epoch:02d}-{train_loss_epoch:.4f}',
            save_last=True,
        )
        callbacks.append(checkpoint_callback)
        
        # Add early stopping to stop training when training loss stops improving
        early_stopping_callback = EarlyStopping(
            monitor='val_loss',
            mode='min',
            patience=5,
            verbose=True,
            min_delta=1e-4,
        )
        callbacks.append(early_stopping_callback)
        
        trainer_params_with_callbacks['callbacks'] = callbacks
        trainer_params_with_callbacks['reload_dataloaders_every_n_epochs'] = 1

        # Dataset yields pre-batched tensors; DataLoader should not add another batch dimension.
        train_dataloader = DataLoader(
            train_dataset,
            batch_size=None,
            num_workers= 16#int(trainer_params.get('num_workers', 0)),
        )
        val_dataloader = DataLoader(
            val_dataset,
            batch_size=None,
            num_workers= 16#int(trainer_params.get('num_workers', 0)),
        )
        
        logger.info("GNNBaseline ready to fit ...")
        trainer_params_with_callbacks.pop('batch_size', None)  # Remove batch_size if present
        trainer_params_with_callbacks.pop('model_path', None)  # Remove model_path if present
        self.trainer = pl.Trainer(**trainer_params_with_callbacks)

        self.trainer.fit(self.model, train_dataloader, val_dataloader)
        
        logger.info("GNNBaseline.fit completed.")
        if self.loss_history_callback.train_losses:
            final_loss = self.loss_history_callback.train_losses[-1]
            logger.info(f"Final training loss: {final_loss:.4f}")

    # def _lookup_lat_lon_index(self, lat: float, lon: float) -> int:
    #     lat = float(lat)
    #     lon = float(lon)

    #     for decimals in range(self.lat_lon_precision, 1, -1):
    #         key = (round(lat, decimals), round(lon, decimals))
    #         if key in self.lat_lon_to_idx:
    #             return self.lat_lon_to_idx[key]

    #     for (stored_lat, stored_lon), idx in self.lat_lon_to_idx.items():
    #         if abs(stored_lat - lat) <= self.lat_lon_tolerance and abs(stored_lon - lon) <= self.lat_lon_tolerance:
    #             return idx

    #     raise ValueError(
    #         f"Lat/lon coordinate ({lat:.6f}, {lon:.6f}) was unseen during training even after rounding "
    #         f"and tolerance (tol={self.lat_lon_tolerance})."
    #     )

    def predict(
        self,
        X: xr.Dataset,
        *,
        target_vars: list[str] | None = None,
        time_chunk: int = 1,
        pixel_batch: int = 192*288,
        out_path: str | Path | None = None,
        out_chunks: dict | None = None,
    ):
        """Predict without loading full X into memory.

        Streams over time in chunks and runs inference over pixels in mini-batches.
        If `out_path` is provided, predictions are written incrementally to a Zarr
        store and a dask-backed dataset is returned.

        Args:
            X: xarray Dataset with dims (time, lat, lon) or (sample, lat, lon).
               May also contain forcing_scenario; if size==1 it will be squeezed.
            time_chunk: number of time steps per read.
            pixel_batch: number of pixels per Torch batch.
            out_path: optional path to write scaled predictions as Zarr.
            out_chunks: optional chunking for the written Zarr (e.g. {'time': 365}).
        """
        self.model.eval()

        if target_vars is not None:
            self.target_vars = target_vars
        if self.target_vars is None:
            raise RuntimeError("The model must be fitted before predicting (target variable names unknown).")

        # Handle forcing_scenario dimension if it exists.
        if 'forcing_scenario' in X.dims:
            if int(X.sizes['forcing_scenario']) != 1:
                raise ValueError("predict() currently supports forcing_scenario of size 1; please select one scenario.")
            X = X.isel(forcing_scenario=0, drop=True)

        time_dim = 'time' if 'time' in X.dims else ('sample' if 'sample' in X.dims else None)
        if time_dim is None:
            raise ValueError("Expected X to have a 'time' or 'sample' dimension.")

        n_lat = int(X.sizes['lat'])
        n_lon = int(X.sizes['lon'])
        n_time = int(X.sizes[time_dim])
        n_pixels = n_lat * n_lon
        feature_vars = list(X.data_vars)
        n_features = len(feature_vars)
        n_targets = len(self.target_vars)

        # Embedding index convention: flatten lat-major => lat_idx * n_lon + lon_idx.
        #lat_lon_idx = np.arange(n_pixels, dtype=np.int64)

        device = self.model.device
        time_chunk = int(time_chunk)
        pixel_batch = int(pixel_batch)

        if out_chunks is None:
            out_chunks = {time_dim: time_chunk}

        if out_path is not None:
            out_path = Path(out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Making GNNBaseline predictions (streaming): time_dim=%s, time=%d, lat=%d, lon=%d, features=%d, targets=%d",
            time_dim,
            n_time,
            n_lat,
            n_lon,
            n_features,
            n_targets,
        )

        first_write = True
        pred_chunks: list[xr.Dataset] | None = None
        if out_path is None:
            logger.warning(
                "out_path was not provided; predictions will be assembled in-memory and may be very large "
                "(time=%d, lat=%d, lon=%d, targets=%d).",
                n_time,
                n_lat,
                n_lon,
                n_targets,
            )
            pred_chunks = []

        n_time_chunks = (n_time + time_chunk - 1) // time_chunk
        pbar = tqdm(total=n_time_chunks, desc="Predicting", unit="chunk")
        
        for t0 in range(0, n_time, time_chunk):
            t1 = min(n_time, t0 + time_chunk)
            t_len = int(t1 - t0)
            if t_len <= 0:
                continue

            X_block = X.isel({time_dim: slice(t0, t1)})

            # (features, time, lat, lon) -> numpy for this chunk only
            x = (
                X_block.to_array(dim='feature_variable')
                .transpose('feature_variable', time_dim, 'lat', 'lon')
                .values
                .astype(np.float32, copy=False)
            )
            # print(x.shape)
            # reshape to (pixels, features, time)
            x = x.reshape(n_features, t_len, n_pixels).transpose(2, 0, 1)

            pred_pixels = np.empty((n_pixels, n_targets, t_len), dtype=np.float32)

            with torch.no_grad():
                for p0 in range(0, n_pixels, pixel_batch):
                    p1 = min(n_pixels, p0 + pixel_batch)
                    xb = torch.from_numpy(x[p0:p1])
                    xb = xb.reshape(-1,1,  pixel_batch, n_features) # (batch_pixels, features, time) [batch, 1, latXlon, input_features]
                    xb = xb.to(device=device, dtype=torch.float32) #ib = torch.from_numpy(lat_lon_idx[p0:p1]).to(device=device, dtype=torch.long)
                    yb = self.model(xb) #, ib)  # (batch_pixels, targets, time)
                    # print('out shape:', yb.shape, pred_pixels.shape,  yb.reshape(-1, n_targets, t_len).shape)
                    pred_pixels[p0:p1] = yb.reshape(-1, n_targets, t_len).detach().to('cpu').numpy()

            # print('all run', pred_pixels.shape)
            # Build a Dataset chunk with dims (time, lat, lon)
            time_coord = X[time_dim].isel({time_dim: slice(t0, t1)})
            pred_chunk = xr.Dataset(coords={time_dim: time_coord, 'lat': X['lat'], 'lon': X['lon']})
            for i, var in enumerate(self.target_vars):
                arr = pred_pixels[:, i, :].T.reshape(t_len, n_lat, n_lon)
                pred_chunk[var] = (('time', 'lat', 'lon'), arr) if time_dim == 'time' else ((time_dim, 'lat', 'lon'), arr)

            # Write incrementally if requested.
            if out_path is not None:
                pred_chunk = pred_chunk.chunk(out_chunks)
                for v in pred_chunk.data_vars:
                    pred_chunk[v].encoding.clear()

                if first_write:
                    pred_chunk.to_zarr(out_path, mode='w')
                    first_write = False
                else:
                    pred_chunk.to_zarr(out_path, mode='a', append_dim=time_dim)
            else:
                pred_chunks.append(pred_chunk)
            
            pbar.update(1)
        
        pbar.close()

        if out_path is not None:
            # Return lazily loaded dataset.
            return xr.open_zarr(out_path, chunks=out_chunks)

        if pred_chunks is None or len(pred_chunks) == 0:
            coords = {time_dim: X[time_dim], 'lat': X['lat'], 'lon': X['lon']}
            return xr.Dataset(coords=coords)

        # Assemble full prediction dataset in memory.
        return xr.concat(pred_chunks, dim=time_dim)

    def save(self, path):
        # Saving logic for the PyTorch model
        self.trainer.save_checkpoint(path)
        logger.info(f"GNNBaseline model saved to {path}")

    def load(self, path):
        # Loading logic for the PyTorch model
        self.model = ClimateGNN.load_from_checkpoint(path)
        
        # Ensure model is on the correct device (GPU if available)
        if torch.cuda.is_available():
            self.model = self.model.cuda()
            logger.info(f"GNNBaseline model loaded from {path} and moved to GPU")
        else:
            logger.info(f"GNNBaseline model loaded from {path} (CPU mode)")

    def plot_loss(self, save_path=None):
        """Plots the training loss."""
        if not self.loss_history_callback.train_losses:
            logger.info("No loss history found. Please fit the model first.")
            return

        plt.figure(figsize=(10, 6))
        plt.plot(self.loss_history_callback.train_losses)
        plt.title("Training Loss per Epoch")
        plt.xlabel("Epoch")
        plt.ylabel("Loss")
        plt.grid(True)
        
        if save_path:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, bbox_inches='tight')
            logger.info(f"Loss plot saved to {save_path}")
            plt.close()
        else:
            plt.show()
