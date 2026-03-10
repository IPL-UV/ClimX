# Climatology Baseline Model Results

Here are the latest results after running the baseline climatology model on the `ssp245` test scenario.

### Kaggle Score

| Metric | Score |
|---|---|
| nNSE (↑) | -0.564821 |

### Quantitative Results

| Variable                             |     R² |
|:-------------------------------------|-------:|
| `tas` (Near-Surface Air Temperature) |  0.178 |
| `tasmax` (Daily Max Temperature)     |  0.189 |
| `tasmin` (Daily Min Temperature)     |  0.183 |
| `pr` (Precipitation)                 | -0.081 |
| `huss` (Specific Humidity)           |  0.235 |
| `psl` (Sea Level Pressure)           |  0.173 |
| `sfcWind` (Surface Wind Speed)       |  0.108 |

**Climate Extreme Indices Metrics:**

| Index   | Description   | Unit   |    RMSE |       R2 |
|:--------|:--------------|:-------|--------:|---------:|
| FD      | FD            |        |  10.914 |   -1.31  |
| SU      | SU            |        |  18.971 |   -4.113 |
| ID      | ID            |        |  13.677 |   -2.547 |
| TR      | TR            |        |  14.959 |   -1.771 |
| GSL     | GSL           |        |  10.508 |    0.127 |
| TXX     | TXX           |        |   5.787 |   -2.523 |
| TNN     | TNN           |        |   3.623 |    0.422 |
| WSDI    | WSDI          |        |  88.632 |   -2.73  |
| CSDI    | CSDI          |        |  10.614 |  -96.076 |
| RX5DAY  | RX5DAY        |        |  34.462 |   -2.139 |
| CDD     | CDD           |        | 197.028 | -855.698 |
| CWD     | CWD           |        |  86.032 | -613.164 |
| R95P    | R95P          |        |   0.004 |   -9.782 |
| SDII    | SDII          |        |   4.411 |  -61.883 |
| R10MM   | R10MM         |        |  22.489 |  -11.705 |

### Visual Results

The visualizations for spatial maps and time series comparisons are generated within the `playground.ipynb` notebook. Below are all visuals from `climatology_visuals/`.
#### Spatial Comparison Maps

<table>
  <tr>
