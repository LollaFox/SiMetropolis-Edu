"""Controls and map views for the spring investigation."""

from .investigation import (
    ACCESS_ROUTES, ALIGNMENTS, CROSSING_TYPES, MAP_BOTTOM, STATIONS, WETLAND_TOP,
    crossing_geometry, nesting_habitat, overlapping_works,
)
from .localization import words


COPY = {
    "spring": ("Spring investigation", "春季探究"),
    "map": ("Spring site map", "春季場地地圖"),
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
    "map_key": ("Map key", "圖例"),
    "test": ("Test crossing", "測試走線"),
    "save": ("Save for swap", "儲存走線以交換場地"),
    "saved": ("Crossing saved for Pass the City.", "已儲存走線，交換場地後可繼續測試。"),
    "comparison": ("Compare the same spring site", "比較同一個春季場地"),
    "proposed": ("With proposed works", "有擬議工程"),
    "baseline": ("Without proposed works", "無擬議工程"),
    "baseline_title": ("Spring baseline", "春季基準"),
    "baseline_help": ("This view shows the same spring site before any railway works.", "這個畫面顯示鐵路工程展開前的同一個春季場地。"),
    "replay": ("Replay crossing", "重播走線測試"),
    "replayed": ("Crossing replayed.", "已重播走線測試。"),
    "reset": ("Reset crossing", "重設走線"),
    "share": ("Share comparison", "分享比較結果"),
    "shared": ("Comparison shared with your teacher.", "已與老師分享比較結果。"),
    "station_west": ("West station", "西面車站"),
    "station_east": ("East station", "東面車站"),
    "wetland": ("Wetland", "濕地"),
    "river": ("River", "河道"),
    "habitat": ("Modelled nesting habitat", "模型中的築巢生境"),
    "overlap": ("Footprint overlap", "佔地重疊範圍"),
    "select_overlap": ("Select a striped area to inspect the overlap.", "選取斜紋區域，查看該處的重疊情況。"),
    "inspect_work": ("Inspect overlap for {}", "查看{}的重疊範圍"),
    "finding": ("Possible disturbance", "可能造成滋擾"),
    "inspect": ("Inspect the evidence", "查看證據"),
    "no_overlap": ("No modelled overlap", "模型未顯示重疊"),
    "no_overlap_help": ("In this test, all surface works are clear of the modelled nesting habitat.",
                        "在這次測試中，所有地面工程都避開了模型中的築巢生境。"),
    "access_evidence": ("Construction access route overlaps modelled nesting habitat.", "施工通道與模型中的築巢生境重疊。"),
    "supports_evidence": ("Bridge supports overlap modelled nesting habitat.", "橋墩與模型中的築巢生境重疊。"),
    "entrances_evidence": ("Tunnel entrances overlap modelled nesting habitat.", "隧道出入口與模型中的築巢生境重疊。"),
    "rule_title": ("How the spring model works", "春季模型如何判斷？"),
    "rule": ("The model flags possible disturbance wherever a surface work covers part of the spring nesting habitat. The striped area on the map shows exactly where the footprints overlap.",
             "地面工程的佔地只要覆蓋部分春季築巢生境，模型就會標示可能造成滋擾。地圖上的斜紋標出兩者實際重疊的位置。"),
    "basis": ("Birds such as black-winged stilts nest at Long Valley in spring. The habitat shown here is drawn for the classroom model.",
              "黑翅長腳鷸等雀鳥會在春季於塱原築巢。圖中的生境範圍是為課堂模型繪製的。"),
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


def spring_investigation(session, group, notice):
    t = words(group.language, COPY)
    draft = group.draft_design
    design_action = f"/join/{session.code}/design?lang={group.language}"
    save = "" if session.swapped else f"""<button class="secondary" formaction="{design_action}"
      name="save" value="1">{t["save"]}</button>"""
    return f"""<section class="investigation" id="spring-investigation" aria-labelledby="spring-title">
  <h3 id="spring-title">{t["spring"]}</h3>
  <form class="crossing-controls" id="crossing-design" action="/join/{session.code}/view?lang={group.language}"
    method="post" autocomplete="off">
    <input type="hidden" name="revision" value="{group.revision}">
    <input type="hidden" name="site" value="{group.site}">
    {select_control("alignment", ALIGNMENTS, draft.alignment, t)}
    {select_control("crossing_type", CROSSING_TYPES, draft.crossing_type, t)}
    {select_control("access", ACCESS_ROUTES, draft.access_route, t)}
    <div class="design-actions">
      <button formaction="{design_action}">{t["test"]}</button>
      {save}
      <button class="secondary" name="view" value="reset">{t["reset"]}</button>
    </div>
  </form>
  <div>
    {spring_comparison(session, group, t, notice)}
    {model_rule(group.language, t)}
  </div>
</section>"""


def spring_comparison(session, group, t, notice):
    status = ""
    if notice in {"replayed", "saved", "shared"}:
        status = f'<p class="experiment-status" role="status">{t[notice]}</p>'
    comparison_key, comparison = group.capture_comparison()
    return f"""<div id="spring-comparison">
  <div class="compare-controls" role="group" aria-label="{t["comparison"]}">
    {view_button("proposed", group.show_works, t)}
    {view_button("baseline", not group.show_works, t)}
    <button class="secondary replay" form="crossing-design" name="view" value="replay">{t["replay"]}</button>
    <button class="secondary" form="crossing-design" name="comparison" value="{comparison_key}"
      formaction="/join/{session.code}/share?lang={group.language}">{t["share"]}</button>
  </div>
  {status}
  {spring_result(comparison, group.show_works, t, "spring")}
</div>"""


def design_summary(design, language):
    t = words(language, COPY)
    return " · ".join(t[key] for key in (design.alignment, design.crossing_type, design.access_route))


def projected_maps(comparison, language):
    t = words(language, COPY)
    return f"""<div class="comparison-maps">
  <section aria-labelledby="baseline-heading">
    <h2 id="baseline-heading">{t["baseline"]}</h2>
    {spring_result(comparison, False, t, "baseline")}
  </section>
  <section aria-labelledby="proposed-heading">
    <h2 id="proposed-heading">{t["proposed"]}</h2>
    {spring_result(comparison, True, t, "proposed", expanded=True)}
  </section>
</div>"""


def spring_result(comparison, show_works, t, prefix, *, expanded=False):
    design = comparison.design if show_works else None
    crossing = crossing_geometry(design) if design else None
    works = crossing.works if crossing else {}
    habitat = nesting_habitat(comparison.site)
    overlaps = overlapping_works(works, habitat)
    keys = ["habitat"]
    if design:
        keys.extend([design.crossing_type, *works])
    if overlaps:
        keys.append("overlap")
    return f"""{spring_map(comparison.site, crossing, habitat, overlaps, t, prefix)}
  <ul class="map-key" aria-label="{t["map_key"]}">{map_key(keys, t)}</ul>
  {finding_panel(show_works, overlaps, t, expanded=expanded)}"""


def view_button(view, active, t):
    pressed = "true" if active else "false"
    return f'<button class="secondary" form="crossing-design" name="view" value="{view}" aria-pressed="{pressed}">{t[view]}</button>'


def map_key(keys, t):
    return "".join(f'<li><span class="key-mark {key}"></span>{t[key]}</li>' for key in keys)


def finding_panel(show_works, overlaps, t, *, expanded=False):
    if not show_works:
        return f'<div class="finding clear"><strong>{t["baseline_title"]}</strong><p>{t["baseline_help"]}</p></div>'
    if not overlaps:
        return f'<div class="finding clear"><strong>{t["no_overlap"]}</strong><p>{t["no_overlap_help"]}</p></div>'
    evidence = "".join(
        f'<li id="evidence-{work}" tabindex="-1">{t[work + "_evidence"]}</li>' for work in overlaps
    )
    help_text = "" if expanded else f'<p class="map-help">{t["select_overlap"]}</p>'
    inspect_label = "" if expanded else f'<span>{t["inspect"]}</span>'
    return f"""{help_text}
<details class="finding disturbance"{" open" if expanded else ""}>
  <summary><strong>{t["finding"]}</strong>{inspect_label}</summary>
  <ul>{evidence}</ul>
</details>"""


def model_rule(language, t):
    locale = "tc" if language == "zh-Hant" else "en"
    source = f"https://www.lvnp.gov.hk/{locale}/LVNP_Seasonal_attractions.htm"
    return f"""<details class="model-rule">
  <summary>{t["rule_title"]}</summary>
  <p>{t["rule"]}</p>
  <p>{t["basis"]} <a href="{source}" target="_blank" rel="noopener">{t["source"]}</a></p>
</details>"""


def railway_segment(points, style=""):
    coordinates = " ".join(f"{x},{y}" for x, y in points)
    return f'<polyline class="map-railway{style}" points="{coordinates}"/>'


def footprint_rect(footprint, style):
    return (f'<rect class="{style}" x="{footprint.x}" y="{footprint.y}" '
            f'width="{footprint.width}" height="{footprint.height}"/>')


def overlap_links(overlaps, t, prefix):
    hit_areas = []
    highlights = []
    for work, boxes in overlaps.items():
        href = f'#evidence-{work}'
        label = t["inspect_work"].format(t[work])
        for box in boxes:
            hit_areas.append(f'<a href="{href}" tabindex="-1" aria-hidden="true">'
                             f'{footprint_rect(box, "map-overlap-hit")}</a>')
            highlights.append(f'<a href="{href}" aria-label="{label}" fill="url(#{prefix}-overlap)">'
                              f'{footprint_rect(box, "map-overlap")}</a>')
    # Draw all visible links above the touch padding of neighbouring highlights.
    return "".join(hit_areas + highlights)


def spring_map(site, crossing, habitat, overlaps, t, prefix):
    wetland_top = WETLAND_TOP[site]
    railway = ""
    footprints = ""
    if crossing:
        railway = ("".join(railway_segment(line) for line in crossing.surface_lines)
                   + "".join(railway_segment(line, " map-tunnel") for line in crossing.tunnel_lines))
        footprints = "".join(footprint_rect(box, f"map-{work}")
                             for work, boxes in crossing.works.items() for box in boxes)
    stations = "".join(
        f'<rect class="map-station" x="{x - 7}" y="{y - 7}" width="14" height="14" rx="3"/>'
        f'<text x="{x}" y="{y + 31}" text-anchor="middle">{t[key]}</text>'
        for (x, y), key in zip(STATIONS, ("station_west", "station_east"))
    )
    return f"""<svg class="site-map" viewBox="0 0 720 {MAP_BOTTOM}" role="group" aria-label="{t["map"]}" aria-describedby="{prefix}-map-features">
  <desc id="{prefix}-map-features">{t["river"]} · {t["wetland"]} · {t["station_west"]} · {t["station_east"]}</desc>
  <defs>
    <pattern id="{prefix}-overlap" patternUnits="userSpaceOnUse" width="5" height="5" patternTransform="rotate(45)">
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
  {overlap_links(overlaps, t, prefix)}
  <text x="407" y="{wetland_top + 97}" text-anchor="middle">{t["wetland"]}</text>
  {stations}
</svg>"""
