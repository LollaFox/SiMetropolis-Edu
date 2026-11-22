"""Localized HTML for the classroom."""

from base64 import b64encode
from hashlib import sha256
from html import escape
from math import ceil
from pathlib import Path
from urllib.parse import quote, urlencode

from .investigation_views import design_summary, projected_maps, spring_investigation
from .localization import words
from .state import CODE_LENGTH, SITES


GROUP_STATUS_SCRIPT = Path(__file__).with_name("static").joinpath("load-class-status.js").read_text(encoding="utf-8")
GROUP_STATUS_SCRIPT_HASH = b64encode(sha256(GROUP_STATUS_SCRIPT.encode()).digest()).decode()


LANGUAGES = {"en": "English", "zh-Hant": "繁體中文"}
COPY = {
    "name": ("Long Valley classroom", "塱原課堂"),
    "student_entry": ("Join as a group", "以小組身分加入"),
    "teacher_entry": ("Teacher view", "教師介面"),
    "credential": ("Teacher credential", "教師憑證"),
    "sign_in": ("Sign in", "登入"),
    "bad_credential": ("Check your teacher credential and try again.", "請檢查教師憑證，然後再試一次。"),
    "launch_wait": ("Opening the teacher view…", "正在開啟教師介面⋯"),
    "launch_renewed": ("Your sign-in link expired. Continue in the new teacher tab.",
                       "登入連結已逾時。請到新開啟的教師分頁繼續。"),
    "launch_error": ("Open SiMetropolis Edu again to reach the teacher view.", "請重新開啟 SiMetropolis Edu，以進入教師介面。"),
    "start_title": ("Open a Long Valley class", "開啟塱原課堂"),
    "start_help": ("Choose the language groups see when they join.", "選擇小組加入時使用的語言。"),
    "starting_language": ("Starting language", "起始語言"),
    "start": ("Start class", "開始課堂"),
    "open": ("Your class is open", "課堂已開啟"),
    "time_remaining": ("Time remaining", "剩餘時間"),
    "project": ("Project join information", "投影加入資訊"),
    "project_help": ("Open the join information in this browser and show that tab on the projector.", "請在此瀏覽器開啟加入資訊，並將該分頁投影給小組。"),
    "network_problem": ("The classroom network is unavailable. Edu is retrying automatically.",
                        "無法連接課堂網絡。Edu 正在自動重試。"),
    "network_settings": ("Open network settings", "開啟網絡設定"),
    "network_settings_error": ("Edu couldn’t open network settings. Open them from your computer’s settings menu.",
                               "Edu 無法開啟網絡設定。請從電腦的設定選單開啟。"),
    "shared_comparisons": ("Shared comparisons", "已分享的比較結果"),
    "select_comparison": ("Choose a comparison to show on the projector.", "選擇要投影的比較結果。"),
    "no_comparisons": ("No group has shared a comparison yet.", "暫時沒有小組分享比較結果。"),
    "back_to_comparisons": ("Back to shared comparisons", "返回已分享的比較結果"),
    "spring_construction": ("Spring · Construction", "春季 · 施工階段"),
    "pass_the_city": ("Pass the City", "交換場地"),
    "pass_help": ("Ask both groups to save a crossing, then send them to their partner sites.",
                  "請兩組各自儲存走線，然後讓兩組交換場地。"),
    "pass_waiting": ("Both groups need to join before you can swap sites.", "兩組都加入課堂後，便可交換場地。"),
    "pass_done": ("Both groups have moved to their partner sites.", "兩組已到達對方的場地。"),
    "partner_site": ("You’re at your partner site. Try your crossing here.", "你們已到達對方的場地。試試你們的走線吧。"),
    "checking_site": ("Checking your current site…", "正在確認你們的場地⋯"),
    "opening_partner": ("Opening your partner site…", "正在開啟對方的場地⋯"),
    "end": ("End class", "結束課堂"),
    "sign_out": ("Sign out", "登出"),
    "join_title": ("Join the Long Valley class", "加入塱原課堂"),
    "join_help": ("Use one device per group. Scan the QR code, open the link, or enter the join code.", "每組共用一部裝置。掃描二維碼、開啟連結，或輸入課堂代碼。"),
    "qr": ("Join QR code", "加入課堂的二維碼"),
    "enter_code": ("Enter the code at", "請在此輸入代碼"),
    "code": ("Join code", "課堂代碼"),
    "find": ("Find class", "尋找課堂"),
    "find_help": ("Enter the code shown by your teacher.", "輸入老師展示的課堂代碼。"),
    "choose_site": ("Choose your starting site", "選擇起始場地"),
    "choose_help": ("Agree with your neighbouring group who will start at each site.", "與鄰近的小組商量，各選一個場地出發。"),
    "choose": ("Choose Site {}", "選擇場地 {}"),
    "occupied": ("A group has taken this site.", "已有小組選擇這個場地。"),
    "choose_again": ("That site has been taken. Check which site is available.", "這個場地已有小組選擇。請查看哪些場地仍可選擇。"),
    "help_rejoin": ("Help a group rejoin", "協助小組重新加入"),
    "starting_site": ("Group’s starting site", "小組的起始場地"),
    "site_name": ("Site {}", "場地 {}"),
    "get_rejoin_code": ("Get group rejoin code", "取得小組重入碼"),
    "rejoin_code": ("Group rejoin code", "小組重入碼"),
    "give_rejoin_code": ("Privately give this one-use code to the group that started at Site {}.",
                         "請私下把這個一次性重入碼交給從場地 {} 出發的小組。"),
    "no_group": ("No group has started at Site {} yet.", "暫時未有小組從場地 {} 出發。"),
    "back_to_teacher": ("Back to teacher view", "返回教師介面"),
    "already_joined": ("Already joined this class?", "你們已加入這個課堂嗎？"),
    "rejoin_help": ("Ask your teacher for your group rejoin code to return to your work.",
                    "請向老師索取你們的小組重入碼，繼續先前的活動。"),
    "rejoin": ("Rejoin my group", "返回我的小組"),
    "invalid_rejoin": ("Check the group rejoin code with your teacher and try again.",
                       "請向老師核對小組重入碼，然後再試一次。"),
    "puzzle": ("How would you get a railway across Long Valley?", "你會怎樣讓鐵路穿越塱原？"),
    "puzzle_help": ("The two stations are fixed. Look at where the wetland lies between them. Where might you cross, and what would you want to find out first?",
                    "兩個車站的位置已定。看看它們之間的濕地在哪裏。你會選擇從哪裏穿越？你最想先弄清楚甚麼？"),
    "imagined": ("Imagined Long Valley setting", "以塱原為背景的想像場地"),
    "A": ("Site A: Central wetland", "場地 A：中央濕地"),
    "B": ("Site B: Riverside wetland", "場地 B：河畔濕地"),
    "site_A": ("The wetland sits in the middle of the valley.", "濕地位於河谷中央。"),
    "site_B": ("The wetland sits closer to the river, on the north side of the valley.", "濕地位於河谷北面，較接近河道。"),
    "unavailable": ("This class is closed", "這個課堂已結束"),
    "unavailable_help": ("Ask your teacher for the current join link or code.", "請向老師索取目前課堂的加入連結或代碼。"),
}


