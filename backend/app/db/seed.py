import logging
import re
from pathlib import Path
from app.config import settings

from sqlmodel import select

from app.db.engine import async_session_factory
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
DOMAIN_DB_PATH = settings.DOMAIN_DB_PATH


# The dataset convention: manuals/<serialNumber>_manual_<LANG>.pdf
# The serial number is the only thing a PDF knows about its machine, which is
# why it is the RESOLUTION key here, while machine_id is the resting link.
#
# The serial part is deliberately NOT \d+: real serials come in two shapes,
# numeric (17478) and alphanumeric (A2055). A digits-only pattern would drop
# half the fleet silently.
MANUAL_FILENAME_RE = re.compile(r"^(?P<serial>.+?)_manual_(?P<lang>[A-Za-z]{2})\.pdf$")


# Reference data
#
# ALL of the rows below are transcribed from AROL_Q2_synthetic_fleet_dataset.xlsx,
# the same workbook the mock-backoffice serves to the agents service. This is not
# decoration: company_id is the tenant boundary the Docs Agent filters on, and
# serial_number is what resolves a manual PDF to a machine. If these two systems
# disagree on who owns what, the backend resolves a tenant the backoffice does not
# recognise, and manual citations land on the wrong machine — silently, with no
# error anywhere. The workbook is the source of truth; this file must follow it.


def _fixture_companies() -> list[Company]:
    # Companies sheet, all five rows. CMP-004 and CMP-005 are not optional:
    # MCH-0006 belongs to CMP-004, so omitting it breaks the machines FK.
    return [
        Company(id="CMP-001", name="Valgrande Bevande S.p.A.", country="Italy",
                city="Novara", sector="Beverage", currency="EUR", locale="it-IT"),
        Company(id="CMP-002", name="Distillerie Bruyere SAS", country="France",
                city="Saintes", sector="Spirits", currency="EUR", locale="fr-FR"),
        Company(id="CMP-003", name="Farmaceutica del Ebro S.L.", country="Spain",
                city="Zaragoza", sector="Pharmaceutical", currency="EUR",
                locale="es-ES"),
        Company(id="CMP-004", name="Kilbrannan Beverages Ltd",
                country="United Kingdom", city="Glasgow", sector="Soft Drinks",
                currency="GBP", locale="en-GB"),
        Company(id="CMP-005", name="Aguas de Cascais Lda", country="Portugal",
                city="Setubal", sector="Mineral Water", currency="EUR",
                locale="pt-PT"),
    ]


