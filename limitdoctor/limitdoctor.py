# -*- coding: utf-8 -*-
r"""LimitDoctor 0.4.6 — отчёт о расходе лимита Claude Code по локальным логам. Один файл, без зависимостей, Python 3.8+.

  python limitdoctor.py                 отчёт по всем чатам за неделю лимита → usage_report_<дата_время>.html, открывается сам
  python limitdoctor.py --chat [ID]     один чат: текущий (по папке запуска) или по началу id / пути к .jsonl
  python limitdoctor.py --week-reset 2026-10-11T02:00Z   когда Claude обнуляет неделю (один раз; неделя отчёта — от сброса)
  python limitdoctor.py --effort-check  пересчитать множители effort по своим логам
  python limitdoctor.py --statusline    режим статус-строки: пишет проценты Claude (весь аккаунт) в account.jsonl
  ещё: --days N, --since ГГГГ-ММ-ДД, --top N, --out ПАПКА, --no-open, --plan ($ в месяц); для человека — README.md

═══ Для нейросети и разработчика: как устроено ═══

Принцип. Отчёт — лёгкий HTML-снимок, не база и не сервер. Питон только читает логи и вклеивает сырые вызовы в шаблон
  PAGE (в конце файла); расчёты, переключатели и сценарии «а если бы» считает JS на странице. Новую фичу сначала
  проверить на вес: размер HTML (≈420 КБ на 40 чатов), время сборки (≈5,5 с), перерисовка (≈20 мс). Тяжёлое,
  на что никто не смотрит, не брать. Наружу ничего не отправляется. Интерфейс по-русски и для новичка, не знающего
  Claude Code: всё непонятное объясняется подсказкой при наведении.

Единица. Хайку-токен (ХТ) = цена входного токена Haiku = $1 за миллион. Цена вызова в ХТ:
  вход·p0 + запись на 5 мин·p0·1,25 + запись на 1 ч·p3 + чтение кэша·p2 + выход·p1·mult[effort]/mult[effort как был],
  где [p0, p1, p2, p3] = PARAMS["price"][модель]. ht() здесь и cost() на странице считают одинаково.

Логи. ~/.claude/projects/<папка>/<id>.jsonl (и $CLAUDE_CONFIG_DIR, ~/.config/claude), агенты — <id>/subagents/agent-*.jsonl.
  Берутся записи type=assistant с message.id и message.usage. Один ответ пишется несколькими строками с одним id:
  по полям берётся максимум. Множество seen общее на весь проход: вызов, учтённый в одном чате, в другом не считается.
  Форк чата копирует к себе историю родителя (и папку агентов) с родительским sessionId: такие записи пропускаются,
  вызов считается только в файле сессии, которая его сделала (иначе он уезжал в тот чат, что трогали последним).
  Ещё из лога: perTurnEffort, thinkingDurationMs, version, custom-title (имя чата), записи attachment — обвязка (harness()).

Вызов — массив k (load_chat):
  [0 время, 1 модель 0..3 по FAM, 2 effort 0..4 по EFF или −1, 3 вход, 4 запись 5 мин, 5 запись 1 ч, 6 чтение кэша,
   7 выход, 8 думала мс, 9 агент 0/1, 10 инструменты строкой, 11 = 1, если с прошлого вызова обновился Claude Code]
  Чат: {id, title, k, h — обвязка}. Одинаковые списки скиллов хранятся один раз (SK: имена и списки [имя, символов]).

Размер лимита — константа PARAMS["cap"]. С процентами Claude не синхронизируемся (решение Командора 08.10): Claude
  показывает весь аккаунт — облачные сессии, другие компьютеры, других людей, — а мы видим только чаты этого компьютера.
  Наши проценты = наш расход ÷ размер лимита; они и должны быть меньше, чем у Claude. Из calibration.json (папка
  отчётов) берётся только время сброса недели (--week-reset): отчёт по умолчанию — от сброса.
  Для сравнения (не для расчёта) — account.jsonl: проценты Claude по времени, весь аккаунт. Пишет их --statusline
  (статус-строка терминального Claude Code; десктоп её, похоже, не вызывает) или вручную показания get_usage.
  На дашборде acctHtml() рисует две линии: аккаунт по Claude и наши чаты нарастающим итогом; разрыв — другие люди.

Холодный старт (страница: ci(), cc()). Вызов основной цепочки (не агент), где запись кэша ≥ max(25 тыс., 45% контекста).
  Переплата = (записано − обычный прирост) × (цена записи − цена чтения). Сценарий «компакт перед ним»: выжимка
  summary_tokens поверх системного минимума. TTL кэша — час (по чужим замерам попадание на 59,84 мин, промах на 60,46).
  Причина ev.cs, в порядке проверки: cmp — контекст стал меньше 60% прошлого (компакт); idle — пауза от 59 мин;
  sw — смена модели; upd — обновился Claude Code; cmp — меньше 90% (автоочистка); ttl5 — пауза больше 5 мин при кэше
  на 5 минут; unk — по логу не видно. «Можно было избежать»: sw и пауза, перед которой компакт сэкономил бы.

Обвязка (hz()). Системный минимум = контекст первого вызова чата, делится по длине текста из лога (chars_per_token):
  скиллы, память, MCP, списки инструментов, системный промпт; остаток — встроенные инструменты. Скиллы: самая длинная
  запись каждого из всех skill_listing (первый список в логе обычно без описаний; сверка с get_usage 08.10 — 9,9 тыс.).

Effort. PARAMS["mult"] — множитель выхода против medium. --effort-check пересчитывает его методом Thinkpload: вызовы
  одной модели при похожем размере контекста сравниваются со своим medium. Ряд обязан расти по effort.

Страница. Вместо __CHATS__, __SK__, __PARAMS__ (PARAMS + cap, cal, since, now, heat, plan), __ADMIN__ (true — дашборд
  и список чатов, false — один чат), __GEN__, __NAME__, __VER__ вклеиваются данные. Состояние S: c — открытый чат
  (−1 — дашборд), m/e — сценарий модель/effort (−1 — как было), w — окно процентов, hm — период тепловой карты;
  клик меняет S, draw() перерисовывает всё.
  central() сверху вниз: троица — «а если бы» на одной модели, «Чаты в отчёте съели» с прогнозом к сбросу (fcLine),
  «Подписка окупилась» (roiCard: ХТ/1e6 = $ против доли plan за те же дни); сравнение чатов (expHtml: по моделям или
  по effort, S.xm; шкала общая для всех effort); куда ушли токены; расход по дням (в подсказке — какие чаты съели день);
  весь аккаунт и наши чаты (acctHtml); «Когда горит лимит» (heatHtml: «эта неделя» — строки
  по датам из чатов отчёта, «обычная неделя» — дни недели в среднем, heat из питона с тремя главными чатами в клетке);
  самые дорогие чаты; холодные старты системы с причинами (coldAllHtml); фичи-реквесты; «как это читать».
  chatView(): «а если бы», «этот чат съел», куда ушли токены с обвязкой, лента вызовов (tapeHtml: столбик — вызов,
  высота √(цена/макс); в сценарии левые 2 px — как было; подсказка tipCall — во сколько раз дороже среднего вызова
  чата и полоска заполненности контекста: окно 1 млн, у Haiku 200 тыс.), холодные старты (coldHtml: число над
  столбиком — цена старта в % цены чата, бледные — неизбежные), сколько таких чатов влезет.
  Иконки — LOGO (персонаж: глаза-кресты красный и зелёный, рот — график из красного в зелёный; он же favicon) и SYS («вся система»: квадраты цветов моделей).
"""
import argparse, json, math, os, re, sys, time, datetime as dt
from pathlib import Path

NAME, VER = "LimitDoctor", "0.4.6"
sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent          # src\
REPO = HERE.parent                               # папка репозитория
# Куда писать отчёты и журнал замеров: LIMITDOCTOR_DIR, если задан; в мастерской разработчика рядом с репозиторием лежит
# reports\ — туда; иначе ~/limitdoctor (после установки пакетом писать рядом с кодом некуда).
REPORTS = (Path(os.environ["LIMITDOCTOR_DIR"]) if os.environ.get("LIMITDOCTOR_DIR")
           else REPO.parent / "reports" if (REPO.parent / "reports").is_dir() else Path.home() / "limitdoctor")
CAL = REPORTS / "calibration.json"
ACCT = REPORTS / "account.jsonl"           # проценты Claude по времени: --statusline и замеры get_usage
FAM = ["haiku", "sonnet", "opus", "fable"]
EFF = ["low", "medium", "high", "xhigh", "max"]
PARAMS = {
    # ХТ за один токен: вход, выход, чтение кэша, запись кэша на 1 час (запись на 5 минут = 1,25 × вход). Порядок — FAM.
    # Это цены Claude API на 02.10.2026 в долях цены входа Haiku 4.5 ($1 за миллион), поэтому 1 ХТ = $0,000001.
    "price": [[1, 5, 0.1, 2], [2, 10, 0.2, 4], [4, 20, 0.2, 8], [10, 50, 0.25, 20]],
    # Множитель выходных токенов (ответ и мысли) по effort low, medium, high, xhigh, max относительно medium.
    # Замер 08.10 (--effort-check, 11 тыс. вызовов за 30 дней, средний выход при похожем контексте):
    # Opus 0,67 / 1 / 1,09 / 1,51 / 3,54; Sonnet high 1,16, xhigh 2,09, max 4,57, low — вызовов мало, взят как у Opus.
    # Fable — вызовов мало, взят как Opus. У Haiku effort нет. Ряд обязан расти: иначе low выходит дороже medium.
    "mult": [[1, 1, 1, 1, 1], [0.65, 1, 1.15, 2.1, 4.6], [0.65, 1, 1.1, 1.5, 3.5], [0.65, 1, 1.1, 1.5, 3.5]],
    # Размер лимита плана Max ($200) в ХТ: за 5 часов и за неделю; сутки = неделя / 7. Claude его не сообщает.
    # Оценка по замеру 07.10: неделя — 530 млн ХТ наших при 15% у Claude, 5 часов — 22 млн при 4%. Если в тех процентах
    # был чужой расход, настоящий лимит больше. По процентам Claude не пересчитывается: там весь аккаунт, у нас — часть.
    "cap": [550_000_000, 3_500_000_000],
    "summary_tokens": 10000,                # выжимка компакта, токенов (сценарий «компакт перед холодным стартом»)
    "chars_per_token": 3.5,                 # обвязка оценивается по длине текста в логе
    "cold": {"min_write": 25000, "min_share": 0.45},   # холодный старт: запись кэша ≥ max(25 тыс., 45% контекста)
    "plan_usd_month": 200,                  # цена подписки для плитки «подписка окупилась» (--plan)
}
PRICE = PARAMS["price"]


def claude_dirs():
    """Папки projects со всеми логами Claude Code на этом компьютере."""
    base = [Path(p.strip()).expanduser() for p in os.environ.get("CLAUDE_CONFIG_DIR", "").split(",") if p.strip()]
    base += [Path.home() / ".config" / "claude", Path.home() / ".claude"]
    out = []
    for b in base:
        p = b / "projects"
        if p.is_dir() and p.resolve() not in out:
            out.append(p.resolve())
    return out


PROJS = claude_dirs()


def all_logs():
    return [f for d in PROJS for f in d.glob("*/*.jsonl")]


def fam(model):
    for i, k in enumerate(FAM):
        if k in (model or ""):
            return i


def tool_name(n):
    return n.split("__")[-1] if n.startswith("mcp__") else n


def epoch(ts):
    return int(dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())


def ht(c, m=None):
    """Цена вызова в ХТ; m — другая модель при том же effort (выход пересчитан множителями, как на странице)."""
    m0 = c[1]
    m = m0 if m is None else m
    p, e = PRICE[m], (c[2] if c[2] >= 0 else 1)
    om = PARAMS["mult"][m][e] / PARAMS["mult"][m0][e]
    return c[3] * p[0] + c[4] * p[0] * 1.25 + c[5] * p[3] + c[6] * p[2] + c[7] * om * p[1]


def harness(line, H, sid):
    """Обвязка из записей-вложений лога: скиллы, файлы памяти, инструкции MCP, списки инструментов и агентов, системный промпт (в символах)."""
    try:
        e = json.loads(line)
    except json.JSONDecodeError:
        return
    if e.get("sessionId") not in (None, sid):
        return
    a = e.get("attachment") or {}
    t = a.get("type")
    if t == "skill_listing":
        # Список пишется в лог несколько раз, первый — часто без описаний (так скиллы и выходили втрое меньше):
        # берём самую длинную запись каждого скилла. Строка без «- » продолжает описание предыдущего.
        cur = None
        for ln in a.get("content", "").split("\n"):
            if ln.startswith("- "):
                cur, n = ln[2:].split(": ", 1)[0].strip(), len(ln)
            elif cur:
                n += len(ln) + 1
            else:
                continue
            H["sk"][cur] = max(H["sk"].get(cur, 0), n)
    elif t == "instructions" and not H["mem"]:
        H["mem"] = [[Path(f.get("path", "?")).parent.name + "/" + Path(f.get("path", "?")).name, len(f.get("content", ""))] for f in a.get("files", [])]
    elif t == "mcp_instructions_delta":
        known = {x[0] for x in H["mcp"]}
        for n, b in zip(a.get("addedNames", []), a.get("addedBlocks", [])):
            if n[:36] not in known:
                H["mcp"].append([n[:36], len(b)])
    elif t == "deferred_tools_delta" and not H["tl"]:
        H["tl"] = sum(len(x) + 1 for x in a.get("addedLines", []))
    elif t == "agent_listing_delta" and not H["ag"]:
        H["ag"] = sum(len(x) + 1 for x in a.get("addedLines", []))
    elif t == "prompt_snapshot" and not H["sys"]:
        H["sys"] = sum(len(s) for s in a.get("systemPrompt", []))


