"""Localized HTML for the classroom."""

from base64 import b64encode
from hashlib import sha256
from html import escape
from math import ceil
from pathlib import Path
from time import monotonic
from urllib.parse import quote

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
    "start_title": ("Open a Long Valley class", "開啟塱原課堂"),
    "start_help": ("Choose the language groups see when they join.", "選擇小組加入時使用的語言。"),
    "starting_language": ("Starting language", "起始語言"),
    "start": ("Start class", "開始課堂"),
    "open": ("Your class is open", "課堂已開啟"),
    "time_remaining": ("Time remaining", "剩餘時間"),
    "project": ("Project join information", "投影加入資訊"),
    "project_help": ("Open the join information in this browser and show that tab on the projector.", "請在此瀏覽器開啟加入資訊，並將該分頁投影給小組。"),
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


def page(language, title, content, *, layout="", session=None, teacher_only=False, joined=False):
    name = words(language, COPY)["name"]
    status_base = "/teacher/project" if teacher_only else "/classes"
    if joined:
        status_base = "/join"
    status = f' data-class-status="{status_base}/{session.code}/status"' if session else ""
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


def teacher(language, session=None, *, notice="", can_project=False):
    t = words(language, COPY)
    sign_out = f"""<form class="inline" action="/teacher/sign-out?lang={language}" method="post">
  <button class="secondary">{t["sign_out"]}</button>
</form>"""
    if session:
        remaining_ms = max(0, ceil((session.expires_at - monotonic()) * 1000))
        minutes, seconds = divmod(ceil(remaining_ms / 1000), 60)
        project_help = f'<p>{t["project_help"]}</p>' if can_project else ""
        project_link = f"""<a class="button" href="/teacher/project/{session.code}"
      target="_blank" rel="noopener">{t["project"]}</a>""" if can_project else ""
        return page(language, t["open"], f"""
<section class="panel">
  <h1>{t["open"]}</h1>
  <p><span id="class-time-label">{t["time_remaining"]}</span>
    <span role="timer" aria-labelledby="class-time-label" data-remaining-ms="{remaining_ms}">{minutes:02d}:{seconds:02d}</span>
  </p>
  {project_help}
  <div class="teacher-actions">
    {project_link}
    <a class="button secondary" href="{comparison_url(session)}" target="_blank" rel="noopener">{t["shared_comparisons"]}</a>
  </div>
  {pass_the_city_controls(session, t, notice)}
  <div class="teacher-actions">
    <form class="inline" action="/teacher/end?lang={language}" method="post">
      <button class="end" name="code" value="{session.code}">{t["end"]}</button>
    </form>
    {sign_out}
  </div>
</section>""", session=session, teacher_only=True)
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


def projection(session, url):
    language = session.language
    t = words(language, COPY)
    code_entry = escape(url.rsplit("/", 1)[0], quote=True)
    return page(language, t["join_title"], f"""
<section class="panel projection">
  <div>
    <h1>{t["join_title"]}</h1>
    <p>{t["join_help"]}</p>
    <p class="code-label">{t["code"]}</p>
    <code>{session.code}</code>
    <p><a class="join-url" href="{escape(url, quote=True)}">{escape(url)}</a></p>
    <p>{t["enter_code"]} <a class="join-url" href="{code_entry}?lang={language}">{code_entry}</a></p>
    <p><a href="{comparison_url(session)}">{t["shared_comparisons"]}</a></p>
  </div>
  <img class="join-qr" src="/teacher/project/{session.code}/qr.png" alt="{t["qr"]}">
</section>""", layout="wide", session=session, teacher_only=True)


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


def choose_site(session, taken=False):
    language = session.language
    t = words(language, COPY)
    occupied = session.occupied_sites()
    alert = f'<p class="alert" role="alert">{t["choose_again"]}</p>' if taken else ""
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
