"""Teacher sign-in, lesson selection and live classroom controls."""

from html import escape
from json import dumps
from math import ceil

from .localization import words
from .state import SITES
from .views import COPY as CLASSROOM_COPY, LANGUAGES, comparison_url, network_notice


SIGN_IN_COPY = {
    "credential": ("Teacher credential", "教師憑證"),
    "sign_in": ("Sign in", "登入"),
    "missing_credential": ("Enter your teacher credential", "請輸入教師憑證。"),
    "bad_credential": ("Check your teacher credential and try again.", "請檢查教師憑證，然後再試一次。"),
    "language": ("Language", "語言"),
}

COPY = {
    **CLASSROOM_COPY,
    **SIGN_IN_COPY,
    "launch_wait": ("Opening the teacher view…", "正在開啟教師介面⋯"),
    "launch_renewed": ("Your sign-in link expired. Continue in the new teacher tab. "
                       "If no tab opens, double-click Open SiMetropolis Edu again.",
                       "登入連結已逾時。請到新開啟的教師分頁繼續。如果沒有新分頁，請再次按兩下 Open SiMetropolis Edu。"),
    "launch_error": ("Open SiMetropolis Edu again to reach the teacher view.", "請重新開啟 SiMetropolis Edu，以進入教師介面。"),
    "starting_language": ("Starting language", "起始語言"),
    "time_remaining": ("Time remaining", "剩餘時間"),
    "network_settings": ("Open network settings", "開啟網絡設定"),
    "network_settings_error": ("Edu couldn’t open network settings. Open them from your computer’s settings menu.",
                               "Edu 無法開啟網絡設定。請從電腦的設定選單開啟。"),
    "pass_the_city": ("Pass the City", "交換場地"),
    "pass_help": ("Ask both groups to save a crossing, then send them to their partner sites.",
                  "請兩組各自儲存走線，然後讓兩組交換場地。"),
    "pass_waiting": ("Both groups need to join before you can swap sites.", "兩組都加入課堂後，便可交換場地。"),
    "pass_done": ("Both groups have moved to their partner sites.", "兩組已到達對方的場地。"),
    "end": ("End class", "結束課堂"),
    "sign_out": ("Sign out", "登出"),
    "help_rejoin": ("Help a group rejoin", "協助小組重新加入"),
    "starting_site": ("Group’s starting site", "小組的起始場地"),
    "site_name": ("Site {}", "場地 {}"),
    "get_rejoin_code": ("Get group rejoin code", "取得小組重入碼"),
    "give_rejoin_code": ("Privately give this one-use code to the group that started at Site {}.",
                         "請私下把這個一次性重入碼交給從場地 {} 出發的小組。"),
    "no_group": ("No group has started at Site {} yet.", "暫時未有小組從場地 {} 出發。"),
    "back_to_teacher": ("Back to teacher view", "返回教師介面"),
    "unit": ("Unit", "單元"),
    "valley": ("Long Valley", "塱原"),
    "choose_lesson": ("Choose a lesson", "選擇課節"),
    "all_lessons": ("All lessons", "所有課節"),
    "start": ("Start Lesson", "開始課節"),
    "started": ("Lesson started", "課節已開始"),
    "preview": ("Preview only", "僅供預覽"),
    "launch_qr": ("Launch the QR code page", "開啟二維碼頁面"),
}

