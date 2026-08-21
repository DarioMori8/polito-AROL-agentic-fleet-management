# resources/schemas.py
from datetime import datetime

from pydantic import BaseModel

from app.db.models import Machine, Manual, PlcFamily

# These are WIRE schemas, not storage schemas. Two reasons they exist as a
# separate layer instead of returning the SQLModel tables directly:
#   1. subtraction — Manual.storage_path is where the bytes live on our disk
#      and must never leave the process;
#   2. addition — `url` is not a column at all, it is derived from the route
#      that serves the file. The client needs it, the database has no use
#      for it, so it lives exactly here and nowhere else.
# The dependency runs one way only: schemas know about models, models never
# know about schemas.

# Path of the endpoint that streams the PDF. Relative on purpose: behind
# nginx an absolute URL built from the internal host would be wrong.
_MANUAL_FILE_ROUTE = "/v1/manuals/{manual_id}/file"


class MachineOut(BaseModel):
    """
    An installed machine as the client sees it.

    Note what is NOT here any more: `status`. Runtime state is not an
    attribute of a machine, it is the latest reading of its telemetry
    stream, and it belongs to a table that does not exist yet. Publishing it
    from here would have meant inventing it.
    """
    id: str
    company_id: str
    model_id: str
    serial_number: str
    delivery_date: str
    plant_location: str
    configuration_profile: str
    plc_family: PlcFamily
    software_version: str

    @classmethod
    def from_model(cls, machine: Machine) -> "MachineOut":
        return cls.model_validate(machine, from_attributes=True)


class ManualOut(BaseModel):
    """The use-and-maintenance manual of one machine, as the client sees it."""
    id: str
    machine_id: str
    title: str
    filename: str
    language: str
    content_type: str
    size: int
    uploaded_at: datetime
    url: str

    @classmethod
    def from_model(cls, manual: Manual) -> "ManualOut":
        # model_validate cannot invent `url`, so it is composed here, in the
        # one place that knows both the row and the route.
        return cls(
            id=manual.id,
            machine_id=manual.machine_id,
            title=manual.title,
            filename=manual.filename,
            language=manual.language,
            content_type=manual.content_type,
            size=manual.size,
            uploaded_at=manual.uploaded_at,
            url=_MANUAL_FILE_ROUTE.format(manual_id=manual.id),
        )