def _fixture_users() -> list[User]:
    # Users sheet, all nineteen rows. Every visibility level appears in more than
    # one company, which is what makes the access model testable: a scope that
    # exists in a single tenant cannot show whether filtering works or whether
    # the query simply happened to match.
    return [
        User(id="USR-001", company_id="CMP-001", first_name="Elena",
             last_name="Fabbri", email="elena.fabbri@valgrande.example",
             job_title="Plant Maintenance Manager", visibility=Visibility.FULL),
        User(id="USR-002", company_id="CMP-001", first_name="Matteo",
             last_name="Bonetti", email="matteo.bonetti@valgrande.example",
             job_title="Maintenance Man", visibility=Visibility.TECHNICIAN),
        User(id="USR-003", company_id="CMP-001", first_name="Serena",
             last_name="Lupo", email="serena.lupo@valgrande.example",
             job_title="Line Operator", visibility=Visibility.TECHNICIAN),
        User(id="USR-004", company_id="CMP-001", first_name="Davide",
             last_name="Ranieri", email="davide.ranieri@valgrande.example",
             job_title="Procurement Specialist", visibility=Visibility.COMMERCIAL),
        User(id="USR-005", company_id="CMP-001", first_name="Ilaria",
             last_name="Sacchetti", email="ilaria.sacchetti@valgrande.example",
             job_title="Quality Assurance Manager", visibility=Visibility.FULL),
        User(id="USR-006", company_id="CMP-001", first_name="Fulvio",
             last_name="Mandelli", email="fulvio.mandelli@valgrande.example",
             job_title="Line Operator", visibility=Visibility.TECHNICIAN),
        User(id="USR-007", company_id="CMP-002", first_name="Adrien",
             last_name="Lemaitre", email="adrien.lemaitre@bruyere.example",
             job_title="Technical Director", visibility=Visibility.FULL),
        User(id="USR-008", company_id="CMP-002", first_name="Camille",
             last_name="Berthaud", email="camille.berthaud@bruyere.example",
             job_title="Maintenance Man", visibility=Visibility.TECHNICIAN),
        User(id="USR-009", company_id="CMP-002", first_name="Thibault",
             last_name="Marchand", email="thibault.marchand@bruyere.example",
             job_title="Bottling Hall Supervisor", visibility=Visibility.TECHNICIAN),
        User(id="USR-010", company_id="CMP-002", first_name="Solene",
             last_name="Vasseur", email="solene.vasseur@bruyere.example",
             job_title="Purchasing Manager", visibility=Visibility.COMMERCIAL),
        User(id="USR-011", company_id="CMP-003", first_name="Nuria",
             last_name="Castellon", email="nuria.castellon@ebro.example",
             job_title="Engineering Manager", visibility=Visibility.FULL),
        User(id="USR-012", company_id="CMP-003", first_name="Joaquin",
             last_name="Peralta", email="joaquin.peralta@ebro.example",
             job_title="Maintenance Man", visibility=Visibility.TECHNICIAN),
        User(id="USR-013", company_id="CMP-003", first_name="Beatriz",
             last_name="Aldana", email="beatriz.aldana@ebro.example",
             job_title="Validation Specialist", visibility=Visibility.TECHNICIAN),
        User(id="USR-014", company_id="CMP-003", first_name="Ignacio",
             last_name="Rueda", email="ignacio.rueda@ebro.example",
             job_title="Procurement Manager", visibility=Visibility.COMMERCIAL),
        User(id="USR-015", company_id="CMP-004", first_name="Fiona",
             last_name="Drummond", email="fiona.drummond@kilbrannan.example",
             job_title="Operations Manager", visibility=Visibility.FULL),
        User(id="USR-016", company_id="CMP-004", first_name="Callum",
             last_name="Ferrier", email="callum.ferrier@kilbrannan.example",
             job_title="Maintenance Man", visibility=Visibility.TECHNICIAN),
        User(id="USR-017", company_id="CMP-004", first_name="Rhona",
             last_name="Baxter", email="rhona.baxter@kilbrannan.example",
             job_title="Line Operator", visibility=Visibility.TECHNICIAN),
        User(id="USR-018", company_id="CMP-005", first_name="Mariana",
             last_name="Esteves", email="mariana.esteves@cascais.example",
             job_title="Industrial Project Manager", visibility=Visibility.FULL),
        User(id="USR-019", company_id="CMP-005", first_name="Rui",
             last_name="Cardoso", email="rui.cardoso@cascais.example",
             job_title="Procurement Lead", visibility=Visibility.COMMERCIAL),
    ]


