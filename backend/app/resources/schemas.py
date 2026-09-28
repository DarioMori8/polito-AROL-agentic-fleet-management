from datetime import date, datetime

from pydantic import BaseModel, computed_field

from app.db.models import Machine, Manual, PlcFamily

# These are WIRE schemas, not storage schemas: they define the exact JSON the
# client receives. Two reasons they exist as a separate layer instead of
# returning the SQLModel tables directly:
#   1. subtraction — Manual.storage_path is where the bytes live on our disk
#      and must never leave the process;
#   2. addition — `url` is not a column at all, it is derived from the route
#      that serves the file. The client needs it, the database has no use
#      for it, so it lives exactly here and nowhere else.
# The dependency runs one way only: schemas know about models, models never
# know about schemas.

# Path of the endpoint that streams the PDF. Relative on purpose: behind a
# reverse proxy an absolute URL built from the internal host would be wrong.
# It duplicates the route declared in resources/router.py: if that prefix or
# path changes, this string must change with it.
_MANUAL_FILE_ROUTE = "/v1/manuals/{manual_id}/file"


class MachineOut(BaseModel):
    """
    An installed machine as the client sees it.

    Runtime state (online/offline, current throughput) is deliberately absent:
    it is not an attribute of the machine but the latest reading of its
    telemetry stream, which the IoT agent owns.
    """
    id: str
    company_id: str
    model_id: str
    serial_number: str
    delivery_date: date                  # serialized as "YYYY-MM-DD"
    plant_location: str
    configuration_profile: str
    plc_family: PlcFamily                # serialized as its value
    software_version: str | None         # null when the machine has none

    @classmethod
    def from_model(cls, machine: Machine) -> "MachineOut":
        # from_attributes: read machine.<field> instead of dict keys, copying
        # only the fields declared above.
        return cls.model_validate(machine, from_attributes=True)


class ManualOut(BaseModel):
    """The use-and-maintenance manual of one machine, as the client sees it."""
    id: str
    machine_id: str
    title: str
    filename: str
    language: str
    content_type: str
    size: int                            # bytes
    uploaded_at: datetime                # UTC-aware, serialized with its offset

    @computed_field
    @property
    def url(self) -> str:
        # Derived, not stored: computed from the id at serialization time, so
        # from_model needs no hand-written list of fields.
        return _MANUAL_FILE_ROUTE.format(manual_id=self.id)

    @classmethod
    def from_model(cls, manual: Manual) -> "ManualOut":
        # storage_path is not declared above, so it is never copied: the
        # subtraction happens by omission.
        return cls.model_validate(manual, from_attributes=True)
