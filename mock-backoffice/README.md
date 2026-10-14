# Mock Backoffice

Stands in for AROL's real ERP/CRM. It serves the Q2 synthetic dataset over HTTP: companies, machines, quotes with their revisions, orders, telemetry, alarms and maintenance tickets. Only the agents call it; the backend never reaches it directly.

## Data

The source is the workbook `dataset/AROL_Q2_synthetic_fleet_dataset.xlsx` (versioned). At startup the service loads it into `data/backoffice.db` (SQLite, not versioned) if the DB is missing or older than the workbook. Loading takes less than a second, so there is nothing to run by hand.

- **Updated dataset:** replace the workbook and restart the service. The newer file date is enough to trigger a reload.
- **Force a rebuild:** delete `data/backoffice.db` and restart, or run `python load_dataset.py`.

If the workbook is missing, the service still starts (so it doesn't block the stack) but answers `503 Dataset not loaded`.

## Endpoints

| Endpoint | Returns |
|---|---|
| `GET /health` | `{"status": "ok"}` |
| `GET /machines` | The fleet, with serial, model and owner company |
| `GET /machines/{machine_id}` | Machine details, as-built configuration and model specs |
| `GET /machines/{machine_id}/health` | Operational summary over a window: last snapshot, uptime, production, state distribution, top alarms |
| `GET /machines/{machine_id}/telemetry` | Hourly snapshots; filters `window_hours`, `from_timestamp`, `to_timestamp`, `operational_status`, `limit` |
| `GET /machines/{machine_id}/alarms` | Alarm events and counts; filters `window_hours`, `from_timestamp`, `to_timestamp`, `severity`, `status`, `alarm_code`, `limit` |
| `GET /machines/{machine_id}/maintenance-tickets` | Maintenance tickets; filters `from_date`, `to_date`, `status`, `priority`, `alarm_id`, `limit` |
| `GET /companies/{company_id}/orders` | Orders with their lines; filters `machine_id`, `order_id`, `status` |
| `GET /companies/{company_id}/quotes` | Quotes with revision history; filters `machine_id`, `quote_id`, `status` |

Interactive docs: `http://localhost:8003/docs`.

Notes:

- **Time windows** end at the machine's last snapshot, not at `now()`, because the dataset ends on 4 August 2026. `window_hours` is at most 720 (one month).
- **Limits** keep the responses small enough for the LLM context.
- **Commercial data is scoped by company**, not by machine. An order reaches a machine only through the lines of a quote revision, and a quote for a machine not yet installed has no machine at all. `machine_id` only narrows the result.
- **No authentication:** access control (company and visibility) is enforced by the backend before any agent is called. This service must therefore be reachable only by the agents (see the Notes in [backend/README.md](../backend/README.md)).

## Running

With Docker it starts with the rest of the stack (`docker compose up -d` from the repo root).

Locally:

```bash
cd mock-backoffice
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8003
```

Check that it answers:

```bash
curl http://localhost:8003/machines
```

It should list the 8 machines of the fleet.

## Tests

```bash
docker compose exec mock-backoffice python -m unittest discover -s tests
```
