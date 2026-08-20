"""Stand-in for AROL's ERP/CRM, served out of the Q2 dataset.

Every endpoint reads the SQLite database built from the workbook by
load_dataset.py. The rules the dataset is deliberately tricky about are encoded
here, once, so that no caller has to rediscover them:

  * an order carries neither machine nor amount: both come from the lines of the
    *approved* revision of its quote
  * a quote carries no status either — the status is the one of its highest
    revision number
  * QuoteLines.price is already net of the revision's discount
  * OrderLines tracks fulfilment only, with no item, quantity or price
"""

import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query

import load_dataset

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "backoffice.db"

WindowHours = Annotated[int, Query(ge=1, le=720)]
ResultLimit = Annotated[int, Query(ge=1, le=100)]
OperationalStatus = Literal[
    "Running", "Alarm", "Idle", "Stopped", "Maintenance", "Size change"
]
AlarmSeverity = Literal["Critical", "High", "Medium", "Low"]
AlarmStatus = Literal["Open", "Acknowledged", "Resolved"]
TicketStatus = Literal["Open", "In progress", "Waiting for parts", "Resolved", "Closed"]
TicketPriority = Literal["Critical", "High", "Medium", "Low"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the SQLite database from the workbook before serving.

    The database is derived data, so it is not versioned: only the workbook is.
    Rebuilding it here means a fresh clone needs nothing but `docker compose up`,
    and dropping in a corrected workbook is picked up on the next restart.
    Loading 6k rows takes well under a second, so blocking startup is fine —
    unlike the manuals ingestion, which is minutes of embedding calls and
    therefore stays a manual step.
    """
    source = load_dataset.DEFAULT_SOURCE
    if source.is_file() and (
        not DB_PATH.is_file() or DB_PATH.stat().st_mtime < source.stat().st_mtime
    ):
        load_dataset.main(source)
    yield


app = FastAPI(
    title="AROL Mock Backoffice (stand-in for ERP/CRM)",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok"}


def _db() -> sqlite3.Connection:
    """Open a connection for the current request.

    SQLite opens in microseconds, so a connection per request costs nothing and
    keeps no shared state between them. Checked here rather than at import time
    so the service still starts when the dataset has not been loaded yet.
    """
    if not DB_PATH.is_file():
        raise HTTPException(
            status_code=503,
            detail="Dataset not loaded — run `python load_dataset.py` in mock-backoffice/",
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _require_machine(conn: sqlite3.Connection, machine_id: str) -> dict:
    machine = conn.execute(
        "SELECT machineId FROM Machines WHERE machineId = ?", (machine_id,)
    ).fetchone()
    if machine is None:
        raise HTTPException(status_code=404, detail=f"Unknown machine: {machine_id}")
    return dict(machine)


def _normalise_timestamp(value: str | None, field_name: str) -> str | None:
    """Validate an ISO timestamp and return the format used by the workbook."""
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} must be an ISO-8601 date or timestamp",
        ) from exc

    if len(value.strip()) == 10 and field_name == "to_timestamp":
        return parsed.strftime("%Y-%m-%dT23:59")
    return parsed.strftime("%Y-%m-%dT%H:%M")


def _latest_telemetry_timestamp(conn: sqlite3.Connection, machine_id: str) -> str:
    row = conn.execute(
        "SELECT MAX(timestamp) AS timestamp FROM TelemetrySnapshots WHERE machineId = ?",
        (machine_id,),
    ).fetchone()
    if row["timestamp"] is None:
        raise HTTPException(status_code=404, detail=f"No telemetry for {machine_id}")
    return row["timestamp"]


def _time_bounds(
    conn: sqlite3.Connection,
    machine_id: str,
    window_hours: int | None,
    from_timestamp: str | None,
    to_timestamp: str | None,
) -> tuple[str | None, str | None]:
    """Resolve explicit bounds or a dataset-relative rolling window.

    The synthetic stream ends on 2026-08-04. Rolling windows must therefore be
    anchored to that machine's newest snapshot rather than to wall-clock time.
    Explicit bounds take precedence and are useful for historical questions.
    """
    start = _normalise_timestamp(from_timestamp, "from_timestamp")
    end = _normalise_timestamp(to_timestamp, "to_timestamp")
    if start is not None or end is not None:
        return start, end

    if window_hours is None:
        return None, None

    latest = _latest_telemetry_timestamp(conn, machine_id)
    start_row = conn.execute(
        "SELECT strftime('%Y-%m-%dT%H:%M', datetime(?, ?)) AS timestamp",
        (latest, f"-{window_hours - 1} hours"),
    ).fetchone()
    return start_row["timestamp"], latest


def _append_time_filters(
    sql: str,
    params: list,
    start: str | None,
    end: str | None,
    column: str = "timestamp",
) -> tuple[str, list]:
    if start is not None:
        sql += f" AND {column} >= ?"
        params.append(start)
    if end is not None:
        sql += f" AND {column} <= ?"
        params.append(end)
    return sql, params


def _normalise_date(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"{field_name} must be an ISO-8601 date"
        ) from exc


#  Machine registry


@app.get("/machines")
def list_machines():
    """The fleet, with its model spelled out.

    This is also where the rest of the platform learns that machine MCH-0001 is
    documented by the manual named after serial 15610.
    """
    with _db() as conn:
        return {
            "results": _rows(
                conn,
                """
                SELECT m.machineId            AS machine_id,
                       m.serialNumber         AS serial_number,
                       m.companyId            AS company_id,
                       c.companyName          AS company_name,
                       mm.modelCode           AS model_code,
                       mm.description         AS model_description,
                       m.deliveryDate         AS delivery_date,
                       m.plantLocation        AS plant_location,
                       m.configurationProfile AS configuration_profile,
                       m.plcFamily            AS plc_family,
                       m.softwareVersion      AS software_version
                FROM Machines m
                JOIN Companies c ON c.companyId = m.companyId
                JOIN MachineModels mm ON mm.modelId = m.modelId
                ORDER BY m.machineId
                """,
            )
        }


@app.get("/machines/{machine_id}")
def get_machine(machine_id: str):
    with _db() as conn:
        _require_machine(conn, machine_id)
        results = _rows(
            conn,
            """
            SELECT m.machineId            AS machine_id,
                   m.serialNumber         AS serial_number,
                   m.companyId            AS company_id,
                   c.companyName          AS company_name,
                   mm.modelCode           AS model_code,
                   mm.description         AS model_description,
                   mm.primitiveDiameter   AS primitive_diameter,
                   mm.nominalHeads        AS nominal_heads,
                   mm.containerType       AS container_type,
                   mm.capType             AS cap_type,
                   m.deliveryDate         AS delivery_date,
                   m.plantLocation        AS plant_location,
                   m.configurationProfile AS configuration_profile,
                   m.plcFamily            AS plc_family,
                   m.softwareVersion      AS software_version
            FROM Machines m
            JOIN Companies c ON c.companyId = m.companyId
            JOIN MachineModels mm ON mm.modelId = m.modelId
            WHERE m.machineId = ?
            """,
            (machine_id,),
        )
        return results[0]


#  Commercial domain
#
#  Scoped by company, not by machine: that is how the data is actually shaped.
#  Orders and Quotes carry a companyId directly, while a machine is reachable
#  only through the lines of a quote revision — and a quote for a machine that
#  is not installed yet reaches none at all. Scoping by machine would make those
#  quotes permanently invisible; the machine is available as a filter instead.


# What "concerning this machine" means, for the optional narrowing filter.
_QUOTES_OF_MACHINE = """
    SELECT DISTINCT qr.quoteId
    FROM QuoteRevisions qr
    JOIN QuoteLines ql ON ql.quoteRevisionId = qr.quoteRevisionId
    WHERE ql.machineId = ?
"""


def _require_company(conn: sqlite3.Connection, company_id: str) -> None:
    if conn.execute(
        "SELECT 1 FROM Companies WHERE companyId = ?", (company_id,)
    ).fetchone() is None:
        raise HTTPException(status_code=404, detail=f"Unknown company: {company_id}")


@app.get("/companies/{company_id}/orders")
def company_orders(
    company_id: str,
    machine_id: str | None = None,
    order_id: str | None = None,
    status: str | None = None,
):
    with _db() as conn:
        _require_company(conn, company_id)

        sql = """
            SELECT o.orderId              AS order_id,
                   o.quoteId              AS quote_id,
                   o.orderStatus          AS status,
                   o.shipmentStatus       AS shipment_status,
                   o.orderDate            AS order_date,
                   o.expectedDeliveryDate AS expected_delivery_date,
                   o.currency             AS currency,
                   o.notes                AS notes,
                   c.companyName          AS customer_name
            FROM Orders o
            JOIN Companies c ON c.companyId = o.companyId
            WHERE o.companyId = ?
        """
        params: list = [company_id]
        if machine_id:
            sql += f" AND o.quoteId IN ({_QUOTES_OF_MACHINE})"
            params.append(machine_id)
        if order_id:
            sql += " AND o.orderId = ?"
            params.append(order_id)
        if status:
            sql += " AND o.orderStatus = ?"
            params.append(status)
        sql += " ORDER BY o.orderDate DESC"

        orders = _rows(conn, sql, tuple(params))

        for order in orders:
            lines = _rows(
                conn,
                """
                SELECT ql.description, ql.price, ql.machineId AS machine_id
                FROM QuoteRevisions qr
                JOIN QuoteLines ql ON ql.quoteRevisionId = qr.quoteRevisionId
                WHERE qr.quoteId = ? AND qr.revisionStatus = 'Approved'
                ORDER BY ql.quoteLineId
                """,
                (order["quote_id"],),
            )
            fulfillment = _rows(
                conn,
                """
                SELECT fulfillmentStatus, COUNT(*) AS count
                FROM OrderLines WHERE orderId = ? GROUP BY fulfillmentStatus
                """,
                (order["order_id"],),
            )

            order["lines"] = lines
            order["total_amount"] = round(sum(line["price"] for line in lines), 2)
            order["fulfillment"] = {r["fulfillmentStatus"]: r["count"] for r in fulfillment}

        return {"results": orders}


@app.get("/companies/{company_id}/quotes")
def company_quotes(
    company_id: str,
    machine_id: str | None = None,
    quote_id: str | None = None,
    status: str | None = None,
):
    with _db() as conn:
        _require_company(conn, company_id)

        sql = """
            SELECT q.quoteId     AS quote_id,
                   q.createdAt   AS created_at,
                   q.validUntil  AS valid_until,
                   q.currency    AS currency,
                   q.description AS description,
                   c.companyName AS customer_name,
                   (SELECT o.orderId FROM Orders o WHERE o.quoteId = q.quoteId)
                       AS linked_order_id
            FROM Quotes q
            JOIN Companies c ON c.companyId = q.companyId
            WHERE q.companyId = ?
        """
        params: list = [company_id]
        if machine_id:
            sql += f" AND q.quoteId IN ({_QUOTES_OF_MACHINE})"
            params.append(machine_id)
        if quote_id:
            sql += " AND q.quoteId = ?"
            params.append(quote_id)
        sql += " ORDER BY q.createdAt DESC"

        quotes = _rows(conn, sql, tuple(params))

        for quote in quotes:
            revisions = _rows(
                conn,
                """
                SELECT qr.revisionNumber AS revision_number,
                       qr.revisionStatus AS status,
                       qr.issuedAt       AS issued_at,
                       qr.discountRate   AS discount_rate,
                       qr.changeSummary  AS change_summary,
                       (SELECT ROUND(SUM(price), 2) FROM QuoteLines
                        WHERE quoteRevisionId = qr.quoteRevisionId) AS amount
                FROM QuoteRevisions qr
                WHERE qr.quoteId = ?
                ORDER BY qr.revisionNumber
                """,
                (quote["quote_id"],),
            )
            # The lifecycle state of a quote is the state of its latest revision;
            # everything before it has been superseded.
            latest = revisions[-1] if revisions else None
            quote["revisions"] = revisions
            quote["current_status"] = latest["status"] if latest else "Unknown"
            quote["current_amount"] = latest["amount"] if latest else None

        if status:
            quotes = [q for q in quotes if q["current_status"] == status]

        return {"results": quotes}


#  Operational domain


@app.get("/machines/{machine_id}/health")
def machine_health(machine_id: str, window_hours: WindowHours = 168):
    """Condensed health picture, anchored to the newest synthetic snapshot."""
    with _db() as conn:
        _require_machine(conn, machine_id)
        window_start, window_end = _time_bounds(
            conn, machine_id, window_hours, None, None
        )

        machine = conn.execute(
            """
            SELECT m.configurationProfile AS configuration_profile,
                   mm.modelCode AS model_code
            FROM Machines m JOIN MachineModels mm ON mm.modelId = m.modelId
            WHERE m.machineId = ?
            """,
            (machine_id,),
        ).fetchone()

        bounds = (machine_id, window_start, window_end)
        latest = conn.execute(
            """
            SELECT telemetryId AS telemetry_id, timestamp,
                   operationalStatus AS operational_status,
                   productionRateBph AS production_rate_bph,
                   uptimePercentage AS uptime_percentage,
                   alarmCount AS alarm_count, temperatureC AS temperature_c,
                   energyKwh AS energy_kwh, healthNote AS health_note
            FROM TelemetrySnapshots
            WHERE machineId = ? ORDER BY timestamp DESC LIMIT 1
            """,
            (machine_id,),
        ).fetchone()

        telemetry = conn.execute(
            """
            SELECT COUNT(*)                        AS snapshots,
                   ROUND(AVG(uptimePercentage), 1) AS avg_uptime_pct,
                   ROUND(AVG(productionRateBph))   AS avg_production_bph,
                   ROUND(AVG(CASE WHEN operationalStatus = 'Running'
                                  THEN productionRateBph END))
                                                      AS avg_running_production_bph,
                   MAX(productionRateBph)          AS peak_production_bph,
                   ROUND(AVG(temperatureC), 1)     AS avg_temperature_c,
                   MAX(temperatureC)               AS max_temperature_c,
                   ROUND(SUM(energyKwh), 1)        AS total_energy_kwh,
                   SUM(alarmCount)                 AS alarm_events
            FROM TelemetrySnapshots
            WHERE machineId = ? AND timestamp >= ? AND timestamp <= ?
            """,
            bounds,
        ).fetchone()

        status_rows = _rows(
            conn,
            """
            SELECT operationalStatus AS status, COUNT(*) AS hours
            FROM TelemetrySnapshots
            WHERE machineId = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY operationalStatus ORDER BY hours DESC, status
            """,
            bounds,
        )
        snapshots = telemetry["snapshots"]
        for row in status_rows:
            row["percentage"] = round(row["hours"] * 100 / snapshots, 1) if snapshots else 0

        top_alarms = _rows(
            conn,
            """
            SELECT alarmCode, severity, COUNT(*) AS count
            FROM Alarms
            WHERE machineId = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY alarmCode, severity
            ORDER BY count DESC, alarmCode
            LIMIT 5
            """,
            bounds,
        )

        alarm_totals = conn.execute(
            """
            SELECT COUNT(*)                                              AS total,
                   SUM(CASE WHEN alarmStatus = 'Open' THEN 1 ELSE 0 END) AS still_open
            FROM Alarms
            WHERE machineId = ? AND timestamp >= ? AND timestamp <= ?
            """,
            bounds,
        ).fetchone()

    return {
        "machine_id": machine_id,
        "machine": dict(machine),
        "window": {
            "from": window_start,
            "to": window_end,
            "hours": window_hours,
        },
        "latest": dict(latest),
        "telemetry": dict(telemetry),
        "operational_statuses": status_rows,
        "alarms": {
            "total": alarm_totals["total"],
            "still_open": alarm_totals["still_open"] or 0,
            "top_codes": top_alarms,
        },
    }


@app.get("/machines/{machine_id}/telemetry")
def search_telemetry(
    machine_id: str,
    window_hours: WindowHours | None = 24,
    from_timestamp: str | None = None,
    to_timestamp: str | None = None,
    operational_status: OperationalStatus | None = None,
    limit: ResultLimit = 24,
):
    """Search bounded telemetry rows and include aggregates for the same filter."""
    with _db() as conn:
        _require_machine(conn, machine_id)
        start, end = _time_bounds(
            conn, machine_id, window_hours, from_timestamp, to_timestamp
        )

        where = " WHERE machineId = ?"
        params: list = [machine_id]
        where, params = _append_time_filters(where, params, start, end)
        if operational_status:
            where += " AND operationalStatus = ?"
            params.append(operational_status)

        summary = conn.execute(
            f"""
            SELECT COUNT(*) AS matched_snapshots,
                   ROUND(AVG(uptimePercentage), 1) AS avg_uptime_pct,
                   ROUND(AVG(productionRateBph)) AS avg_production_bph,
                   MAX(productionRateBph) AS peak_production_bph,
                   ROUND(AVG(temperatureC), 1) AS avg_temperature_c,
                   MAX(temperatureC) AS max_temperature_c,
                   ROUND(SUM(energyKwh), 1) AS total_energy_kwh,
                   SUM(alarmCount) AS alarm_events
            FROM TelemetrySnapshots {where}
            """,
            tuple(params),
        ).fetchone()

        rows = _rows(
            conn,
            f"""
            SELECT telemetryId AS telemetry_id, timestamp,
                   operationalStatus AS operational_status,
                   productionRateBph AS production_rate_bph,
                   uptimePercentage AS uptime_percentage,
                   alarmCount AS alarm_count, temperatureC AS temperature_c,
                   energyKwh AS energy_kwh, healthNote AS health_note
            FROM TelemetrySnapshots {where}
            ORDER BY timestamp DESC LIMIT ?
            """,
            tuple([*params, limit]),
        )

    return {
        "machine_id": machine_id,
        "window": {"from": start, "to": end, "hours": window_hours},
        "filters": {"operational_status": operational_status},
        "summary": dict(summary),
        "results": rows,
    }


@app.get("/machines/{machine_id}/alarms")
def search_alarms(
    machine_id: str,
    window_hours: WindowHours | None = 168,
    from_timestamp: str | None = None,
    to_timestamp: str | None = None,
    severity: AlarmSeverity | None = None,
    alarm_status: AlarmStatus | None = Query(None, alias="status"),
    alarm_code: str | None = None,
    limit: ResultLimit = 50,
):
    """Search alarm history without ever widening beyond the requested machine."""
    with _db() as conn:
        _require_machine(conn, machine_id)
        start, end = _time_bounds(
            conn, machine_id, window_hours, from_timestamp, to_timestamp
        )

        where = " WHERE machineId = ?"
        params: list = [machine_id]
        where, params = _append_time_filters(where, params, start, end)
        if severity:
            where += " AND severity = ?"
            params.append(severity)
        if alarm_status:
            where += " AND alarmStatus = ?"
            params.append(alarm_status)
        if alarm_code:
            where += " AND alarmCode = ?"
            params.append(alarm_code.upper())

        total = conn.execute(
            f"SELECT COUNT(*) AS count FROM Alarms {where}", tuple(params)
        ).fetchone()["count"]
        by_severity = _rows(
            conn,
            f"""SELECT severity, COUNT(*) AS count FROM Alarms {where}
                GROUP BY severity ORDER BY CASE severity
                    WHEN 'Critical' THEN 1 WHEN 'High' THEN 2
                    WHEN 'Medium' THEN 3 ELSE 4 END""",
            tuple(params),
        )
        by_status = _rows(
            conn,
            f"""SELECT alarmStatus AS status, COUNT(*) AS count FROM Alarms {where}
                GROUP BY alarmStatus ORDER BY status""",
            tuple(params),
        )
        rows = _rows(
            conn,
            f"""
            SELECT alarmId AS alarm_id, timestamp, alarmCode AS alarm_code,
                   severity, alarmStatus AS status
            FROM Alarms {where} ORDER BY timestamp DESC LIMIT ?
            """,
            tuple([*params, limit]),
        )

    return {
        "machine_id": machine_id,
        "window": {"from": start, "to": end, "hours": window_hours},
        "filters": {
            "severity": severity,
            "status": alarm_status,
            "alarm_code": alarm_code,
        },
        "summary": {
            "matched_alarms": total,
            "by_severity": by_severity,
            "by_status": by_status,
        },
        "results": rows,
    }


@app.get("/machines/{machine_id}/maintenance-tickets")
def search_maintenance_tickets(
    machine_id: str,
    from_date: str | None = None,
    to_date: str | None = None,
    ticket_status: TicketStatus | None = Query(None, alias="status"),
    priority: TicketPriority | None = None,
    alarm_id: str | None = None,
    limit: ResultLimit = 50,
):
    """Search operational service records, including tickets without an alarm."""
    with _db() as conn:
        _require_machine(conn, machine_id)
        start = _normalise_date(from_date, "from_date")
        end = _normalise_date(to_date, "to_date")

        where = " WHERE machineId = ?"
        params: list = [machine_id]
        if start:
            where += " AND createdDate >= ?"
            params.append(start)
        if end:
            where += " AND createdDate <= ?"
            params.append(end)
        if ticket_status:
            where += " AND ticketStatus = ?"
            params.append(ticket_status)
        if priority:
            where += " AND priority = ?"
            params.append(priority)
        if alarm_id:
            where += " AND alarmId = ?"
            params.append(alarm_id.upper())

        total = conn.execute(
            f"SELECT COUNT(*) AS count FROM MaintenanceTickets {where}", tuple(params)
        ).fetchone()["count"]
        rows = _rows(
            conn,
            f"""
            SELECT ticketId AS ticket_id, alarmId AS alarm_id,
                   ticketType AS ticket_type, ticketStatus AS status,
                   priority, createdDate AS created_date, ownerRole AS owner_role
            FROM MaintenanceTickets {where}
            ORDER BY createdDate DESC, ticketId DESC LIMIT ?
            """,
            tuple([*params, limit]),
        )

    return {
        "machine_id": machine_id,
        "filters": {
            "from_date": start,
            "to_date": end,
            "status": ticket_status,
            "priority": priority,
            "alarm_id": alarm_id,
        },
        "summary": {"matched_tickets": total},
        "results": rows,
    }
