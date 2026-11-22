"""The student-facing controls and schematic for the Long Valley crossing."""

from .investigation import (
    ACCESS_ROUTES, ALIGNMENTS, CROSSING_TYPES, MAP_BOTTOM, SEASONAL_HABITAT, STAGES, STATIONS, WETLAND_TOP,
    crossing_geometry, overlapping_works, seasonal_habitat,
)
from .localization import words


COPY = {
    "investigation": ("Crossing investigation", "鐵路走線探究"),
    "map": ("{} site map", "{}場地地圖"),
    "viewing_season": ("Viewing season", "查看季節"),
    "spring": ("Spring", "春季"),
    "summer": ("Summer", "夏季"),
    "autumn": ("Autumn", "秋季"),
    "winter": ("Winter", "冬季"),
    "play": ("Play seasons", "播放四季"),
    "pause": ("Pause seasons", "暫停播放四季"),
    "construction_season": ("Construction season", "施工季節"),
    "stage": ("Railway stage", "鐵路階段"),
    "construction": ("Construction", "施工"),
    "operation": ("Operation", "營運"),
    "scheduled": ("The tested crossing is scheduled for construction in {}.", "已測試的走線安排在{}施工。"),
    "opened": ("The railway is open. The permanent structures remain in every season.", "鐵路已通車，永久設施在每個季節都會保留。"),
    "inactive": ("No construction this season", "這個季節沒有施工"),
    "inactive_help": ("The map shows the planned alignment. Surface works are active only in the scheduled season.",
                      "地圖顯示規劃中的走線。地面工程只會在預定施工季節出現。"),
    "alignment": ("Railway alignment", "鐵路走線"),
    "central": ("Central crossing", "中央走線"),
    "north": ("Northern crossing", "北面走線"),
    "south": ("Southern crossing", "南面走線"),
    "crossing_type": ("Crossing type", "鐵路形式"),
    "elevated": ("Elevated railway", "高架鐵路"),
    "tunnel": ("Tunnel", "隧道"),
    "valley": ("Valley approach", "谷中通道"),
    "east": ("East approach", "東面通道"),
    "access": ("Construction access route", "施工通道"),
    "supports": ("Bridge supports", "橋墩"),
    "entrances": ("Tunnel entrances", "隧道出入口"),
    "temporary": ("Temporary", "臨時"),
    "permanent": ("Permanent", "永久"),
    "map_key": ("Map key", "圖例"),
    "test": ("Test crossing", "測試走線"),
    "comparison": ("Compare the same site and season", "比較同一場地和季節"),
    "proposed": ("With proposed works", "有擬議工程"),
    "baseline": ("Without proposed works", "無擬議工程"),
    "baseline_title": ("{} baseline", "{}基準"),
    "baseline_help": ("The same seasonal habitat is shown without a railway footprint.",
                      "這個畫面顯示相同的季節生境，沒有鐵路佔地。"),
    "replay": ("Replay crossing", "重播走線測試"),
    "replayed": ("Crossing replayed.", "已重播走線測試。"),
    "reset": ("Reset crossing", "重設走線"),
    "station_west": ("West station", "西面車站"),
    "station_east": ("East station", "東面車站"),
    "wetland": ("Wetland", "濕地"),
    "river": ("River", "河道"),
    "habitat_spring": ("Modelled nesting habitat", "模型中的築巢生境"),
    "habitat_summer": ("Modelled habitat for young birds", "模型中的幼鳥生境"),
    "habitat_autumn": ("Modelled harvest feeding habitat", "模型中的稻田覓食生境"),
    "habitat_winter": ("Modelled wintering bird habitat", "模型中的候鳥越冬生境"),
    "overlap": ("Footprint overlap", "佔地重疊範圍"),
    "select_overlap": ("Select a striped area to inspect the overlap.", "選取斜紋區域，查看該處的重疊情況。"),
    "inspect_work": ("Inspect overlap for {}", "查看{}的重疊範圍"),
    "finding": ("Possible disturbance", "可能造成滋擾"),
    "inspect": ("Inspect the evidence", "查看證據"),
    "no_overlap": ("No modelled overlap", "模型未顯示重疊"),
    "no_overlap_help": ("The visible railway footprints are clear of the {}.", "圖中可見的鐵路佔地避開了{}。"),
    "access_evidence": ("Construction access route overlaps {}.", "施工通道與{}重疊。"),
    "supports_evidence": ("Bridge supports overlap {}.", "橋墩與{}重疊。"),
    "entrances_evidence": ("Tunnel entrances overlap {}.", "隧道出入口與{}重疊。"),
    "finding_context": ("Site {} · {} · {}", "場地 {} · {} · {}"),
    "rule_title": ("How the model works", "模型如何判斷？"),
    "rule": ("The habitat shapes are drawn for this classroom experiment. Stripes mark where a surface footprint covers part of the modelled habitat for that season. This overlap flags possible disturbance.",
             "生境範圍是為課堂探究繪製的。斜紋標出地面佔地與該季模型生境重疊的位置。模型以重疊範圍標示可能造成滋擾的地方。"),
    "observed": ("Observed at Long Valley", "塱原實地觀察"),
    "observed_spring": ("Black-winged stilts and common moorhens build nests in spring.",
                        "黑翅長腳鷸和黑水雞在春季築巢。"),
    "observed_summer": ("Young black-winged stilts and common moorhens feed and grow in the summer wetlands.",
                        "黑翅長腳鷸和黑水雞的幼鳥在夏季的濕地覓食和成長。"),
    "observed_autumn": ("Ripe rice offers food for migratory birds arriving around the autumn harvest.",
                        "秋收時節，成熟的稻穀為到訪的候鳥提供食物。"),
    "observed_winter": ("Winter visitors to the wetland include Eurasian teal and common snipe.",
                        "冬季到訪濕地的候鳥包括綠翅鴨和扇尾沙錐。"),
    "source": ("Long Valley Nature Park seasonal guide", "塱原自然生態公園四季指南"),
}


