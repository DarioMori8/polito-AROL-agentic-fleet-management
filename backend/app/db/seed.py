import logging
import re
from pathlib import Path
from app.config import settings

from sqlmodel import select

from app.db.engine import _async_session_factory
from app.db.models import (
    Company,
    Machine,
    MachineModel,
    Manual,
    PlcFamily,
    User,
    Visibility,
)

logger = logging.getLogger(__name__)

# Where the manual PDFs live. Move this to settings when the backend starts
# owning document storage for real (upload endpoint instead of a folder).
MANUALS_DIR = settings.MANUALS_DIR
DOMAIN_DB_PATH= settings.DOMAIN_DB_PATH


# The dataset convention: manuals/<serialNumber>_manual_<LANG>.pdf
# The serial number is the only thing a PDF knows about its machine, which is
# why it is the RESOLUTION key here, while machine_id is the resting link.
#
# The serial part is deliberately NOT \d+: real serials come in two shapes,
# numeric (17478) and alphanumeric (A2055). A digits-only pattern would drop
# half the fleet silently.
MANUAL_FILENAME_RE = re.compile(r"^(?P<serial>.+?)_manual_(?P<lang>[A-Za-z]{2})\.pdf$")


# Reference data


def _fixture_companies() -> list[Company]:
    return [
        Company(id="CMP-001", name="Fonte Alpina S.p.A.", country="Italy",
                city="Bergamo", sector="Beverage", currency="EUR", locale="it-IT"),
        Company(id="CMP-002", name="Iberia Zumos S.L.", country="Spain",
                city="Valencia", sector="Food", currency="EUR", locale="es-ES"),
        Company(id="CMP-003", name="NordPharma AB", country="Sweden",
                city="Uppsala", sector="Pharmaceutical", currency="SEK",
                locale="sv-SE"),
    ]


def _fixture_users() -> list[User]:
    # One user per visibility level, so the access model can actually be
    # exercised end to end instead of being tested with a single scope.
    return [
        User(id="USR-001", company_id="CMP-001", first_name="Giulia",
             last_name="Rossi", email="g.rossi@fontealpina.it",
             job_title="Plant Maintenance Manager", visibility=Visibility.FULL),
        User(id="USR-002", company_id="CMP-001", first_name="Marco",
             last_name="Bianchi", email="m.bianchi@fontealpina.it",
             job_title="Maintenance Man", visibility=Visibility.TECHNICIAN),
        User(id="USR-003", company_id="CMP-002", first_name="Elena",
             last_name="Navarro", email="e.navarro@iberiazumos.es",
             job_title="Procurement Specialist", visibility=Visibility.COMMERCIAL),
        User(id="USR-004", company_id="CMP-003", first_name="Anders",
             last_name="Lindqvist", email="a.lindqvist@nordpharma.se",
             job_title="Line Operator", visibility=Visibility.TECHNICIAN),
    ]


def _fixture_machine_models() -> list[MachineModel]:
    return [
        MachineModel(id="MDL-100", model_code="EURO PK",
                     description="Rotary capper for pre-threaded plastic caps",
                     primitive_diameter=280, nominal_heads=12,
                     container_type="PET bottle", cap_type="Plastic screw cap",
                     industry_segment="Water", notes="Standard carousel layout"),
        MachineModel(id="MDL-101", model_code="EQUATORQUE",
                     description="Capper with magnetic torque control heads",
                     primitive_diameter=360, nominal_heads=16,
                     container_type="Glass bottle", cap_type="Aluminium ROPP",
                     industry_segment="Beverage", notes="Magnetic head assembly"),
        MachineModel(id="MDL-102", model_code="EURO VP",
                     description="Vacuum capper for food containers",
                     primitive_diameter=None, nominal_heads=8,
                     container_type="Glass jar", cap_type="Twist-off",
                     industry_segment="Food", notes="Vacuum chamber option"),
    ]