def _fixture_machine_models() -> list[MachineModel]:
    # MachineModels sheet, all six rows. primitive_diameter is genuinely absent
    # for the two turret models (they are single-head, there is no carousel
    # pitch circle to state), which is why the column is nullable.
    return [
        MachineModel(
            id="MDL-100", model_code="TS-EURO-PK-TWIN-CHUTE-D",
            description="Rotary closing machine for pre-threaded plastic screw "
                        "caps, twin caps chute",
            primitive_diameter=720, nominal_heads=20,
            container_type="PET and glass bottles",
            cap_type="Pre-threaded plastic screw cap",
            industry_segment="Beverage",
            notes="Twin-hopper cap feeding: two independent caps chutes fed by "
                  "one reversible centrifugal sorter with double exit mouth, so "
                  "a chute jam or a missed transfer-disc release does not stop "
                  "production. Magnetic closure heads with PK 314 ball chuck; "
                  "static tightening torque set on a graduated ring nut "
                  "(Lbs x inch), tolerance +/-5%. Supplied as partly completed "
                  "machinery (Declaration of Incorporation).",
        ),
        MachineModel(
            id="MDL-200", model_code="TSI-EURO-VA-IES-LIGHT",
            description="Rotary closing machine for aluminium roll-on (ROPP) caps",
            primitive_diameter=288, nominal_heads=6,
            container_type="Glass and PET bottles",
            cap_type="Aluminium roll-on screw cap (ROPP)",
            industry_segment="Beverage",
            notes="SSD closure head: the cap is threaded and sealed onto the "
                  "container neck by threading and skirting rollers following a "
                  "cam profile. Pick-off cap distribution from a flat centrifugal "
                  "caps sorter. Electrical height adjustment of the closure "
                  "carousel. Optional UV-ray cap steriliser. Supplied as partly "
                  "completed machinery (Declaration of Incorporation).",
        ),
        MachineModel(
            id="MDL-300", model_code="M-EURO-VP-IES",
            description="Closing machine for pre-threaded screw caps with "
                        "closure gripper",
            primitive_diameter=288, nominal_heads=3,
            container_type="Glass and plastic bottles and containers",
            cap_type="Pre-threaded screw cap",
            industry_segment="Pharmaceutical",
            notes="Complete machine (Declaration of Conformity) with its own "
                  "SIMATIC touch HMI, PROFIBUS field bus and frequency converters "
                  "on machine, heads, sorter and height motors. VP750 closure "
                  "head and VP750 closure gripper, both with documented "
                  "wearing-part kits at 3000/6000/12000/18000 working hours. "
                  "Upper and lower closure carousel, transfer disc for closure "
                  "systems.",
        ),
        MachineModel(
            id="MDL-400", model_code="TSI-CLOSYS-EAGLE-PK",
            description="Single-head automatic closing machine for pre-threaded "
                        "plastic caps",
            primitive_diameter=410, nominal_heads=1,
            container_type="Glass and plastic bottles",
            cap_type="Pre-threaded plastic screw cap",
            industry_segment="Pharmaceutical",
            notes="Single closure head on a 410 mm star-wheel, pick-and-place cap "
                  "distribution. Suited to small batches and frequent format "
                  "changeovers. Supplied as partly completed machinery "
                  "(Declaration of Incorporation).",
        ),
        MachineModel(
            id="MDL-500", model_code="EAGLE-PK-TURRET",
            description="Single-head automatic turret for pre-threaded plastic "
                        "screw caps",
            primitive_diameter=None, nominal_heads=1,
            container_type="PET bottles",
            cap_type="Plastic screw cap",
            industry_segment="Beverage",
            notes="CLOSYS single-head automatic turret. Caps leave the "
                  "orientator, run down a caps chute to the distribution head, "
                  "are taken at about 45 degrees by a pick-and-place transfer "
                  "device and gripped by the closure chuck. Star-wheel transfers "
                  "containers under the capping head. Manufacturer Declaration "
                  "(pre-2009 machinery).",
        ),
        MachineModel(
            id="MDL-600", model_code="EAGLE-VA-TURRET",
            description="Single-head automatic turret for aluminium and pressure "
                        "caps",
            primitive_diameter=None, nominal_heads=1,
            container_type="Glass bottles",
            cap_type="Aluminium screw cap or pressure cap",
            industry_segment="Spirits",
            notes="CLOSYS single-head automatic turret. Cap taken at about 45 "
                  "degrees by the pick-off system directly by the incoming "
                  "bottle. The capping head threads and seams the cap by threader "
                  "and seamer rollers following a cam profile; a pressure-cap "
                  "variant applies press-on closures instead. Manufacturer "
                  "Declaration (pre-2009 machinery).",
        ),
    ]


