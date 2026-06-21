import os, csv, io, re, hashlib, time, random, threading
from datetime import datetime, date, timedelta
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, make_response, send_file)
from data import load_user, save_user, delete_user, reset_user, list_users

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "resflecto-secret-dev-key-change-me")

HEARTBEAT_INTERVAL = 30
heartbeat_lock = threading.Lock()

def heartbeat_worker():
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        with heartbeat_lock:
            print(f" Reflecto server alive at {datetime.now().strftime('%H:%M:%S')}")

threading.Thread(target=heartbeat_worker, daemon=True).start()


THEMES = {
    "light": "☀️ Light",      "dark": "🌑 Dark",
    "brown": "🍂 Brown",      "brown-dark": "🌰 Brown Dark",
    "blue": "🌊 Blue",        "blue-dark": "🌌 Blue Dark",
    "green": "🌿 Green",      "green-dark": "🌲 Green Dark",
    "purple": "💜 Purple",    "purple-dark": "🌙 Purple Dark",
    "pink": "🌸 Pink",        "pink-dark": "🌷 Pink Dark",
}

MOODS = [
    "😄 Happy", "😊 Calm", "😐 Okay", "😔 Sad", "😤 Stressed",
    "😴 Tired", "🤩 Excited", "🥰 Grateful", "😰 Anxious", "😡 Angry",
    "🥱 Bored", "🤒 Unwell", "💪 Motivated", "🤗 Loved", "😶 Numb", "🌈 Hopeful",
]

PAGES = {
    "mood":    "🌤 Mood Board",
    "journal": "✍️ Journal",
    "notes":   "📚 Study Notes",
    "tasks":   "✅ Tasks",
    "timer":   "⏱ Timer & Alarm",
    "contact": "🐾 Contact",
    "about":   "💡 About",
}

TASK_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

TOAST_MESSAGES = {
    "mood":    ("Mood logged! 🎉",                 "success"),
    "quick":   ("Saved to Journal! ✍️",            "success"),
    "saved":   ("Saved successfully ✓",            "success"),
    "deleted": ("Deleted.",                         ""),
    "added":   ("Task added! ✅",                  "success"),
    "cleared": ("Cleared completed tasks.",         ""),
    "reset":   ("All data reset. Fresh start! 🐾", "success"),
}



def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def new_id():
    return str(int(time.time())) + str(random.randint(100, 999))


def fmt_date(dt):
    return f"{dt.month}/{dt.day}/{dt.year}"


def today():
    return fmt_date(date.today())



def is_overdue(due):
    if not due:
        return False
    try:
        return datetime.strptime(due, "%Y-%m-%d").date() < date.today()
    except ValueError:
        return False


def parse_date(s):
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def mood_streak(moods):
    if not moods:
        return 0
    dates = sorted(
        {d for m in moods if (d := parse_date(m.get("date", "")))},
        reverse=True,
    )
    streak, check = 0, date.today()
    for d in dates:
        if d == check:
            streak += 1
            check = d - timedelta(days=1)
        else:
            break
    return streak



def dashboard_stats(data):
    today_mood = next(
        (m["mood"] for m in data.get("moods", []) if m.get("date") == today()), ""
    )
    pending_count = sum(1 for t in data.get("tasks", []) if not t.get("done"))
    return {
        "journal": len(data.get("journal", [])),
        "notes":   len(data.get("notes", [])),
        "tasks":   len(data.get("tasks", [])),
        "pending": pending_count,
        "mood":    today_mood.split(" ")[0] if today_mood else "—",
    }


def find_by_id(collection, item_id):
    return next((item for item in collection if str(item["id"]) == str(item_id)), None)


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("index"))
        user = session["user"]
        data = load_user(user)
        return f(user, data, *args, **kwargs)
    return wrapper



@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    theme = request.cookies.get("reflecto_theme", "light")
    if theme not in THEMES:
        theme = "light"
    return render_template("index.html",
        users=list_users(),
        err=request.args.get("err", ""),
        ok=request.args.get("ok", ""),
        theme=theme,
    )


