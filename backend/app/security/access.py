"""
The access model: which kinds of data each visibility level may reach.

Access is decided by two independent checks, and both must pass:

  1. company_id — the tenant boundary. Enforced by injecting the user's
     company into every query and every agent call; never crossed.
  2. visibility — narrows WHAT KIND of data a user sees inside their own
     company. Defined here.

This module is the single source of truth for check 2. Every enforcement
point reads from it, so changing the policy means changing this file only.
It is plain data and plain functions: the decision is deterministic and never
depends on the LLM.
"""

from enum import Enum

from app.db.models import Visibility


class DataDomain(str, Enum):
    """The three domains the dataset splits into, for access purposes."""
    IDENTITY = "identity"            # machines, models, manuals
    OPERATIONAL = "operational"      # telemetry, alarms, maintenance tickets
    COMMERCIAL = "commercial"        # quotes, revisions, orders


# The policy table.
#   full        -> everything
#   technician  -> identity + operational
#   commercial  -> identity + commercial
# Identity data is visible at every level (for the user's own company).
_ALLOWED_DOMAINS: dict[Visibility, frozenset[DataDomain]] = {
    Visibility.FULL: frozenset(DataDomain),
    Visibility.TECHNICIAN: frozenset({DataDomain.IDENTITY, DataDomain.OPERATIONAL}),
    Visibility.COMMERCIAL: frozenset({DataDomain.IDENTITY, DataDomain.COMMERCIAL}),
}

# Human-readable description of each domain, used in denial messages.
DOMAIN_DESCRIPTIONS: dict[DataDomain, str] = {
    DataDomain.IDENTITY: "machine identity and documentation",
    DataDomain.OPERATIONAL: "operational data (telemetry, alarms, maintenance)",
    DataDomain.COMMERCIAL: "commercial data (quotes and orders)",
}


def is_allowed(visibility: Visibility | str | None, domain: DataDomain) -> bool:
    """
    Fail closed: an unknown or missing visibility is allowed nothing. A bug
    that loses the visibility on the way must deny access, never grant it.
    """
    try:
        level = Visibility(visibility)
    except ValueError:
        return False
    return domain in _ALLOWED_DOMAINS.get(level, frozenset())


def denial_message(domain: DataDomain) -> str:
    return f"Access denied: {DOMAIN_DESCRIPTIONS[domain]} is outside your access profile."
