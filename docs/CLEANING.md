# Data cleaning

`data/clean/` is a cleaned copy of `data/raw/`. It is produced by `data_prep/clean_datasets.py`:

```bash
docker/run.sh python3 data_prep/clean_datasets.py    # rebuilds $EXIMO_DATA/clean/ and $EXIMO_DATA/cleaning_log.json
```

What cleaning does and doesn't do:

- **It only removes.** Whole files, or contiguous runs of rows at the start or end of a file or inside it, are dropped.
- **Kept data is untouched.** Every kept CSV or text row is copied byte-for-byte from `raw/`. HDF5 datasets are sliced with their dtype unchanged.
- **No other processing.** There is no resampling, filtering, unit conversion or re-splitting into train/test.
- **`raw/` is never modified.** `data/clean/` can be regenerated in about a minute.
- **Every decision is recorded.** `cleaning_log.json` (ours: `data_prep/cleaning_log_reference.json`) lists each source file with the action taken, the rules that fired, the row and time ranges kept and removed, and the diagnostics behind each decision.

All 401 output sequences were verified after the build:
- Rows are identical to the source rows.
- Re-running the detector on the output finds no extrapolated edges and no interior gaps ≥ 0.25 s.
- NanoBench motor and vbat values are inside the R7 limits.

## Summary

| dataset | files in | files kept | output sequences | duration in → out | what was removed |
|---|---|---|---|---|---|
| NanoBench | 107 | **86** | 86 | 72.7 → **57.1 min** | 20 duplicates, 1 aborted flight, extrapolated tails in 82 files (11 of them longer than 1 s), 1 interior gap |
| AI-IO | 46 HDF5 files (22 sequences) | **33** | 36 | 43.9 → **34.2 min** | 13 files whose ground truth is 18–51% interpolated; 3 files split at ground-truth gaps |
| TII-RATM | 36 flights | 36 | 36 | 33.2 → 33.2 min | nothing; no issues found |
| NeuroBEM | 247 segments | **243** | 243 | 75.3 → **74.7 min** | 4 segments of the one 164 Hz flight; 1 editor swap file |

## How "questionable" was detected

The main detector targets **synthetic samples**: values that were never measured but filled in by the dataset's own processing.

- NanoBench and AI-IO resample each sensor onto a uniform time grid.
- Where a sensor's log has a hole, the resampler drew a **straight line** between the last sample before and the first sample after (interpolation).
- Where a log ended early, it **continued the last slope** to the end of the file (extrapolation).

