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
from pathlib import Path

from fastapi import FastAPI, HTTPException

import load_dataset

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "backoffice.db"


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


# Example of the shape the operational endpoints should take: the aggregation
# happens in SQL and the response carries an answer, not rows. A month of hourly
# telemetry is 720 rows per machine — it could never be handed to a model
# running on a few thousand tokens of context.
@app.get("/machines/{machine_id}/health")
def machine_health(machine_id: str, window_hours: int = 168):
    """Condensed health picture of one machine over the last `window_hours`."""
    with _db() as conn:
        _require_machine(conn, machine_id)

        # The window is anchored to the most recent snapshot of this machine,
        # not to the current time: the dataset stops on 2026-08-04, so a window
        # measured from now() would always come back empty.
        # strftime re-normalises the result, because datetime() separates date
        # and time with a space while the dataset uses "T" — comparing the two
        # formats as strings silently shifts the boundary by a day.
        window = conn.execute(
            """
            SELECT MAX(timestamp) AS window_end,
                   strftime('%Y-%m-%dT%H:%M', datetime(MAX(timestamp), ?)) AS window_start
            FROM TelemetrySnapshots WHERE machineId = ?
            """,
            (f"-{window_hours} hours", machine_id),
        ).fetchone()

        if window["window_end"] is None:
            raise HTTPException(status_code=404, detail=f"No telemetry for {machine_id}")

        bounds = (machine_id, window["window_start"])

        telemetry = conn.execute(
            """
            SELECT COUNT(*)                        AS snapshots,
                   ROUND(AVG(uptimePercentage), 1) AS avg_uptime_pct,
                   ROUND(AVG(productionRateBph))   AS avg_production_bph,
                   MAX(productionRateBph)          AS peak_production_bph,
                   MAX(temperatureC)               AS max_temperature_c,
                   ROUND(SUM(energyKwh), 1)        AS total_energy_kwh
            FROM TelemetrySnapshots
            WHERE machineId = ? AND timestamp >= ?
            """,
            bounds,
        ).fetchone()

        top_alarms = _rows(
            conn,
            """
            SELECT alarmCode, severity, COUNT(*) AS count
            FROM Alarms
            WHERE machineId = ? AND timestamp >= ?
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
            WHERE machineId = ? AND timestamp >= ?
            """,
            bounds,
        ).fetchone()

    return {
        "machine_id": machine_id,
        "window": {
            "from": window["window_start"],
            "to": window["window_end"],
            "hours": window_hours,
        },
        "telemetry": dict(telemetry),
        "alarms": {
            "total": alarm_totals["total"],
            "still_open": alarm_totals["still_open"],
            "top_codes": top_alarms,
        },
    }