def select_control(key, choices, current, t):
    options = "".join(
        f'<option value="{value}"{" selected" if value == current else ""}>{t[value]}</option>'
        for value in choices
    )
    return f"""<div>
  <label for="design-{key}">{t[key]}</label>
  <select id="design-{key}" name="{key}">{options}</select>
</div>"""


def crossing_investigation(session, group, season, notice):
    t = words(group.language, COPY)
    draft = group.draft_design
    return f"""<section class="investigation" id="crossing-investigation" aria-labelledby="crossing-title">
  <script src="/season-playback.js" defer></script>
  <h3 id="crossing-title">{t["investigation"]}</h3>
  <form class="crossing-controls" id="crossing-design" action="/join/{session.code}/view?lang={group.language}" method="post">
    <input type="hidden" name="season" value="{season}">
    {select_control("alignment", ALIGNMENTS, draft.alignment, t)}
    {select_control("crossing_type", CROSSING_TYPES, draft.crossing_type, t)}
    {select_control("access", ACCESS_ROUTES, draft.access_route, t)}
    {select_control("construction_season", SEASONAL_HABITAT, draft.construction_season, t)}
    <div class="design-actions">
      <button formaction="/join/{session.code}/design?lang={group.language}">{t["test"]}</button>
      <button class="secondary" name="view" value="reset">{t["reset"]}</button>
    </div>
  </form>
  <div>
    {crossing_comparison(group, season, notice, t)}
    {model_rule(t)}
  </div>
</section>"""


