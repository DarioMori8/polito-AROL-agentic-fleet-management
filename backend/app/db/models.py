from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

import sqlalchemy as sa
from sqlmodel import SQLModel, Field


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    """
    Tells SQLAlchemy to persist the enum *values* ('full') instead of the
    member *names* ('FULL'), which is the default. Without this the DB would
    contain FULL/TECHNICIAN/COMMERCIAL and never match the dataset.
    """
    return [e.value for e in enum_cls]



class Visibility(str, Enum):
    """Users.visibility — the access scope inside the user's own company."""
    FULL = "full"
    TECHNICIAN = "technician"
    COMMERCIAL = "commercial"


class PlcFamily(str, Enum):
    """Machines.plcFamily — the control architecture of a specific machine."""
    SIEMENS_SIMATIC_S7 = "SIEMENS-SIMATIC-S7"
    LINE_PLC_INTEGRATED = "LINE-PLC-INTEGRATED"
    HARDWIRED_CONTROL_PANEL = "HARDWIRED-CONTROL-PANEL"



class Company(SQLModel, table=True):
    """A customer organization. The tenant boundary of the access model."""
    __tablename__ = "companies"

    id: str = Field(primary_key=True)            # "CMP-001"
    name: str
    country: str
    city: str
    sector: str
    currency: str
    locale: str


class User(SQLModel, table=True):
    """A person belonging to one company, carrying a visibility scope."""
    __tablename__ = "users"

    id: str = Field(primary_key=True)            # "USR-001"
    company_id: str = Field(
        foreign_key="companies.id", ondelete="RESTRICT", index=True
    )
    first_name: str
    last_name: str
    email: str
    job_title: str
    visibility: Visibility = Field(
        sa_column=sa.Column(
            sa.Enum(
                Visibility,
                values_callable=_enum_values,
                create_constraint=True,      
                name="visibility_enum",
            ),
            nullable=False,
        )
    )


class MachineModel(SQLModel, table=True):
    """
    Engineering specification of a model. Note: what a *specific* machine can
    do is in Machine.configuration_profile, not here.
    """
    __tablename__ = "machine_models"

    id: str = Field(primary_key=True)            # "MDL-100"
    model_code: str
    description: str
    primitive_diameter: int | None = Field(default=None)
    nominal_heads: int
    container_type: str
    cap_type: str
    industry_segment: str
    notes: str


class Machine(SQLModel, table=True):
    """An installed machine: the central entity everything else hangs off."""
    __tablename__ = "machines"

    id: str = Field(primary_key=True)            # "MCH-0001"
    company_id: str = Field(
        foreign_key="companies.id", ondelete="RESTRICT", index=True
    )
    model_id: str = Field(
        foreign_key="machine_models.id", ondelete="RESTRICT", index=True
    )
    # Natural key from the outside world. Unique because it is the key used to
    # RESOLVE a machine from a manual filename or a QR code: a duplicate would
    # make that resolution ambiguous. Indexed because we look it up by name.
    serial_number: str = Field(unique=True, index=True)
    delivery_date: str                           # ISO string, as in the dataset
    plant_location: str
    configuration_profile: str
    plc_family: PlcFamily = Field(
        sa_column=sa.Column(
            sa.Enum(
                PlcFamily,
                values_callable=_enum_values,
                create_constraint=True,      # emit the CHECK; off by default
                name="plc_family_enum",
            ),
            nullable=False,
        )
    )
    software_version: str                        # often the literal 'n/a'


class Manual(SQLModel, table=True):
    """
    The use-and-maintenance manual of one machine. One per machine, exactly:
    'every machine has a manual and every manual corresponds to a machine'.
    """
    __tablename__ = "manuals"

    # Surrogate id: the file is ours, so we mint its identity.
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)

    # The FK is the resting link (integrity). The serial number is only the
    # resolution key used at ingest time to find which machine this is.
    # unique=True is what turns the 1:N a FK allows into the 1:1 the data says.
    machine_id: str = Field(
        foreign_key="machines.id", ondelete="RESTRICT", unique=True, index=True
    )

    # File block
    filename: str                                # "17478_manual_EN.pdf"
    storage_path: str                            # where the bytes live on disk
    content_type: str                            # MIME, e.g. "application/pdf"
    size: int                                    # bytes
    uploaded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)   # UTC, not local
    )

    # Domain metadata
    language: str                                # "en", from the _EN suffix
    title: str