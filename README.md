# IT Help Desk Ticketing Lab

A Flask and SQLite lab for logging, prioritizing, filtering, and resolving IT incidents.

## Run locally

Use Python 3.11 or newer. Run these commands from the project root.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell, use `py -m venv .venv` and `.venv\Scripts\Activate.ps1`.

```sh
python -m flask --app app init-db
python -m flask --app app seed-demo
python -m flask --app app run --host 127.0.0.1
```

Open http://127.0.0.1:5000. The optional seed command adds a Wi-Fi outage, a reception printer failure, and an account lockout. You can repeat the command safely.

- Use **New ticket** to log an issue with its category and priority.
- Open a ticket to change priority, move it through triage and resolution, or reopen it. Add a note when resolving a ticket. The activity timeline records updates.
- The dashboard counts both Open and In progress tickets in its active totals. The queue can be filtered by category, priority, and status.
- Tickets are stored in `instance/helpdesk.sqlite` by default. The Flask app is a loopback lab with no sign-in.