def crossing_comparison(group, season, notice, t):
    season_buttons = "".join(view_button(key, key == season, t) for key in SEASONAL_HABITAT)
    stage_buttons = "".join(view_button(key, key == group.stage, t) for key in STAGES)
    crossing = crossing_geometry(group.tested_design) if group.show_works else None
    scenes = {key: season_scene(group, key, crossing, t) for key in SEASONAL_HABITAT}
    current_scene = scenes.pop(season)
    templates = "".join(f'<template data-season="{key}">{scene}</template>' for key, scene in scenes.items())
    status = f'<p class="experiment-status" role="status">{t[notice]}</p>' if notice == "replayed" else ""
    return f"""<div id="crossing-comparison">
  <div class="season-controls">
    <span id="season-label">{t["viewing_season"]}</span>
    <div id="season-buttons" class="compare-controls" role="group" aria-labelledby="season-label">
      {season_buttons}
    </div>
    <button id="play-seasons" class="secondary" type="button" data-pause="{t["pause"]}" hidden>{t["play"]}</button>
    <span class="screen-reader-only" id="season-announcement" aria-live="polite"></span>
  </div>
  <div class="compare-controls" role="group" aria-label="{t["stage"]}">{stage_buttons}</div>
  <div class="compare-controls" role="group" aria-label="{t["comparison"]}">
    {view_button("proposed", group.show_works, t)}
    {view_button("baseline", not group.show_works, t)}
    <button class="secondary replay" form="crossing-design" name="view" value="replay">{t["replay"]}</button>
  </div>
  {status}
  <div id="season-scene">{current_scene}</div>
  {templates}
</div>"""


def season_scene(group, season, crossing, t):
    design = group.tested_design
    scheduled = design.construction_season == season
    works = crossing.active_footprints(group.stage, scheduled) if crossing else {}
    habitat = seasonal_habitat(group.site, season)
    overlaps = overlapping_works(works, habitat)
    keys = ["habitat"]
    if crossing:
        keys.extend([design.crossing_type, *works])
    if overlaps:
        keys.append("overlap")
    stage_status = ""
    if crossing:
        status = t["opened"] if group.stage == "operation" else t["scheduled"].format(t[design.construction_season])
        stage_status = f'<p class="stage-status">{status}</p>'
    return f"""<div>
  {stage_status}
  {site_map(group.site, season, crossing, works, habitat, overlaps, t)}
  <ul class="map-key" aria-label="{t["map_key"]}">{map_key(keys, season, t)}</ul>
  {finding_panel(group, season, overlaps, scheduled, t)}
  {season_observation(group.language, season, t)}
</div>"""


def view_button(view, active, t):
    pressed = "true" if active else "false"
    return f'<button class="secondary" form="crossing-design" name="view" value="{view}" aria-pressed="{pressed}">{t[view]}</button>'


def map_key(keys, season, t):
    items = []
    lifetimes = {"access": "temporary", "supports": "permanent", "entrances": "permanent"}
    for key in keys:
        label = t[f"habitat_{season}"] if key == "habitat" else t[key]
        tag = f'<small class="work-lifetime">{t[lifetimes[key]]}</small>' if key in lifetimes else ""
        items.append(f'<li><span class="key-mark {key}"></span><span>{label}</span>{tag}</li>')
    return "".join(items)


def finding_panel(group, season, overlaps, scheduled, t):
    habitat = t[f"habitat_{season}"].lower()
    if not group.show_works:
        title = t["baseline_title"].format(t[season])
        return f'<div class="finding clear"><strong>{title}</strong><p>{t["baseline_help"]}</p></div>'
    if group.stage == "construction" and not scheduled:
        return f'<div class="finding clear"><strong>{t["inactive"]}</strong><p>{t["inactive_help"]}</p></div>'
    if not overlaps:
        return (f'<div class="finding clear"><strong>{t["no_overlap"]}</strong>'
                f'<p>{t["no_overlap_help"].format(habitat)}</p></div>')
    context = t["finding_context"].format(group.site, t[season], t[group.stage])
    evidence = "".join(
        f'<li id="evidence-{work}" tabindex="-1">{t[work + "_evidence"].format(habitat)}</li>' for work in overlaps
    )
    return f"""<p class="map-help">{t["select_overlap"]}</p>
<details class="finding disturbance">
  <summary><strong>{t["finding"]}</strong><span>{t["inspect"]}</span></summary>
  <p class="evidence-context">{context}</p>
  <ul>{evidence}</ul>
</details>"""