def page(language, title, content, *, layout="", session=None, teacher_only=False, joined=False,
         track_network=False):
    name = words(language, COPY)["name"]
    status_base = "/teacher/project" if teacher_only else "/classes"
    if joined:
        status_base = "/join"
    network_query = "?network=1" if track_network else ""
    status = f' data-class-status="{status_base}/{session.code}/status{network_query}"' if session else ""
    script = '<script src="/class-status.js" defer></script>' if session and not joined else ""
    bootstrap = f"<script>{GROUP_STATUS_SCRIPT}</script>" if joined else ""
    return f"""<!doctype html>
<html lang="{language}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} · {name}</title>
  <link rel="stylesheet" href="/classroom.css">
  {script}
</head>
<body>
  <header class="masthead"><a href="/?lang={language}">{name}</a></header>
  <main class="{layout}"{status}>{content}</main>
  {bootstrap}
</body>
</html>"""


def alternate_language(language):
    return "zh-Hant" if language == "en" else "en"


def language_link(path, language, *, parameter="lang"):
    alternate = alternate_language(language)
    return f'<a href="{path}?{parameter}={alternate}" lang="{alternate}">{LANGUAGES[alternate]}</a>'


def language_button(path, language):
    alternate = alternate_language(language)
    return f"""<button class="language secondary" form="crossing-design" formaction="{path}?lang={language}"
  name="language" value="{alternate}" lang="{alternate}">{LANGUAGES[alternate]}</button>"""