CLASSROOM_LESSON = "railway"
LESSONS = {
    "railway": {
        "title": ("A railway across Long Valley", "穿越塱原的鐵路"),
        "summary": (
            "How would you get a railway across Long Valley? The two stations are fixed, and groups test which construction works overlap modelled nesting habitat.",
            "你會怎樣讓鐵路穿越塱原？兩個車站的位置已定，小組會測試哪些施工範圍與模擬營巢地重疊。",
        ),
    },
    "bund": {
        "title": ("A road along the old bund", "沿舊堤的道路"),
        "summary": (
            "A road is proposed on top of a flood bund. Groups test whether the bund still holds water once the road is there.",
            "有人建議把道路建在防洪堤上。小組會測試道路建好之後，堤岸還能否擋住洪水。",
        ),
    },
    "housing": {
        "title": ("Housing at the valley edge", "河谷邊緣的房屋"),
        "summary": (
            "Housing is proposed where the fields meet the wetland. Groups see which lots stay dry and which sit on modelled habitat.",
            "有人建議在農田與濕地相接處建房屋。小組會查看哪些地塊仍然乾爽，哪些座落在模擬棲息地上。",
        ),
    },
    "station": {
        "title": ("A station by the river", "河畔的車站"),
        "summary": (
            "A station is proposed on the north side of the valley, close to the river. Groups compare access on high ground with access built toward the water.",
            "有人建議在河谷北面近河道處設車站。小組會比較建在高地的通道，與建向水邊的通道。",
        ),
    },
    "drains": {
        "title": ("Drains across the fields", "穿過農田的排水渠"),
        "summary": (
            "New drains would carry runoff from growing streets into the valley. Groups trace where that water arrives in spring.",
            "新排水渠會把街道的雨水帶進河谷。小組會追蹤這些水在春天流到哪裏。",
        ),
    },
    "lights": {
        "title": ("Lights above the night roost", "夜棲地上方的燈光"),
        "summary": (
            "Street lighting is proposed on a path that crosses a roost. Groups compare the path in the dark with the path lit.",
            "有人建議在穿過夜棲地的小徑上加設街燈。小組會比較黑暗中的小徑與亮燈後的小徑。",
        ),
    },
}


def artwork(symbol, css_class, viewbox):
    return (f'<svg class="{css_class}" viewBox="{viewbox}" aria-hidden="true" focusable="false">'
            f'<use href="/teacher-art.svg#{symbol}"/></svg>')


