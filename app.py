import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, g, redirect, render_template, request, url_for

CATEGORIES = ("Hardware", "Software", "Network")
PRIORITIES = ("Critical", "High", "Medium", "Low")
STATUSES = ("Open", "In progress", "Resolved")
TRANSITIONS = {
    "Open": ("Open", "In progress", "Resolved"),
    "In progress": ("In progress", "Open", "Resolved"),
    "Resolved": ("Resolved", "Open"),
}
# Tickets added by `flask seed-demo` so the dashboard isn't empty on first run
SAMPLES = (
    ("Wi-Fi outage in training room",
     "Several laptops lost connectivity on the training room access point.",
     "Network", "High", "Open"),
    ("Reception printer will not print",
     "Jobs queue without printing. The panel shows a paper jam.",
     "Hardware", "Medium", "In progress"),
    ("Employee account locked out",
     "The user cannot sign in after repeated password attempts.",
     "Software", "Medium", "Open"),
)


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_app(test_config=None):
    app = Flask(__name__)
    default_db = Path(app.instance_path) / "helpdesk.sqlite"
    app.config.from_mapping(DATABASE=os.environ.get("HELPDESK_DATABASE", default_db))
    if test_config:
        app.config.update(test_config)

    def database():
        # one connection per request, stored on flask's g
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    @app.teardown_appcontext
    def close_database(_error):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.cli.command("init-db")
    def init_db():
        """Create the database tables."""
        Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
        database().executescript("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY,
                ticket_id INTEGER NOT NULL REFERENCES tickets(id),
                event TEXT NOT NULL,
                note TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS lab_metadata (key TEXT PRIMARY KEY);
        """)
        print("Database ready.")

    def get_history(db, ticket_id):
        return db.execute("SELECT * FROM history WHERE ticket_id = ? ORDER BY id DESC",
                          (ticket_id,)).fetchall()

    def log_event(db, ticket_id, event, note, when):
        db.execute("INSERT INTO history (ticket_id, event, note, created_at) VALUES (?, ?, ?, ?)",
                   (ticket_id, event, note, when))

    def insert_ticket(db, title, description, category, priority, status="Open"):
        now = timestamp()
        cursor = db.execute("""
            INSERT INTO tickets (title, description, category, priority, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, description, category, priority, status, now, now))
        log_event(db, cursor.lastrowid, "Ticket opened", "", now)
        if status != "Open":
            log_event(db, cursor.lastrowid, f"Open → {status}", "Initial triage in sample incident.", now)
        return cursor.lastrowid

    @app.cli.command("seed-demo")
    def seed_demo():
        """Insert three sample tickets once."""
        db = database()
        with db:
            inserted = db.execute("INSERT OR IGNORE INTO lab_metadata VALUES ('demo_seeded')")
            if inserted.rowcount:
                for ticket in SAMPLES:
                    insert_ticket(db, *ticket)
        print("Demo tickets loaded." if inserted.rowcount else "Demo tickets already loaded.")

    @app.context_processor
    def choices():
        return dict(categories=CATEGORIES, priorities=PRIORITIES, statuses=STATUSES)

    @app.get("/")
    def dashboard():
        category = request.args.get("category", "")
        priority = request.args.get("priority", "")
        status = request.args.get("status", "")
        filters = {"category": category, "priority": priority, "status": status}

        db = database()
        # only count tickets that still need work
        grouped = db.execute("""
            SELECT category, priority, COUNT(*) AS total
            FROM tickets WHERE status != 'Resolved'
            GROUP BY category, priority
        """).fetchall()
        counts = {(row["category"], row["priority"]): row["total"] for row in grouped}
        # an empty filter value means "match everything"
        tickets = db.execute("""
            SELECT * FROM tickets
            WHERE (? = '' OR category = ?) AND (? = '' OR priority = ?) AND (? = '' OR status = ?)
            ORDER BY id DESC
        """, (category, category, priority, priority, status, status)).fetchall()
        category_totals = {category: sum(counts.get((category, priority), 0)
                                         for priority in PRIORITIES) for category in CATEGORIES}
        return render_template("dashboard.html", counts=counts, tickets=tickets,
                               category_totals=category_totals,
                               filters=filters, active=sum(counts.values()))

    @app.route("/tickets/new", methods=["GET", "POST"])
    def new_ticket():
        form = request.form
        if request.method == "POST":
            title = form.get("title", "").strip()
            description = form.get("description", "").strip()
            category = form.get("category")
            priority = form.get("priority")
            if not (0 < len(title) <= 120 and 0 < len(description) <= 3000
                    and category in CATEGORIES and priority in PRIORITIES):
                error = "Enter a title, description, category, and priority within the field limits."
                return render_template("new.html", form=form, error=error), 400
            db = database()
            with db:
                ticket_id = insert_ticket(db, title, description, category, priority)
            return redirect(url_for("ticket_detail", ticket_id=ticket_id), code=303)
        return render_template("new.html", form=form)

    @app.get("/tickets/<int:ticket_id>")
    def ticket_detail(ticket_id):
        db = database()
        ticket = db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            abort(404)
        return render_template("ticket.html", ticket=ticket, history=get_history(db, ticket_id),
                               next_statuses=TRANSITIONS[ticket["status"]])

    @app.post("/tickets/<int:ticket_id>")
    def update_ticket(ticket_id):
        priority = request.form.get("priority")
        status = request.form.get("status")
        note = request.form.get("note", "").strip()
        db = database()
        with db:
            db.execute("BEGIN IMMEDIATE")  # lock so two edits can't overwrite each other
            ticket = db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            if ticket is None:
                abort(404)
            if (priority not in PRIORITIES or status not in TRANSITIONS[ticket["status"]]
                    or len(note) > 2000 or (status == "Resolved" and ticket["status"] != status and not note)):
                error = "Choose a valid status and priority. Add a resolution note when resolving a ticket."
                return render_template("ticket.html", ticket=ticket, history=get_history(db, ticket_id),
                                       note=note, next_statuses=TRANSITIONS[ticket["status"]],
                                       error=error), 400

            # build a readable list of what actually changed for the history log
            changes = [f"{field.title()} · {ticket[field]} → {value}"
                       for field, value in (("priority", priority), ("status", status))
                       if value != ticket[field]]
            if changes or note:
                now = timestamp()
                db.execute("UPDATE tickets SET priority = ?, status = ?, updated_at = ? WHERE id = ?",
                           (priority, status, now, ticket_id))
                log_event(db, ticket_id, " / ".join(changes) or "Note added", note, now)
        return redirect(url_for("ticket_detail", ticket_id=ticket_id), code=303)

    return app
