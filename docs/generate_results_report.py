import json
import argparse
from pathlib import Path
import pandas as pd
import os
from typing import Optional, Union, Dict
from numbers import Number
import numpy as np

try:
    from ..indices import INDEX_METADATA as DEFAULT_INDEX_METADATA
except Exception:  # pragma: no cover
    DEFAULT_INDEX_METADATA = {}

try:
    from ..indices_xclim import INDEX_METADATA_XCLIM
except Exception:  # pragma: no cover
    INDEX_METADATA_XCLIM = {}

try:
    from ..index_metadata import INDEX_METADATA_OVERRIDES
except Exception:  # pragma: no cover
    try:
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        from index_metadata import INDEX_METADATA_OVERRIDES
    except Exception:
        INDEX_METADATA_OVERRIDES = {}


def create_image_table(image_list, image_dir, md_file_path):
    """Creates a markdown table for a list of images."""
    table_md = ""
    # create pairs of images
    pairs = [image_list[i : i + 2] for i in range(0, len(image_list), 2)]

    for pair in pairs:
        # Header row with filenames
        header_cells = []
        for img_path in pair:
            header_cells.append(f'<td align="center"><b>{img_path.name}</b></td>')
        if len(header_cells) == 1:
            header_cells.append('<td align="center"></td>')
        table_md += "  <tr>\n" + "\n".join(header_cells) + "\n  </tr>\n"

        # Image row
        img_cells = []
        for img_path in pair:
            # Make image path relative to the markdown file location
            relative_img_path = os.path.relpath(img_path, md_file_path.parent)
            img_cells.append(
                f'<td><img src="{relative_img_path}" width="100%"></td>'
            )
        if len(img_cells) == 1:
            img_cells.append("<td></td>")
        table_md += "  <tr>\n" + "\n".join(img_cells) + "\n  </tr>\n"

    return "<table>\n" + table_md + "</table>\n"


def format_visuals_section(image_dir, md_file_path):
    """Formats the visual results section with all images."""
    content = []

    # Find and sort all images
    maps = sorted([f for f in image_dir.glob("result_map_*.png")])
    timeseries = sorted([f for f in image_dir.glob("result_timeseries_*.png")])
    scatter = sorted([f for f in image_dir.glob("result_scatter_*.png")])
    other_visuals = sorted(
        [
            f
            for f in image_dir.glob("*.png")
            if f not in maps and f not in timeseries and f not in scatter
        ]
    )

    if maps:
        content.append("#### Spatial Comparison Maps\n")
        content.append(create_image_table(maps, image_dir, md_file_path))
    if timeseries:
        content.append("#### Time Series Comparisons\n")
        content.append(create_image_table(timeseries, image_dir, md_file_path))
    if scatter:
        content.append("#### Scatter Plots\n")
        content.append(create_image_table(scatter, image_dir, md_file_path))
    if other_visuals:
        content.append("#### Other Visualizations\n")
        content.append(create_image_table(other_visuals, image_dir, md_file_path))

    return "\n".join(content)


def format_comparison_visuals_section(comparison_dir, md_file_path):
    """Formats all comparison visualization sections."""
    content = []

    # Find images organized by type
    taylor_plots = sorted([f for f in comparison_dir.glob("taylor_diagram_*.png")])
    other_plots = sorted(
        [
            f
            for f in comparison_dir.glob("*.png")
            if f not in taylor_plots
        ]
    )

    if taylor_plots:
        content.append("#### Taylor Diagrams\n")
        content.append(
            "Taylor diagrams compare model predictions to observed/reference data, "
            "showing correlation, standard deviation, and RMSE relationships.\n"
        )
        content.append(create_image_table(taylor_plots, comparison_dir, md_file_path))

    if other_plots:
        content.append("#### Other Comparison Plots\n")
        content.append(create_image_table(other_plots, comparison_dir, md_file_path))

    if not taylor_plots and not other_plots:
        content.append("_No comparison plots found._\n")

    return "\n".join(content)