def home(language):
    t = words(language, COPY)
    return page(language, t["name"], f"""
<section class="panel">
  <h1>{t["name"]}</h1>
  <p><a href="/join?lang={language}">{t["student_entry"]}</a></p>
  <p><a href="/teacher?lang={language}">{t["teacher_entry"]}</a></p>
  {language_link("/", language)}
</section>""")


def sign_in(language, invalid=False):
    t = words(language, COPY)
    error = f'<p class="alert" role="alert">{t["bad_credential"]}</p>' if invalid else ""
    return page(language, t["teacher_entry"], f"""
<section class="panel">
  <h1>{t["teacher_entry"]}</h1>
  {error}
  <form action="/teacher/sign-in?lang={language}" method="post">
    <label for="credential">{t["credential"]}</label>
    <input id="credential" type="password" name="credential" required>
    <button>{t["sign_in"]}</button>
  </form>
  {language_link("/teacher", language)}
</section>""")


def teacher_launch(language):
    t = words(language, COPY)
    return page(language, t["teacher_entry"], f"""
<section class="panel">
  <h1>{t["teacher_entry"]}</h1>
  <p id="launch-status" role="status">{t["launch_wait"]}</p>
  <p id="launch-renewed" role="status" hidden>{t["launch_renewed"]}</p>
  <p id="launch-error" class="alert" role="alert" hidden>{t["launch_error"]}</p>
  <script src="/teacher-launch.js" defer></script>
</section>""")


def network_notice(t, *, hidden=True, action=""):
    return f"""
  <div data-network-notice{' hidden' if hidden else ''}>
    <p class="alert" role="status">{t["network_problem"]}</p>
    {action}
  </div>"""


def teacher(language, session=None, *, notice="", track_network=False, local_settings=False):
    t = words(language, COPY)
    sign_out = f"""<form class="inline" action="/teacher/sign-out?lang={language}" method="post">
  <button class="secondary">{t["sign_out"]}</button>
</form>"""
    if session:
        remaining_ms = ceil(session.remaining_seconds() * 1000)
        minutes, seconds = divmod(ceil(remaining_ms / 1000), 60)
        checking = " hidden" if track_network else ""
        settings = f"""<form class="inline" action="/teacher/network-settings" method="post" data-network-settings>
      <input type="hidden" name="code" value="{session.code}">
      <button class="secondary">{t["network_settings"]}</button>
    </form>
    <p class="alert" role="alert" data-network-settings-error hidden>{t["network_settings_error"]}</p>""" if local_settings else ""
        return page(language, t["open"], f"""
<section class="panel">
  <h1>{t["open"]}</h1>
  <p><span id="class-time-label">{t["time_remaining"]}</span>
    <span role="timer" aria-labelledby="class-time-label" data-remaining-ms="{remaining_ms}">{minutes:02d}:{seconds:02d}</span>
  </p>
  {network_notice(t, action=settings) if track_network else ""}
  <p data-network-ready{checking}>{t["project_help"]}</p>
  <div class="teacher-actions">
    <span data-network-ready{checking}><a class="button" href="/teacher/project/{session.code}"
      target="_blank" rel="noopener">{t["project"]}</a></span>
    <a class="button secondary" href="{comparison_url(session)}" target="_blank" rel="noopener">{t["shared_comparisons"]}</a>
  </div>
  {pass_the_city_controls(session, t, notice)}
  <details>
    <summary>{t["help_rejoin"]}</summary>
    <form action="/teacher/rejoin/{session.code}" method="get">
      <label for="starting-site">{t["starting_site"]}</label>
      <select id="starting-site" name="site">
        {''.join(f'<option value="{site}">{t["site_name"].format(site)}</option>' for site in SITES)}
      </select>
      <button class="secondary">{t["get_rejoin_code"]}</button>
    </form>
  </details>
  <div class="teacher-actions">
    <form class="inline" action="/teacher/end?lang={language}" method="post">
      <button class="end" name="code" value="{session.code}">{t["end"]}</button>
    </form>
    {sign_out}
  </div>
</section>""", session=session, teacher_only=True, track_network=track_network)
    options = "".join(
        f'<option value="{value}" lang="{value}"{" selected" if value == language else ""}>{label}</option>'
        for value, label in LANGUAGES.items()
    )
    return page(language, t["start_title"], f"""
<section class="panel">
  <h1>{t["start_title"]}</h1>
  <p>{t["start_help"]}</p>
  <form action="/teacher/start" method="post">
    <label for="language">{t["starting_language"]}</label>
    <select id="language" name="language">{options}</select>
    <button>{t["start"]}</button>
  </form>
  <div class="teacher-actions">{language_link("/teacher", language)} {sign_out}</div>
</section>""")


