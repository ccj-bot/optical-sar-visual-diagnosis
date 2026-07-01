# GM_RM011 Caution Notes

GM_RM011 must not mechanically copy GM_RM019.

GM_RM019 is the current pilot. GM_RM011 has not reproduced the same candidate input chain and may have scene-specific geometry or OBB convention risks.

Before claiming cross-scene generalization, first run probe and geometry convention audit for GM_RM011. Check:

- optical/SAR frame path mapping
- SAR frame numbering
- whether fan center / azimuth mapping can be shared
- whether `w/h/heading` storage-axis conventions are mixed
- whether OBB convention matches GM_RM019
- whether SAR target visual structure differs
- whether range prior is systematically biased
- whether GM_RM011 needs a separate candidate generation policy

Until this is done, GM_RM011 should be treated as a probe scene, not as proof of generalization.