Real IMU, motor or motion-capture data never stays on an exact straight line in time: noise alone breaks it within a few samples. So a stretch where *all* columns of a signal group have a constant, non-zero slope (to 1e-6 relative, in real time, so timestamp jitter doesn't matter) for **≥ 0.1 s** is classified as synthetic.

Signal groups checked:

| dataset | groups |
|---|---|
| NanoBench | IMU (6), motor PWM (4), Vicon position (3) |
| AI-IO | IMU `accel_raw`+`gyro_raw`, `rotor_spd`, ground-truth position and velocity (`traj_target` columns 0–2, 7–9) |
| TII-RATM | IMU (6), `thrust[0-3]`, mocap position |
| NeuroBEM | acc + body rates (6), `mot 1..4`, position |

Battery voltage is deliberately **not** used for detection. NanoBench logs it at 10 Hz, so straight segments between its samples are expected.

I also checked for frozen (sample-and-hold) runs, where all six IMU axes are identical for ≥ 5 samples. None were found in any dataset.

## Rules

| id | rule | threshold | why |
|---|---|---|---|
| R1 | Exclude byte-identical copies of a file. Keep the first in natural order (lowest repetition number) | sha256 equal | NanoBench ships the same recording under 2–3 names (identical metadata timestamps). Keeping copies inflates the data and leaks test into train |
| R2 | Exclude files whose median sample rate is off the dataset's nominal rate | > 1% from nominal | One NeuroBEM flight is at 164 Hz, not 400 Hz. Its timestamps are genuine (differentiated position matches recorded velocity, ratio 0.997), but it breaks a fixed-rate assumption, and there is no resampling here |
| R3 | Trim synthetic stretches that touch the start or end of a file | ≥ 0.10 s | This is extrapolation after a log stopped. It is where NanoBench's out-of-range motor values (to −2.5 M / +4.8 M) and impossible battery readings (to 10.5 V) came from |
| R4 | Exclude a file if, after R3, too many of its samples are interior synthetic | > 10% of samples | At that point the signal is effectively low-rate and mostly invented. Cutting it into pieces would leave fragments |
| R5 | Cut out interior synthetic stretches and split the file into parts | ≥ 0.25 s | Long enough to bias velocity labels and IMU windows. Shorter gaps (0.10–0.25 s; radio drops, brief mocap loss) are kept and listed in the log |
| R6 | Drop recordings, or parts created by R3/R5, that are too short | < 5 s | Too short to be useful as an IO sequence. **Not applied to NeuroBEM's author-curated segments**, 80 of which are under 5 s by design |
| R7 | Drop a part if any core value is NaN or physically impossible | NanoBench PWM ∉ [0, 65535], vbat ∉ [2.5, 4.35] V (1S LiPo); TII thrust ∉ [0, 1]; AI-IO `rotor_spd` < 0; NeuroBEM `mot` < 0 | Final safety net. **Fired 0 times**: every out-of-range value was already inside an R3 tail |
| R8 | Don't copy non-data files | — | NeuroBEM's `processed_data/.merged_2021-02-03-13-43-38_seg_1.csv.swp` |

The thresholds are module constants at the top of `data_prep/clean_datasets.py`, and the values used are stored in `cleaning_log.json`.

## Per-dataset details

### NanoBench

**Duplicates removed (R1): 20 files in 18 groups, all trefoil (B9).** Each excluded file is listed with the copy that was kept:

| excluded | kept copy |
|---|---|
| B9_trefoil_fast_rep9 | rep2 |
| B9_trefoil_fast_rep10 | rep5 |
| B9_trefoil_fast_rep11 | rep6 |
| B9_trefoil_fast_rep12 | rep7 |
| B9_trefoil_fast_rep13 | rep8 |
| B9_trefoil_fast_rep15 | rep3 |
| B9_trefoil_medium_rep7, rep10 | rep3 |
| B9_trefoil_medium_rep8 | rep2 |
| B9_trefoil_medium_rep9 | rep1 |
| B9_trefoil_medium_rep11 | rep6 |
| B9_trefoil_medium_rep12 | rep4 |
| B9_trefoil_medium_rep13, rep16 | rep5 |
| B9_trefoil_slow_rep8 | rep2 |
| B9_trefoil_slow_rep9 | rep6 |
| B9_trefoil_slow_rep10 | rep5 |
| B9_trefoil_slow_rep11 | rep4 |
| B9_trefoil_slow_rep12 | rep7 |
| B9_trefoil_slow_rep18 | rep3 |

**Aborted flight (R6).** `B7_oval_slow_rep1` lasts 2.1 s; its metadata plans a 30 s flight.

**Long extrapolated tails (R3).** In these 11 files, IMU and motor logging stopped together, well before the end of the file:

| file | kept | removed tail |
|---|---|---|
| B9_trefoil_fast_rep2 | 0–12.49 s | 29.8 s |
| B12_staircase_climb_rep1 | 0–41.28 s | 31.0 s |
| B9_trefoil_fast_rep5 | 0–19.19 s | 23.1 s |
| B9_trefoil_fast_rep3 | 0–19.57 s | 22.7 s |
| C4_battery_drain_rep1 | 0–115.22 s | 19.1 s |
| B2_circle_medium_rep3 | 0–31.27 s | 11.0 s |
| B6_linear_ramp_rep4 | 0–23.10 s | 9.1 s |
| B9_trefoil_medium_rep15 | 0–34.37 s | 7.9 s |
| B9_trefoil_medium_rep5 | 0–37.97 s | 4.3 s |
| B2_circle_medium_rep1 | 0–25.02 s | 2.2 s |
| B5_helix_medium_rep2 | 0–40.55 s | 1.7 s (0.41 s gap (R5) + a 0.04 s fragment (R6) + 1.25 s tail) |

**Routine end-of-log trims (R3).** 71 more files lose a median 0.28 s of extrapolated IMU at the very end. Only 4 files were copied completely unchanged: `B2_circle_fast_rep3`, `B7_oval_medium_rep2`, `B7_oval_slow_rep3` and `B9_trefoil_fast_rep1`.

**Kept as-is but worth knowing:**
- 105 short interior gaps (0.10–0.25 s, by rule; at most 3.9% of any file) remain.
- 475 rows in 4 files have vbat between 2.85 and 3.0 V: `B2_circle_fast_rep2`, `B2_circle_medium_rep3`, `B3_figure8_medium_rep2` and `B6_linear_ramp_rep1`. This is plausible voltage sag under load, so it's kept, though it is below the 3.08 V minimum the NanoBench README states.
- The metadata YAMLs are copied unchanged. Their `row_counts` describe the original recording, not the trimmed CSV.

### AI-IO

**Ground-truth interpolation (R4): 13 files excluded.** These are all splits of `manual/low/seq_1`, `low/seq_2` and `medium/seq_2`, plus the val and test splits of `manual/high/seq_1` and `high/seq_2`.
- 18–51% of their `traj_target` samples (position *and* velocity) lie on straight lines.
- Counted stretches are 0.1–0.76 s long (with many shorter ones besides) and irregular, and occur during fast flight (median 2.2–3.6 m/s), which matches interpolated motion-capture dropouts.
- `stamped_groundtruth_imu.txt` holds the same values.
- IMU and rotor speed in these files are clean; only the ground truth is synthetic.

**Splits (R5).** Three files were split at a single ground-truth gap and written as `data__part1.hdf5` / `data__part2.hdf5` (plus matching `stamped_groundtruth_imu__partN.txt`) in the same folder:

| file | gap removed |
|---|---|
| `eight/spd_3` test | 42.16–42.91 s |
| `manual/high/seq_2` train | 25.64–25.91 s |
| `manual/medium/seq_1` train | 58.32–58.94 s |

One of these files (`medium/seq_2` val, which was excluded anyway) also had a 0.22 s extrapolated tail.

What is left of the official splits:
- **Test:** 17 of 22 test files remain: 7 manual (high/seq_3–4, low/seq_3–4, medium/seq_1, 3, 4) plus all 10 patterned flights.
- **Train:** `manual/high/seq_1` and `high/seq_2` keep their train split but lose val and test.

The raw ROS 2 recordings (`ros2bag.mcap`) are not copied into `clean/`; they remain in `raw/`.

### TII-RATM

No issues were found: no synthetic stretches, no frozen IMU runs, thrust within [0, 1]. For every flight, the cleaned copy has `_500hz_freq_sync.csv`, `_cam_ts_sync.csv` and `metadata_*.yaml`. ROS 2 bags, `csv_raw/` and the gate labels remain only in `raw/`.

### NeuroBEM

- **Excluded (R2):** `2021-02-18-16-43-54_seg_1..4`, the 164 Hz flight (38.8 s in total). It isn't in `testset.txt`, and all 13 test segments are kept.
- **Excluded (R8):** the vim swap file.
- **Copied:** `Flights.txt`, `testset.txt` and `Readme.md`. `raw_data/` stays only in `raw/`.
- **Not changed, by design:** `vbat` is still in its undocumented unit (≈123–169, probably 0.1 V). The filtered (non-raw) IMU is also unchanged; that is a property of the dataset, not a defect.

## Comparability with published results

Cleaning changes which data exist, so results on `data/clean/` are **not directly comparable** with numbers reported on the original files:

- **NanoBench:** the original release has 107 sequences; only 86 distinct, valid recordings remain. A split of the original files can put copies of one flight on both sides, which makes its test error optimistic.
- **AI-IO:** 5 of the 12 manual test files are excluded because their ground truth is interpolated.

To reproduce a paper's numbers, use `data/raw/`. Use `data/clean/` for new training and evaluation, and report which one you used.

## Output layout

```
data/clean/
  nanobench/<name>.csv, <name>_metadata.yaml                         (flat, as in the repo)
  ai_io/datasets/our2/indoor/<...>/processed_data/<split>/data.hdf5   (+ stamped_groundtruth_imu.txt)
        .../metadata.yaml                                            (per sequence)
  tii_ratm/{autonomous,piloted}/flight-*/<flight>_{500hz_freq_sync,cam_ts_sync}.csv, metadata_<flight>.yaml
  neurobem/processed_data/merged_<flight>_seg_<k>.csv, Flights.txt, testset.txt, Readme.md
```

Paths mirror `raw/`. A file split by R5 becomes `<stem>__part1<ext>`, `<stem>__part2<ext>`, … next to where the original would be.