def pass_the_city_controls(session, t, notice):
    if session.swapped:
        return f'<p class="experiment-status" role="status">{t["pass_done"]}</p>'
    alert = f'<p class="alert" role="alert">{t["pass_waiting"]}</p>' if notice == "waiting-for-groups" else ""
    return f"""<p>{t["pass_help"]}</p>
{alert}
<form class="inline" action="/teacher/pass-the-city?lang={session.language}" method="post">
  <button name="code" value="{session.code}">{t["pass_the_city"]}</button>
</form>"""


def teacher_rejoin(session, site):
    language = session.language
    t = words(language, COPY)
    code = session.rejoin_code_for(site)
    message = t["give_rejoin_code" if code else "no_group"].format(site)
    display = f'<p><code class="rejoin-code">{code}</code></p>' if code else ""
    return page(language, t["rejoin_code"], f"""
<section class="panel">
  <h1>{t["rejoin_code"]}</h1>
  <p>{message}</p>
  {display}
  <p><a href="/teacher?lang={language}">{t["back_to_teacher"]}</a></p>
</section>""", session=session, teacher_only=True)


def projection(session, url, *, track_network=False):
    language = session.language
    t = words(language, COPY)
    qr_path = f"/teacher/project/{session.code}/qr.png"
    code_entry = escape(url.rsplit("/", 1)[0], quote=True) if url else ""
    join_link = f' href="{escape(url, quote=True)}"' if url else ""
    code_link = f' href="{code_entry}?lang={language}"' if url else ""
    qr_src = qr_path + ("?" + urlencode({"join": url}) if track_network and url else "")
    source = f' src="{escape(qr_src, quote=True)}"' if url else ""
    return page(language, t["join_title"], f"""
<section class="panel">
  {network_notice(t, hidden=url is not None) if track_network else ""}
  <div data-network-ready{' hidden' if url is None else ''}>
    <div class="projection">
      <div>
        <h1>{t["join_title"]}</h1>
        <p>{t["join_help"]}</p>
        <p class="code-label">{t["code"]}</p>
        <code>{session.code}</code>
        <p><a class="join-url" data-join-link{join_link}>{escape(url or '')}</a></p>
        <p>{t["enter_code"]} <a class="join-url" data-code-link{code_link}>{code_entry}</a></p>
        <p><a href="{comparison_url(session)}">{t["shared_comparisons"]}</a></p>
      </div>
      <img class="join-qr" data-join-qr="{qr_path}"{source} alt="{t["qr"]}">
    </div>
  </div>
</section>""", layout="wide", session=session, teacher_only=True, track_network=track_network)


def comparison_url(session, entry=""):
    path = f"/teacher/project/{session.code}/comparisons"
    if entry:
        path += f"/{entry}"
    return f"{path}?lang={session.language}"


def comparison_choices(session):
    t = words(session.language, COPY)
    return "".join(
        f'<li><a href="{comparison_url(session, key)}"><strong>{t[comparison.site]}</strong>'
        f'<span>{design_summary(comparison.design, session.language)}</span></a></li>'
        for key, comparison in session.comparisons.items()
    )


def shared_comparisons(session):
    language = session.language
    t = words(language, COPY)
    return page(language, t["shared_comparisons"], f"""
<section class="panel">
  <a href="/teacher/project/{session.code}">{t["project"]}</a>
  <h1>{t["shared_comparisons"]}</h1>
  <p>{t["select_comparison"]}</p>
  <ul class="comparison-list" data-comparison-feed="{comparison_url(session, "feed")}"
    aria-live="polite" aria-label="{t["shared_comparisons"]}">{comparison_choices(session)}</ul>
  <p class="empty-comparisons">{t["no_comparisons"]}</p>
</section>""", layout="wide", session=session, teacher_only=True)


