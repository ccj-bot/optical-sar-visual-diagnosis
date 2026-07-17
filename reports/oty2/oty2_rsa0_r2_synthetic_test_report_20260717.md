# OTY2-RSA0-R2 Synthetic Test Report

Array bundle: `D:\profile\research\workspace\output\oty2_rsa0_r2_20260717\synthetic_tests\oty2_rsa0_r2_synthetic_arrays.npz`
Evidence card: `D:\profile\research\workspace\output\oty2_rsa0_r2_20260717\evidence_cards\synthetic_tests\synthetic_input_operation_output.png`

## SYN01_HORIZONTAL_LINE — PASS

- Input: single horizontal bright line
- Expected: Sobel-y and radial-normal response dominate
- Actual: sobel_y=240.0;sobel_x=0.0;radial=344.52001953125;tangential=119.84215545654297
- Error: `0.000000000`

## SYN02_VERTICAL_LINE — PASS

- Input: single vertical bright line
- Expected: Sobel-x dominates
- Actual: sobel_x=240.0;sobel_y=0.0
- Error: `0.000000000`

## SYN03_KNOWN_ARC — PASS

- Input: circular arc centered on fan origin
- Expected: radial-normal gradient response exceeds tangential-normal response
- Actual: radial=259.96405029296875;tangential=44.62175369262695
- Error: `0.000000000`

## SYN04_TRANSLATED_STATIC_LINE — PASS

- Input: global translations 0,2,4,6,8 px
- Expected: world stabilization reduces temporal max-min change near zero
- Actual: raw_change_mean=0.311279296875;stable_change_mean=0.0
- Error: `0.000000000`

## SYN05_TARGET_RELATIVE_BACKGROUND_MOTION — PASS

- Input: fixed background plus moving local target
- Expected: GT-aligned target stack is more stable than world stack in target ROI
- Actual: world_target_change=13.877551078796387;gt_target_change=0.0
- Error: `0.000000000`

## SYN06_SINGLE_FRAME_PULSE — PASS

- Input: positive pulse at frame 2 only
- Expected: positive change at frame 2 and negative change at frame 3
- Actual: positive_sum=180000.0;negative_sum=180000.0
- Error: `0.0`

## SYN07_CONSTANT_IMAGE — PASS

- Input: constant 42-valued five-frame stack
- Expected: gradient, highpass, MAD, and adjacent change are zero within float convolution tolerance
- Actual: max_error=1.9073486328125e-05
- Error: `1.9073486328125e-05`

