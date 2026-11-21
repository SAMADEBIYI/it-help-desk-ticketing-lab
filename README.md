# IT Help Desk Ticketing Lab

Small help desk app I built with Flask and SQLite to practice the ticket workflow I see in IT support: log an issue, set a priority, work it, resolve it.

## What it does

- Log tickets with a category (Hardware, Software, Network) and priority
- Move a ticket through Open, In progress and Resolved, or reopen it
- Require a note when resolving, and keep a history of every change
- Dashboard with active counts by category and priority, plus filters on the queue

## Run it

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

flask --app app init-db
flask --app app seed-demo   # optional, adds 3 sample tickets
flask --app app run
```

Then open http://127.0.0.1:5000. On Windows, activate with `.venv\Scripts\Activate.ps1`.

Tickets are saved in `instance/helpdesk.sqlite`. There is no login, so keep it on localhost.

## Stack

Python, Flask, SQLite (plain SQL, no ORM), Jinja templates, CSS
