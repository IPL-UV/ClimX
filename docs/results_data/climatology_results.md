# Climatology Baseline Model Results

Here are the latest results after running the baseline climatology model on the `ssp245` test scenario.

### Kaggle Score

| Metric | Score |
|---|---|
| nNSE (↑) | -0.565348 |

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

| Index   | Description                   | Unit     | RMSE           |       R2 |
|:--------|:------------------------------|:---------|:---------------|---------:|
| FD      | Frost Days                    | days     | 10.914 days    |   -1.31  |
| SU      | Summer Days (Tmax ≥ 25°C)     | days     | 18.971 days    |   -4.113 |
| ID      | Ice Days (Tmax < 0°C)         | days     | 13.677 days    |   -2.547 |
| TR      | Tropical Nights (Tmin ≥ 20°C) | days     | 14.959 days    |   -1.771 |
| GSL     | Growing Season Length         | days     | 10.508 days    |    0.127 |
| TXX     | Monthly Max of Daily Tmax     | °C       | 5.787 °C       |   -2.523 |
| TNN     | Monthly Min of Daily Tmin     | °C       | 3.623 °C       |    0.422 |
| WSDI    | Warm Spell Duration Index     | days     | 88.632 days    |   -2.73  |
| CSDI    | Cold Spell Duration Index     | days     | 10.614 days    |  -96.076 |
| RX5DAY  | Max 5-day Precipitation       | mm       | 34.462 mm      |   -2.139 |
| CDD     | Consecutive Dry Days          | days     | 197.028 days   | -855.698 |
| CWD     | Consecutive Wet Days          | days     | 86.032 days    | -613.164 |
| R95P    | Total Precip above 95th pct   | mm       | 330.328 mm     |   -9.782 |
| SDII    | Simple Daily Intensity Index  | mm day⁻¹ | 4.411 mm day⁻¹ |  -61.883 |
| R10MM   | Days with Precip ≥10mm        | days     | 22.489 days    |  -11.705 |

### Visual Results

Below are all visuals from `climatology_visuals/`. To avoid revealing the held-out SSP2-4.5 targets, the maps show only the baseline predictions; index maps add each AR6 land region's nNSE over 2015–2100, as used by the leaderboard metric.
#### Daily Prediction Maps (2015-02-20)

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

#### Index Maps

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
<td align="center"></td>
  </tr>
  <tr>
<td><img src="climatology_visuals/index_map_WSDI_2065-01-01.png" width="100%"></td>
<td></td>
  </tr>
</table>
