from datetime import date, datetime, timezone
from enum import Enum
from uuid import uuid4

import sqlalchemy as sa
from sqlmodel import SQLModel, Field


# --- Column helpers

def _enum_values(enum_cls: type[Enum]) -> list[str]:
    """
    Tells SQLAlchemy to persist the enum *values* ('full') instead of the
    member *names* ('FULL'), which is the default. Without this the DB would
    contain FULL/TECHNICIAN/COMMERCIAL and never match the dataset.
    """
    return [e.value for e in enum_cls]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(sa.types.TypeDecorator):
    """
    A DateTime column that is always timezone-aware UTC on the Python side.

    SQLite has no timezone support: an aware datetime is written without its
    offset and read back naive. Comparing that naive value with an aware
    `datetime.now(timezone.utc)` raises TypeError, so every caller would have
    to remember to re-attach UTC by hand.

    This type does it once, at the boundary:
      - on write, it rejects naive datetimes (ambiguous: which zone?) and
        normalises aware ones to UTC before storing;
      - on read, it re-attaches UTC to what SQLite returns.
    """
    impl = sa.DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetime rejected: store timezone-aware UTC values.")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


# --- Enums

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


# --- Tables

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
    """
    A person belonging to one company, carrying a visibility scope.

    Also holds the authentication material. The password itself is never
    stored: only the scrypt hash and the per-user salt that produced it.
    Hashing is one-way, so a stolen database does not yield passwords.

    The salt is NOT a secret and is stored in the clear on purpose. Its job is
    to make two users with the same password end up with different hashes,
    which is what stops a single precomputed table from breaking every account
    at once.

    Both fields are nullable so that a user row can exist before a password is
    provisioned — the dataset ships people, not credentials.
    """
    __tablename__ = "users"

    id: str = Field(primary_key=True)            # "USR-001"
    company_id: str = Field(
        foreign_key="companies.id", ondelete="RESTRICT", index=True
    )
    first_name: str
    last_name: str
    # The login identifier, compared case-sensitively by design. unique=True
    # makes "find the user with this email" a well-posed question; indexed
    # because every login performs that lookup.
    email: str = Field(unique=True, index=True)
    job_title: str
    # With sa_column, SQLModel ignores the other Field arguments: every column
    # option (nullability included) must live inside the Column itself.
    visibility: Visibility = Field(
        sa_column=sa.Column(
            sa.Enum(
                Visibility,
                values_callable=_enum_values,
                create_constraint=True,      # emit the CHECK; off by default
                name="visibility_enum",
            ),
            nullable=False,
        )
    )

    # Authentication material, hex-encoded.
    password_hash: str | None = Field(default=None)
    salt: str | None = Field(default=None)


class MachineModel(SQLModel, table=True):
    """
    Engineering specification of a model. Note: what a *specific* machine can
    do is in Machine.configuration_profile, not here.
    """
    __tablename__ = "machine_models"

    id: str = Field(primary_key=True)            # "MDL-100"
    model_code: str
    description: str
    # NULL for the single-head turrets: there is no carousel pitch circle.
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
    # make that resolution ambiguous. Indexed because we look it up by value.
    serial_number: str = Field(unique=True, index=True)
    # A real date, not a string: validated on the way in, comparable without
    # relying on the ISO format happening to sort correctly as text.
    delivery_date: date
    plant_location: str
    configuration_profile: str
    plc_family: PlcFamily = Field(
        sa_column=sa.Column(
            sa.Enum(
                PlcFamily,
                values_callable=_enum_values,
                create_constraint=True,
                name="plc_family_enum",
            ),
            nullable=False,
        )
    )
    # NULL for hardwired or line-integrated machines with no versioned software
    # of their own. Absence is NULL everywhere in this schema, never a
    # sentinel string such as 'n/a'.
    software_version: str | None = Field(default=None)


class Manual(SQLModel, table=True):
    """
    The use-and-maintenance manual of one machine. One per machine, exactly:
    'every machine has a manual and every manual corresponds to a machine'.
    """
    __tablename__ = "manuals"

    # Surrogate id: the file is ours, so we mint its identity.
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)

    # UNIQUE is what enforces the 1:1 with Machine. A unique constraint is
    # already backed by an index, so no separate index=True is needed.
    machine_id: str = Field(
        foreign_key="machines.id", ondelete="RESTRICT", unique=True
    )

    # File block
    # UNIQUE: it is how agent citations are resolved back to a row, so it
    # must identify exactly one manual.
    filename: str = Field(unique=True)           # "17478_manual_EN.pdf"
    storage_path: str                            # where the bytes live on disk
    content_type: str                            # MIME, e.g. "application/pdf"
    size: int                                    # bytes
    uploaded_at: datetime = Field(default_factory=_utc_now, sa_type=UTCDateTime)

    # Domain metadata
    language: str                                # "en", from the _EN suffix
    title: str


class AuthSession(SQLModel, table=True):
    """
    A live authentication session: the server-side half of the session cookie.

    Named AuthSession, not Session, to stay distinct from the database session
    (sqlmodel's Session / AsyncSession, the get_session dependency) and from
    the conversation thread id used by LangGraph. The table keeps the plain
    name `sessions`.

    This is the 'session storage' box in the classic session-based auth
    diagram. In Express it is what express-session keeps for you; here it is an
    ordinary table, which also means sessions survive a container restart
    instead of dying with the process.

    The token itself is NEVER stored. The cookie carries the raw random token;
    this table stores only its SHA-256 digest, used as the primary key. A copy
    of the database therefore yields no usable session: the digest cannot be
    turned back into the token the cookie must present. Minting the token and
    hashing it is the job of the security layer, which is why `id` has no
    default here. A plain fast hash is enough (no salt, no scrypt): the token
    has 256 bits of entropy, so it cannot be guessed, unlike a password.
    """
    __tablename__ = "sessions"

    # SHA-256 hex digest of the session token held by the client.
    id: str = Field(primary_key=True)
    user_id: str = Field(
        foreign_key="users.id", ondelete="CASCADE", index=True
    )
    created_at: datetime = Field(default_factory=_utc_now, sa_type=UTCDateTime)
    # No default on purpose: how long a session lives is a policy decision,
    # taken where the session is created, not a property of the model.
    expires_at: datetime = Field(sa_type=UTCDateTime)


class Conversation(SQLModel, table=True):
    """
    Ownership record of one chat thread.

    The messages themselves live in the LangGraph checkpoint DB, keyed by
    thread_id — but the checkpointer has no notion of users: anyone presenting
    a thread_id would get that thread. This row is the missing link. It is
    created on the first turn and checked on every later turn and on every
    history read: the thread must belong to the current user, otherwise the
    answer is 404 (not 403, which would confirm the id exists).

    It also pins the thread to the machine it was opened on, so a client
    cannot continue a conversation about one machine while claiming another.

    The two databases are not linked by a real foreign key (they are separate
    SQLite files): deleting a row here does not delete its checkpoints.
    """
    __tablename__ = "conversations"

    # UUID (as text) shared with the checkpoint DB: the same value is passed to
    # LangGraph as configurable.thread_id.
    thread_id: str = Field(primary_key=True)
    # CASCADE: a thread of a deleted user has no owner left to read it.
    user_id: str = Field(
        foreign_key="users.id", ondelete="CASCADE", index=True
    )
    # RESTRICT, like every other reference to a machine in this schema.
    machine_id: str = Field(
        foreign_key="machines.id", ondelete="RESTRICT", index=True
    )
    created_at: datetime = Field(default_factory=_utc_now, sa_type=UTCDateTime)
