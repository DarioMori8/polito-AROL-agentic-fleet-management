import logging

from sqlmodel import select

from app.db.engine import _async_session_factory
from app.db.models import Machine, Document, MachineStatus, DocumentType

logger = logging.getLogger(__name__)


async def seed_data() -> None:
    """
    Populate the domain DB with fixture data, idempotently: if any machine
    already exists, assume the DB is already seeded and do nothing. Safe to
    call on every startup.
    """
    async with _async_session_factory() as session:
        existing = (await session.exec(select(Machine).limit(1))).first()
        if existing is not None:
            logger.info("Domain DB already seeded, skipping.")
            return

        # --- Phase 1: machines (must exist before documents, due to the FK) ---
        machines = [
            Machine(id="1", name="Capping Line Alpha", model="AROL EURO PK",
                    serial_number="AR-EPK-2021-0453", status=MachineStatus.ONLINE,
                    location="Bottling Line 1"),
            Machine(id="2", name="Capping Line Bravo", model="AROL EQUATORQUE",
                    serial_number="AR-EQT-2022-0817", status=MachineStatus.ONLINE,
                    location="Bottling Line 2"),
            Machine(id="3", name="Capping Line Charlie", model="AROL EURO VP",
                    serial_number="AR-EVP-2023-0129", status=MachineStatus.MAINTENANCE,
                    location="Bottling Line 3"),
        ]
        session.add_all(machines)
        await session.commit()

        # --- Phase 2: documents (reference machines, so committed after) 
        documents = [
            Document(filename="manual_1.pdf",
                     storage_path="data/documents/manual_1.pdf",
                     content_type="application/pdf", size=980_000,
                     document_type=DocumentType.MANUAL, machine_id="2",
                     title="Use & Maintenance Manual", language="en"),
            Document(filename="euro_pk_use_maintenance.pdf",
                     storage_path="data/documents/euro_pk_use_maintenance.pdf",
                     content_type="application/pdf", size=1_420_000,
                     document_type=DocumentType.MANUAL, machine_id="1",
                     title="Use & Maintenance Manual", language="en"),
            Document(filename="euro_pk_warranty.pdf",
                     storage_path="data/documents/euro_pk_warranty.pdf",
                     content_type="application/pdf", size=210_000,
                     document_type=DocumentType.WARRANTY, machine_id="1",
                     title="Warranty Certificate", language="en"),
            Document(filename="quote_rev3.pdf",
                     storage_path="data/documents/quote_rev3.pdf",
                     content_type="application/pdf", size=85_000,
                     document_type=DocumentType.REVISION, order_id="ORD-4471",
                     title="Quotation rev. 3", language="it"),
        ]
        session.add_all(documents)
        await session.commit()
        logger.info("Domain DB seeded: %d machines, %d documents.",
                    len(machines), len(documents))