def parse(path, agent, seen, sid):
    """Вызовы модели из одного файла лога. sid — id сессии-хозяина: форк чата копирует к себе историю родителя
    (и папку агентов) с родительским sessionId; такие записи пропускаем, их считает сам родитель."""
    calls, title, cwd = {}, None, None
    H = {"sk": {}, "mem": [], "mcp": [], "tl": 0, "ag": 0, "sys": 0}
    for line in open(path, encoding="utf-8", errors="ignore"):
        if '"type":"attachment"' in line:
            harness(line, H, sid)
            continue
        if '"custom-title"' in line:
            try:
                title = json.loads(line).get("customTitle") or title
            except json.JSONDecodeError:
                pass
            continue
        if '"usage"' not in line or '"assistant"' not in line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        m = e.get("message") or {}
        if e.get("type") != "assistant" or not m.get("id") or not m.get("usage") or e.get("sessionId") not in (None, sid):
            continue
        f = fam(m.get("model"))
        if f is None or (m["id"] in seen and m["id"] not in calls):
            continue
        cwd = cwd or e.get("cwd")
        u = m["usage"]
        cc = u.get("cache_creation") or {}
        w5, w1 = cc.get("ephemeral_5m_input_tokens", 0), cc.get("ephemeral_1h_input_tokens", 0)
        if not cc:
            w1 = u.get("cache_creation_input_tokens", 0)
        r = calls.setdefault(m["id"], {"ts": e["timestamp"], "m": f, "e": -1, "i": 0, "w5": 0, "w1": 0, "r": 0, "o": 0, "th": 0, "a": agent, "tl": []})
        r["ts"] = min(r["ts"], e["timestamp"])
        r["v"] = e.get("version") or r.get("v")
        eff = e.get("perTurnEffort") or e.get("effort")
        if eff in EFF:
            r["e"] = EFF.index(eff)
        r["th"] = max(r["th"], e.get("thinkingDurationMs") or 0)
        for k, name in (("i", "input_tokens"), ("o", "output_tokens"), ("r", "cache_read_input_tokens")):
            r[k] = max(r[k], u.get(name, 0))
        r["w5"], r["w1"] = max(r["w5"], w5), max(r["w1"], w1)
        for b in m.get("content") or []:
            if b.get("type") == "tool_use" and tool_name(b.get("name", "")) not in r["tl"]:
                r["tl"].append(tool_name(b.get("name", "")))
    return calls, title, cwd, H


def load_chat(log, since=0, seen=None):
    seen = set() if seen is None else seen
    calls, title, cwd, H = parse(log, 0, seen, log.stem)
    for p in sorted((log.parent / log.stem / "subagents").glob("agent-*.jsonl")):
        calls.update(parse(p, 1, seen | set(calls), log.stem)[0])
    seen.update(calls)
    k, pv = [], None
    for t, r in sorted(((epoch(r["ts"]), r) for r in calls.values()), key=lambda x: x[0]):
        c = [t, r["m"], r["e"], r["i"], r["w5"], r["w1"], r["r"], r["o"], int(r["th"]), r["a"], ", ".join(r["tl"][:4])[:48]]
        if not r["a"]:                       # c[11] = 1: Claude Code обновился с прошлого вызова основной цепочки
            if pv and r.get("v") and r["v"] != pv:
                c.append(1)
            pv = r.get("v") or pv
        if t >= since:
            k.append(c)
    return {"id": log.stem[:8], "title": title or (Path(cwd).name if cwd else log.stem[:8]), "k": k, "h": H}


def collect(since):
    seen, chats = set(), []
    for log in sorted(all_logs(), key=lambda f: f.stat().st_mtime, reverse=True):
        if log.stat().st_mtime < since:
            continue
        ch = load_chat(log, since, seen)
        if len(ch["k"]) >= 3:
            chats.append(ch)
    return chats


def pick_log(arg):
    if arg:
        p = Path(arg)
        if p.is_file():
            return p
        found = [f for d in PROJS for f in d.glob(f"*/{arg}*.jsonl")]
        if found:
            return max(found, key=lambda f: f.stat().st_mtime)
        sys.exit(f"не нашла лог: {arg}")
    here = re.sub(r"[^A-Za-z0-9]", "-", os.getcwd())
    files = [f for d in PROJS if (d / here).is_dir() for f in (d / here).glob("*.jsonl")]
    if not files:
        files = all_logs()
    if not files:
        sys.exit("логи Claude Code не найдены: " + ", ".join(map(str, PROJS)) or "нет папки projects")
    return max(files, key=lambda f: f.stat().st_mtime)


# ---------- неделя лимита: от сброса, как у Claude ----------
def when(s):
    """ISO-время или ЧЧ:ММ (сегодня, а если уже прошло — завтра)."""
    if re.fullmatch(r"\d{1,2}:\d{2}", s):
        h, m = map(int, s.split(":"))
        t = dt.datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
        if t.timestamp() < time.time():
            t += dt.timedelta(days=1)
        return int(t.timestamp())
    return epoch(s if re.search(r"[zZ]|[+-]\d\d:?\d\d$", s) else s + "Z")


def set_reset(t):
    """Запомнить, когда Claude обнуляет недельный лимит (calibration.json; старые замеры процентов там не используются)."""
    cal = json.loads(CAL.read_text(encoding="utf-8")) if CAL.exists() else {}
    cal["week_anchor"] = when(t)
    REPORTS.mkdir(parents=True, exist_ok=True)
    CAL.write_text(json.dumps(cal, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"сброс недели: {dt.datetime.fromtimestamp(cal['week_anchor']):%d.%m %H:%M}, дальше — каждые 7 дней")


def last_acct():
    """Последняя запись журнала аккаунта (читается только хвост файла)."""
    if not ACCT.exists():
        return None
    with open(ACCT, "rb") as f:
        f.seek(max(0, ACCT.stat().st_size - 600))
        tail = f.read().decode("utf-8", "ignore").strip().splitlines()
    try:
        return json.loads(tail[-1]) if tail else None
    except json.JSONDecodeError:
        return None


def statusline():
    """Режим статус-строки Claude Code (settings.json → statusLine: {"type": "command", "command": "python …/limitdoctor.py
    --statusline"}). Claude Code передаёт JSON на stdin; из него берутся официальные проценты rate_limits.five_hour и
    .seven_day (used_percentage 0–100, resets_at — секунды) и дописываются в account.jsonl, если изменились или прошло
    5 минут. Печатает короткую строку. Работает в терминальном Claude Code; десктоп статус-строку, похоже, не вызывает.
    Падать нельзя: при любой ошибке — пустой вывод."""
    try:
        rl = (json.load(sys.stdin) or {}).get("rate_limits") or {}
        h5, wk = rl.get("five_hour") or {}, rl.get("seven_day") or {}
        q = {"t": int(time.time()), "week": wk.get("used_percentage"), "h5": h5.get("used_percentage"),
             "week_reset": wk.get("resets_at"), "src": "statusline"}
        if q["week"] is None and q["h5"] is None:
            return
        last = last_acct()
        if not last or (last.get("week"), last.get("h5")) != (q["week"], q["h5"]) or q["t"] - last.get("t", 0) >= 300:
            REPORTS.mkdir(parents=True, exist_ok=True)
            with open(ACCT, "a", encoding="utf-8") as f:
                f.write(json.dumps(q) + "\n")
        print("лимит: " + " · ".join(f"{n} {v:.0f}%" for n, v in (("неделя", q["week"]), ("5 ч", q["h5"])) if v is not None))
    except Exception:
        pass


def caps():
    """Размер лимита (константа PARAMS["cap"]) и начало текущей недели лимита, если известно время сброса."""
    cap, info = list(PARAMS["cap"]), {}
    a = json.loads(CAL.read_text(encoding="utf-8")).get("week_anchor") if CAL.exists() else None
    a = a or (last_acct() or {}).get("week_reset")          # время сброса знает и статус-строка
    if a:
        while a < time.time():
            a += 7 * 86400
        info["week0"] = a - 7 * 86400
    return cap, info


def effort_check(days=30):
    """Множители effort по своим логам (метод Thinkpload): вызовы одной модели при похожем размере контекста
    (корзины ×√2, агенты отдельно) сравниваются с medium; средний выход, корзины весом min(n), в корзине от 5 вызовов."""
    since, seen, B = time.time() - days * 86400, set(), {}
    for log in all_logs():
        if log.stat().st_mtime >= since:
            for c in load_chat(log, since, seen)["k"]:
                if c[2] >= 0:
                    key = (c[1], int(math.log2(max(2, c[3] + c[4] + c[5] + c[6])) * 2), c[9])
                    B.setdefault(key, {}).setdefault(c[2], []).append(c[7])
    avg = lambda x: sum(x) / len(x)
    print(f"выход на каждом effort против medium той же модели при похожем контексте, за {days} дней (в скобках — вызовов):")
    for m in range(1, 4):
        out = []
        for e in range(5):
            num = den = n = 0
            for (mm, _, _), d in B.items():
                if mm == m and len(d.get(e, [])) >= 5 and len(d.get(1, [])) >= 5:
                    w = min(len(d[e]), len(d[1]))
                    num, den, n = num + w * avg(d[e]) / max(1, avg(d[1])), den + w, n + len(d[e])
            out.append(f"{EFF[e]} ×{num / den:.2f} ({n})" if den else f"{EFF[e]} —")
        print(f"  {FAM[m].capitalize()}: " + ", ".join(out))
    print("сейчас в PARAMS['mult']:", PARAMS["mult"][1:])


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def main():
    ap = argparse.ArgumentParser(description=f"{NAME} {VER}: отчёт о расходе лимита Claude Code")
    ap.add_argument("--chat", nargs="?", const="", default=None, help="один чат: без значения — текущий, или начало id")
    ap.add_argument("--session", help="то же, что --chat ID")
    ap.add_argument("--days", type=float, help="за сколько дней (по умолчанию — текущая неделя лимита или 7 дней)")
    ap.add_argument("--since", help="ГГГГ-ММ-ДД вместо --days")
    ap.add_argument("--top", type=int, default=60); ap.add_argument("--out"); ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--admin", action="store_true", help=argparse.SUPPRESS); ap.add_argument("--open", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--week-reset", help="когда Claude обнуляет недельный лимит: 2026-10-11T02:00Z или ЧЧ:ММ (один раз)")
    ap.add_argument("--plan", type=float, help="цена подписки, $ в месяц (по умолчанию 200)")
    ap.add_argument("--effort-check", action="store_true", help="пересчитать множители effort по своим логам за 30 дней")
    ap.add_argument("--statusline", action="store_true", help="режим статус-строки Claude Code: пишет проценты Claude в account.jsonl")
    a = ap.parse_args()
    if a.statusline:
        return statusline()
    if not PROJS:
        sys.exit("не нашла логи Claude Code: нет папки projects в ~/.claude или ~/.config/claude")
    if a.effort_check:
        return effort_check()
    if a.week_reset:
        set_reset(a.week_reset)
    out_dir = Path(a.out) if a.out else REPORTS
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M")
    one = a.session or a.chat
    if one is not None and not a.admin:
        ch = load_chat(pick_log(one))
        if not ch["k"]:
            sys.exit("в логе нет вызовов модели")
        chats, admin, out, heat = [ch], "false", out_dir / f"chat_{ch['id']}_{stamp}.html", None
    else:
        # по умолчанию — та же неделя, что считает Claude (от сброса лимита), если сброс известен из замеров; иначе 7 дней
        week0 = caps()[1].get("week0")
        since = epoch(a.since + "T00:00:00Z") if a.since else int(time.time() - (a.days or 7) * 86400) if a.days or not week0 else int(week0)
        # тепловая карта «день недели × час» — за 4 недели, чтобы проступила привычка; логи читаются одним проходом
        h0, now = int(time.time() - 28 * 86400), time.time()
        pool, hv, hc, first = collect(min(since, h0)), [0.0] * 168, [{} for _ in range(168)], now
        for j, ch in enumerate(pool):
            for c in ch["k"]:
                if c[0] >= h0:
                    d, x = dt.datetime.fromtimestamp(c[0]), ht(c)
                    cell = d.weekday() * 24 + d.hour
                    hv[cell] += x
                    hc[cell][j] = hc[cell].get(j, 0) + x
                    first = min(first, c[0])
            ch["k"] = [c for c in ch["k"] if c[0] >= since]
        # в каждой клетке — три самых прожорливых чата (для подсказки); имена — в общей таблице
        names, top = {}, []
        for cell in hc:
            best = sorted(cell.items(), key=lambda kv: -kv[1])[:3]
            top.append([[names.setdefault(pool[j]["title"], len(names)), round(x)] for j, x in best])
        heat = {"v": [round(x) for x in hv], "days": round((now - first) / 86400, 2), "top": top, "names": list(names)}
        chats = [ch for ch in pool if len(ch["k"]) >= 3]
        chats.sort(key=lambda ch: -sum(ht(c) for c in ch["k"]))
        chats, admin, out = chats[:a.top], "true", out_dir / f"usage_report_{stamp}.html"
        if not chats:
            sys.exit("за этот период вызовов модели нет")
    SK, sig = {"n": [], "l": []}, {}      # одинаковые списки скиллов храним один раз, имена скиллов — в общей таблице
    ix = {}
    for ch in chats:
        H = ch["h"]
        lst = sorted(H["sk"].items(), key=lambda kv: -kv[1])
        if lst and tuple(lst) not in sig:
            sig[tuple(lst)] = len(SK["l"])
            SK["l"].append([[ix.setdefault(n, len(ix)), c] for n, c in lst])
        ch["h"] = {"sys": H["sys"], "mem": H["mem"], "mcp": H["mcp"], "tl": H["tl"], "ag": H["ag"], "sk": sig[tuple(lst)] if lst else -1}
    SK["n"] = list(ix)
    cap, info = caps()
    acct = []                              # [время, % недели, % 5 часов] — весь аккаунт по Claude
    if admin == "true" and ACCT.exists():
        for ln in open(ACCT, encoding="utf-8", errors="ignore"):
            try:
                q = json.loads(ln)
                if q.get("t", 0) >= since:
                    acct.append([q["t"], q.get("week"), q.get("h5")])
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
    P = dict(PARAMS, cap=cap, cal=info, since=(since if admin == "true" else 0), now=int(time.time()), heat=heat,
             plan=a.plan or PARAMS["plan_usd_month"], acct=acct)
    page = PAGE
    for k, v in (("__SK__", dump(SK)), ("__CHATS__", dump(chats)), ("__ADMIN__", admin), ("__GEN__", dt.datetime.now().strftime("%d.%m.%Y %H:%M")),
                 ("__PARAMS__", dump(P)), ("__NAME__", NAME), ("__VER__", VER)):
        page = page.replace(k, v)
    out.write_text(page, encoding="utf-8")
    n = sum(len(c["k"]) for c in chats)
    tot = sum(ht(c) for ch in chats for c in ch["k"])
    print(f"{NAME} {VER}: чатов {len(chats)}, вызовов {n}, {tot / 1e6:.1f} млн ХТ = {tot / cap[1] * 100:.1f}% лимита за неделю (только чаты этого компьютера)")
    if admin == "false":
        k = chats[0]["k"]
        alt = ", ".join(f"{nm} {sum(ht(c, i) for c in k) / cap[0] * 100:.1f}%" for i, nm in enumerate(["Haiku", "Sonnet", "Opus", "Fable"]))
        print(f"чат: {chats[0]['title']}, с {dt.datetime.fromtimestamp(k[0][0]):%d.%m %H:%M} по {dt.datetime.fromtimestamp(k[-1][0]):%d.%m %H:%M}; "
              f"от лимита за 5 часов: как было {tot / cap[0] * 100:.1f}%, на других моделях: {alt}")
    print("ФАЙЛ:", out)
    if not a.no_open and (a.out is None or a.open):
        os.startfile(out) if hasattr(os, "startfile") else __import__("webbrowser").open(out.as_uri())