def format_metrics_table(metrics):
    """Formats the quantitative metrics into a markdown table."""
    if not metrics:
        return "_No quantitative metrics available._"

    df = pd.DataFrame(metrics).T

    units = {
        "tas": "K",
        "tasmax": "K",
        "tasmin": "K",
        "pr": "kg m⁻² s⁻¹",
        "huss": "kg kg⁻¹",
        "psl": "Pa",
        "sfcWind": "m s⁻¹",
    }

    descriptions = {
        "tas": "Near-Surface Air Temperature",
        "tasmax": "Daily Max Temperature",
        "tasmin": "Daily Min Temperature",
        "pr": "Precipitation",
        "huss": "Specific Humidity",
        "psl": "Sea Level Pressure",
        "sfcWind": "Surface Wind Speed",
    }

    col_display_names = {
        "pixel_wise_rmse": "Pixel-wise RMSE",
        "pixel_wise_bias": "Pixel-wise Bias",
        "pixel_wire_remse": "Pixel-wise RMSE (Wire)",
        "spatial_correlation": "Spatial Corr.",
        "temporal_correlation": "Temporal Corr.",
        "r2": "R²",
        "rmse_skewness": "RMSE Skewness",
        "rmse_kurtoise": "RMSE Kurtosis",
    }

    def display_name(col: str) -> str:
        return col_display_names.get(col, col.replace("_", " ").title())

    def format_metric(var: str, col: str, value):
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return "—"
        if not isinstance(value, Number):
            return str(value)
        col_lower = col.lower()
        unit = units.get(var, "")
        if "correlation" in col_lower or col_lower == "r2":
            return f"{value:.3f}"
        if "rmse" in col_lower or "bias" in col_lower:
            if var in {"pr", "huss"}:
                return f"{value:.2e} {unit}".strip()
            return f"{value:.2f} {unit}".strip()
        return f"{value:.3f}"

    formatted_df = pd.DataFrame(index=df.index)
    for col in df.columns:
        formatted_df[display_name(col)] = [
            format_metric(var, col, df.loc[var, col]) for var in df.index
        ]

    formatted_df.index = [
        f"`{idx}` ({descriptions.get(idx, '').strip()})" if idx in descriptions else f"`{idx}`"
        for idx in formatted_df.index
    ]
    formatted_df.index.name = "Variable"

    return formatted_df.to_markdown()


def _format_index_value(value, unit=""):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    if isinstance(value, Number):
        formatted = f"{value:.3f}"
    else:
        formatted = str(value)
    return f"{formatted} {unit}".strip() if unit and isinstance(value, Number) else formatted


def _index_metadata_lookup(key: str) -> Dict[str, str]:
    meta = (
        DEFAULT_INDEX_METADATA.get(key)
        or DEFAULT_INDEX_METADATA.get(key.upper())
        or INDEX_METADATA_XCLIM.get(key)
        or INDEX_METADATA_XCLIM.get(key.upper())
        or INDEX_METADATA_OVERRIDES.get(key)
        or INDEX_METADATA_OVERRIDES.get(key.upper())
    )
    if not isinstance(meta, dict):
        return {"description": key.replace("_", " ").upper(), "unit": ""}

    description = (
        meta.get("description")
        or meta.get("long_name")
        or meta.get("name")
        or key.replace("_", " ").upper()
    )
    unit = meta.get("unit") or meta.get("units") or ""
    return {"description": description, "unit": unit}


def format_indices_metrics(indices_metrics):
    """Formats the climate extreme indices metrics into a markdown table."""
    if not indices_metrics:
        return "_No climate indices metrics available._"

    preferred_order = ["RMSE", "R2"]
    metric_key_set = set()
    for metrics in indices_metrics.values():
        if isinstance(metrics, dict):
            for key in metrics.keys():
                if key == "error":
                    continue
                metric_key_set.add(key.upper())

    metric_key_set.update(preferred_order)
    metric_keys = sorted(
        metric_key_set,
        key=lambda lbl: (preferred_order.index(lbl) if lbl in preferred_order else len(preferred_order), lbl),
    )

    rows = []
    error_notes = []
    for key, metrics in indices_metrics.items():
        meta = _index_metadata_lookup(key)
        description = meta.get("description", key.replace("_", " ").upper())
        unit = meta.get("unit", "")
        row = {
            "Index": key.upper(),
            "Description": description,
            "Unit": unit,
        }

        if isinstance(metrics, dict):
            error_message = metrics.get("error")
            for label in metric_keys:
                value = metrics.get(label.lower())
                metric_unit = unit if label == "RMSE" else ""
                row[label] = _format_index_value(value, metric_unit)
            if error_message:
                error_notes.append(f"- {description} ({key.upper()}): {error_message}")
                for label in metric_keys:
                    row[label] = "—"
        else:
            row["VALUE"] = _format_index_value(metrics, unit)

        rows.append(row)

    df = pd.DataFrame(rows).set_index("Index")
    output = "**Climate Extreme Indices Metrics:**\n\n" + df.to_markdown()
    if error_notes:
        output += "\n\n_Errors encountered (indices omitted in table):_\n" + "\n".join(error_notes)
    return output

