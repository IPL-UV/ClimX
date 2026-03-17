# Lps Baseline Model Results

Here are the latest results after running the baseline lps model on the `ssp245` test scenario.

### Kaggle Score

| Metric | Score |
|---|---|
| nNSE (↑) | -0.448158 |

### Quantitative Results

| Variable                             |     R² |
|:-------------------------------------|-------:|
| `tas` (Near-Surface Air Temperature) |  0.666 |
| `tasmax` (Daily Max Temperature)     |  0.642 |
| `tasmin` (Daily Min Temperature)     |  0.669 |
| `pr` (Precipitation)                 | -0.077 |
| `huss` (Specific Humidity)           |  0.571 |
| `psl` (Sea Level Pressure)           |  0.217 |
| `sfcWind` (Surface Wind Speed)       |  0.134 |

**Climate Extreme Indices Metrics:**

| Index   | Description                   | Unit     | RMSE           |       R2 |
|:--------|:------------------------------|:---------|:---------------|---------:|
| FD      | Frost Days                    | days     | 11.065 days    |  -10.64  |
| SU      | Summer Days (Tmax ≥ 25°C)     | days     | 9.719 days     |   -0.439 |
| ID      | Ice Days (Tmax < 0°C)         | days     | 9.468 days     |   -1.779 |
| TR      | Tropical Nights (Tmin ≥ 20°C) | days     | 7.533 days     |   -0.202 |
| GSL     | Growing Season Length         | days     | 8.670 days     |    0.368 |
| TXX     | Monthly Max of Daily Tmax     | °C       | 4.219 °C       |   -0.865 |
| TNN     | Monthly Min of Daily Tmin     | °C       | 3.903 °C       |    0.226 |
| WSDI    | Warm Spell Duration Index     | days     | 53.408 days    |   -0.931 |
| CSDI    | Cold Spell Duration Index     | days     | 3.300 days     |   -0.11  |
| RX5DAY  | Max 5-day Precipitation       | mm       | 34.487 mm      |   -2.127 |
| CDD     | Consecutive Dry Days          | days     | 200.115 days   | -861.744 |
| CWD     | Consecutive Wet Days          | days     | 86.731 days    | -611.384 |
| R95P    | Total Precip above 95th pct   | mm       | 0.004 mm       |   -9.782 |
| SDII    | Simple Daily Intensity Index  | mm day⁻¹ | 4.432 mm day⁻¹ |  -61.804 |
| R10MM   | Days with Precip ≥10mm        | days     | 22.538 days    |  -11.789 |

### Visual Results

The visualizations for spatial maps and time series comparisons are generated within the `playground.ipynb` notebook. Below are all visuals from `lps_visuals/`.
#### Spatial Comparison Maps

<table>
  <tr>
<td align="center"><b>result_map_huss_2015-02-20.png</b></td>
<td align="center"><b>result_map_pr_2015-02-20.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/result_map_huss_2015-02-20.png" width="100%"></td>
<td><img src="lps_visuals/result_map_pr_2015-02-20.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_map_psl_2015-02-20.png</b></td>
<td align="center"><b>result_map_sfcWind_2015-02-20.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/result_map_psl_2015-02-20.png" width="100%"></td>
<td><img src="lps_visuals/result_map_sfcWind_2015-02-20.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_map_tas_2015-02-20.png</b></td>
<td align="center"><b>result_map_tasmax_2015-02-20.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/result_map_tas_2015-02-20.png" width="100%"></td>
<td><img src="lps_visuals/result_map_tasmax_2015-02-20.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_map_tasmin_2015-02-20.png</b></td>
<td align="center"></td>
  </tr>
  <tr>
<td><img src="lps_visuals/result_map_tasmin_2015-02-20.png" width="100%"></td>
<td></td>
  </tr>
</table>

#### Time Series Comparisons

<table>
  <tr>
<td align="center"><b>result_timeseries_huss_40.0_-95.0.png</b></td>
<td align="center"><b>result_timeseries_pr_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/result_timeseries_huss_40.0_-95.0.png" width="100%"></td>
<td><img src="lps_visuals/result_timeseries_pr_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_timeseries_psl_40.0_-95.0.png</b></td>
<td align="center"><b>result_timeseries_sfcWind_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/result_timeseries_psl_40.0_-95.0.png" width="100%"></td>
<td><img src="lps_visuals/result_timeseries_sfcWind_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_timeseries_tas_40.0_-95.0.png</b></td>
<td align="center"><b>result_timeseries_tasmax_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/result_timeseries_tas_40.0_-95.0.png" width="100%"></td>
<td><img src="lps_visuals/result_timeseries_tasmax_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_timeseries_tasmin_40.0_-95.0.png</b></td>
<td align="center"></td>
  </tr>
  <tr>
<td><img src="lps_visuals/result_timeseries_tasmin_40.0_-95.0.png" width="100%"></td>
<td></td>
  </tr>
</table>

#### Scatter Plots

<table>
  <tr>
