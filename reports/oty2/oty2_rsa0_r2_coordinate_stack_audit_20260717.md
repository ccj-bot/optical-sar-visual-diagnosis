# OTY2-RSA0-R2 Coordinate-Stack Audit

All four stacks use complete contiguous five-frame windows. Image, geometry, points, and valid-source masks share the same translation matrix within each aligned family.

## PV002_337_341

- `RAW_SAR_DISPLAY`: point closure max `0.000000` px; mask IoU min `1.000000`; image reconstruction MAE max `0.000000`.
- `WORLD_STABILIZED_IMAGE_STACK`: point closure max `0.000000` px; mask IoU min `0.993737`; image reconstruction MAE max `2.298725`.
- `GT_ALIGNED_RESEARCH_STACK`: point closure max `0.000000` px; mask IoU min `0.990817`; image reconstruction MAE max `2.032614`.
- `OPTICAL_PROXY_ALIGNED_STACK`: point closure max `0.000000` px; mask IoU min `0.994273`; image reconstruction MAE max `2.204005`.
- Actual background patch NCC median: RAW `0.642894`, WORLD `0.751868`.

## PV003_380_384

- `RAW_SAR_DISPLAY`: point closure max `0.000000` px; mask IoU min `1.000000`; image reconstruction MAE max `0.000000`.
- `WORLD_STABILIZED_IMAGE_STACK`: point closure max `0.000000` px; mask IoU min `0.993468`; image reconstruction MAE max `1.619455`.
- `GT_ALIGNED_RESEARCH_STACK`: point closure max `0.000000` px; mask IoU min `0.991570`; image reconstruction MAE max `1.554974`.
- `OPTICAL_PROXY_ALIGNED_STACK`: point closure max `0.000000` px; mask IoU min `0.993111`; image reconstruction MAE max `2.032972`.
- Actual background patch NCC median: RAW `-0.005846`, WORLD `0.054189`.