def _fixture_machines() -> list[Machine]:
    """
    The eight serial numbers below are REAL: they are the ones carried by the
    PDFs in manuals/. Everything else on each row (machine id, owning company,
    model, dates, configuration) is placeholder, with one exception: the README
    states that MCH-0004 is serial 17478, so that pairing is authoritative.

    """
    return [
        Machine(id="MCH-0001", company_id="CMP-001", model_id="MDL-100",
                serial_number="15610", delivery_date="2016-06-14",
                plant_location="Bergamo Plant - Line 1",
                configuration_profile="24000 bph, 400V, 12 heads",
                plc_family=PlcFamily.SIEMENS_SIMATIC_S7,
                software_version="S7-1500 v2.9"),
        Machine(id="MCH-0002", company_id="CMP-001", model_id="MDL-100",
                serial_number="17203", delivery_date="2018-05-21",
                plant_location="Bergamo Plant - Line 2",
                configuration_profile="24000 bph, 400V, 12 heads",
                plc_family=PlcFamily.LINE_PLC_INTEGRATED,
                software_version="n/a"),
        Machine(id="MCH-0003", company_id="CMP-001", model_id="MDL-102",
                serial_number="17579", delivery_date="2019-03-02",
                plant_location="Bergamo Plant - Line 3",
                configuration_profile="9000 jph, 230V, 8 heads",
                plc_family=PlcFamily.HARDWIRED_CONTROL_PANEL,
                software_version="n/a"),
        Machine(id="MCH-0004", company_id="CMP-002", model_id="MDL-100",
                serial_number="17478", delivery_date="2020-07-30",
                plant_location="Valencia Plant - Line A",
                configuration_profile="22000 bph, 400V, 12 heads",
                plc_family=PlcFamily.LINE_PLC_INTEGRATED,
                software_version="n/a"),
        Machine(id="MCH-0005", company_id="CMP-002", model_id="MDL-101",
                serial_number="A2055", delivery_date="2021-02-11",
                plant_location="Valencia Plant - Line B",
                configuration_profile="18000 bph, 400V, 16 magnetic heads",
                plc_family=PlcFamily.LINE_PLC_INTEGRATED,
                software_version="n/a"),
        Machine(id="MCH-0006", company_id="CMP-002", model_id="MDL-101",
                serial_number="A2064", delivery_date="2021-09-17",
                plant_location="Valencia Plant - Line C",
                configuration_profile="18000 bph, 400V, 16 magnetic heads",
                plc_family=PlcFamily.SIEMENS_SIMATIC_S7,
                software_version="n/a"),
        Machine(id="MCH-0007", company_id="CMP-002", model_id="MDL-101",
                serial_number="A2132", delivery_date="2022-11-08",
                plant_location="Valencia Plant - Line D",
                configuration_profile="16000 bph, 400V, 16 magnetic heads",
                plc_family=PlcFamily.HARDWIRED_CONTROL_PANEL,
                software_version="n/a"),
        Machine(id="MCH-0008", company_id="CMP-001", model_id="MDL-101",
                serial_number="A4344", delivery_date="2023-04-19",
                plant_location="Bergamo Plant - Line 4",
                configuration_profile="20000 bph, 400V, 16 magnetic heads",
                plc_family=PlcFamily.LINE_PLC_INTEGRATED,
                software_version="n/a"),
    ]


# Manual 


async def _ingest_manuals(session) -> int:
    """
    Scan MANUALS_DIR and register one Manual row per PDF, resolving the owning
    machine through the serial number in the filename.

    Idempotent per file, not per run: a machine that already has a manual is
    skipped, so dropping a new PDF in the folder and restarting picks it up
    even though the rest of the seed is already done.
    """
    if not MANUALS_DIR.is_dir():
        logger.warning("Manuals directory %s not found, skipping manual ingest.",
                       MANUALS_DIR)
        return 0

    ingested = 0
    for pdf_path in sorted(MANUALS_DIR.glob("*.pdf")):
        match = MANUAL_FILENAME_RE.match(pdf_path.name)
        if match is None:
            logger.warning("Filename %s does not follow "
                           "<serial>_manual_<LANG>.pdf, skipped.", pdf_path.name)
            continue

        serial = match.group("serial")
        language = match.group("lang").lower()

        machine = (
            await session.exec(select(Machine).where(Machine.serial_number == serial))
        ).first()
        if machine is None:
            logger.warning("No machine with serial %s (file %s), skipped.",
                           serial, pdf_path.name)
            continue

        already = (
            await session.exec(select(Manual).where(Manual.machine_id == machine.id))
        ).first()
        if already is not None:
            logger.debug("Machine %s already has a manual, skipped.", machine.id)
            continue

        session.add(Manual(
            machine_id=machine.id,
            filename=pdf_path.name,
            storage_path=str(pdf_path),
            content_type="application/pdf",
            size=pdf_path.stat().st_size,
            language=language,
            title="Use & Maintenance Manual",
        ))
        ingested += 1
        logger.info("Manual %s linked to machine %s (serial %s).",
                    pdf_path.name, machine.id, serial)

    await session.commit()
    return ingested




async def seed_data() -> None:
    """
    Populate the domain DB, idempotently. Safe to call on every startup.

    Reference data is inserted only on an empty DB. Manuals are reconciled on
    every run, so the folder stays the source of truth for the documentation.
    """
    async with _async_session_factory() as session:
        already_seeded = (await session.exec(select(Machine).limit(1))).first() is not None

        if already_seeded:
            logger.info("Reference data already present, skipping fixtures.")
        else:
            # Insertion order follows the FK graph: a row can only be written
            # once the rows it points at exist.
            companies = _fixture_companies()
            models_ = _fixture_machine_models()
            session.add_all(companies)
            session.add_all(models_)
            await session.commit()

            users = _fixture_users()
            machines = _fixture_machines()
            session.add_all(users)
            session.add_all(machines)
            await session.commit()

            logger.info("Seeded %d companies, %d users, %d models, %d machines.",
                        len(companies), len(users), len(models_), len(machines))

        ingested = await _ingest_manuals(session)
        logger.info("Manual ingest complete: %d new manual(s).", ingested)