<td align="center"><b>result_scatter_huss_2015-02-20.png</b></td>
<td align="center"><b>result_scatter_pr_2015-02-20.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/result_scatter_huss_2015-02-20.png" width="100%"></td>
<td><img src="lps_visuals/result_scatter_pr_2015-02-20.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_scatter_psl_2015-02-20.png</b></td>
<td align="center"><b>result_scatter_sfcWind_2015-02-20.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/result_scatter_psl_2015-02-20.png" width="100%"></td>
<td><img src="lps_visuals/result_scatter_sfcWind_2015-02-20.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_scatter_tas_2015-02-20.png</b></td>
<td align="center"><b>result_scatter_tasmax_2015-02-20.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/result_scatter_tas_2015-02-20.png" width="100%"></td>
<td><img src="lps_visuals/result_scatter_tasmax_2015-02-20.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_scatter_tasmin_2015-02-20.png</b></td>
<td align="center"></td>
  </tr>
  <tr>
<td><img src="lps_visuals/result_scatter_tasmin_2015-02-20.png" width="100%"></td>
<td></td>
  </tr>
</table>

#### Other Visualizations

<table>
  <tr>
<td align="center"><b>index_map_CDD_2065-01-01.png</b></td>
<td align="center"><b>index_map_CSDI_2065-01-01.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/index_map_CDD_2065-01-01.png" width="100%"></td>
<td><img src="lps_visuals/index_map_CSDI_2065-01-01.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_map_CWD_2065-01-01.png</b></td>
<td align="center"><b>index_map_FD_2065-01-01.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/index_map_CWD_2065-01-01.png" width="100%"></td>
<td><img src="lps_visuals/index_map_FD_2065-01-01.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_map_GSL_2065-01-01.png</b></td>
<td align="center"><b>index_map_ID_2065-01-01.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/index_map_GSL_2065-01-01.png" width="100%"></td>
<td><img src="lps_visuals/index_map_ID_2065-01-01.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_map_R10mm_2065-01-01.png</b></td>
<td align="center"><b>index_map_R95p_2065-01-01.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/index_map_R10mm_2065-01-01.png" width="100%"></td>
<td><img src="lps_visuals/index_map_R95p_2065-01-01.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_map_Rx5day_2019-03-01.png</b></td>
<td align="center"><b>index_map_SDII_2065-01-01.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/index_map_Rx5day_2019-03-01.png" width="100%"></td>
<td><img src="lps_visuals/index_map_SDII_2065-01-01.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_map_SU_2065-01-01.png</b></td>
<td align="center"><b>index_map_TNn_2019-03-01.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/index_map_SU_2065-01-01.png" width="100%"></td>
<td><img src="lps_visuals/index_map_TNn_2019-03-01.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_map_TR_2065-01-01.png</b></td>
<td align="center"><b>index_map_TXx_2019-03-01.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/index_map_TR_2065-01-01.png" width="100%"></td>
<td><img src="lps_visuals/index_map_TXx_2019-03-01.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_map_WSDI_2065-01-01.png</b></td>
<td align="center"><b>index_timeseries_CDD_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/index_map_WSDI_2065-01-01.png" width="100%"></td>
<td><img src="lps_visuals/index_timeseries_CDD_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_timeseries_CSDI_40.0_-95.0.png</b></td>
<td align="center"><b>index_timeseries_CWD_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/index_timeseries_CSDI_40.0_-95.0.png" width="100%"></td>
<td><img src="lps_visuals/index_timeseries_CWD_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_timeseries_FD_40.0_-95.0.png</b></td>
<td align="center"><b>index_timeseries_GSL_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/index_timeseries_FD_40.0_-95.0.png" width="100%"></td>
<td><img src="lps_visuals/index_timeseries_GSL_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_timeseries_ID_40.0_-95.0.png</b></td>
<td align="center"><b>index_timeseries_R10mm_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/index_timeseries_ID_40.0_-95.0.png" width="100%"></td>
<td><img src="lps_visuals/index_timeseries_R10mm_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_timeseries_R95p_40.0_-95.0.png</b></td>
<td align="center"><b>index_timeseries_Rx5day_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/index_timeseries_R95p_40.0_-95.0.png" width="100%"></td>
<td><img src="lps_visuals/index_timeseries_Rx5day_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_timeseries_SDII_40.0_-95.0.png</b></td>
<td align="center"><b>index_timeseries_SU_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/index_timeseries_SDII_40.0_-95.0.png" width="100%"></td>
<td><img src="lps_visuals/index_timeseries_SU_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_timeseries_TNn_40.0_-95.0.png</b></td>
<td align="center"><b>index_timeseries_TR_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/index_timeseries_TNn_40.0_-95.0.png" width="100%"></td>
<td><img src="lps_visuals/index_timeseries_TR_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_timeseries_TXx_40.0_-95.0.png</b></td>
<td align="center"><b>index_timeseries_WSDI_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="lps_visuals/index_timeseries_TXx_40.0_-95.0.png" width="100%"></td>
<td><img src="lps_visuals/index_timeseries_WSDI_40.0_-95.0.png" width="100%"></td>
  </tr>
</table>