def _fixture_machines() -> list[Machine]:
    """
    Machines sheet, all eight rows, transcribed field by field.

    Two columns here are cross-system identifiers and must not be improvised:

    - company_id is the tenant the Docs Agent filters commercial records on. The
      backend resolves it from machine_id before every docs call, so a wrong
      pairing here does not raise: it quietly asks the backoffice for another
      customer's quotes and orders.
    - serial_number is what _ingest_manuals() below matches against the PDF
      filenames. The alphanumeric serials (A2055, A2064, A2132, A4344) belong to
      specific machines; swapping two of them links a manual to the wrong machine
      and every citation pointing at it resolves to the wrong row.

    software_version is 'n/a' wherever the workbook leaves it empty — these are
    hardwired or line-integrated machines with no versioned software of their own.
    """
    return [
        Machine(id="MCH-0001", company_id="CMP-001", model_id="MDL-100",
                serial_number="15610", delivery_date="2016-06-14",
                plant_location="Novara Plant 1 - Bottling Line 3",
                configuration_profile="Twin chute / 20 heads / 40000 bph / "
                                      "400V-60Hz / PK 314 chuck",
                plc_family=PlcFamily.LINE_PLC_INTEGRATED,
                software_version="n/a"),
        Machine(id="MCH-0002", company_id="CMP-001", model_id="MDL-200",
                serial_number="17203", delivery_date="2018-10-02",
                plant_location="Novara Plant 1 - Bottling Line 5",
                configuration_profile="IES Light / 6 heads / 10000 bph / "
                                      "480V-60Hz / UV cap steriliser",
                plc_family=PlcFamily.LINE_PLC_INTEGRATED,
                software_version="n/a"),
        Machine(id="MCH-0003", company_id="CMP-001", model_id="MDL-200",
                serial_number="17579", delivery_date="2019-12-05",
                plant_location="Alessandria Plant 2 - Bottling Line 1",
                configuration_profile="IES Light / 6 heads / 6000 bph / 220V-50Hz",
                plc_family=PlcFamily.LINE_PLC_INTEGRATED,
                software_version="n/a"),
        Machine(id="MCH-0004", company_id="CMP-003", model_id="MDL-300",
                serial_number="17478", delivery_date="2019-07-22",
                plant_location="Zaragoza Plant 1 - Filling Suite B",
                configuration_profile="IES / 3 heads / 4500 bph / 220V-60Hz / "
                                      "SIMATIC HMI + PROFIBUS",
                plc_family=PlcFamily.SIEMENS_SIMATIC_S7,
                software_version="2.3.1"),
        Machine(id="MCH-0005", company_id="CMP-003", model_id="MDL-400",
                serial_number="A4344", delivery_date="2018-05-30",
                plant_location="Zaragoza Plant 1 - Filling Suite A",
                configuration_profile="Single head / 410 mm star-wheel / "
                                      "1200 bph / 480V-60Hz",
                plc_family=PlcFamily.LINE_PLC_INTEGRATED,
                software_version="n/a"),
        Machine(id="MCH-0006", company_id="CMP-004", model_id="MDL-500",
                serial_number="A2064", delivery_date="2007-09-18",
                plant_location="Glasgow Plant 1 - Line 2",
                configuration_profile="Single head turret / 3000 bph / "
                                      "380V-50Hz / PET 500 ml",
                plc_family=PlcFamily.HARDWIRED_CONTROL_PANEL,
                software_version="n/a"),
        Machine(id="MCH-0007", company_id="CMP-002", model_id="MDL-600",
                serial_number="A2055", delivery_date="2007-11-06",
                plant_location="Saintes Plant 1 - Bottling Hall A",
                configuration_profile="Single head turret / 3000 bph / "
                                      "380V-50Hz / aluminium cap, glass 500 ml",
                plc_family=PlcFamily.HARDWIRED_CONTROL_PANEL,
                software_version="n/a"),
        Machine(id="MCH-0008", company_id="CMP-002", model_id="MDL-600",
                serial_number="A2132", delivery_date="2007-11-06",
                plant_location="Saintes Plant 1 - Bottling Hall B",
                configuration_profile="Single head turret / 3000 bph / "
                                      "380V-50Hz / pressure cap 33x60, glass",
                plc_family=PlcFamily.HARDWIRED_CONTROL_PANEL,
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

    NOTE: "only on an empty DB" means a database seeded from an earlier, wrong
    set of fixtures is never corrected by restarting — the guard below sees rows
    and skips. Deleting the domain DB file is the only way to pick up a change
    to the fixtures above.
    """
    async with async_session_factory() as session:
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