@app.route("/login", methods=["POST"])
def login():
    name = request.form.get("name", "").strip()
    pw   = request.form.get("password", "").strip()
    if not name:
        return redirect(url_for("index", err="noname"))
    if not pw:
        return redirect(url_for("index", err="nopass"))

    data   = load_user(name)
    stored = data.get("password", "")
    if stored:
        if stored != hash_password(pw):
            return redirect(url_for("index", err="wrongpass"))
    else:
        data["password"] = hash_password(pw)


    session["user"]   = name
    data["lastLogin"] = datetime.now().isoformat()
    save_user(name, data)

    resp = make_response(redirect(url_for("dashboard")))
    resp.set_cookie("reflecto_theme", data.get("theme", "light"), max_age=31_536_000)
    return resp


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/delete_user", methods=["POST"])
def delete_user_route():
    name = request.form.get("name", "").strip()
    if name:
        delete_user(name)
    return redirect(url_for("index", ok="deleted"))



@app.route("/app")
@login_required
def dashboard(user, data):
    page = request.args.get("page", "mood")
    if page not in PAGES:
        page = "mood"


    nsearch = request.args.get("ns", "").strip()
    ncat    = request.args.get("ncat", "")
    all_notes = sorted(data.get("notes", []), key=lambda n: not n.get("pinned", False))
    filtered_notes = [
        n for n in all_notes
        if (not nsearch or nsearch.lower() in n.get("title", "").lower()
                        or nsearch.lower() in n.get("body", "").lower())
        and (not ncat or n.get("cat", "") == ncat)
    ]
    
    
    note_cats = list({n.get("cat", "General") for n in data.get("notes", [])})

    all_tasks = data.get("tasks", [])
    pending   = [t for t in all_tasks if not t.get("done")]
    done      = [t for t in all_tasks if t.get("done")]
    pending.sort(key=lambda t: (
        not is_overdue(t.get("due", "")),
        TASK_PRIORITY_ORDER.get(t.get("priority", "medium"), 1),
    ))
    total = len(pending) + len(done)
    pct   = round(len(done) / total * 100) if total else 0

    jid       = request.args.get("jid", "")
    cur_entry = find_by_id(data.get("journal", []), jid) if jid else None

    return render_template("app.html",
        user=user, data=data, page=page, pages=PAGES, themes=THEMES,
        theme=data.get("theme", "light"),
        st=dashboard_stats(data),
        ok=request.args.get("ok", ""),
        jid=jid, cur_entry=cur_entry,
        filtered_notes=filtered_notes, note_cats=note_cats,
        nsearch=nsearch, ncat=ncat,
        pending=pending, done=done, pct=pct,
        mood_streak=mood_streak(data.get("moods", [])),
        today_mood=next(
            (m["mood"] for m in data.get("moods", []) if m.get("date") == today()), ""
        ),
        moods=MOODS, toasts=TOAST_MESSAGES,
        is_overdue=is_overdue, today=today(),
    )



@app.route("/theme", methods=["POST"])
@login_required
def set_theme(user, data):
    theme = request.form.get("theme", "light")
    data["theme"] = theme
    save_user(user, data)
    resp = make_response(redirect(url_for("dashboard", page=request.form.get("page", "mood"))))
    resp.set_cookie("reflecto_theme", theme, max_age=31_536_000)
    return resp


@app.route("/reset_data", methods=["POST"])
@login_required
def reset_data(user, data):
    reset_user(user)
    return redirect(url_for("dashboard", page="mood", ok="reset"))



@app.route("/mood", methods=["POST"])
@login_required
def mood_log(user, data):
    mood = request.form.get("mood", "").strip()
    if mood:
        entry = {
            "mood": mood,
            "date": request.form.get("client_date", "").strip() or today(),
            "time": request.form.get("client_time", "").strip()
                    or datetime.now().strftime("%I:%M %p").lstrip("0"),
        }
        data.setdefault("moods", []).insert(0, entry)
        data["moods"] = data["moods"][:90]
        save_user(user, data)
    return redirect(url_for("dashboard", page="mood", ok="mood"))