def comparison_projection(session, comparison):
    language = session.language
    t = words(language, COPY)
    return page(language, t[comparison.site], f"""
<section class="panel projected-comparison">
  <a href="{comparison_url(session)}">{t["back_to_comparisons"]}</a>
  <h1>{t[comparison.site]}</h1>
  <div class="comparison-metadata">
    <p><strong>{t["spring_construction"]}</strong> · {t["imagined"]}</p>
    <p>{design_summary(comparison.design, language)}</p>
  </div>
  {projected_maps(comparison, language)}
</section>""", layout="wide comparison-screen", session=session, teacher_only=True)


def find_class(language):
    t = words(language, COPY)
    return page(language, t["join_title"], f"""
<section class="panel">
  <h1>{t["join_title"]}</h1>
  <p>{t["find_help"]}</p>
  <form action="/join" method="get">
    <input type="hidden" name="lang" value="{language}">
    <label for="code">{t["code"]}</label>
    <input id="code" name="code" maxlength="{CODE_LENGTH}" autocapitalize="characters" spellcheck="false" autocomplete="off" required>
    <button>{t["find"]}</button>
  </form>
  {language_link("/join", language)}
</section>""")


def unavailable(language, *, join_code=None):
    t = words(language, COPY)
    switch = ""
    if join_code is not None:
        switch = language_link(f"/join/{quote(join_code, safe='')}", language, parameter="closed-language")
    return page(language, t["unavailable"], f"""
<section class="panel">
  <h1>{t["unavailable"]}</h1>
  <p>{t["unavailable_help"]}</p>
  <p><a href="/join?lang={language}">{t["student_entry"]}</a></p>
  {switch}
</section>""")


def choose_site(session, taken=False, invalid_rejoin=False):
    language = session.language
    t = words(language, COPY)
    occupied = session.occupied_sites()
    alert = f'<p class="alert" role="alert">{t["choose_again"]}</p>' if taken else ""
    error = f'<p class="alert" role="alert">{t["invalid_rejoin"]}</p>' if invalid_rejoin else ""
    rejoin = f"""<section id="rejoin-group">
  <h2>{t["already_joined"]}</h2>
  <p>{t["rejoin_help"]}</p>
  {error}
  <form action="/join/{session.code}/rejoin?lang={language}" method="post">
    <label for="rejoin-code">{t["rejoin_code"]}</label>
    <input id="rejoin-code" name="rejoin_code" autocapitalize="characters" spellcheck="false" autocomplete="off" required>
    <button>{t["rejoin"]}</button>
  </form>
</section>""" if occupied else ""
    cards = []
    for site in SITES:
        occupancy = f'<p>{t["occupied"]}</p>' if site in occupied else ""
        disabled = " disabled" if site in occupied else ""
        cards.append(f"""<section class="site-choice">
  <h2>{t[site]}</h2>
  <p>{t["site_" + site]}</p>
  <button name="site" value="{site}"{disabled}>{t["choose"].format(site)}</button>
  {occupancy}
</section>""")
    return page(language, t["choose_site"], f"""
<section class="panel">
  <h1>{t["choose_site"]}</h1>
  <p>{t["choose_help"]}</p>
  <p class="site-note">{t["imagined"]}</p>
  {alert}
  <form class="site-choices" action="/join/{session.code}/take-site?lang={language}" method="post">
    {''.join(cards)}
  </form>
  {rejoin}
</section>""", layout="wide", session=session)


def group_opening(session, group, *, swap_wait_seconds, notice=""):
    language, site = group.language, group.site
    t = words(language, COPY)
    handoff = f'<p class="experiment-status">{t["partner_site"]}</p>' if session.swapped else ""
    waiting = (
        f'<p class="panel" role="status" data-site-check="{t["checking_site"]}" '
        f'data-site-opening="{t["opening_partner"]}">{t["checking_site"]}</p>'
    )
    return page(language, t["puzzle"], f"""
{waiting}
<section class="panel" data-group-site="{site}" data-swap-wait="{0 if session.swapped else swap_wait_seconds}" hidden>
  <div class="opening">
    <h1>{t["puzzle"]}</h1>
    {language_button(f"/join/{session.code}/language", language)}
    <p>{t["puzzle_help"]}</p>
  </div>
  <section class="site">
    <p class="site-note">{t["imagined"]}</p>
    <h2 id="current-site">{t[site]}</h2>
    {handoff}
    <p>{t["site_" + site]}</p>
    {spring_investigation(session, group, notice)}
  </section>
</section>""", layout="wide", session=session, joined=True)