MARK = artwork("mark", "mark", "0 0 48 48")
WORDMARK = 'SiMetropolis <span class="edu">Edu</span>'
CHEVRON = ('<svg class="chev" viewBox="0 0 20 20" aria-hidden="true"><path d="M7.5 3.5 14 10l-6.5 6.5" '
           'fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def document(language, title, screen, content, scripts=()):
    scripts = "".join(f'<script defer src="/{name}"></script>' for name in scripts)
    return f"""<!doctype html>
<html lang="{language}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} · SiMetropolis Edu</title>
  <link rel="stylesheet" href="/teacher.css">
  {scripts}
</head>
<body data-screen="{screen}">{content}</body>
</html>"""


def language_switch(language, path, label):
    separator = "&amp;" if "?" in path else "?"
    links = "".join(
        f'<a href="{path}{separator}lang={value}" lang="{value}"'
        f' aria-current="{str(value == language).lower()}">{name}</a>'
        for value, name in LANGUAGES.items()
    )
    return f'<div class="lang" role="group" aria-label="{label}">{links}</div>'


def sign_in(language, *, error=None, launching=False):
    t = words(language, COPY)
    scripts = ["teacher-scene.js"]
    switch = ""
    if launching:
        scripts.append("teacher-launch.js")
        form = f"""<div>
          <p id="launch-status" role="status">{t["launch_wait"]}</p>
          <p id="launch-renewed" role="status" hidden>{t["launch_renewed"]}</p>
          <p id="launch-error" class="error" role="alert" hidden>{t["launch_error"]}</p>
        </div>"""
    else:
        scripts.append("teacher-sign-in.js")
        switch = language_switch(language, "/teacher", t["language"])
        message = t[error] if error else ""
        translations = escape(dumps({lang: words(lang, SIGN_IN_COPY) for lang in LANGUAGES}, ensure_ascii=False))
        form = f"""<form class="signin-form" method="post" action="/teacher/sign-in?lang={language}"
          data-copy="{translations}" data-error="{error or ''}" novalidate>
          <label for="credential">{t["credential"]}</label>
          <input id="credential" name="credential" type="password" autocomplete="current-password" required
            autofocus autocapitalize="off" spellcheck="false" aria-describedby="cred-error" aria-invalid="{str(error is not None).lower()}">
          <p class="error" id="cred-error" role="alert">{message}</p>
          <button class="btn btn-primary" type="submit">{t["sign_in"]}</button>
        </form>"""
    return document(language, t["sign_in"], "signin", f"""
<div class="signin">
  <div class="scene" aria-hidden="true">
    <svg class="map" id="map" viewBox="0 0 1200 1000" preserveAspectRatio="xMidYMid slice"></svg>
  </div>
  <main class="panel">
    <div class="panel-top">{switch}</div>
    <div class="panel-body">
      <div class="wordmark" lang="en">{MARK}<h1>{WORDMARK}</h1></div>
      {form}
    </div>
  </main>
</div>""", scripts)


def workspace(language, title, screen, path, content, t, *, status_url=""):
    status = f' data-class-status="{status_url}"' if status_url else ""
    return document(language, title, screen, f"""
<div class="app">
  <header class="bar">
    <div class="brand" lang="en">{MARK}<span>{WORDMARK}</span></div>
    <div class="bar-right">
      {language_switch(language, path, t["language"])}
      <form method="post" action="/teacher/sign-out?lang={language}">
        <button class="btn btn-quiet">{t["sign_out"]}</button>
      </form>
    </div>
  </header>
  <main{status}>{content}</main>
</div>""", ("class-status.js",) if status_url else ())


def lesson_list(language, session):
    t = words(language, COPY)
    railway_title = words(language, LESSONS[CLASSROOM_LESSON])["title"]
    status = f'<span class="lesson-status">{t["started"]}</span>' if session else ""
    previews = []
    for lesson_id, lesson in LESSONS.items():
        if lesson_id == CLASSROOM_LESSON:
            continue
        title = words(language, lesson)["title"]
        previews.append(f"""<li>
          <a class="preview-link" id="lesson-{lesson_id}" href="/teacher/lessons/{lesson_id}?lang={language}">
            {artwork(f"g-{lesson_id}", "glyph", "0 0 120 90")}
            <span>{title}</span>{CHEVRON}
          </a>
        </li>""")
    status_url = f"/teacher/project/{session.code}/status" if session else ""
    return workspace(language, t["choose_lesson"], "list", "/teacher/lessons", f"""
<section class="catalogue">
  <h1>{t["choose_lesson"]}</h1>
  <div class="catalogue-layout">
    <a class="featured-lesson" id="lesson-{CLASSROOM_LESSON}" href="/teacher/lessons/{CLASSROOM_LESSON}?lang={language}">
      <img class="lesson-cover" src="/long-valley-railway.jpg" width="1600" height="1000" alt="">
      <span class="featured-caption">
        <span><span class="featured-name">{railway_title}</span>{status}</span>
        <span class="featured-arrow" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h15m-7-7 7 7-7 7"/></svg>
        </span>
      </span>
    </a>
    <section class="lesson-previews" aria-labelledby="preview-heading">
      <h2 id="preview-heading">{t["preview"]}</h2>
      <ul>{''.join(previews)}</ul>
    </section>
  </div>
</section>""", t, status_url=status_url)


def all_lessons(language, t, lesson_id):
    return (f'<a class="btn btn-quiet back" href="/teacher/lessons?lang={language}#lesson-{lesson_id}">'
            f'{CHEVRON}{t["all_lessons"]}</a>')


def lesson_detail(lesson_id, lesson, t, slot, actions, controls=""):
    return f"""<section class="view lesson-view">
  <div class="slot">{slot}</div>
  <div class="detail">
    <div class="detail-text">
      <p class="eyebrow">{t["unit"]} · {t["valley"]}</p>
      <h1>{lesson["title"]}</h1>
      <p class="summary">{lesson["summary"]}</p>
      {actions}
    </div>
    {artwork(f"g-{lesson_id}", "detail-art", "0 0 120 90")}
  </div>
  {controls}
</section>"""


def lesson_review(language, lesson_id):
    t = words(language, COPY)
    lesson = words(language, LESSONS[lesson_id])
    action = f'<p class="preview-note">{t["preview"]}</p>'
    if lesson_id == CLASSROOM_LESSON:
        options = "".join(
            f'<option value="{value}" lang="{value}"{" selected" if value == language else ""}>{label}</option>'
            for value, label in LANGUAGES.items()
        )
        action = f"""<form class="start-form" method="post" action="/teacher/start">
          <input type="hidden" name="lesson" value="{lesson_id}">
          <label>{t["starting_language"]} <select name="language">{options}</select></label>
          <button class="btn btn-primary btn-start">
            <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 2.5v15l13-7.5z" fill="currentColor"/></svg>
            {t["start"]}
          </button>
        </form>"""
    content = lesson_detail(lesson_id, lesson, t, all_lessons(language, t, lesson_id), action)
    return workspace(language, lesson["title"], "review", f"/teacher/lessons/{lesson_id}", content, t)


def pass_the_city_controls(session, language, t, notice):
    if session.swapped:
        return f'<p role="status">{t["pass_done"]}</p>'
    alert = f'<p class="alert" role="alert">{t["pass_waiting"]}</p>' if notice == "waiting-for-groups" else ""
    return f"""<p>{t["pass_help"]}</p>{alert}
    <form action="/teacher/pass-the-city?lang={language}" method="post">
      <button class="btn btn-quiet" name="code" value="{session.code}">{t["pass_the_city"]}</button>
    </form>"""


def live_lesson(language, session, *, notice, track_network, local_settings):
    t = words(language, COPY)
    remaining_ms = ceil(session.remaining_seconds() * 1000)
    minutes, seconds = divmod(ceil(remaining_ms / 1000), 60)
    slot = f"""<p class="live" role="status"><span class="dot"></span>{t["started"]}</p>
      <p class="countdown"><span id="timer-label">{t["time_remaining"]}</span>
        <span role="timer" aria-labelledby="timer-label" data-remaining-ms="{remaining_ms}">{minutes:02d}:{seconds:02d}</span>
      </p>"""
    projection = f"/teacher/project/{session.code}"
    settings = f"""<form action="/teacher/network-settings" method="post" data-network-settings>
      <input type="hidden" name="code" value="{session.code}">
      <button class="btn btn-quiet">{t["network_settings"]}</button>
    </form>
    <p class="alert" role="alert" data-network-settings-error hidden>{t["network_settings_error"]}</p>""" if local_settings else ""
    actions = f"""{network_notice(t, action=settings) if track_network else ""}
      <a class="btn btn-primary btn-start" data-network-ready{' hidden' if track_network else ''}
        href="{projection}" target="_blank" rel="noopener">{t["launch_qr"]}</a>
      {all_lessons(language, t, CLASSROOM_LESSON)}"""
    controls = f"""<div class="class-tools">
      <div>{pass_the_city_controls(session, language, t, notice)}</div>
      <div>
        <a class="btn btn-quiet" href="{comparison_url(session)}" target="_blank" rel="noopener">{t["shared_comparisons"]}</a>
        <details>
          <summary>{t["help_rejoin"]}</summary>
          <form action="/teacher/rejoin/{session.code}" method="get">
            <input type="hidden" name="lang" value="{language}">
            <label>{t["starting_site"]} <select name="site">
              {''.join(f'<option value="{site}">{t["site_name"].format(site)}</option>' for site in SITES)}
            </select></label>
            <button class="btn btn-quiet">{t["get_rejoin_code"]}</button>
          </form>
        </details>
      </div>
      <form action="/teacher/end?lang={language}" method="post">
        <button class="btn btn-quiet end" name="code" value="{session.code}">{t["end"]}</button>
      </form>
    </div>"""
    status_url = projection + "/status" + ("?network=1" if track_network else "")
    lesson = words(language, LESSONS[CLASSROOM_LESSON])
    content = lesson_detail(CLASSROOM_LESSON, lesson, t, slot, actions, controls)
    return workspace(language, t["started"], "started", "/teacher", content, t, status_url=status_url)


def teacher_rejoin(language, session, site):
    t = words(language, COPY)
    code = session.rejoin_code_for(site)
    message = t["give_rejoin_code" if code else "no_group"].format(site)
    display = f'<code>{code}</code>' if code else ""
    return workspace(language, t["rejoin_code"], "started", f"/teacher/rejoin/{session.code}?site={site}", f"""
<section class="view rejoin">
  <a class="btn btn-quiet back" href="/teacher?lang={language}">{CHEVRON}{t["back_to_teacher"]}</a>
  <h1>{t["rejoin_code"]}</h1><p>{message}</p>{display}
</section>""", t, status_url=f"/teacher/project/{session.code}/status")