def create_comparison_table(results_dir):
    """
    Reads results files and compiles the model comparison. 
    """
    metrics = {}
    indices = {}
    kaggle_scores = {}
    json_files = sorted(results_dir.glob("*_evaluation.json"))
    for json_file in json_files:
        model_name = json_file.stem.split("_")[:-1]
        model_name = "_".join(model_name)
        with open(json_file, 'r') as f:
            results = json.load(f)
            metrics[model_name]= results['metrics']
            for k,v in metrics[model_name].items():
                metrics[model_name][k] = np.clip(v['r2'], -1, 1)
            indices[model_name]= results['indices_metrics']
            for k,v in indices[model_name].items():
                try:
                    indices[model_name][k] = np.clip(v['r2'], -1, 1)
                except:
                    indices[model_name][k] = np.nan
            if 'kaggle_metric' in results:
                kaggle_scores[model_name] = results['kaggle_metric']

    def format_to_string(value):
        if isinstance(value, (int, float)):
            return f'{value:.3f}'
        return str(value)

    def format_max_to_bold(df, max_mask):
        for col in df.columns:
            max_indices = max_mask[col][max_mask[col]].index    
            for idx in max_indices:
                current_value = df.loc[idx, col]
                df.loc[idx, col] = f'**{current_value}**'
        return df

    compilation_metrics = pd.DataFrame.from_dict(metrics, orient='index')
    max_mask = compilation_metrics == compilation_metrics.max(axis=0)
    compilation_metrics = compilation_metrics.applymap(format_to_string)
    compilation_metrics = format_max_to_bold(compilation_metrics, max_mask)

    metrics_max_count = max_mask.sum(axis=1)

    compilation_indices = pd.DataFrame.from_dict(indices, orient='index')
    max_mask = compilation_indices == compilation_indices.max(axis=0)
    compilation_indices = compilation_indices.applymap(format_to_string)
    compilation_indices = format_max_to_bold(compilation_indices, max_mask)
    indices_max_count = max_mask.sum(axis=1)

    compilation_metrics_md = compilation_metrics.to_markdown()
    compilation_indices_md = compilation_indices.to_markdown()

    ranking = pd.DataFrame(data={'Metrics Count': metrics_max_count, 'Indices Count': indices_max_count, 'Total Count': metrics_max_count + indices_max_count})
    if kaggle_scores:
        ranking['Kaggle nNSE (↑)'] = pd.Series(kaggle_scores).map(lambda v: f'{v:.6f}')
    ranking = ranking.to_markdown()

    return compilation_metrics_md, compilation_indices_md, ranking


def generate_comparison_report(results_dir, output_path=None, report_title="Model Comparison Report"):
    """
    Generates a markdown report for Taylor diagram comparison plots in results_dir/taylor.
    """
    taylor_dir = Path(results_dir) / "taylor"
    if not taylor_dir.is_dir():
        return
    image_files = sorted(list(taylor_dir.glob("*.png")))
    if not image_files:
        return
    if output_path is None:
        output_path = Path(results_dir)
    else:
        output_path = Path(output_path)
    output_path = output_path / "model_comparison.md"
    md_content = []
    md_content.append(f"# {report_title}\n")
    md_content.append("This report contains visualizations comparing different model predictions.\n")

    metrics_table, indices_table, ranking_table = create_comparison_table(results_dir)
    md_content.append("## Ranking\n")
    md_content.append("Ranking based on the number of best performances across all metrics and indices.\n")
    md_content.append(ranking_table)

    md_content.append("## Metrics Comparison\n")
    md_content.append("Table with the comparison of metrics across different models. Bold indicates best performing model.\n")
    md_content.append(metrics_table)

    md_content.append("## Indices Comparison\n")
    md_content.append("Table with the comparison of indices across different models. Bold indicates best performing model.\n")
    md_content.append(indices_table)

    md_content.append("## Taylor Diagram Analysis\n")
    md_content.append(
        "Taylor diagrams provide a comprehensive comparison of model predictions "
        "against reference data. Each point represents a model's performance for a specific variable.\n"
    )
    md_content.append(format_comparison_visuals_section(taylor_dir, output_path ))
    with open(output_path, "w") as f:
        f.write("\n".join(md_content))

    print(f"Report generated at {output_path}")