# ---------- шаблон отчёта: данные вклеиваются вместо __CHATS__, __SK__, __PARAMS__ и др. (см. шапку) ----------
PAGE = r"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__NAME__</title><link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%2315181d'/%3E%3Cpath d='M8.2 5.6h3.6v2.6h2.6v3.6h-2.6v2.6H8.2v-2.6H5.6V8.2h2.6z' fill='%23E24B4A'/%3E%3Cpath d='M20.2 5.6h3.6v2.6h2.6v3.6h-2.6v2.6h-3.6v-2.6h-2.6V8.2h2.6z' fill='%231D9E75'/%3E%3Cpath d='M7 25L11 21.5L13.5 23.5' fill='none' stroke='%23E24B4A' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'/%3E%3Cpath d='M13.5 23.5L18 19L20.5 20.5' fill='none' stroke='%23EF9F27' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'/%3E%3Cpath d='M20.5 20.5L25 16' fill='none' stroke='%231D9E75' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<style>
:root{--bg:#f4f5f7;--card:#fff;--fg:#15181d;--mut:#667085;--faint:#98a2b3;--bd:#e4e7ec;--pn:#f0f2f5;--sel:#eaf1fe;--sh:0 1px 2px rgba(16,24,40,.05),0 1px 3px rgba(16,24,40,.07);
 --k-hv:#98a2b3;--k-hi:#d0d5dd;--k-cold:#f0b429;--k-out:#475467;--ok:#12b76a;--heat:#e8590c}
@media (prefers-color-scheme:dark){:root{--bg:#0f1114;--card:#181b20;--fg:#e9ebee;--mut:#9aa1ab;--faint:#6b7280;--bd:#2a2f36;--pn:#22262c;--sel:#1f2a3d;--sh:none;
 --k-hv:#7a8494;--k-hi:#3e4550;--k-cold:#e0a526;--k-out:#a9b6cc;--ok:#32d583;--heat:#ff7a3d}}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
#app{display:flex;height:100vh}
#side{display:none;width:272px;flex:none;overflow-y:auto;border-right:1px solid var(--bd);background:var(--card)}.adm #side{display:block}
#main{flex:1;min-width:0;overflow-y:auto;overflow-x:hidden}
#view{max-width:1720px;margin:0 auto;padding:22px 26px 44px}
h1{font-size:22px;font-weight:650;margin:0;letter-spacing:-.01em;overflow-wrap:anywhere}
.meta{color:var(--mut);margin-top:3px}
.row{display:flex;flex-wrap:wrap;gap:16px;margin-top:18px;align-items:flex-start}
.card{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:16px 18px;box-shadow:var(--sh);min-width:0}
.card+.card,.row+.card{margin-top:16px}.row .card+.card{margin-top:0}
h2{font-size:13px;font-weight:600;color:var(--mut);margin:0 0 10px}
.mut{color:var(--mut)}b{font-weight:650}
/* переключатели */
.seg{display:inline-flex;background:var(--pn);border-radius:9px;padding:2px;gap:2px;flex-wrap:wrap}
.seg button{border:0;background:transparent;color:var(--mut);font:inherit;font-size:12.5px;padding:4px 10px;border-radius:7px;cursor:pointer}
.seg button:hover{color:var(--fg)}.seg button.on{background:var(--card);color:var(--fg);box-shadow:0 1px 2px rgba(0,0,0,.12);font-weight:600}
/* сколько съел */
.vd{flex:0 0 270px}
.big{font-size:46px;font-weight:700;line-height:1;letter-spacing:-.02em;margin-top:2px}
.bl{color:var(--mut);margin:4px 0 12px}
.sub{color:var(--mut);margin-top:12px;font-size:13px}
.scn{margin-top:12px;padding-top:12px;border-top:1px solid var(--bd);font-size:15px;cursor:default}.scn b{font-size:18px}
.scn .sn{font-size:12.5px;color:var(--mut);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.wd{height:20px;margin-top:3px}.wd .x{margin-left:0}
.dpr{display:grid;grid-template-columns:minmax(120px,220px) 1fr 70px;gap:12px;align-items:center;padding:4px 8px;margin:0 -8px;border-radius:8px;cursor:pointer;font-size:13px}
.dpr:hover{background:var(--pn)}.dpr .n{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.dpr .r{text-align:right;color:var(--mut)}
.dtk{position:relative;height:22px}.dtk i{position:absolute;display:block}
.dtk .ax{top:0;bottom:0;width:1px;background:var(--bd)}.dtk .rng{top:9px;height:4px;border-radius:2px;background:var(--k-hi)}
.dtk .d{top:5px;width:12px;height:12px;margin-left:-6px;border-radius:50%;background:var(--c);cursor:default}
.dtk .ring{top:2px;width:18px;height:18px;margin-left:-9px;border-radius:50%;border:2px solid var(--fg);cursor:default}
.x{display:inline-block;font-size:12px;font-weight:650;border-radius:6px;padding:1px 6px;margin-left:4px;background:var(--pn)}
.x.up{color:#d92d20}.x.dn{color:var(--ok)}
/* куда ушли токены */
.cp{flex:1 1 480px}
.hb{display:grid;grid-template-columns:44px 1fr;gap:10px;align-items:center;margin:6px 0}
.hb>span{color:var(--mut);font-size:12.5px}
.hbar{display:flex;height:26px;border-radius:7px;overflow:hidden;min-width:4px}.hbar i{display:block;height:100%;min-width:0}
.hbar i+i{box-shadow:inset 1px 0 0 var(--card)}
.keys{display:flex;flex-wrap:wrap;gap:6px 18px;margin-top:12px;font-size:13px}
.key{cursor:default;white-space:nowrap}.key i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.key em{font-style:normal;color:var(--mut)}
/* а если бы */
.wi{flex:0 1 440px}
.wcs{display:flex;gap:14px;align-items:flex-end;height:142px}
.wc{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;border-radius:10px;padding:4px 0 6px;min-width:52px}
.wc.go{cursor:pointer}.wc.go:hover{background:var(--pn)}
.wv{font-size:12.5px;font-weight:600;margin-bottom:4px;white-space:nowrap}
.wb{width:30px;border-radius:5px 5px 2px 2px;display:flex;flex-direction:column-reverse;overflow:hidden;min-height:3px}.wb i{display:block}
.wn{font-size:12px;color:var(--mut);margin-top:6px;white-space:nowrap}
.wc.on{background:var(--sel)}.wc.on .wn{color:var(--fg);font-weight:650}
.ef{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:10px}.ef>span{color:var(--mut);font-size:12.5px;cursor:default;border-bottom:1px dotted var(--faint)}
.hint{color:var(--faint);font-size:12px;margin-top:8px}
/* лента */
.tph{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 18px;margin-bottom:6px}.tph h2{margin:0;color:var(--fg);font-size:15px}
.lgd{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12.5px;color:var(--mut)}
.chip i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;background:var(--c)}
.chip.ag i{background:transparent;border:1px dashed var(--mut)}
.chip.two i{width:10px;background:linear-gradient(90deg,var(--mut) 0 2px,var(--faint) 2px)}
.tr{display:grid;grid-template-columns:54px 1fr;gap:12px;margin-top:14px}
.tt{font-size:11.5px;color:var(--mut);line-height:1.3;align-self:end;padding-bottom:2px}.tt b{display:block;color:var(--fg);font-size:13px}
.bars{display:grid;grid-template-columns:repeat(150,minmax(0,1fr));column-gap:2px;height:78px;border-bottom:1px solid var(--bd)}
.sl{position:relative;height:100%;cursor:default;border-radius:2px}
.sl:hover,.sl.hl{background:var(--pn)}
.sl i{position:absolute;bottom:0;display:block;background:var(--c)}
.sl .one{left:0;right:0;border-radius:2px 2px 0 0}
.sl .was{left:0;width:2px}
.sl .now{left:2px;right:0;border-radius:0 2px 0 0}
.sl.ag .one,.sl.ag .now{background:color-mix(in srgb,var(--c) 22%,transparent);border:1px dashed var(--c);border-bottom:0}
.cap{color:var(--mut);font-size:12.5px;margin-top:10px}
/* холодные старты */
.cl{display:flex;flex-wrap:wrap;gap:28px;align-items:flex-end;margin-top:14px}
.lead{font-size:15.5px;line-height:1.55;max-width:980px}.lead b{font-size:17px}
.vc{width:96px;text-align:center;cursor:default}
.vc .v{font-size:13px;font-weight:650;margin-bottom:4px}
.vb{display:flex;flex-direction:column;justify-content:flex-end;height:150px}.vb i{display:block;width:100%}
.vb i.gh{border:2px dashed var(--ok);border-bottom:0;border-radius:4px 4px 0 0;background:color-mix(in srgb,var(--ok) 10%,transparent)}
.vb i.top{border-radius:4px 4px 0 0}
.vc .l{font-size:12px;color:var(--mut);margin-top:6px}
.evs{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:flex-start;padding-left:10px;border-left:1px solid var(--bd)}
.ev{width:58px;text-align:center;cursor:default;border-radius:8px;padding:4px 0}.ev:hover{background:var(--pn)}
.ev .s{font-size:11.5px;font-weight:650;height:16px;white-space:nowrap}.ev .s.no{color:var(--faint);font-weight:400}.ev .p i.un{opacity:.45}
.ev .p{height:90px;display:flex;align-items:flex-end;justify-content:center}.ev .p i{display:block;width:16px;border-radius:3px 3px 0 0;background:var(--k-cold);min-height:2px}
.ev .t{font-size:11px;color:var(--mut);line-height:1.25;margin-top:4px}.ev .t b{color:var(--fg);font-weight:600}
.sw{display:inline-block;width:10px;height:10px;border-radius:3px;vertical-align:-1px;margin-right:4px}
/* влезет */
.fr{display:grid;grid-template-columns:118px 1fr 120px;gap:12px;align-items:center;margin:7px 0;font-size:13.5px}
.fr .n{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.fr.on .n{font-weight:700}
.tiles{height:20px;border-radius:5px;background-color:var(--pn)}
.fr .r{text-align:right;color:var(--mut)}.fr .r b{color:var(--fg)}
/* обвязка */
.hv{margin-top:14px;border-top:1px solid var(--bd);padding-top:10px}
.hv summary{cursor:pointer;font-size:13px;color:var(--mut);list-style:revert}.hv summary b{color:var(--fg)}
.hv p{font-size:13px;color:var(--mut);margin:8px 0 10px;max-width:760px}
.sr{display:grid;grid-template-columns:minmax(120px,240px) 1fr 150px;gap:10px;align-items:center;margin:4px 0;font-size:12.5px;cursor:default}
.sr .n{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sr .r{color:var(--mut);white-space:nowrap}
.sr .t{height:10px;border-radius:3px;background:var(--pn);overflow:hidden}.sr .t i{display:block;height:100%;background:var(--k-hv);border-radius:3px}
.hv h4{font-size:12.5px;margin:14px 0 4px;font-weight:600}
/* подпись */
.notes{font-size:15px;line-height:1.6;max-width:980px}.notes p{margin:0 0 10px}
.ver{color:var(--faint);font-size:12.5px}
/* центральный */
.dr{display:grid;grid-template-columns:52px 1fr 150px;gap:12px;align-items:center;margin:6px 0;font-size:13px;cursor:default}
.dt{position:relative;height:18px}.dt .k{display:flex;height:100%;border-radius:5px;overflow:hidden}.dt .k i{display:block;height:100%}
.dt .bl2{position:absolute;top:-4px;bottom:-4px;width:0;border-left:2px dashed var(--fg);opacity:.45}
.tc{display:grid;grid-template-columns:minmax(140px,260px) 1fr 120px;gap:12px;align-items:center;margin:2px -8px;padding:4px 8px;border-radius:8px;cursor:pointer;font-size:13px}
.tc:hover{background:var(--pn)}.tc .n{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tc .k{display:flex;height:12px;border-radius:4px;overflow:hidden}.tc .k i{display:block}
.tc .r{color:var(--mut);text-align:right}
.frs div{margin:4px 0;font-size:13.5px}
.fc{color:var(--mut);font-size:13px;margin-top:8px;cursor:default}.fc b{color:var(--fg)}
.row.top{align-items:stretch}
/* доктор: живой талисман дашборда; лицо меняется от effort, по клику — шутка с цифрами недели */
.masc{flex:1 1 320px;display:flex;flex-direction:column;cursor:pointer;user-select:none}
.mrow{flex:1;display:flex;align-items:center;gap:18px}
.masc svg{flex:none;width:173px;height:200px;overflow:visible}
.mb{position:relative;background:var(--pn);border-radius:14px;padding:12px 14px;font-size:14.5px;line-height:1.45;animation:ld-pop .25s ease-out}
.mb:before{content:"";position:absolute;left:-8px;top:22px;border:8px solid transparent;border-right-color:var(--pn);border-left:0}
.ld-blink{transform-box:fill-box;transform-origin:center;animation:ld-blink 4.5s infinite}
.ld-spin{transform-box:fill-box;transform-origin:center;animation:ld-spin 1.1s linear infinite}
.ld-shake{animation:ld-shake .35s infinite}.ld-z{animation:ld-z 2.4s infinite}.ld-z2{animation:ld-z 2.4s .8s infinite}
.ld-steam{animation:ld-steam 1.4s infinite}.ld-steam2{animation:ld-steam 1.4s .45s infinite}.ld-drop{animation:ld-drop 1.6s infinite}
.masc:active svg{transform:scale(.94)}
@keyframes ld-blink{0%,93%,100%{transform:scaleY(1)}96%{transform:scaleY(.1)}}
@keyframes ld-spin{to{transform:rotate(360deg)}}
@keyframes ld-shake{0%,100%{transform:translate(0,0) rotate(0)}25%{transform:translate(-1.5px,1px) rotate(-2deg)}75%{transform:translate(1.5px,-1px) rotate(2deg)}}
@keyframes ld-z{0%{opacity:0;transform:translate(0,0)}30%{opacity:1}100%{opacity:0;transform:translate(5px,-12px)}}
@keyframes ld-steam{0%{opacity:0;transform:translateY(2px)}50%{opacity:.85}100%{opacity:0;transform:translateY(-9px)}}
@keyframes ld-drop{0%{opacity:0;transform:translateY(-2px)}30%{opacity:1}100%{opacity:0;transform:translateY(7px)}}
@keyframes ld-pop{from{transform:scale(.92);opacity:.3}to{transform:scale(1);opacity:1}}
@media (prefers-reduced-motion:reduce){.masc *{animation:none!important}}
.roi{flex:0 0 220px}
/* тепловая карта */
.hm{display:grid;grid-template-columns:62px repeat(24,minmax(0,1fr)) 64px;gap:3px;align-items:center;font-size:11.5px;margin-top:6px}
.hm i{display:block;height:24px;border-radius:4px;background:color-mix(in srgb,var(--heat) var(--a),var(--pn));cursor:default}
.hm i:hover{outline:2px solid var(--fg);outline-offset:-1px}
.hm .h{color:var(--faint);font-size:10.5px}.hm .d{color:var(--mut)}.hm .s{color:var(--mut);text-align:right;white-space:nowrap}
/* откуда холод */
.cg{font-size:12.5px;font-weight:650;margin:14px 0 2px}.cg span{font-weight:400;color:var(--mut)}
/* список чатов */
.sh{padding:16px 16px 12px;font-weight:700;font-size:16px;display:flex;gap:10px;align-items:center}.sh span{display:block;font-weight:400;font-size:12px;color:var(--mut)}
.it .t svg{vertical-align:-3px;margin-right:6px}
.it{padding:9px 16px;cursor:pointer;border-top:1px solid var(--bd)}.it:hover{background:var(--pn)}.it.sel{background:var(--sel)}
.it .t{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:13.5px}.it .s{font-size:12px;color:var(--mut)}
.it .mx{display:flex;height:4px;border-radius:2px;overflow:hidden;margin-top:5px;background:var(--pn)}.it .mx i{display:block}
#tip{position:fixed;z-index:50;display:none;max-width:350px;background:var(--card);color:var(--fg);border:1px solid var(--bd);border-radius:12px;padding:10px 12px;font-size:13px;line-height:1.45;box-shadow:0 10px 30px rgba(0,0,0,.2);pointer-events:none}
#tip .m{color:var(--mut)}#tip .tb{display:flex;height:8px;border-radius:4px;overflow:hidden;margin:6px 0 4px}#tip .tb i{display:block}
#tip .cw{margin-top:8px;padding-top:8px;border-top:1px solid var(--bd)}
#tip .cf{position:relative;height:8px;border-radius:4px;margin:7px 0 3px;background:linear-gradient(90deg,#12b76a,#f0b429 50%,#d92d20)}
#tip .cf i{position:absolute;right:0;top:0;bottom:0;background:var(--pn);border-radius:0 4px 4px 0}
#tip .tl{display:flex;justify-content:space-between;gap:12px}#tip .tl span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#tip .dot{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px;background:var(--c)}
@media(max-width:900px){#view{padding:16px}.vd,.wi{flex:1 1 100%}.tr{grid-template-columns:1fr}.tt{display:flex;gap:8px}.tt b{display:inline}.fr{grid-template-columns:90px 1fr 90px}.sr{grid-template-columns:120px 1fr 110px}.hm{gap:1px;grid-template-columns:52px repeat(24,minmax(0,1fr)) 40px}.hm i{height:18px}}
</style></head>
<body><div id="app"><aside id="side"></aside><main id="main"><div id="view"></div></main></div><div id="tip"></div>
<script>
const CH=__CHATS__,ADMIN=__ADMIN__,GEN='__GEN__',SK=__SK__,P=__PARAMS__,APP='__NAME__',VER='__VER__';
const PR=P.price,MU=P.mult,CAP=[P.cap[0],P.cap[1]/7,P.cap[1]],SUM=P.summary_tokens,CPT=P.chars_per_token,PER=150;
const NM=['Haiku','Sonnet','Opus','Fable'],CL=['#1D9E75','#378ADD','#7F77DD','#D85A30'],EN=['low','medium','high','xhigh','max'];
const WN=['5 часов','сутки','неделя'],WG=['лимита за 5 часов','лимита за сутки','лимита за неделю'];
/* куда уходят токены: четыре части цены */
const BK=[
 {n:'Обвязка',c:'var(--k-hv)',t:'Что Claude Code кладёт в каждый вызов ещё до твоего сообщения: встроенные инструменты, скиллы, память (CLAUDE.md), системные инструкции. Подробно — ниже, «Обвязка подробно».'},
 {n:'Переписка',c:'var(--k-hi)',t:'Модель не помнит разговор: на каждом вызове она заново перечитывает всю переписку. Переписка растёт, и каждый следующий вызов дороже предыдущего.'},
 {n:'Холодные старты',c:'var(--k-cold)',t:'После паузы дольше часа или смены модели переписку пришлось записать заново, а запись в 12–20 раз дороже перечитывания. Подробно — в разделе «Холодные старты».'},
 {n:'Ответы и мысли',c:'var(--k-out)',t:'Что модель написала и сколько думала перед ответом. Effort меняет только эту часть.'}];
const EXP={ok:'Если сжать чат (компакт), пока кэш тёплый, после паузы записывать пришлось бы только короткую выжимку.',no:'Переписка тут короткая: компакт (модель перечитывает весь чат и пишет выжимку) стоил бы не меньше, чем сэкономил.'};
/* причина холодного старта — только то, что видно по логу; av: можно было избежать (пауза — если компакт перед ней сэкономил бы) */
const CAU={sw:{n:'смена модели',g:'Смена модели посреди чата',av:1,t:'Кэш привязан к модели: после смены модели всю переписку пришлось записать заново. Дешевле менять модель в новом чате или сразу после компакта.'},
 idle:{n:'пауза',g:'Пауза дольше часа',av:0,t:'Кэш живёт час: после паузы всю переписку пришлось записать заново.'},
 cmp:{n:'после сжатия',g:'Контекст сжался: компакт или автоочистка',av:0,t:'Переписка укоротилась (компакт или Claude Code убрал старые выводы инструментов), и новое начало пришлось записать. Это цена сжатия, а не потеря.'},
 upd:{n:'обновление',g:'Обновился Claude Code',av:0,t:'Между вызовами сменилась версия Claude Code, а с ней начало контекста.'},
 ttl5:{n:'кэш на 5 минут',g:'Пауза, а кэш был на 5 минут',av:0,t:'Этот кэш был записан на 5 минут, а не на час, и пауза оказалась длиннее.'},
 unk:{n:'без причины',g:'Без видимой причины',av:0,t:'Пауза короче часа, модель та же, контекст не сжимался, а кэш пропал. Так бывает, когда меняется начало контекста: подключили сервис (MCP), поправили CLAUDE.md, перезапустили приложение.'}};
const why=r=>r.cs==='idle'?'пауза '+fG(r.gap):r.cs==='ttl5'?'пауза '+fG(r.gap)+', кэш был на 5 минут':CAU[r.cs].n;
const avTag=r=>r.av?'<span class="x up">можно было избежать</span>':'<span class="x">неизбежно</span>';
const FR=[['FR-10','Облачные сессии','сейчас видны только чаты на этом компьютере.'],['FR-11','Что чинить первым','три совета с ценой в процентах лимита.'],
['FR-12','Из чего состоит контекст хода','в подсказке столбика: обвязка, файлы и выводы инструментов, переписка, мысли.'],['FR-13','Демо-режим','отчёт на выдуманных данных для README и живого демо.']];
let S={c:ADMIN?-1:0,m:-1,e:-1,w:0,hv:false,hc:false,hm:0,xm:0};
/* доктор говорит только полезное: срезы этой недели (по клику — следующий); при выбранном effort — во что обошлась бы неделя */
function mascHtml(all,vals,fc,BA,days){const wk=x=>fp(x/CAP[2]*100),sumT=(m,e)=>CH.reduce((s,ch)=>s+totals(ch,m,e).t,0),v=k=>vals.find(x=>x.m===k).t;
 const roi=P.since&&P.now?(all/1e6)/(P.plan*12/365*Math.max(1/24,(P.now-P.since)/86400)):0;
 let cl=0,av=0,ag=0,big=null;CH.forEach(ch=>{const C=cc(ch,-1);cl+=C.pen;for(const k in C.rows)if(C.rows[k].av)av+=C.rows[k].pen;
  const T=totals(ch,-1,-1);ch.k.forEach((c,i)=>{const x=T.cs[i][0];if(c[9])ag+=x;if(!big||x>big.x)big={x,t:c[0],ch}})});
 const dsum=k=>days[k].reduce((s,x)=>s+x,0),dk=Object.keys(days).sort((a,b)=>dsum(b)-dsum(a))[0],mxT=sumT(-1,4);
 MQ=[`Неделя: съедено ${fp(all/CAP[2]*100)}% лимита${fc?`; в таком темпе к сбросу будет ≈${fI(fc)}%`:''}.`,
  roi?`Подписка окупилась ×${fx(roi)}: по ценам API эти вызовы стоили бы $${fI(all/1e6)}.`:'',
  CH[0]?`Больше всех съел «${esc(CH[0].title)}»: ${wk(AG[0].t)}% недели — ${fI(AG[0].t/all*100)}% всего расхода.`:'',
  cl?`Холодные старты — ${wk(cl)}% недели; можно было избежать ${wk(av)}%.`:'',
  `Обвязка — ${fI(BA[0]/all*100)}% всего расхода: её заново читает каждый вызов.`,
  `Вся неделя на Fable стоила бы ${wk(sumT(3,-1))}% лимита, на Haiku — ${wk(sumT(0,-1))}%.`,
  dk?`Самый прожорливый день — ${dk.slice(8)}.${dk.slice(5,7)}: ${fp(dsum(dk)/CAP[1]*100)}% суточного лимита.`:'',
  ag?`Агенты съели ${fI(ag/all*100)}% расхода недели.`:'',
  big?`Самый дорогой вызов — ${fh2(big.x)} в «${esc(big.ch.title)}», ${fd(big.t)}.`:'',
  `Если бы всё шло на effort max: ${wk(mxT)}% лимита — ${ddt(mxT/all)}.`].filter(Boolean);
 MI=Math.min(MI,MQ.length-1);
 const eff=S.e>=0?`Effort ${EN[S.e]} на всю неделю: ${wk(v(-1))}% лимита — ${ddt(v(-1)/all)}.`:'';
 return `<div class="card masc"><div class="mrow">${face(S.e)}<div class="mb" id="mb">${eff||MQ[MI]}</div></div>${MCL?'':'<div class="hint" id="mh">Нажми на доктора — расскажет про неделю</div>'}</div>`}
const $=id=>document.getElementById(id);
const LOGO=`<svg width="30" height="30" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="8" fill="#15181d"/><path d="M8.2 5.6h3.6v2.6h2.6v3.6h-2.6v2.6H8.2v-2.6H5.6V8.2h2.6z" fill="#E24B4A"/><path d="M20.2 5.6h3.6v2.6h2.6v3.6h-2.6v2.6h-3.6v-2.6h-2.6V8.2h2.6z" fill="#1D9E75"/><path d="M7 25L11 21.5L13.5 23.5" fill="none" stroke="#E24B4A" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M13.5 23.5L18 19L20.5 20.5" fill="none" stroke="#EF9F27" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M20.5 20.5L25 16" fill="none" stroke="#1D9E75" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const SYS=`<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">${CL.map((c,m)=>`<rect x="${m%2*8.5}" y="${(m>>1)*8.5}" width="7.5" height="7.5" rx="2" fill="${c}"/>`).join('')}</svg>`;
/* доктор: лицо по effort (−1 — как было, 0..4 — low…max); глаза-кресты красный и зелёный, рот — график вверх */
function face(st){const X=(cx,cy,f,k)=>{const a=3.4*k,w=1.3*k;return `<path d="M${cx-w} ${cy-a}h${2*w}v${a-w}h${a-w}v${2*w}h${-(a-w)}v${a-w}h${-2*w}v${-(a-w)}h${-(a-w)}v${-2*w}h${a-w}z" fill="${f}"/>`};
 const mouth=pts=>{const P=pts.map(q=>q.join(' '));return `<path d="M${P[0]}L${P[1]}L${P[2]}" fill="none" stroke="#E24B4A" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M${P[2]}L${P[3]}L${P[4]}" fill="none" stroke="#EF9F27" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M${P[4]}L${P[5]}" fill="none" stroke="#1D9E75" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>`};
 const norm=[[7,25],[11,21.5],[13.5,23.5],[18,19],[20.5,20.5],[25,16]];
 let eyes=`<g class="ld-blink">${X(10,10,'#E24B4A',1)}</g><g class="ld-blink">${X(22,10,'#1D9E75',1)}</g>`,m=mouth(norm),extra='',sh='';
 if(st===0){eyes='<path d="M6.5 10.5h7" stroke="#E24B4A" stroke-width="2.4" stroke-linecap="round"/><path d="M18.5 10.5h7" stroke="#1D9E75" stroke-width="2.4" stroke-linecap="round"/>';
  m=mouth([[8,24],[11.5,23],[13.5,23.6],[18,22.4],[20.5,22.9],[24.5,21.6]]);
  extra='<text class="ld-z" x="27" y="4" font-size="6" font-weight="700" fill="#98a2b3">z</text><text class="ld-z2" x="30" y="-1" font-size="8" font-weight="700" fill="#98a2b3">Z</text>'}
 else if(st===1){m=mouth([[7,24],[11,21.8],[13.5,23],[18,20],[20.5,20.8],[25,18]]);extra='<path d="M6.5 3.8l7 .8M18.5 4.6l7-.8" stroke="#98a2b3" stroke-width="1.6" stroke-linecap="round"/>'}
 else if(st===2)extra='<circle cx="10" cy="10" r="5.4" fill="none" stroke="#e9ebee" stroke-width="1.3"/><circle cx="22" cy="10" r="5.4" fill="none" stroke="#e9ebee" stroke-width="1.3"/><path d="M15.4 10h1.2" stroke="#e9ebee" stroke-width="1.3"/>';
 else if(st===3){eyes=`<g class="ld-blink">${X(10,10,'#E24B4A',1.25)}</g><g class="ld-blink">${X(22,10,'#1D9E75',1.25)}</g>`;m=mouth([[6.5,26],[10.5,20],[13,24],[18,16],[20.5,19],[25.5,12]]);
  extra='<path class="ld-drop" d="M29 7c1.6 2.2 2.2 3.4 2.2 4.3a2.2 2.2 0 0 1-4.4 0c0-.9.6-2.1 2.2-4.3z" fill="#378ADD"/>'}
 else if(st===4){eyes=`<g class="ld-spin">${X(10,10,'#E24B4A',1.2)}</g><g class="ld-spin">${X(22,10,'#1D9E75',1.2)}</g>`;m=mouth([[6,27],[10,17],[13,25],[18,11],[21,20],[26,5]]);sh=' class="ld-shake"';
  extra='<circle class="ld-steam" cx="8" cy="-3" r="2.2" fill="#98a2b3"/><circle class="ld-steam2" cx="16" cy="-5" r="2.6" fill="#98a2b3"/><circle class="ld-steam" cx="24" cy="-3" r="2.2" fill="#98a2b3"/>'}
 return `<svg viewBox="-3 -9 38 44"${sh} aria-hidden="true"><rect width="32" height="32" rx="8" fill="#15181d"/>${eyes}${m}${extra}</svg>`}
let MQ=[],MI=0,MCL=false;
/* формат */
const f1=x=>x.toLocaleString('ru-RU',{maximumFractionDigits:1}),fM=x=>f1(x/1e6),fI=x=>Math.round(x).toLocaleString('ru-RU');
const fp=x=>x<0.001?'<0,001':x<0.1?x.toLocaleString('ru-RU',{maximumSignificantDigits:2}):x<10?x.toLocaleString('ru-RU',{maximumFractionDigits:1}):fI(x);
const fx=x=>x<10?x.toLocaleString('ru-RU',{maximumFractionDigits:1}):fI(x);
const fh2=x=>x>=1e6?fM(x)+' млн ХТ':x>=1e3?f1(x/1e3)+' тыс. ХТ':fI(x)+' ХТ';
const fK=x=>x>=1000?f1(x/1000)+' тыс.':fI(x);
const z2=x=>(x<10?'0':'')+x,esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'),ea=s=>esc(s).replace(/"/g,'&quot;');
const D=t=>new Date(t*1000),fdd=t=>z2(D(t).getDate())+'.'+z2(D(t).getMonth()+1),fh=t=>z2(D(t).getHours())+':'+z2(D(t).getMinutes()),fd=t=>fdd(t)+' '+fh(t);
const fT=ms=>{const s=ms/1000;return s<60?fI(s)+' с':Math.floor(s/60)+' мин '+fI(s%60)+' с'},fG=s=>s>=3600?f1(s/3600)+' ч':fI(s/60)+' мин';
const pl=(n,a,b,c)=>{const m=n%10,h=n%100;return m===1&&h!==11?a:m>=2&&m<=4&&(h<12||h>14)?b:c};
const W=x=>x/CAP[S.w]*100;
/* расчёт */
const ctx=c=>c[3]+c[4]+c[5]+c[6];
function cost(c,sm,se){const m=sm<0?c[1]:sm,e0=c[2]<0?1:c[2],e=se<0?e0:se,p=PR[m],om=MU[m][e]/MU[c[1]][e0];
 const rd=c[6]*p[2],wr=c[3]*p[0]+c[4]*p[0]*1.25+c[5]*p[3],ou=c[7]*om*p[1];return [rd+wr+ou,rd,wr,ou]}
function totals(ch,sm,se){const k=sm+'|'+se;ch._t=ch._t||{};if(ch._t[k])return ch._t[k];let t=0;const cs=ch.k.map(c=>{const x=cost(c,sm,se);t+=x[0];return x});return ch._t[k]={t,cs}}
function mixOf(ch,sm,se){const T=totals(ch,sm,se),m=[0,0,0,0];ch.k.forEach((c,i)=>{m[sm<0?c[1]:sm]+=T.cs[i][0]});return m}
/* холодные старты: вызов основной цепочки, где почти весь контекст записан заново */
function ci(ch){if(ch._ci)return ch._ci;const K=ch.k,main=[];K.forEach((c,i)=>{if(!c[9])main.push(i)});
 const ws=main.map(i=>K[i][4]+K[i][5]).filter(w=>w<8000).sort((a,b)=>a-b),g=ws.length?ws[ws.length>>1]:1000,ev=[];
 for(let p=1;p<main.length;p++){const i=main[p],c=K[i],pc=K[main[p-1]],Wr=c[4]+c[5],x=ctx(c),xp=ctx(pc),gap=c[0]-pc[0];
  /* причина: компакт (контекст меньше 60%) → пауза от 59 мин (TTL кэша — час; после неё кэш умер бы и без смены модели)
     → смена модели → обновление Claude Code → подчистка (меньше 90%) → пауза при кэше на 5 минут → не видно */
  if(Wr>=Math.max(P.cold.min_write,P.cold.min_share*x))ev.push({i,p,W:Wr,x,xp,sw:c[1]!==pc[1],gap,
   cs:x<.6*xp?'cmp':gap>=3540?'idle':c[1]!==pc[1]?'sw':c[11]?'upd':x<.9*xp?'cmp':gap>=300&&pc[4]>pc[5]?'ttl5':'unk'})}
 ev.forEach((e,k)=>{e.end=k+1<ev.length?ev[k+1].p:main.length});
 return ch._ci={main,ev,g,floor:main.length?ctx(K[main[0]]):0}}
function cc(ch,sm){ch._cc=ch._cc||{};if(ch._cc[sm])return ch._cc[sm];const I=ci(ch),K=ch.k;let pen=0,sav=0;const rows={};
 I.ev.forEach(e=>{const c=K[e.i],m=sm<0?c[1]:sm,p=PR[m],pw=(c[4]*p[0]*1.25+c[5]*p[3])/e.W,pe=Math.max(0,e.W-I.g)*(pw-p[2]);pen+=pe;
  const pm=sm<0?K[I.main[e.p-1]][1]:sm,pp=PR[pm],xn=I.floor+SUM,gi=Math.max(0,e.x-e.xp),dl=e.xp-xn;let sv=0;
  if(dl>0&&e.cs!=='cmp'){const old=e.W*pw+c[6]*p[2],cmp=e.xp*pp[2]+SUM*pp[1],nw=(xn+gi)*p[3];let fl=0;
   for(let q=e.p+1;q<e.end;q++){const mj=sm<0?K[I.main[q]][1]:sm;fl+=dl*PR[mj][2]}sv=old-(cmp+nw)+fl}
  sav+=sv;rows[e.i]={pen:pe,sv,sw:e.sw,gap:e.gap,cs:e.cs,av:CAU[e.cs].av||(e.cs==='idle'&&sv>0)}});
 return ch._cc[sm]={pen,sav,rows,I}}
/* разложение цены вызова на четыре части */
function split(ch,i,sm,se){const c=ch.k[i],x=cost(c,sm,se),r=cc(ch,sm).rows[i],pen=r?r.pen:0,fl=ci(ch).floor,base=Math.max(0,x[1]+x[2]-pen),s=fl?Math.min(1,fl/Math.max(1,ctx(c))):0;
 return [base*s,base*(1-s),pen,x[3]]}
function bk(ch,sm,se){const k=sm+'|'+se;ch._b=ch._b||{};if(ch._b[k])return ch._b[k];const b=[0,0,0,0];ch.k.forEach((c,i)=>split(ch,i,sm,se).forEach((v,j)=>b[j]+=v));return ch._b[k]=b}
/* обвязка: системный минимум (контекст первого вызова) по частям, оценка по длине текста в логе */
function hz(ch){const h=ch.h,fl=ci(ch).floor;if(!h||!fl)return null;const ht=bk(ch,-1,-1)[0],tot=totals(ch,-1,-1).t,pt=ht/fl;
 const skl=h.sk>=0?SK.l[h.sk].map(s=>[SK.n[s[0]],s[1]]):[],sum=a=>a.reduce((s,b)=>s+b[1],0);
 const raw=[['Скиллы',sum(skl)],['Память (CLAUDE.md, AGENTS.md)',sum(h.mem)],['Подключённые сервисы (MCP)',sum(h.mcp)],['Списки инструментов и агентов',h.tl+h.ag],['Системный промпт',h.sys]];
 const est=raw.reduce((s,r)=>s+r[1]/CPT,0),k=est>fl?fl/est:1;
 const cats=raw.map(r=>[r[0],r[1]/CPT*k*pt]),rest=Math.max(0,fl-raw.reduce((s,r)=>s+r[1]/CPT*k,0));cats.push(['Встроенные инструменты Claude Code',rest*pt]);
 return {ht,tot,fl,cats,sk:skl.map(s=>[s[0],s[1]/CPT*k*pt]).sort((a,b)=>b[1]-a[1])}}
function hzAll(){const a={ht:0,tot:0,c:{},s:{}};CH.forEach(ch=>{const z=hz(ch);if(!z)return;a.ht+=z.ht;a.tot+=z.tot;z.cats.forEach(c=>{a.c[c[0]]=(a.c[c[0]]||0)+c[1]});z.sk.forEach(s=>{a.s[s[0]]=(a.s[s[0]]||0)+s[1]})});
 return {ht:a.ht,tot:a.tot,fl:0,cats:Object.keys(a.c).map(n=>[n,a.c[n]]),sk:Object.keys(a.s).map(n=>[n,a.s[n]]).sort((x,y)=>y[1]-x[1])}}
/* куски страницы */
const seg=(g,names,off)=>`<div class="seg">${names.map((n,i)=>`<button data-g="${g}" data-v="${i+off}" class="${S[g]===i+off?'on':''}">${n}</button>`).join('')}</div>`;
const scnName=()=>(S.m<0?'модели как были':'на '+NM[S.m])+(S.e<0?'':', effort '+EN[S.e]);
const HTT=`<b>Хайку-токен (ХТ)</b> — единица цены: 1 ХТ равен одному входному токену Haiku, остальное пересчитано в него. Лимит плана Max за 5 часов ≈ ${fM(CAP[0])} млн ХТ, за неделю ≈ ${f1(CAP[2]/1e9)} млрд ХТ, за сутки — неделя ÷ 7 (оценка).`;
const dd=k=>{const d=(k-1)*100;return Math.abs(d)<0.5?'<span class="x">так же</span>':`<span class="x ${d>0?'up':'dn'}">${d>0?'+':'−'}${fx(Math.abs(d))}%</span>`};
const ddt=k=>{const d=(k-1)*100;return Math.abs(d)<0.5?'столько же, сколько было':d>0?`на ${fx(d)}% дороже, чем было`:`на ${fx(-d)}% дешевле, чем было`};
const EFT='<b>Effort</b> — сколько модель думает перед ответом. Меняет только «ответы и мысли». По замерам на 11 тыс. вызовов (тот же размер контекста, против medium): low ≈ ×0,65, high ≈ ×1,1, xhigh ≈ ×1,5 (у Sonnet ×2), max ≈ ×3,5 (у Sonnet ×4,6). У Haiku effort нет.';
function verdictCard(A,T,scn,title){const pa=W(A.t),pt=W(T.t),k=T.t/A.t;
 return `<div class="card vd"><h2>${title}</h2><div class="big">${fp(pa)}%</div><div class="bl">${WG[S.w]}</div>${seg('w',WN,0)}
 <div class="sub" data-tip="${ea(HTT)}">${fh2(A.t)} · ${fp(A.t/CAP[2]*100)}% за неделю</div>
 ${scn?`<div class="scn" data-tip="${ea(`<b>${scnName()}</b><br>${fp(pt)}% ${WG[S.w]}: ${ddt(k)}.`)}"><div class="sn">${scnName()}</div><b>${fp(pt)}%</b> ${dd(k)}</div>`:'<div class="scn" style="visibility:hidden"><div class="sn">·</div><b>·</b></div>'}</div>`}
function compCard(BA,tA,BT,tT,hvh,rs){const mx=Math.max(tA,BT?tT:0)||1;
 const tipB=(j,v,t)=>`<b>${BK[j].n}: ${f1(v/t*100)}% цены</b><br>${fh2(v)} · ${fp(W(v))}% ${WG[S.w]}<div class="cw m">${BK[j].t}</div>`;
 const bar=(B,t,lab)=>`<div class="hb"><span>${lab}</span><div class="hbar" style="width:${t/mx*100}%">${B.map((v,j)=>v>0?`<i style="width:${v/t*100}%;background:${BK[j].c}" data-tip="${ea(tipB(j,v,t))}"></i>`:'').join('')}</div></div>`;
 const keys=BK.map((b,j)=>`<span class="key" data-tip="${ea(`<b>${b.n}</b><br>${b.t}`)}"><i style="background:${b.c}"></i>${b.n} <b>${f1(BA[j]/(tA||1)*100)}%</b>${BT?` <em>→ ${f1(BT[j]/(tT||1)*100)}%</em>`:''}</span>`).join('');
 return `<div class="card cp"><h2>Куда ушли токены</h2>${bar(BA,tA,BT||rs?'было':'')}${BT?bar(BT,tT,'стало'):rs?'<div class="hb" style="visibility:hidden"><span>·</span><div class="hbar"></div></div>':''}<div class="keys">${keys}</div>${hvh}</div>`}
function whatifCard(vals,clickable,note){const mx=Math.max(...vals.map(v=>v.t))||1;
 const col=v=>{const h=Math.max(3,v.t/mx*96),on=clickable&&S.m===v.m,
  inner=v.mix?v.mix.map((x,m)=>x>0?`<i style="height:${x/v.t*100}%;background:${CL[m]}"></i>`:'').join(''):`<i style="height:100%;background:${CL[v.m]}"></i>`,
  tp=`<b>${v.m<0?(S.e<0?'Как было':'Модели как были, effort '+EN[S.e]):NM[v.m]+(S.e<0?'':', effort '+EN[S.e])}</b><br>${fp(W(v.t))}% ${WG[S.w]} · ${fh2(v.t)}${v.m<0&&S.e<0?'':'<br>'+ddt(v.k)}`
   +(v.mix&&v.mix.filter(x=>x>0).length>1?'<div class="cw">'+v.mix.map((x,m)=>x>0?`<span class="dot" style="--c:${CL[m]}"></span>${NM[m]} ${f1(x/v.t*100)}%`:'').filter(Boolean).join('<br>')+'</div>':'')
   +(clickable?'<div class="cw m">Нажми, и лента ниже покажет каждый вызов в этом варианте.</div>':'');
  return `<div class="wc${clickable?' go':''}${on?' on':''}" data-m="${v.m}" data-tip="${ea(tp)}"><div class="wv">${fp(W(v.t))}%</div><div class="wb" style="height:${h}px">${inner}</div><div class="wn">${v.m<0?'как было':NM[v.m]}</div><div class="wd">${v.m<0&&S.e<0?'':dd(v.k)}</div></div>`};
 return `<div class="card wi"><h2>А если бы на другой модели</h2><div class="wcs">${vals.map(col).join('')}</div>
 <div class="ef"><span data-tip="${ea(EFT)}">Effort</span>${seg('e',['как был'].concat(EN),-1)}</div>${note?`<div class="hint">${note}</div>`:''}</div>`}
function hvHtml(z,key,scope){if(!z||!z.ht)return '';const tw=x=>fp(x/CAP[2]*100)+'% за неделю',mx=Math.max(...z.cats.map(c=>c[1]),1e-9),sk=z.sk.slice(0,12),rest=z.sk.slice(12),ms=Math.max(1e-9,...sk.map(s=>s[1]));
 const rw=(n,v,m,tip)=>`<div class="sr"${tip?` data-tip="${ea(tip)}"`:''}><div class="n">${esc(n)}</div><div class="t"><i style="width:${v/m*100}%"></i></div><div class="r">${f1(v/z.ht*100)}% · ${tw(v)}</div></div>`;
 const skT=z.sk.reduce((s,x)=>s+x[1],0);
 return `<details class="hv" data-k="${key}"${S[key]?' open':''}><summary><b>Обвязка подробно</b> — ${f1(z.ht/(z.tot||1)*100)}% цены ${scope}, ${tw(z.ht)}${skT?`; из них скиллы — ${tw(skT)}`:''}</summary>
 <p>Обвязку Claude Code кладёт в каждый вызов${z.fl?` (здесь около ${fK(z.fl)} токенов)`:''}, поэтому платишь за неё на каждом шаге. Части оценены по длине текста в логе, это прикидка. Справа — доля обвязки и доля лимита за неделю.</p>
 ${z.cats.slice().sort((a,b)=>b[1]-a[1]).filter(c=>c[1]>0).map(c=>rw(c[0],c[1],mx)).join('')}
 ${sk.length?`<h4>Скиллы по отдельности</h4>`+sk.map(s=>rw(s[0],s[1],ms,`<b>${esc(s[0])}</b><br>Описание скилла лежит в каждом вызове, даже если скилл не запускали.<br>${fh2(s[1])} за период`)).join('')
  +(rest.length?`<div class="mut" style="font-size:12.5px;margin-top:4px">и ещё ${rest.length} ${pl(rest.length,'скилл','скилла','скиллов')}: ${tw(rest.reduce((s,x)=>s+x[1],0))}</div>`:''):''}</details>`}
/* лента */
function tapeHtml(ch,A,T,scn){const K=ch.k,n=K.length;let mxv=0;K.forEach((c,i)=>{mxv=Math.max(mxv,A.cs[i][0],scn?T.cs[i][0]:0)});mxv=mxv||1;
 /* шкала по самому дорогому вызову из «как было» и варианта; самый высокий — 90% ряда, потолка не касается; √ — чтобы мелкие были видны */
 const H=v=>`max(2px,${(Math.sqrt(v/mxv)*90).toFixed(2)}%)`;
 const used=[0,1,2,3].filter(m=>K.some(c=>c[1]===m)||m===S.m),hasAg=K.some(c=>c[9]);
 const lg=used.map(m=>`<span class="chip"><i style="--c:${CL[m]}"></i>${NM[m]}</span>`).join('')+(hasAg?'<span class="chip ag"><i></i>пунктир — агент</span>':'')
  +(scn?`<span class="chip two"><i></i>тонкая линия слева — как было, остальное — ${scnName()}</span>`:'');
 let h='';for(let s=0;s<n;s+=PER){const e=Math.min(n,s+PER);let b='';
  for(let i=s;i<e;i++){const c=K[i],m0=c[1],m=S.m<0?m0:S.m,ag=c[9]?' ag':'';
   b+=scn?`<div class="sl${ag}" data-i="${i}"><i class="was" style="height:${H(A.cs[i][0])};--c:${CL[m0]}"></i><i class="now" style="height:${H(T.cs[i][0])};--c:${CL[m]}"></i></div>`
     :`<div class="sl${ag}" data-i="${i}"><i class="one" style="height:${H(A.cs[i][0])};--c:${CL[m0]}"></i></div>`}
  h+=`<div class="tr"><div class="tt">${fdd(K[s][0])}<br><b>${fh(K[s][0])}</b>→ ${fdd(K[e-1][0])!==fdd(K[s][0])?fd(K[e-1][0]):fh(K[e-1][0])}</div><div class="bars">${b}</div></div>`}
 return `<div class="card"><div class="tph"><h2>Лента вызовов</h2><div class="lgd">${lg}</div></div>${h}
 <div class="cap">Каждый столбик — один вызов модели: прочитала всё и ответила. Выше — дороже. Самые высокие — холодные старты. Наведи на столбик, чтобы увидеть, на что ушли токены.</div></div>`}
const rz=v=>{const s=fx(v);return s.includes(',')?s+' раза':s+' '+pl(Math.round(v),'раз','раза','раз')};
function tipCall(ch,i){const c=ch.k[i],scn=S.m>=0||S.e>=0,x=cost(c,-1,-1),sp=split(ch,i,-1,-1),t=x[0]||1,r=cc(ch,-1).rows[i];
 const eff=c[1]===0?'':` · effort ${c[2]<0?'не записан':EN[c[2]]}`,q=t/(totals(ch,-1,-1).t/ch.k.length);
 /* контекстное окно: 1 млн токенов, у Haiku — 200 тыс.; полоска-светофор, незаполненное — серым */
 const win=c[1]===0?2e5:1e6,fill=Math.min(1,ctx(c)/win);
 let h=`<div><span class="dot" style="--c:${CL[c[1]]}"></span><b>${NM[c[1]]}</b>${eff}${c[9]?' · агент':''}</div><div class="m">вызов № ${i+1} · ${fd(c[0])}</div>
 <div style="margin-top:6px">${q>=1.15?`<b>в ${rz(q)} дороже</b> среднего вызова этого чата`:q<=.87?`<b>в ${rz(1/q)} дешевле</b> среднего вызова этого чата`:'<b>как средний вызов</b> этого чата'} <span class="m">· ${fh2(x[0])}</span></div>
 <div class="tb">${sp.map((v,j)=>v>0?`<i style="width:${v/t*100}%;background:${BK[j].c}"></i>`:'').join('')}</div>
 <div class="m">${sp.map((v,j)=>v/t>=.005?`${BK[j].n.toLowerCase()} ${f1(v/t*100)}%`:'').filter(Boolean).join(' · ')}</div>
 <div class="cf"><i style="width:${((1-fill)*100).toFixed(1)}%"></i></div><div class="m">контекст заполнен на ${fI(fill*100)}%: ${fK(ctx(c))} из ${win===1e6?'1 млн':'200 тыс.'} токенов</div>
 <div style="margin-top:4px">написала ${fK(c[7])} токенов${c[8]?' · думала '+fT(c[8]):''}</div>${c[10]?`<div class="m">инструменты: ${esc(c[10])}</div>`:''}`;
 if(r)h+=`<div class="cw"><span class="sw" style="background:var(--k-cold)"></span><b>Холодный старт</b>: ${why(r)} ${avTag(r)}<br>${CAU[r.cs].t}${r.sv>0?' Компакт перед ним сэкономил бы '+fh2(r.sv)+'.':''}</div>`;
 if(scn){const y=cost(c,S.m,S.e)[0];h+=`<div class="cw">Этот вызов ${scnName()}: <b>${ddt(y/t)}</b>.<div class="m">Весь чат — в карточке «Этот чат съел».</div></div>`}
 return h}
/* холодные старты */
function coldHtml(ch,T){const C=cc(ch,S.m),I=C.I,tot=T.t||1,pen=C.pen,sav=C.sav,ok=sav>0,n=I.ev.length,pc=x=>f1(x/tot*100);
 if(!n)return `<div class="card"><h2>Холодные старты</h2><div class="lead">Холодных стартов не было: модель не менялась, а пауз дольше часа не случалось.</div></div>`;
 const H=150,col=(lab,top,body,tip)=>`<div class="vc" data-tip="${ea(tip)}"><div class="v">${top}</div><div class="vb">${body}</div><div class="l">${lab}</div></div>`;
 const was=col('сейчас','100%',`<i class="top" style="height:${pen/tot*H}px;background:var(--k-cold)"></i><i style="height:${(tot-pen)/tot*H}px;background:var(--k-hi)"></i>`,
  `<b>Цена чата сейчас</b><br><span class="sw" style="background:var(--k-cold)"></span>холодные старты: ${pc(pen)}% цены, ${fh2(pen)}`);
 const aft=ok?col('с компактом','−'+pc(sav)+'%',`<i class="gh" style="height:${sav/tot*H}px"></i><i style="height:${(pen-Math.min(pen,sav))/tot*H}px;background:var(--k-cold)"></i><i style="height:${(tot-pen-Math.max(0,sav-pen))/tot*H}px;background:var(--k-hi)"></i>`,
  `<b>Если бы перед каждым холодным стартом был компакт</b><br>Чат стал бы дешевле на ${pc(sav)}%: ${fh2(sav)}. Пунктир — то, что ушло бы.<div class="cw m">${EXP.ok} Допущение: выжимка ${fK(SUM)} токенов.</div>`)
  :col('с компактом','не поможет',`<i style="height:${H}px;background:var(--k-hi);opacity:.5"></i>`,`<b>Компакт не помог бы</b><br>${EXP.no}`);
 const idx=Object.keys(C.rows).map(Number).sort((a,b)=>a-b),shown=idx.slice(0,30),mx=Math.max(1e-9,...shown.map(i=>C.rows[i].pen));
 const evs=shown.map(i=>{const r=C.rows[i],c=ch.k[i];
  const tip=`<b>Холодный старт ${fd(c[0])}</b>: ${why(r)} ${avTag(r)}<br>${CAU[r.cs].t}<br>Лишние ${fh2(r.pen)}: ${pc(r.pen)}% цены чата.<div class="cw">${r.cs==='cmp'?'Компакт уже был.':r.sv>0?'Компакт перед ним сэкономил бы '+fh2(r.sv)+' ('+pc(r.sv)+'% цены чата). '+EXP.ok:'Компакт перед ним ничего бы не сэкономил. '+EXP.no}</div>`;
  return `<div class="ev" data-i="${i}" data-tip="${ea(tip)}"><div class="s${r.av?'':' no'}">${fp(r.pen/tot*100)}%</div><div class="p"><i${r.av?'':' class="un"'} style="height:${r.pen/mx*100}%"></i></div><div class="t">${fdd(c[0])}<br><b>${fh(c[0])}</b><br>${r.cs==='idle'||r.cs==='ttl5'?'пауза '+fG(r.gap):CAU[r.cs].n}</div></div>`}).join('');
 return `<div class="card"><h2>Холодные старты</h2>
 <div class="lead">${n} ${pl(n,'раз','раза','раз')} чат начинал с холодного кэша и записывал переписку заново. Это <b>${pc(pen)}% цены чата</b> (${fp(W(pen))}% ${WG[S.w]}).<br>
 ${ok?`Компакт перед каждым сделал бы чат дешевле на <b>${pc(sav)}%</b>.`:'Компакт перед ними ничего бы не сэкономил: переписка короткая.'}</div>
 <div class="cl">${was}${aft}<div class="evs">${evs}${idx.length>shown.length?`<div class="mut" style="font-size:12px;align-self:center">и ещё ${idx.length-shown.length}</div>`:''}</div></div>
 <div class="cap">Каждый столбик — один холодный старт, число над ним — сколько он стоил в процентах цены чата. Яркие можно было избежать, бледные — неизбежные. Наведи, чтобы увидеть причину.</div></div>`}
/* сколько влезет */
function fitsHtml(ch){const K=ch.k,n=K.length,rows=[-1,0,1,2,3].map(m=>{const t=totals(ch,m,S.e).t,p=W(t),P2=Math.min(p,100),c=m<0?'var(--fg)':CL[m];
 const bg=p>=100?`linear-gradient(${c},${c})`:`repeating-linear-gradient(90deg,${c} 0,${c} calc(${P2}% - 2px),transparent calc(${P2}% - 2px),transparent ${P2}%)`;
 const lab=m<0?'как было':NM[m];
 return `<div class="fr${m===S.m?' on':''}"><div class="n" style="color:${c}">${lab}</div><div class="tiles" style="background-image:${bg};${p>=100?'opacity:.85':''}"></div><div class="r">${p>=100?`не влезет: <b>${fx(p/100)}</b> окна`:(q=>`<b>${fx(q)}</b> ${q%1?'чата':pl(q,'чат','чата','чатов')}`)(Math.floor(100/p*10)/10)}</div></div>`}).join('');
 return `<div class="card"><div class="tph"><h2>Сколько таких чатов влезет в ${['лимит за 5 часов','лимит за сутки','лимит за неделю'][S.w]}</h2>${seg('w',WN,0)}</div><div class="cap" style="margin:0 0 6px">«Такой чат» — этот чат целиком: все ${n} ${pl(n,'вызов','вызова','вызовов')} с ${fd(K[0][0])} по ${fd(K[n-1][0])}${S.e<0?'':', effort '+EN[S.e]}. Одна плитка — один такой чат.</div>${rows}</div>`}
const NOTES=()=>`<div class="card notes"><h2>Как это читать</h2>
<p><b>Вызов</b> — один раз, когда модель прочитала всё и ответила. На один твой вопрос часто приходится несколько вызовов: модель зовёт инструменты (читает файлы, ищет) и после каждого думает заново.</p>
<p><b>Почему длинный чат дорогой.</b> Модель не помнит разговор. На каждом вызове она заново перечитывает всю переписку и обвязку. Перечитывать дёшево, но переписка растёт, и к концу длинного чата почти вся цена уходит на перечитывание.</p>
<p><b>Холодный старт.</b> Кэш живёт около часа и привязан к модели. После паузы или смены модели переписку приходится записать заново, а запись в 12–20 раз дороже перечитывания. На ленте это самые высокие столбики. У каждого подписана причина и можно ли было его избежать.</p>
<p><b>Effort</b> — сколько модель думает перед ответом. Он меняет только «ответы и мысли».</p>
<p>${HTT}</p>
<p><b>Почему проценты меньше, чем в Claude.</b> Здесь только чаты на этом компьютере. Claude в настройках считает весь аккаунт: облачные сессии, другие компьютеры, других людей на том же аккаунте. Поэтому у него процент выше — так и должно быть. Размер лимита Claude не сообщает, мы оценили его один раз и с его процентами не сверяемся.</p>
<p class="ver">${APP} ${VER} · снимок логов ${GEN} · данные не покидают компьютер</p></div>`;
/* страница чата */
function chatView(ch){const n=ch.k.length,A=totals(ch,-1,-1),scn=S.m>=0||S.e>=0,T=scn?totals(ch,S.m,S.e):A,ag=ch.k.filter(c=>c[9]).length;
 const vals=[-1,0,1,2,3].map(m=>{const t=totals(ch,m,S.e).t;return {m,t,k:t/A.t,mix:m<0?mixOf(ch,-1,S.e):null}});
 return `<h1>${esc(ch.title)}</h1><div class="meta">${fd(ch.k[0][0])} → ${fd(ch.k[n-1][0])} · ${n} ${pl(n,'вызов','вызова','вызовов')} модели${ag?`, из них ${ag} — агенты`:''}</div>
 <div class="row top">${whatifCard(vals,true,'')}${verdictCard(A,T,scn,'Этот чат съел')}${compCard(bk(ch,-1,-1),A.t,scn?bk(ch,S.m,S.e):null,T.t,hvHtml(hz(ch),'hv','чата'),1)}</div>
 ${tapeHtml(ch,A,T,scn)}${coldHtml(ch,T)}${fitsHtml(ch)}${NOTES()}`}
/* центральный дашборд */
const AG=CH.map(ch=>{const t=totals(ch,-1,-1).t;return {t,m:mixOf(ch,-1,-1)}}),MX=Math.max(1e-9,...AG.map(a=>a.t));
function central(){const days={},dch={},sumT=(sm,se)=>CH.reduce((s,ch)=>s+totals(ch,sm,se).t,0),all=sumT(-1,-1);
 const t0=new Date();t0.setHours(0,0,0,0);let today=0;
 CH.forEach(ch=>{const T=totals(ch,-1,-1);ch.k.forEach((c,i)=>{const x=T.cs[i][0],d=D(c[0]),k=d.getFullYear()+'-'+z2(d.getMonth()+1)+'-'+z2(d.getDate());(days[k]=days[k]||[0,0,0,0])[c[1]]+=x;const q=dch[k]=dch[k]||{};q[ch.title]=(q[ch.title]||0)+x;if(c[0]>=t0/1000)today+=x})});
 const BA=[0,0,0,0];CH.forEach(ch=>bk(ch,-1,-1).forEach((v,j)=>BA[j]+=v));
 const sw=S.w;S.w=2;
 const mixAll=[0,0,0,0];AG.forEach(a=>a.m.forEach((v,m)=>mixAll[m]+=v));
 const vals=[-1,0,1,2,3].map(m=>{const t=sumT(m,S.e);return {m,t,k:t/all,mix:m<0?(S.e<0?mixAll:CH.reduce((acc,ch)=>{mixOf(ch,-1,S.e).forEach((v,j)=>acc[j]+=v);return acc},[0,0,0,0])):null}});
 const ks=Object.keys(days).sort(),dmx=Math.max(CAP[1],...ks.map(k=>days[k].reduce((a,b)=>a+b,0)));
 const dh=ks.map(k=>{const v=days[k],t=v.reduce((a,b)=>a+b,0),lab=k.slice(8)+'.'+k.slice(5,7);
  const cs=Object.entries(dch[k]).sort((a,b)=>b[1]-a[1]),cl=cs.slice(0,10).map(([nm,x])=>`<div class="tl"><span>${esc(nm)}</span><b>${fp(x/CAP[1]*100)}%</b></div>`).join('')
   +(cs.length>10?`<div class="m">и ещё ${cs.length-10} ${pl(cs.length-10,'чат','чата','чатов')}: ${fp(cs.slice(10).reduce((s,a)=>s+a[1],0)/CAP[1]*100)}%</div>`:'');
  return `<div class="dr" data-tip="${ea(`<b>${lab}</b>: ${fp(t/CAP[1]*100)}% лимита за сутки<div class="cw"><div class="m">какие чаты съели, % лимита за сутки:</div>${cl}</div><div class="cw m">`+v.map((x,m)=>x>0?`<span class="dot" style="--c:${CL[m]}"></span>${NM[m]} ${f1(x/t*100)}%`:'').filter(Boolean).join(' · ')+'</div>')}"><div>${lab}</div>
  <div class="dt"><div class="k" style="width:${t/dmx*100}%">${v.map((x,m)=>x>0?`<i style="width:${x/t*100}%;background:${CL[m]}"></i>`:'').join('')}</div><div class="bl2" style="left:${CAP[1]/dmx*100}%"></div></div>
  <div class="mut"><b style="color:var(--fg)">${fp(t/CAP[1]*100)}%</b> лимита за сутки</div></div>`}).join('');
 const top=CH.map((ch,i)=>i).slice(0,15).map(i=>{const a=AG[i];return `<div class="tc go-chat" data-i="${i}"><div class="n">${esc(CH[i].title)}</div><div class="k" style="width:${a.t/MX*100}%">${a.m.map((v,m)=>v>0?`<i style="width:${v/a.t*100}%;background:${CL[m]}"></i>`:'').join('')}</div><div class="r"><b style="color:var(--fg)">${fp(a.t/CAP[2]*100)}%</b> за неделю</div></div>`}).join('');
 const nk=CH.reduce((a,c)=>a+c.k.length,0);
 const per=P.since?(P.cal&&P.cal.week0===P.since?`неделя лимита Claude: с ${fd(P.since)}`:`с ${fd(P.since)}`)+' · ':'';
 const html=`<h1>Вся система за неделю</h1><div class="meta">${per}${CH.length} ${pl(CH.length,'чат','чата','чатов')} · ${fI(nk)} ${pl(nk,'вызов','вызова','вызовов')} модели · снимок логов ${GEN}</div>
 <div class="row top">${whatifCard(vals,false,'Вся неделя на одной модели. Чат по отдельности — в списке слева.')}<div class="card vd"><h2>Чаты в отчёте съели</h2><div class="big">${fp(all/CAP[2]*100)}%</div><div class="bl">лимита за неделю</div>
  <div class="sub" data-tip="${ea(HTT)}">${fh2(all)}</div><div class="scn">сегодня: <b>${fp(today/CAP[1]*100)}%</b> лимита за сутки</div>${fcLine(all)}</div>
  ${roiCard(all)}${mascHtml(all,vals,fcPct(all),BA,days)}</div>
 ${expHtml()}${compCard(BA,all,null,0,hvHtml(hzAll(),'hc','системы'))}
 <div class="card"><h2>Расход по дням</h2><div class="cap" style="margin:0 0 8px">Пунктир — лимит за сутки (неделя ÷ 7). Цвет — модель. Наведи на день — какие чаты его съели.</div>${dh}</div>
 ${acctHtml()}${heatHtml()}
 <div class="card"><h2>Самые дорогие чаты — нажми, чтобы открыть</h2>${top}</div>
 ${coldAllHtml()}
 <div class="card frs"><h2>Фичи-реквесты</h2>${FR.map(f=>`<div><b>${f[0]}.</b> ${f[1]}${f[2]?': '+f[2]:''}</div>`).join('')}</div>${NOTES()}`;
 S.w=sw;return html}
/* холодные старты всей системы: стоит ли с ними бороться */
function coldAllHtml(){let pen=0,sav=0,n=0;const rows=CH.map((ch,i)=>{const C=cc(ch,-1);pen+=C.pen;sav+=C.sav;n+=C.I.ev.length;return {i,pen:C.pen,sav:C.sav,n:C.I.ev.length}}).filter(r=>r.n).sort((a,b)=>b.pen-a.pen);
 if(!n)return '';const all=AG.reduce((s,a)=>s+a.t,0),wk=x=>fp(x/CAP[2]*100),mx=Math.max(1e-9,...rows.map(r=>r.pen)),h5=sav/CAP[0];
 const list=rows.slice(0,10).map(r=>`<div class="tc go-chat" data-i="${r.i}" data-tip="${ea(`<b>${esc(CH[r.i].title)}</b><br>${r.n} ${pl(r.n,'холодный старт','холодных старта','холодных стартов')}: ${wk(r.pen)}% лимита за неделю.<br>${r.sav>0?'Компакт перед каждым сэкономил бы '+wk(r.sav)+'%.':'Компакт перед ними ничего бы не сэкономил.'}`)}"><div class="n">${esc(CH[r.i].title)}</div><div class="k" style="width:${r.pen/mx*100}%"><i style="width:100%;background:var(--k-cold)"></i></div><div class="r"><b style="color:var(--fg)">${wk(r.pen)}%</b> за неделю</div></div>`).join('');
 /* откуда холод: причины с ценой, «можно было избежать» сверху */
 const G={};CH.forEach(ch=>{const R=cc(ch,-1).rows;for(const k in R){const r=R[k],key=r.cs==='idle'?(r.sv>0?'idle+':'idle-'):r.cs,g=G[key]=G[key]||{n:0,pen:0,sv:0};g.n++;g.pen+=r.pen;g.sv+=r.sv}});
 const CN={'idle+':['Пауза дольше часа без компакта','Компакт перед паузой сэкономил бы: после неё записывать пришлось бы только короткую выжимку.'],
  'idle-':['Пауза дольше часа','Переписка была короткая: компакт перед паузой ничего бы не сэкономил.']},cn=k=>CN[k]||[CAU[k].g,CAU[k].t];
 const AV=['sw','idle+'],UN=['idle-','cmp','upd','ttl5','unk'],cm=Math.max(1e-9,...Object.values(G).map(g=>g.pen)),gs=ks=>ks.reduce((s,k)=>s+(G[k]?G[k].pen:0),0);
 const crow=k=>{const g=G[k];if(!g)return '';const [nm,t]=cn(k);
  return `<div class="tc" style="cursor:default" data-tip="${ea(`<b>${nm}</b><br>${g.n} ${pl(g.n,'раз','раза','раз')} · ${wk(g.pen)}% лимита за неделю, ${f1(g.pen/pen*100)}% всего холода${g.sv>0?'<br>Компакт перед каждым вернул бы '+wk(g.sv)+'%.':''}<div class="cw m">${t}</div>`)}"><div class="n">${nm} <span class="mut">· ${g.n}</span></div><div class="k" style="width:${g.pen/cm*100}%"><i style="width:100%;background:var(--k-cold)${UN.includes(k)?';opacity:.45':''}"></i></div><div class="r"><b style="color:var(--fg)">${wk(g.pen)}%</b> за неделю</div></div>`};
 const src=(gs(AV)?`<div class="cg">Можно было избежать <span>— ${wk(gs(AV))}% лимита за неделю</span></div>${AV.map(crow).join('')}`:'')
  +(gs(UN)?`<div class="cg">Неизбежно <span>— ${wk(gs(UN))}% лимита за неделю</span></div>${UN.map(crow).join('')}`:'');
 return `<div class="card"><h2>Холодные старты всей системы</h2>
 <div class="lead">За неделю чаты ${n} ${pl(n,'раз','раза','раз')} начинали с холодного кэша. Это <b>${wk(pen)}% лимита за неделю</b>, ${f1(pen/all*100)}% всего расхода.<br>
 ${sav>0?`Компакт перед каждым сэкономил бы <b>${wk(sav)}% лимита за неделю</b>${h5>=.5?` — это примерно ${fx(h5)} ${pl(Math.round(h5),'лимит','лимита','лимитов')} за 5 часов`:''}.`:'Компакт перед ними в сумме ничего бы не сэкономил.'}</div>
 <div class="cap" style="margin:12px 0 0">Откуда холод — наведи на строку, чтобы увидеть объяснение:</div>${src}
 <div class="cap" style="margin:16px 0 6px">В каких чатах холодные старты съели больше всего — нажми, чтобы открыть:</div>${list}</div>`}
/* когда горит лимит: строка — день, клетка — час. «Эта неделя» — даты с начала недели, из чатов отчёта;
   «обычная неделя» — дни недели в среднем за последние недели (heat из питона, с тремя главными чатами в клетке) */
const WD=['пн','вт','ср','чт','пт','сб','вс'];
function heatHtml(){const H=P.heat;if(!H)return '';let rows=[],wk=1;
 const top=(o,k)=>Object.entries(o).sort((a,b)=>b[1]-a[1]).slice(0,k);
 if(S.hm){wk=Math.max(1,H.days/7);for(let d=0;d<7;d++)rows.push({lab:WD[d],v:H.v.slice(d*24,d*24+24).map(x=>x/wk),
   who:H.top.slice(d*24,d*24+24).map(t=>t.map(([ni,x])=>[H.names[ni],x/wk]))})}
 else{const by={};CH.forEach(ch=>{const T=totals(ch,-1,-1);ch.k.forEach((c,i)=>{const d=D(c[0]),key=fdd(c[0]),h=d.getHours();
   const r=by[key]=by[key]||{t:c[0],lab:WD[(d.getDay()+6)%7]+' '+key,v:new Array(24).fill(0),w:[...Array(24)].map(()=>({}))};
   r.t=Math.min(r.t,c[0]);r.v[h]+=T.cs[i][0];r.w[h][ch.title]=(r.w[h][ch.title]||0)+T.cs[i][0]})});
  rows=Object.values(by).sort((a,b)=>a.t-b.t).map(r=>({lab:r.lab,v:r.v,who:r.w.map(o=>top(o,5))}))}
 const mx=Math.max(1e-9,...rows.flatMap(r=>r.v)),pd=x=>x>0?fp(x/CAP[1]*100)+'%':'—',avg=S.hm?', в среднем за неделю':'';
 let h='<div></div>'+[...Array(24)].map((_,j)=>`<div class="h">${j%3?'':j}</div>`).join('')+'<div class="h" style="text-align:right">за сутки</div>';
 rows.forEach(r=>{let s=0;h+=`<div class="d">${r.lab}</div>`;
  r.v.forEach((x,j)=>{s+=x;const who=r.who[j].map(([nm,y])=>`<div class="tl"><span>${esc(nm)}</span><b>${fh2(y)} · ${fI(y/x*100)}%</b></div>`).join('');
   h+=`<i style="--a:${x>0?Math.max(6,Math.sqrt(x/mx)*100).toFixed(0):0}%" data-tip="${ea(`<b>${r.lab}, ${z2(j)}:00–${z2((j+1)%24)}:00</b>${avg}<br>${x>0?`сгорело <b>${fh2(x)}</b><br>${fp(x/CAP[0]*100)}% лимита за 5 часов · ${fp(x/CAP[1]*100)}% за сутки · ${fp(x/CAP[2]*100)}% за неделю<div class="cw"><div class="m">кто съел — токены и доля часа:</div>${who}</div>`:'ничего не потрачено'}`)}"></i>`});
  h+=`<div class="s">${pd(s)}</div>`});
 const L1=P.cal&&P.cal.week0===P.since?'эта неделя':'период отчёта',since=fdd(P.now-H.days*86400);
 return `<div class="card"><div class="tph"><h2>Когда горит лимит</h2>${seg('hm',[L1,'обычная неделя'],0)}</div>
 <div class="cap" style="margin:0 0 4px">${S.hm?`Дни недели в среднем за последние ${fI(H.days)} ${pl(Math.round(H.days),'день','дня','дней')} (с ${since}) — видно привычку: в какие дни и часы обычно горит лимит.`:`Строка — день, клетка — час.`} Чем ярче клетка, тем больше лимита съедено в этот час. Справа — весь день в % лимита за сутки. Наведи на клетку — сколько сгорело и какие чаты жрали.</div><div class="hm">${h}</div></div>`}
/* подписка окупилась: те же вызовы по ценам API (1 ХТ = $1 за миллион) против доли подписки за те же дни */
function roiCard(all){if(!P.since||!P.now)return '';const days=Math.max(1/24,(P.now-P.since)/86400),usd=all/1e6,sub=P.plan*12/365*days,k=usd/sub;
 const tip=`<b>${k>=1?'Подписка окупилась':'Подписка пока не окупилась'}</b><br>Те же вызовы по ценам Claude API стоили бы $${fI(usd)}. Подписка $${fI(P.plan)} в месяц — за эти ${f1(days)} дн. это $${fI(sub)}.<div class="cw m">Цены API за миллион входных токенов: Haiku $1, Sonnet $2, Opus $4, Fable $10, поэтому 1 ХТ = $1 за миллион. Считаются только чаты на этом компьютере. Цена плана — флаг --plan.</div>`;
 return `<div class="card vd roi" data-tip="${ea(tip)}"><h2>${k>=1?'Подписка окупилась':'Подписка пока не окупилась'}</h2><div class="big">×${fx(k)}</div><div class="bl">за ${f1(days)} ${days%1?'дня':pl(days,'день','дня','дней')}</div>
 <div class="sub">по ценам API <b style="color:var(--fg)">$${fI(usd)}</b><br>подписка за эти дни $${fI(sub)}</div></div>`}
/* прогноз к сбросу: средний темп с начала недели лимита, не раньше чем через 12 часов */
const fcPct=all=>{const w0=P.cal&&P.cal.week0;if(!w0||P.since!==w0||!P.now||P.now-w0<12*3600)return 0;return all/CAP[2]*100*7*86400/(P.now-w0)};
function fcLine(all){const w0=P.cal&&P.cal.week0;if(!w0||P.since!==w0||!P.now)return '';const el=P.now-w0,pct=all/CAP[2]*100;if(el<12*3600||pct<=0)return '';
 const end=w0+7*86400,f=pct*7*86400/el,wd=t=>['вс','пн','вт','ср','чт','пт','сб'][D(t).getDay()]+' '+fh(t);
 const tip=`<b>Прогноз по среднему темпу недели</b><br>С начала недели прошло ${f1(el/86400)} дн., съедено ${fp(pct)}%. Если тратить так же, к сбросу (${wd(end)}) будет ≈${fI(f)}%.<div class="cw m">Только чаты на этом компьютере: если аккаунт общий, у Claude процент может быть больше.</div>`;
 return f<100?`<div class="fc" data-tip="${ea(tip)}">в таком темпе к сбросу будет ≈<b>${fI(f)}%</b></div>`
  :`<div class="fc" data-tip="${ea(tip)}">в таком темпе лимит кончится ≈ <b>${wd(w0+el*100/pct)}</b></div>`}
/* сравнение чатов: тот же чат на каждой модели или на каждом effort. Шкала общая для всех переключателей
   (максимум по всем моделям и effort), поэтому точки ездят, а не прилипают к правому краю */
const EC=['#9FE1CB','#1D9E75','#378ADD','#7F77DD','#D85A30'];
function expHtml(){const rows=CH.map((ch,i)=>i).slice(0,14),byE=S.xm===1,wk=x=>fp(x/CAP[2]*100);
 const mx=Math.max(1e-9,...rows.map(i=>{const ch=CH[i];let m=0;for(let e=-1;e<5;e++)for(let k=-1;k<4;k++)m=Math.max(m,totals(ch,k,e).t);return m})),X=x=>(x/mx*96).toFixed(2);
 const V=rows.map(i=>({i,a:totals(CH[i],-1,-1).t,v:byE?[0,1,2,3,4].map(e=>totals(CH[i],-1,e).t):[0,1,2,3].map(m=>totals(CH[i],m,S.e).t)}));
 const ticks=[.24,.48,.72,.96].map(f=>`<i class="ax" style="left:${f*100}%"></i>`).join('');
 const nm=j=>byE?'effort '+EN[j]:'на '+NM[j]+(S.e<0?'':', effort '+EN[S.e]),col=j=>byE?EC[j]:CL[j];
 const body=V.map(r=>{const lo=Math.min(...r.v),hi=Math.max(...r.v);
  return `<div class="dpr go-chat" data-i="${r.i}"><div class="n">${esc(CH[r.i].title)}</div><div class="dtk">${ticks}<i class="rng" style="left:${X(lo)}%;width:${(X(hi)-X(lo)).toFixed(2)}%"></i>`
  +r.v.map((x,j)=>`<i class="d" style="left:${X(x)}%;--c:${col(j)}" data-tip="${ea(`<b>${esc(CH[r.i].title)} ${nm(j)}</b>${byE?' (модели как были)':''}<br>${wk(x)}% лимита за неделю · ${ddt(x/r.a)}`)}"></i>`).join('')
  +`<i class="ring" style="left:${X(r.a)}%" data-tip="${ea(`<b>${esc(CH[r.i].title)}: как было</b><br>${wk(r.a)}% лимита за неделю`)}"></i></div><div class="r" data-tip="${ea(`<b>${esc(CH[r.i].title)}</b><br>на самом деле съел ${wk(r.a)}% лимита за неделю`)}">${wk(r.a)}%</div></div>`}).join('');
 const lg=(byE?EN.map((e,j)=>`<span class="chip"><i style="--c:${EC[j]};border-radius:50%"></i>${e}</span>`):[0,1,2,3].map(m=>`<span class="chip"><i style="--c:${CL[m]};border-radius:50%"></i>${NM[m]}</span>`)).join('');
 const WH=byE?'<b>По effort.</b> Модели в каждом чате остаются как были, меняется только effort — от low до max. Цветная точка — сколько чат съел бы на этом effort, кольцо — сколько съел на самом деле.'
  :'<b>По моделям.</b> Весь чат пересчитан на одну модель: Haiku, Sonnet, Opus или Fable. Effort — тот, что выбран справа («как был» — как на самом деле). Кольцо — сколько чат съел на самом деле.';
 return `<div class="card"><div class="tph"><h2>Сравнение чатов: тот же чат ${byE?'на каждом effort':'на каждой модели'} <span class="mut" style="font-weight:400;border-bottom:1px dotted var(--faint);cursor:help" data-tip="${ea(WH+'<div class="cw m">Проценты справа и в подсказках — доля лимита за неделю, которую чат съел.</div>')}">что это?</span></h2>${seg('xm',['по моделям','по effort'],0)}${byE?'':seg('e',['effort как был'].concat(EN),-1)}</div>
 <div class="lgd" style="margin:4px 0 10px">${lg}<span class="chip"><i style="background:none;border:2px solid var(--fg);border-radius:50%"></i>как было</span><span>чем дальше точки друг от друга, тем сильнее ${byE?'effort':'модель'} меняет цену чата; справа — % лимита за неделю</span></div>
 ${body}<div class="cap">${byE?'Модели как были, меняется только effort. Видно, во что обходится max против xhigh. Шкала та же, что по моделям.':'Видно, где Fable избыточен, а где Sonnet и Opus стоят почти одинаково. Шкала одна для всех effort: точки двигаются, а не прилипают к краю.'} Нажми на чат, чтобы открыть его.</div></div>`}
let CUM=null;
/* весь аккаунт и наши чаты: верхняя линия — проценты Claude (account.jsonl), нижняя — наши чаты нарастающим итогом
   с начала недели; разрыв — другие устройства и люди. Где замеров не было — пунктир: что там было, неизвестно */
function acctHtml(){if(!P.since||!P.now)return '';const wk0=P.cal&&P.cal.week0===P.since;
 const A=(P.acct||[]).filter(q=>q[1]!=null&&q[0]>=P.since).sort((a,b)=>a[0]-b[0]);if(wk0)A.unshift([P.since,0,null]);
 if(!CUM){const ev=[];CH.forEach(ch=>{const T=totals(ch,-1,-1);ch.k.forEach((c,i)=>ev.push([c[0],T.cs[i][0]]))});ev.sort((a,b)=>a[0]-b[0]);
  CUM=[];let s=0;ev.forEach(([t,x])=>{s+=x;CUM.push([t,s/CAP[2]*100])})}const cum=CUM;
 const at=t=>{let lo=0,hi=cum.length-1,r=0;while(lo<=hi){const md=(lo+hi)>>1;if(cum[md][0]<=t){r=cum[md][1];lo=md+1}else hi=md-1}return r};
 const pts=A.filter(q=>q[2]!==null||q[0]>P.since);
 if(!pts.length)return `<div class="card"><h2>Весь аккаунт и наши чаты</h2><div class="cap" style="margin:0">Замеров Claude за эту неделю нет. Их пишет статус-строка Claude Code: <b>python limitdoctor.py --statusline</b> в настройке statusLine.</div></div>`;
 const t0=P.since,t1=P.now,Wd=1000,Hh=190,ym=Math.max(1,...A.map(q=>q[1]),at(t1))*1.15,X=t=>((t-t0)/(t1-t0)*Wd).toFixed(1),Y=v=>(8+Hh-v/ym*Hh).toFixed(1);
 const N=300;let ours='';for(let j=0;j<=N;j++){const t=t0+(t1-t0)*j/N;ours+=(j?' L':'M')+X(t)+' '+Y(at(t))}
 let line='',gap='';for(let j=1;j<A.length;j++){const seg=`M${X(A[j-1][0])} ${Y(A[j-1][1])} L${X(A[j][0])} ${Y(A[j][1])}`;if(A[j][0]-A[j-1][0]>3*3600)gap+=seg;else line+=seg}
 let days='';const d=new Date(t0*1000);d.setHours(24,0,0,0);for(let t=d/1000;t<t1;t+=86400)days+=`<line x1="${X(t)}" x2="${X(t)}" y1="8" y2="${8+Hh}" stroke="var(--bd)"/><text x="${(+X(t)+4).toFixed(1)}" y="${Hh+4}" font-size="11" fill="var(--faint)">${['вс','пн','вт','ср','чт','пт','сб'][D(t).getDay()]} ${fdd(t)}</text>`;
 const dots=A.map((q,j)=>{if(q[2]===null&&q[0]===P.since)return '';const o=at(q[0]),pr=A[j-1];
  const dl=pr?`<div class="cw">С прошлого замера (${fd(pr[0])}): весь аккаунт +${fp(q[1]-pr[1])}%, наши +${fp(o-at(pr[0]))}%${q[1]-pr[1]>0?` — наши ${fI(Math.min(100,(o-at(pr[0]))/(q[1]-pr[1])*100))}% этого расхода`:''}.</div>`:'';
  return `<circle cx="${X(q[0])}" cy="${Y(q[1])}" r="5" fill="var(--fg)" style="cursor:default" data-tip="${ea(`<b>${fd(q[0])}</b><br>Claude, весь аккаунт: <b>${fp(q[1])}%</b> лимита за неделю<br>наши чаты: <b>${fp(o)}%</b> · другие: ${fp(Math.max(0,q[1]-o))}%${dl}`)}"/>`}).join('');
 const L=pts[pts.length-1],lo=at(L[0]),sh=lo/L[1]*100;
 return `<div class="card"><h2>Весь аккаунт и наши чаты</h2>
 <div class="lead" style="font-size:14.5px">Последний замер Claude, ${fd(L[0])}: весь аккаунт съел <b>${fp(L[1])}%</b> недели, наши чаты — <b>${fp(lo)}%</b>. ${sh<=100?`Наши — <b>${fI(sh)}%</b> всего расхода аккаунта, остальное — другие устройства и люди.`:'Наших больше, чем у Claude: значит, размер лимита в настройках отчёта занижен.'}</div>
 <svg viewBox="0 0 ${Wd} ${Hh+22}" style="width:100%;height:auto;margin-top:10px;overflow:visible">${days}
 <path d="${ours} L${X(t1)} ${Y(0)} L${X(t0)} ${Y(0)} Z" fill="#7F77DD" opacity=".22"/><path d="${ours}" fill="none" stroke="#7F77DD" stroke-width="2.5"/>
 <path d="${line}" fill="none" stroke="var(--fg)" stroke-width="2.5"/><path d="${gap}" fill="none" stroke="var(--fg)" stroke-width="2" stroke-dasharray="6 6" opacity=".6"/>${dots}</svg>
 <div class="lgd" style="margin-top:6px"><span class="chip"><i style="--c:var(--fg)"></i>весь аккаунт — по Claude</span><span class="chip"><i style="--c:#7F77DD"></i>наши чаты — этот компьютер</span><span>пунктир — замеров не было, что там происходило, неизвестно; наведи на точку</span></div>
 <div class="cap">Сам отчёт у Anthropic ничего не спрашивает. Точки — проценты Claude, которые записала статус-строка терминального Claude Code (--statusline) или сняли вручную. Нет замеров — нет и верхней линии.</div></div>`}
/* сборка */
function side(){$('side').innerHTML='<div class="sh">'+LOGO+'<div>'+APP+'<span>снимок логов '+GEN+'</span></div></div>'
 +`<div class="it${S.c<0?' sel':''}" data-i="-1"><div class="t">${SYS}Вся система</div><div class="s">центральный дашборд за неделю</div></div>`
 +CH.map((ch,i)=>{const a=AG[i];return `<div class="it${i===S.c?' sel':''}" data-i="${i}"><div class="t">${esc(ch.title)}</div><div class="s">${fp(a.t/CAP[2]*100)}% за неделю · ${ch.k.length} ${pl(ch.k.length,'вызов','вызова','вызовов')}</div><div class="mx" style="width:${Math.max(4,a.t/MX*100)}%">${a.m.map((v,m)=>v>0?`<i style="width:${v/a.t*100}%;background:${CL[m]}"></i>`:'').join('')}</div></div>`}).join('')}
function draw(){document.body.classList.toggle('adm',ADMIN);if(ADMIN)side();$('view').innerHTML=S.c<0?central():chatView(CH[S.c])}
document.addEventListener('click',ev=>{const b=ev.target.closest('button[data-g]');if(b){S[b.dataset.g]=+b.dataset.v;draw();return}
 if(ev.target.closest('.masc')&&MQ.length){MCL=true;const mh=$('mh');if(mh)mh.remove();let j=MI;while(MQ.length>1&&j===MI)j=Math.floor(Math.random()*MQ.length);MI=j;const e=$('mb');e.textContent=MQ[MI].replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>');e.style.animation='none';void e.offsetWidth;e.style.animation='';return}
 const w=ev.target.closest('.wc.go');if(w){const m=+w.dataset.m;S.m=(S.m===m&&m>=0)?-1:m;draw();return}
 const it=ev.target.closest('.it,.go-chat');if(it){S.c=+it.dataset.i;S.m=-1;S.e=-1;draw();$('main').scrollTop=0}});
document.addEventListener('toggle',ev=>{const d=ev.target;if(d.classList&&d.classList.contains('hv'))S[d.dataset.k]=d.open},true);
let HL=null;
document.addEventListener('mouseover',ev=>{const e=ev.target.closest('.ev');if(HL){HL.classList.remove('hl');HL=null}
 if(e){HL=document.querySelector('.sl[data-i="'+e.dataset.i+'"]');if(HL)HL.classList.add('hl')}});
document.addEventListener('mousemove',ev=>{const t=$('tip'),sl=ev.target.closest('.sl'),dt=ev.target.closest('[data-tip]');let h=null;
 if(sl&&S.c>=0)h=tipCall(CH[S.c],+sl.dataset.i);else if(dt)h=dt.dataset.tip;
 if(!h){t.style.display='none';return}
 t.innerHTML=h;t.style.display='block';let x=ev.clientX+16,y=ev.clientY+16;
 if(x+t.offsetWidth>innerWidth-8)x=ev.clientX-t.offsetWidth-16;if(y+t.offsetHeight>innerHeight-8)y=Math.max(8,ev.clientY-t.offsetHeight-16);t.style.left=x+'px';t.style.top=y+'px'});
draw();
</script></body></html>
"""


if __name__ == "__main__":
    main()
