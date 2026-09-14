import json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
index=json.loads((R/'footprint_visuals/visual_index.json').read_text())
# Authored AFTER actual view_image calls on five numbered montages and four risk originals,
# plus an explicitly upscaled low-resolution risk crop. Not a geometric quality score.
observations={
1:('plausible_visible_body','unavailable_geometry_rejected','unavailable','qualitatively_valid_proxy','黑色SUV可见轮廓大致贴合车身；无橙色候选（切带几何拒绝）。紫色框仅覆盖前轮/前保险杠附近的宽松下部ROI，包含路面，非接地面。'),
2:('plausible_visible_body','plausible_visible_bottom_only','qualitatively_valid_proxy','qualitatively_valid_proxy','白色SUV轮廓贴合车身；橙色带沿前轮与下保险杠，遗漏透视后轮接地点，作为可见底带可解释，不能代表整车地面占用。紫框为较宽下部ROI。'),
3:('plausible_visible_body','plausible_visible_bottom_only','qualitatively_valid_proxy','qualitatively_valid_proxy','银色轿车可见外轮廓合理；底带覆盖近侧前轮和前保险杠下缘，不覆盖远端轮胎接地。紫框包含下方路面，只有ROI意义。'),
4:('partial_occluded_truncated','unavailable_geometry_rejected','unavailable','uncertain','白色轿车左端被图像边缘截断，尾端受黑车遮挡；原mask沿遮挡轮廓并有异常窄连接。无候选。紫框跨到遮挡车辆，不能视为清晰单车底部代理。'),
5:('partial_occluded','uncertain_occluded_contact','uncertain','uncertain','后排白车被前排车辆严重遮挡；橙带只落在可见轮胎小片区域，紫框穿过邻车。不能确认完整目标的下部代理质量。'),
6:('plausible_visible_body','plausible_visible_bottom_only','qualitatively_valid_proxy','qualitatively_valid_proxy','白色轿车正前方轮廓大致合理；橙带覆盖前保险杠和可见近侧轮胎底部，紫框为前下部粗ROI。仍非真实ground footprint。'),
7:('poor_background_fragment_contamination','unavailable_geometry_rejected','unavailable','qualitatively_valid_proxy','白色面包车主体轮廓大致对齐，但左侧出现邻车/镜子附近多余细碎环线，不能当成干净mask。无橙带。紫框在面包车前轮和低保险杠附近，粗ROI视觉可解释。'),
8:('partial_truncated','uncertain_truncated','uncertain','uncertain','夜间银车前部在右图像边缘截断；橙带和紫框均被边界切掉。只看到局部，保持不确定。'),
9:('partial_top_truncated_body_lower_visible','plausible_visible_bottom_only','qualitatively_valid_proxy','qualitatively_valid_proxy','皮卡车顶被图像上边界截断，但正前方双轮和下保险杠清楚可见；橙带沿前下部、紫框围绕下部，作为局部可见proxy合理。截断风险保留，绝不ground validated。'),
10:('uncertain_low_resolution_occlusion','uncertain_low_resolution_occlusion','uncertain','uncertain','远处红车目标小且左下方被白车遮挡；当前真实像素不足以确认轮胎/下缘质量，几何合法不能代替视觉通过。'),
11:('uncertain_low_resolution_occlusion','uncertain_low_resolution_occlusion','uncertain','uncertain','远处并排白车相互遮挡；橙色区域与紫框紧邻多个车辆下缘，分辨率不足，未给视觉合理通过。'),
12:('partial_truncated','unavailable_disconnected_band','unavailable','uncertain','黑色侧视车辆左端截断，轮胎底端与车身下沿形成分开的低处；未输出橙带。紫框夹带大量路面且目标不完整。'),
13:('poor_background_fragment_contamination','unavailable_geometry_rejected','unavailable','qualitatively_valid_proxy','蓝色SUV主体mask大体对齐，左上方连入邻近白车附近的细环/片段，原轮廓非干净单体。无橙带。紫框覆盖SUV近侧前轮和低前部，可作为粗ROI。'),
14:('plausible_visible_body','plausible_visible_bottom_only','qualitatively_valid_proxy','qualitatively_valid_proxy','白色轿车轮廓及橙色底带大体贴合可见前轮/前裙；紫框为下部粗ROI，包含投影下的路面。两者仅视觉proxy合理。'),
15:('uncertain_low_resolution_occlusion','unavailable_geometry_rejected','unavailable','uncertain','远处货车很小，下部被近处车辆遮挡；底部候选未输出。紫框处真实轮胎/地面不可分辨，不作视觉通过。'),
16:('plausible_visible_body','plausible_visible_bottom_only','qualitatively_valid_proxy','qualitatively_valid_proxy','正前方白色SUV可见主体轮廓合理；橙带顺着前裙和前轮低处，紫框覆盖同一区域。整车后部接地不可见，仅proxy合理。'),
17:('plausible_visible_body','unavailable_disconnected_band','unavailable','qualitatively_valid_proxy','放大后灰色MPV的可见外轮廓合理；后轮和近侧前轮低处被较高底盘连接，底带若直接连成单polygon会跨越非mask区域。拒绝橙带正确；紫框为宽松前下部ROI。'),
18:('uncertain_low_resolution_truncation','uncertain_low_resolution_truncation','uncertain','uncertain','原始风险小图及5倍插值放大均已查看。目标紧贴边界且像素极少，车轮与阴影不清，橙带与紫框几乎压成细线；放大不增加证据，保持不确定。'),
19:('poor_mask_bbox_target_inconsistency','poor_occlusion_boundary_not_ground','poor','poor','风险放大明确：青色mask在后方白色车的车窗/上车身，可见下缘是被前方黑车遮挡的边界；橙带落在遮挡边界，不是轮胎/底部。紫色bbox下带却落在前方黑车保险杠。mask/bbox目标归属不一致，两proxy均不可视觉通过。'),
20:('plausible_body_with_mirror_contour_artifacts','unavailable_geometry_rejected','unavailable','qualitatively_valid_proxy','黑色SUV正前方轮廓主体贴合，镜子周围局部细线不够干净；原polygon有几何问题，因此无橙带。紫框与双前轮和低保险杠对齐，仅粗ROI合理。')}
reviews=[]
for i in index:
    n=i['number'];mask,band,aq,bq,note=observations[n]
    evidence=[i['montage']]
    if i['risk_enlargement']:evidence.append(i['risk_enlargement'])
    if n==18:evidence.append(str(R/'footprint_visuals/risk_18_5x_no_new_detail.jpg'))
    reviews.append(dict(number=n,image_id=i['image_id'],vehicle_id=i['vehicle_id'],mask_visual_quality=mask,contact_band_quality=band,mask_method_proxy_quality=aq,bbox_method_proxy_quality=bq,observations=note,evidence=evidence))
    i['review_status']='reviewed_pixels_via_view_image'
(R/'visual_review_log.json').write_text(json.dumps({'source_sha256':index[0]['source_sha256'],'review_date':'2026-09-10','reviewer':'AI visual reviewer via view_image; not human gold',
 'definition':'qualitatively_valid_proxy is visible lower-band/coarse ROI plausibility, never groundvalidated. Unreviewed population is not extrapolated.',
 'sampling':'16 fixed evenly spaced target indices + 4 first-distinct-risk examples; labels not used to select sample', 'reviews':reviews},ensure_ascii=False,indent=2)+'\n')
(R/'footprint_visuals/visual_index.json').write_text(json.dumps(index,indent=2)+'\n')
