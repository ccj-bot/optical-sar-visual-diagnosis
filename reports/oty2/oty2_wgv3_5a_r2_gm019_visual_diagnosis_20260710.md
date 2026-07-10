# OTY2 WGV3.5A-R2 GM_RM019 Visual Diagnosis

Date: 20260710

Diagnostic PNGs are written under ignored `outputs/wgv3_5a_r2_gm019_20260710/`.

## Contact Sheets

- all_pairs: `outputs/wgv3_5a_r2_gm019_20260710/gm019_all_pair_visual_review.png`
- truncated: `outputs/wgv3_5a_r2_gm019_20260710/gm019_truncated_visual_review.png`
- failures: `outputs/wgv3_5a_r2_gm019_20260710/gm019_failed_visual_review.png`

## Chinese Review Notes

- 16个GM_RM019配对样本均已打开成接触图复核。
- 主要车辆包括近场黑色轿车、白色SUV、银色MPV、灰色左缘车辆，以及一个右缘深色碎片。
- 当前看到的车辆大多贴近图像底边或左右边，框中心不能稳定代表整车中心。
- 深度图在近场边缘框内包含路面、车身局部和背景混合，存在相对深度尺度变化风险。
- 没有满足身份明确、车体完整、无硬/软边缘截断的GM_RM019直接锚点，因此不能安全执行时序整车恢复。
- Z0只是局部观测直接投影，用来分解失败来源；Z1因锚点不足被阻断。