<td align="center"><b>result_map_huss_2015-02-20.png</b></td>
<td align="center"><b>result_map_pr_2015-02-20.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/result_map_huss_2015-02-20.png" width="100%"></td>
<td><img src="climatology_visuals/result_map_pr_2015-02-20.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_map_psl_2015-02-20.png</b></td>
<td align="center"><b>result_map_sfcWind_2015-02-20.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/result_map_psl_2015-02-20.png" width="100%"></td>
<td><img src="climatology_visuals/result_map_sfcWind_2015-02-20.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_map_tas_2015-02-20.png</b></td>
<td align="center"><b>result_map_tasmax_2015-02-20.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/result_map_tas_2015-02-20.png" width="100%"></td>
<td><img src="climatology_visuals/result_map_tasmax_2015-02-20.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_map_tasmin_2015-02-20.png</b></td>
<td align="center"></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/result_map_tasmin_2015-02-20.png" width="100%"></td>
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
<td><img src="climatology_visuals/result_timeseries_huss_40.0_-95.0.png" width="100%"></td>
<td><img src="climatology_visuals/result_timeseries_pr_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_timeseries_psl_40.0_-95.0.png</b></td>
<td align="center"><b>result_timeseries_sfcWind_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/result_timeseries_psl_40.0_-95.0.png" width="100%"></td>
<td><img src="climatology_visuals/result_timeseries_sfcWind_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_timeseries_tas_40.0_-95.0.png</b></td>
<td align="center"><b>result_timeseries_tasmax_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/result_timeseries_tas_40.0_-95.0.png" width="100%"></td>
<td><img src="climatology_visuals/result_timeseries_tasmax_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_timeseries_tasmin_40.0_-95.0.png</b></td>
<td align="center"></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/result_timeseries_tasmin_40.0_-95.0.png" width="100%"></td>
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
<td><img src="climatology_visuals/result_scatter_huss_2015-02-20.png" width="100%"></td>
<td><img src="climatology_visuals/result_scatter_pr_2015-02-20.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_scatter_psl_2015-02-20.png</b></td>
<td align="center"><b>result_scatter_sfcWind_2015-02-20.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/result_scatter_psl_2015-02-20.png" width="100%"></td>
<td><img src="climatology_visuals/result_scatter_sfcWind_2015-02-20.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_scatter_tas_2015-02-20.png</b></td>
<td align="center"><b>result_scatter_tasmax_2015-02-20.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/result_scatter_tas_2015-02-20.png" width="100%"></td>
<td><img src="climatology_visuals/result_scatter_tasmax_2015-02-20.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>result_scatter_tasmin_2015-02-20.png</b></td>
<td align="center"></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/result_scatter_tasmin_2015-02-20.png" width="100%"></td>
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
<td><img src="climatology_visuals/index_map_CDD_2065-01-01.png" width="100%"></td>
<td><img src="climatology_visuals/index_map_CSDI_2065-01-01.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_map_CWD_2065-01-01.png</b></td>
<td align="center"><b>index_map_FD_2065-01-01.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/index_map_CWD_2065-01-01.png" width="100%"></td>
<td><img src="climatology_visuals/index_map_FD_2065-01-01.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_map_GSL_2065-01-01.png</b></td>
<td align="center"><b>index_map_ID_2065-01-01.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/index_map_GSL_2065-01-01.png" width="100%"></td>
<td><img src="climatology_visuals/index_map_ID_2065-01-01.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_map_R10mm_2065-01-01.png</b></td>
<td align="center"><b>index_map_R95p_2065-01-01.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/index_map_R10mm_2065-01-01.png" width="100%"></td>
<td><img src="climatology_visuals/index_map_R95p_2065-01-01.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_map_Rx5day_2019-03-01.png</b></td>
<td align="center"><b>index_map_SDII_2065-01-01.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/index_map_Rx5day_2019-03-01.png" width="100%"></td>
<td><img src="climatology_visuals/index_map_SDII_2065-01-01.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_map_SU_2065-01-01.png</b></td>
<td align="center"><b>index_map_TNn_2019-03-01.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/index_map_SU_2065-01-01.png" width="100%"></td>
<td><img src="climatology_visuals/index_map_TNn_2019-03-01.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_map_TR_2065-01-01.png</b></td>
<td align="center"><b>index_map_TXx_2019-03-01.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/index_map_TR_2065-01-01.png" width="100%"></td>
<td><img src="climatology_visuals/index_map_TXx_2019-03-01.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_map_WSDI_2065-01-01.png</b></td>
<td align="center"><b>index_timeseries_CDD_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/index_map_WSDI_2065-01-01.png" width="100%"></td>
<td><img src="climatology_visuals/index_timeseries_CDD_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_timeseries_CSDI_40.0_-95.0.png</b></td>
<td align="center"><b>index_timeseries_CWD_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/index_timeseries_CSDI_40.0_-95.0.png" width="100%"></td>
<td><img src="climatology_visuals/index_timeseries_CWD_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_timeseries_FD_40.0_-95.0.png</b></td>
<td align="center"><b>index_timeseries_GSL_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/index_timeseries_FD_40.0_-95.0.png" width="100%"></td>
<td><img src="climatology_visuals/index_timeseries_GSL_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_timeseries_ID_40.0_-95.0.png</b></td>
<td align="center"><b>index_timeseries_R10mm_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/index_timeseries_ID_40.0_-95.0.png" width="100%"></td>
<td><img src="climatology_visuals/index_timeseries_R10mm_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_timeseries_R95p_40.0_-95.0.png</b></td>
<td align="center"><b>index_timeseries_Rx5day_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/index_timeseries_R95p_40.0_-95.0.png" width="100%"></td>
<td><img src="climatology_visuals/index_timeseries_Rx5day_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_timeseries_SDII_40.0_-95.0.png</b></td>
<td align="center"><b>index_timeseries_SU_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/index_timeseries_SDII_40.0_-95.0.png" width="100%"></td>
<td><img src="climatology_visuals/index_timeseries_SU_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_timeseries_TNn_40.0_-95.0.png</b></td>
<td align="center"><b>index_timeseries_TR_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/index_timeseries_TNn_40.0_-95.0.png" width="100%"></td>
<td><img src="climatology_visuals/index_timeseries_TR_40.0_-95.0.png" width="100%"></td>
  </tr>
  <tr>
<td align="center"><b>index_timeseries_TXx_40.0_-95.0.png</b></td>
<td align="center"><b>index_timeseries_WSDI_40.0_-95.0.png</b></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/index_timeseries_TXx_40.0_-95.0.png" width="100%"></td>
<td><img src="climatology_visuals/index_timeseries_WSDI_40.0_-95.0.png" width="100%"></td>
  </tr>
</table>