def generate_report(json_path: Union[str, Path], output_path: Optional[Union[str, Path]] = None):
    """
    Generates a markdown report from a model evaluation JSON file.

    Args:
        json_path (Union[str, Path]): Path to the model evaluation JSON file.
        output_path (Optional[Union[str, Path]]): Path to the output markdown file. 
            If None, it's inferred from the model name and saved in the current directory.
    """
    json_path = Path(json_path)
    if not json_path.is_file():
        print(f"Error: JSON file not found at {json_path}")
        return

    model_name = json_path.stem.split("_")[:-1]
    model_name = "_".join(model_name)

    if output_path:
        output_path = Path(output_path)
    else:
        # Place the report in the project root by default
        output_path = Path(f"./{model_name}_results.md")

    with open(json_path, "r") as f:
        data = json.load(f)

    # Infer image directory from JSON path
    image_dir = json_path.parent / f"{model_name}_visuals"
    if not image_dir.is_dir():
        print(f"Warning: Image directory not found at {image_dir}")
        image_dir = None

    # --- Build Markdown Content ---
    md_content = []
    md_content.append(f"# {model_name.capitalize()} Baseline Model Results")
    md_content.append(
        f"\nHere are the latest results after running the baseline {model_name} model on the `ssp245` test scenario."
    )

    if "kaggle_metric" in data:
        kaggle_val = data["kaggle_metric"]
        md_content.append("\n### Kaggle Score\n")
        md_content.append(f"| Metric | Score |\n|---|---|\n| nNSE (↑) | {kaggle_val:.6f} |")

    if "metrics" in data:
        md_content.append("\n### Quantitative Results\n")
        md_content.append(format_metrics_table(data["metrics"]))
    
    if "indices_metrics" in data:
        md_content.append("\n" + format_indices_metrics(data["indices_metrics"]))

    if image_dir:
        md_content.append("\n### Visual Results\n")
        relative_image_dir = os.path.relpath(image_dir, output_path.parent)
        md_content.append(
            f"The visualizations for spatial maps and time series comparisons are generated within the `playground.ipynb` notebook. Below are all visuals from `{relative_image_dir}/`."
        )
        md_content.append(format_visuals_section(image_dir, output_path))

    with open(output_path, "w") as f:
        f.write("\n".join(md_content))

    print(f"Report generated at {output_path}")


def generate_reports_from_dir(input_dir: Union[str, Path], output_dir: Optional[Union[str, Path]] = None):
    """
    Finds all '*_evaluation.json' files in a directory and generates reports for them.

    Args:
        input_dir (Union[str, Path]): Path to the directory containing evaluation JSON files.
        output_dir (Optional[Union[str, Path]]): Path to the output directory for markdown files.
            Defaults to the project root.
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir) if output_dir else Path(".")
    
    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    if not input_dir.is_dir():
        print(f"Error: Input path is not a valid directory: {input_dir}")
        return

    json_files = sorted(input_dir.glob("*_evaluation.json"))
    if not json_files:
        print(f"No '*_evaluation.json' files found in '{input_dir}'")
        return
        
    print(f"Found {len(json_files)} evaluation files. Generating reports...")
    for json_file in json_files:
        model_name = json_file.stem.split("_")[:-1]
        model_name = "_".join(model_name)
        output_file = output_dir / f"{model_name}_results.md"
        generate_report(json_file, output_file)
    
    generate_comparison_report(input_dir, output_dir)


def main():
    """Main function to handle command-line arguments and generate report(s)."""
    parser = argparse.ArgumentParser(
        description="Generate results reports from model evaluation JSON files."
    )
    parser.add_argument(
        "input_path", type=Path, 
        help="Path to a model evaluation JSON file or a directory containing them."
    )
    parser.add_argument(
        "-o", "--output_dir", type=Path, 
        help="Path to the output directory for markdown files. Defaults to the project root."
    )
    args = parser.parse_args()

    input_path = args.input_path
    output_dir = args.output_dir if args.output_dir else Path(".")
    
    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    if input_path.is_dir():
        generate_reports_from_dir(input_path, output_dir)
    elif input_path.is_file():
        model_name = input_path.stem.split("_")[0]
        output_file = f"{model_name}_results.md"
        generate_report(input_path, output_file)
    else:
        print(f"Error: Input path is not a valid file or directory: {input_path}")


if __name__ == "__main__":
    main()