@app.route("/mood_del", methods=["POST"])
@login_required
def mood_del(user, data):
    idx = int(request.form.get("idx", -1))
    if 0 <= idx < len(data.get("moods", [])):
        data["moods"].pop(idx)
        save_user(user, data)
    return redirect(url_for("dashboard", page="mood"))



@app.route("/quick", methods=["POST"])
@login_required
def quick_thought(user, data):
    body = request.form.get("body", "").strip()
    if body:
        entry = {"id": new_id(), "title": "Quick Thought", "body": body, "date": today(), "tags": []}
        data.setdefault("journal", []).insert(0, entry)
        save_user(user, data)
    return redirect(url_for("dashboard", page="mood", ok="quick"))


@app.route("/journal_save", methods=["POST"])
@login_required
def journal_save(user, data):
    jid   = request.form.get("id", "")
    title = request.form.get("title", "").strip() or "Untitled"
    body  = request.form.get("body", "").strip()
    tags  = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
    if body:
        data.setdefault("journal", [])
        if jid:
            entry = find_by_id(data["journal"], jid)
            if entry:
                entry.update({"title": title, "body": body, "tags": tags, "edited": today()})
        else:
            jid = new_id()
            data["journal"].insert(0, {"id": jid, "title": title, "body": body, "date": today(), "tags": tags})
        save_user(user, data)
    return redirect(url_for("dashboard", page="journal", jid=jid, ok="saved"))


@app.route("/journal_del", methods=["POST"])
@login_required
def journal_del(user, data):
    jid = request.form.get("id", "")
    data["journal"] = [e for e in data.get("journal", []) if str(e["id"]) != str(jid)]
    save_user(user, data)
    return redirect(url_for("dashboard", page="journal", ok="deleted"))



@app.route("/note_save", methods=["POST"])
@login_required
def note_save(user, data):
    nid   = request.form.get("id", "")
    title = request.form.get("title", "").strip() or "Untitled"
    body  = request.form.get("body", "").strip()
    cat   = request.form.get("cat", "General")
    if body:
        data.setdefault("notes", [])
        if nid:
            note = find_by_id(data["notes"], nid)
            if note:
                note.update({"title": title, "body": body, "cat": cat, "edited": today()})
        else:
            nid = new_id()
            data["notes"].insert(0, {"id": nid, "title": title, "body": body,
                                     "cat": cat, "date": today(), "pinned": False})
        save_user(user, data)
    return redirect(url_for("dashboard", page="notes", nid=nid, ok="saved"))


@app.route("/note_del", methods=["POST"])
@login_required
def note_del(user, data):
    nid = request.form.get("id", "")
    data["notes"] = [n for n in data.get("notes", []) if str(n["id"]) != str(nid)]
    save_user(user, data)
    return redirect(url_for("dashboard", page="notes", ok="deleted"))


@app.route("/note_pin", methods=["POST"])
@login_required
def note_pin(user, data):
    nid  = request.form.get("id", "")
    note = find_by_id(data.get("notes", []), nid)
    if note:
        note["pinned"] = not bool(note.get("pinned", False))
    save_user(user, data)
    return redirect(url_for("dashboard", page="notes"))


@app.route("/note_csv/<nid>")
@login_required
def note_csv(user, data, nid):
    note = find_by_id(data.get("notes", []), nid)
    if not note:
        return redirect(url_for("dashboard", page="notes"))
    buf = io.StringIO()
    csv.writer(buf).writerows([
        ["Title", "Category", "Date", "Body"],
        [note.get("title", ""), note.get("cat", ""), note.get("date", ""), note.get("body", "")],
    ])
    fname = re.sub(r"[^a-z0-9]", "_", note.get("title", "note").lower()) + ".csv"
    return send_file(io.BytesIO(buf.getvalue().encode()),
                     mimetype="text/csv", as_attachment=True, download_name=fname)



