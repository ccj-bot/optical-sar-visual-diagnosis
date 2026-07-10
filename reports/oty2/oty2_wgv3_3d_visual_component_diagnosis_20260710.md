# OTY2 WGV3.3D Visual Component Diagnosis

Date: 20260710

Codex opened the generated local overlay contact images for visual inspection. PNG overlays are ignored by Git and are not committed.

| review_id | review_category | response_thread_id | sar_frame | azimuth_center | radial_pixel_center | duration_frames | dynamic_response_status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WGV33D_VIS_01 | t001_high_persistence | WGV33D_THREAD_000011 | 19 | -6.9895 | 63.9581 | 34 | dynamic_local_response_mixed |
| WGV33D_VIS_02 | t001_high_persistence | WGV33D_THREAD_000145 | 42 | 27.5251 | 70.1003 | 29 | dynamic_local_response_mixed |
| WGV33D_VIS_03 | t001_high_persistence | WGV33D_THREAD_000073 | 26 | 3.4835 | 228.0095 | 21 | dynamic_local_response_mixed |
| WGV33D_VIS_04 | transient_unlinked | WGV33D_THREAD_003333 | 676 | -3.4409 | 154.9746 | 3 | transient_unlinked |
| WGV33D_VIS_05 | transient_unlinked | WGV33D_THREAD_002570 | 474 | -6.1725 | 97.9636 | 3 | transient_unlinked |
| WGV33D_VIS_06 | background_high_response | WGV33D_THREAD_003192 | 664 | 2.4613 | 47.4169 | 65 | dynamic_local_response_mixed |
| WGV33D_VIS_07 | background_high_response | WGV33D_THREAD_003188 | 640 | -2.5779 | 138.4601 | 64 | dynamic_local_response_mixed |
| WGV33D_VIS_08 | t004_complex_window | WGV33D_THREAD_001245 | 279 | 11.9871 | 107.8464 | 93 | dynamic_local_response_mixed |

## Chinese Judgments

Static-clutter-like visual review: unavailable because the automatic response-thread bank produced 0 `static_clutter_like` threads.

### WGV33D_VIS_01 t001_high_persistence

- Overlay: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_3d_20260710/wgv3_3d_review_01_WGV33D_THREAD_000011.png`
- 判断：局部响应位于约 -6.9895 deg 方位、径向像素 63.9581；线程持续 34 帧，方位漂移 32.7081 deg、径向漂移 13.7729 px。状态为 dynamic_local_response_mixed，当前只能解释为 local_sar_response_component；需继续区分固定结构、道路/桥梁散射和非固定动态响应。

### WGV33D_VIS_02 t001_high_persistence

- Overlay: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_3d_20260710/wgv3_3d_review_02_WGV33D_THREAD_000145.png`
- 判断：局部响应位于约 27.5251 deg 方位、径向像素 70.1003；线程持续 29 帧，方位漂移 32.4582 deg、径向漂移 47.7402 px。状态为 dynamic_local_response_mixed，当前只能解释为 local_sar_response_component；需继续区分固定结构、道路/桥梁散射和非固定动态响应。

### WGV33D_VIS_03 t001_high_persistence

- Overlay: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_3d_20260710/wgv3_3d_review_03_WGV33D_THREAD_000073.png`
- 判断：局部响应位于约 3.4835 deg 方位、径向像素 228.0095；线程持续 21 帧，方位漂移 13.0011 deg、径向漂移 -12 px。状态为 dynamic_local_response_mixed，当前只能解释为 local_sar_response_component；需继续区分固定结构、道路/桥梁散射和非固定动态响应。

### WGV33D_VIS_04 transient_unlinked

- Overlay: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_3d_20260710/wgv3_3d_review_04_WGV33D_THREAD_003333.png`
- 判断：局部响应位于约 -3.4409 deg 方位、径向像素 154.9746；线程持续 3 帧，方位漂移 5.7988 deg、径向漂移 -8.3985 px。状态为 transient_unlinked，当前只能解释为 local_sar_response_component；需继续区分固定结构、道路/桥梁散射和非固定动态响应。

### WGV33D_VIS_05 transient_unlinked

- Overlay: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_3d_20260710/wgv3_3d_review_05_WGV33D_THREAD_002570.png`
- 判断：局部响应位于约 -6.1725 deg 方位、径向像素 97.9636；线程持续 3 帧，方位漂移 5.9958 deg、径向漂移 -1.5046 px。状态为 transient_unlinked，当前只能解释为 local_sar_response_component；需继续区分固定结构、道路/桥梁散射和非固定动态响应。

### WGV33D_VIS_06 background_high_response

- Overlay: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_3d_20260710/wgv3_3d_review_06_WGV33D_THREAD_003192.png`
- 判断：局部响应位于约 2.4613 deg 方位、径向像素 47.4169；线程持续 65 帧，方位漂移 59.7759 deg、径向漂移 -78.3566 px。状态为 dynamic_local_response_mixed，当前只能解释为 local_sar_response_component；需继续区分固定结构、道路/桥梁散射和非固定动态响应。

### WGV33D_VIS_07 background_high_response

- Overlay: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_3d_20260710/wgv3_3d_review_07_WGV33D_THREAD_003188.png`
- 判断：局部响应位于约 -2.5779 deg 方位、径向像素 138.4601；线程持续 64 帧，方位漂移 48.445 deg、径向漂移 34.7985 px。状态为 dynamic_local_response_mixed，当前只能解释为 local_sar_response_component；需继续区分固定结构、道路/桥梁散射和非固定动态响应。

### WGV33D_VIS_08 t004_complex_window

- Overlay: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_3d_20260710/wgv3_3d_review_08_WGV33D_THREAD_001245.png`
- 判断：局部响应位于约 11.9871 deg 方位、径向像素 107.8464；线程持续 93 帧，方位漂移 91.3361 deg、径向漂移 -22.4438 px。状态为 dynamic_local_response_mixed，当前只能解释为 local_sar_response_component；需继续区分固定结构、道路/桥梁散射和非固定动态响应。