def season_observation(language, season, t):
    locale = "tc" if language == "zh-Hant" else "en"
    source = f"https://www.lvnp.gov.hk/{locale}/LVNP_Seasonal_attractions.htm"
    return f"""<aside class="season-observation" aria-label="{t["observed"]}">
  <strong>{t["observed"]}</strong>
  <p>{t[f"observed_{season}"]} <a href="{source}" target="_blank" rel="noopener">{t["source"]}</a></p>
</aside>"""


def model_rule(t):
    return f"""<details class="model-rule">
  <summary>{t["rule_title"]}</summary>
  <p>{t["rule"]}</p>
</details>"""


def railway_segment(points, style=""):
    coordinates = " ".join(f"{x},{y}" for x, y in points)
    return f'<polyline class="map-railway{style}" points="{coordinates}"/>'


def footprint_rect(footprint, style):
    return (f'<rect class="{style}" x="{footprint.x}" y="{footprint.y}" '
            f'width="{footprint.width}" height="{footprint.height}"/>')


def overlap_links(overlaps, t):
    hit_areas = []
    highlights = []
    for work, boxes in overlaps.items():
        href = f'#evidence-{work}'
        label = t["inspect_work"].format(t[work])
        for box in boxes:
            hit_areas.append(f'<a href="{href}" tabindex="-1" aria-hidden="true">'
                             f'{footprint_rect(box, "map-overlap-hit")}</a>')
            highlights.append(f'<a href="{href}" aria-label="{label}">'
                              f'{footprint_rect(box, "map-overlap")}</a>')
    # Draw all visible links above the touch padding of neighbouring highlights.
    return "".join(hit_areas + highlights)


def site_map(site, season, crossing, works, habitat, overlaps, t):
    wetland_top = WETLAND_TOP[site]
    railway = ""
    footprints = ""
    if crossing:
        railway = ("".join(railway_segment(line) for line in crossing.surface_lines)
                   + "".join(railway_segment(line, " map-tunnel") for line in crossing.tunnel_lines))
        if not works:
            railway = f'<g class="planned-railway">{railway}</g>'
        footprints = "".join(footprint_rect(box, f"map-{work}")
                             for work, boxes in works.items() for box in boxes)
    stations = "".join(
        f'<rect class="map-station" x="{x - 7}" y="{y - 7}" width="14" height="14" rx="3"/>'
        f'<text x="{x}" y="{y + 31}" text-anchor="middle">{t[key]}</text>'
        for (x, y), key in zip(STATIONS, ("station_west", "station_east"))
    )
    map_label = t["map"].format(t[season])
    return f"""<svg class="site-map" data-season="{season}" viewBox="0 0 720 {MAP_BOTTOM}" role="group" aria-label="{map_label}" aria-describedby="site-map-features">
  <desc id="site-map-features">{t["river"]} · {t["wetland"]} · {t["station_west"]} · {t["station_east"]}</desc>
  <defs>
    <pattern id="footprint-overlap" patternUnits="userSpaceOnUse" width="5" height="5" patternTransform="rotate(45)">
      <rect width="5" height="5" fill="#ffdea1"/>
      <path d="M0 0V5" stroke="#9a3c20" stroke-width="3"/>
    </pattern>
  </defs>
  <rect class="map-land" width="720" height="{MAP_BOTTOM}"/>
  <path class="map-fields" d="M0 77H174L185 156H0Z M192 77H289L280 156H204Z M474 77H720V156H507Z
    M0 263H125L143 344H0Z M145 263H251L230 344H163Z M477 263H565L547 344H457Z M586 263H720V344H568Z"/>
  <path class="map-river" d="M0 0H720V40Q594 31 484 47T242 45T0 50Z"/>
  <text x="34" y="31">{t["river"]}</text>
  <rect class="map-wetland" x="225" y="{wetland_top}" width="270" height="104" rx="28"/>
  {footprint_rect(habitat, "map-habitat")}
  {railway}
  {footprints}
  {overlap_links(overlaps, t)}
  <text x="407" y="{wetland_top + 97}" text-anchor="middle">{t["wetland"]}</text>
  {stations}
</svg>"""