@app.route("/export_pdf")
@login_required
def export_pdf(user, data):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib import colors

    buf  = io.BytesIO()
    doc    = SimpleDocTemplate(buf, pagesize=A4,
                               leftMargin=2*cm, rightMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    h1     = ParagraphStyle("H1", parent=styles["Title"],    fontSize=20, spaceAfter=6)
    h2     = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, spaceAfter=4)
    muted  = ParagraphStyle("Mu", parent=styles["BodyText"],
                             textColor=colors.HexColor("#888888"), fontSize=9)
    body   = styles["BodyText"]
    hr     = lambda: HRFlowable(width="100%", color=colors.HexColor("#cccccc"))

    story = [
        Paragraph(f"Reflecto — {user}", h1),
        Paragraph(f"Exported {datetime.now().strftime('%b %d, %Y %I:%M %p')}", muted),
        Spacer(1, .4*cm), hr(), Spacer(1, .3*cm),
    ]

    if data.get("journal"):
        story.append(Paragraph("Journal", h2))
        for e in data["journal"]:
            story += [
                Paragraph(f"<b>{e.get('title','')}</b> — {e.get('date','')}", body),
                Paragraph(e.get("body", "").replace("\n", "<br/>"), body),
                Spacer(1, .2*cm),
            ]

    if data.get("notes"):
        story += [hr(), Paragraph("Study Notes", h2)]
        for n in data["notes"]:
            story += [
                Paragraph(f"<b>{n.get('title','')}</b> [{n.get('cat','')}] — {n.get('date','')}", body),
                Paragraph(n.get("body", "").replace("\n", "<br/>"), body),
                Spacer(1, .2*cm),
            ]

    if data.get("tasks"):
        story += [hr(), Paragraph("Tasks", h2)]
        for t in data["tasks"]:
            status = "✓" if t.get("done") else "○"
            story.append(Paragraph(
                f"{status} <b>{t.get('title','')}</b> [{t.get('priority','medium')}] Due: {t.get('due','—')}",
                body,
            ))

    if data.get("moods"):
        story += [Spacer(1, .2*cm), hr(), Paragraph("Mood Log", h2)]
        for m in data["moods"][:30]:
            story.append(Paragraph(f"{m.get('date','')} {m.get('time','')} — {m.get('mood','')}", body))

    doc.build(story)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=True, download_name=f"reflecto_{user}.pdf")


@app.route("/task_add", methods=["POST"])
@login_required
def task_add(user, data):
    title    = request.form.get("title", "").strip()
    due      = request.form.get("due", "").strip()
    priority = request.form.get("priority", "medium")
    if priority not in ("high", "medium", "low"):
        priority = "medium"
    if title:
        task = {"id": new_id(), "title": title, "due": due, "done": False, "priority": priority}
        data.setdefault("tasks", []).insert(0, task)
        save_user(user, data)
    return redirect(url_for("dashboard", page="tasks", ok="added"))


@app.route("/task_toggle", methods=["POST"])
@login_required
def task_toggle(user, data):
    tid  = request.form.get("id", "")
    task = find_by_id(data.get("tasks", []), tid)
    if task:
        now_done = not bool(task.get("done", False))
        task["done"] = now_done
        if now_done:
            task["done_late"] = bool(task.get("due") and is_overdue(task["due"]))
            task["done_date"] = today()
        else:
            task["done_late"] = False
            task.pop("done_date", None)
    save_user(user, data)
    return redirect(url_for("dashboard", page="tasks"))


@app.route("/task_del", methods=["POST"])
@login_required
def task_del(user, data):
    tid = request.form.get("id", "")
    data["tasks"] = [t for t in data.get("tasks", []) if str(t["id"]) != str(tid)]
    save_user(user, data)
    return redirect(url_for("dashboard", page="tasks"))


@app.route("/task_clear", methods=["POST"])
@login_required
def task_clear(user, data):
    data["tasks"] = [t for t in data.get("tasks", []) if not t.get("done")]
    save_user(user, data)
    return redirect(url_for("dashboard", page="tasks", ok="cleared"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
