"""Localized HTML for the classroom."""

from base64 import b64encode
from hashlib import sha256
from html import escape
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
    "project": ("Project join information", "投影加入資訊"),
    "network_problem": ("The classroom network is unavailable. Edu is retrying automatically.",
                        "無法連接課堂網絡。Edu 正在自動重試。"),
    "shared_comparisons": ("Shared comparisons", "已分享的比較結果"),
    "select_comparison": ("Choose a comparison to show on the projector.", "選擇要投影的比較結果。"),
    "no_comparisons": ("No group has shared a comparison yet.", "暫時沒有小組分享比較結果。"),
    "back_to_comparisons": ("Back to shared comparisons", "返回已分享的比較結果"),
    "spring_construction": ("Spring · Construction", "春季 · 施工階段"),
    "partner_site": ("You’re at your partner site. Try your crossing here.", "你們已到達對方的場地。試試你們的走線吧。"),
    "checking_site": ("Checking your current site…", "正在確認你們的場地⋯"),
    "opening_partner": ("Opening your partner site…", "正在開啟對方的場地⋯"),
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
    "join_check_error": ("Couldn’t check your site. Reload the join page and try again.",
                         "無法確認你們的場地。請重新載入加入頁面再試。"),
    "rejoin_code": ("Group rejoin code", "小組重入碼"),
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


def network_notice(t, *, hidden=True, action=""):
    return f"""
  <div data-network-notice{' hidden' if hidden else ''}>
    <p class="alert" role="status">{t["network_problem"]}</p>
    {action}
  </div>"""


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
    <input type="hidden" name="browser_key">
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
    return page(language, t["join_title"], f"""
<p class="panel" role="status" data-join-check>{t["checking_site"]}</p>
<p class="panel alert" role="alert" data-join-check-error hidden>{t["join_check_error"]}</p>
<section class="panel" data-join-chooser data-resume-path="/join/{session.code}/resume?lang={language}" hidden>
  <h1>{t["choose_site"]}</h1>
  <p>{t["choose_help"]}</p>
  <p class="site-note">{t["imagined"]}</p>
  {alert}
  <form class="site-choices" action="/join/{session.code}/take-site?lang={language}" method="post">
    <input type="hidden" name="browser_key">
    {''.join(cards)}
  </form>
  {rejoin}
</section>
<script src="/join-group.js" defer></script>""", layout="wide", session=session)


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
