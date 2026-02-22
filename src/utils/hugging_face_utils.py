from dataclasses import dataclass
import xarray as xr
from pathlib import Path
from typing import Iterable, Literal, Optional
from huggingface_hub import snapshot_download

DEFAULT_HF_DATASET_REPO_ID = "isp-uv-es/ClimX"
Variant = Literal["full", "lite"]

def get_dataset_from_hf(local_dir: Path, variant: str, *, repo_type: str = "dataset", revision: str | None = None,
                      allow_patterns: list[str] | None = None, ignore_patterns: list[str] | None = None ) -> Path:
    """Download a Hugging Face dataset snapshot into local_dir if it is missing.

    - Skips download if local_dir contains files and sentinel exists.
    - Uses HUGGINGFACE_HUB_TOKEN automatically if set in env.
    """
    data_path = Path(local_dir)

    # "Exists" means: folder has at least one file + sentinel created by this helper.
    local_has_files = data_path.exists() and any(data_path.iterdir())
    if local_has_files:
        print(f"Data already present: {data_path}")

    data_path.mkdir(parents=True, exist_ok=True)

    print(f"Downloading HF {repo_type} '{DEFAULT_HF_DATASET_REPO_ID}' → {data_path} ...")
    snapshot_download(
        repo_id=DEFAULT_HF_DATASET_REPO_ID,
        repo_type=repo_type,
        revision=revision,
        local_dir=str(data_path),
        allow_patterns=[f"{variant}/**"],
        local_dir_use_symlinks=False,
        ignore_patterns=ignore_patterns,
        resume_download=True,
    )
    print("Download complete.")

def _glob_sorted(d: Path, patterns: Iterable[str]) -> list[Path]:
    out: list[Path] = []
    for pat in patterns:
        out.extend(sorted(d.glob(pat)))
    # stable unique
    seen: set[Path] = set()
    uniq: list[Path] = []
    for p in out:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq

class MissingArtifactsError(FileNotFoundError):
    pass

def _as_path(p: str | Path) -> Path:
    return p if isinstance(p, Path) else Path(p)

@dataclass(frozen=True)
class ClimXVirtualDatasets:
    """
    Three datasets commonly used in notebooks.
    """

    hist: xr.Dataset
    train: xr.Dataset
    test_forcings: xr.Dataset


def open_climx_virtual_datasets(
    root_dir: str | Path,
    variant: Variant = "lite",
    *,
    engine: str = "netcdf4",
    chunks: object = "auto",
) -> ClimXVirtualDatasets:
    """
    Open the downloaded ClimX artifacts as three lazily-loaded "virtual" xarray Datasets:
      - hist: historical (targets + forcings)
      - train: projections train (targets + forcings) for non-ssp245 scenarios
      - test_forcings: ssp245 forcings only (no targets)

    `root_dir` can be the artifacts root containing `full/` and `lite/`, or the `full/`/`lite/` folder itself.
    """
    root = _as_path(root_dir)
    d = root / variant
    if not d.exists():
        raise MissingArtifactsError(f"Missing dataset directory: {d}")

    hist_files = _glob_sorted(d, ["*hist_train_*.nc", "*hist_train.nc"])
    train_files = _glob_sorted(d, ["*train_*.nc", "*train.nc"])
    # Ensure train does not accidentally include hist files
    train_files = [p for p in train_files if "hist_train" not in p.name]

    test_files = _glob_sorted(d, ["*test_forcings_ssp245.nc"])

    if not hist_files:
        raise MissingArtifactsError(f"No historical files found under {d} (expected '*hist_train*.nc').")
    if not train_files:
        raise MissingArtifactsError(f"No train files found under {d} (expected '*train*.nc', excluding hist).")
    if len(test_files) != 1:
        raise MissingArtifactsError(
            f"Expected exactly one test forcings file under {d} (matching '*test_forcings_ssp245.nc'), found {len(test_files)}."
        )

    ds_hist = xr.open_mfdataset([str(p) for p in hist_files], combine="by_coords", engine=engine, chunks=chunks, parallel=True)
    ds_train = xr.open_mfdataset([str(p) for p in train_files], combine="by_coords", engine=engine, chunks=chunks, parallel=True)
    ds_test = xr.open_dataset(str(test_files[0]), engine=engine, chunks=chunks)

    return ClimXVirtualDatasets(hist=ds_hist, train=ds_train, test_forcings=ds_test)