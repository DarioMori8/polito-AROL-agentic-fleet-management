"""
Credentials of the per-company guest accounts, and the QR codes that carry them.

A guest is someone physically in the customer's plant who scans the QR code
on a machine without having an account. The QR carries the email and the
password of the guest account of the company that owns the machine; the
frontend logs in with them through the ordinary POST /v1/sessions and shows
that machine's manual.

Each company has its OWN random password. A shared one would let the QR of one
company open the guest account of every other (guest emails are guessable),
crossing the tenant boundary.

The password exists in clear only at minting time: the DB keeps its scrypt
hash, like every other password. The QR URLs are therefore written once, to a
file readable only by its owner. If the file is lost, the password cannot be
recovered: rotate it and reprint that company's QR codes.

Rotate one company's guest password (e.g. a photo of a QR has been shared):

    docker compose exec backend python -m app.db.guest_accounts rotate CMP-001
"""

import argparse
import asyncio
import logging
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings
from app.db.engine import async_session_factory
from app.db.models import Machine, User, Visibility
from app.security.passwords import hash_password

logger = logging.getLogger(__name__)

# Next to the domain DB: inside the persisted data directory, outside git.
QR_URLS_FILE = Path(settings.DOMAIN_DB_PATH).parent / "qr_urls.txt"


def _new_password() -> str:
    # 24 random bytes, URL-safe text: printed in a QR, never typed by a person.
    return secrets.token_urlsafe(24)


def qr_url(machine_id: str, email: str, password: str) -> str:
    """The URL encoded in a machine's QR code."""
    query = urlencode({"u": email, "k": password})
    return f"{settings.GUEST_QR_BASE_URL.rstrip('/')}/{machine_id}?{query}"


def _append_qr_urls(lines: list[str]) -> None:
    """
    Append to the QR file, creating it with mode 0600: it contains live
    credentials, so it must not be readable by other users.
    """
    QR_URLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(QR_URLS_FILE, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(f"# minted {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n")
        for line in lines:
            f.write(line + "\n")


async def _set_password_and_qr_lines(session: AsyncSession, guest: User) -> list[str]:
    """
    Give the guest a fresh password (replacing any previous one) and return one
    QR line per machine of its company. The clear password lives only in the
    returned lines.
    """
    password = _new_password()
    guest.password_hash, guest.salt = hash_password(password)
    session.add(guest)

    machines = (
        await session.exec(
            select(Machine).where(Machine.company_id == guest.company_id).order_by(Machine.id)
        )
    ).all()
    if not machines:
        # The account works, but there is no machine to stick a QR on.
        return [f"# {guest.company_id}: no machines, no QR code ({guest.email})"]
    return [f"{m.id}\t{qr_url(m.id, guest.email, password)}" for m in machines]


async def mint_missing_guest_passwords(session: AsyncSession) -> int:
    """
    Seed step: give a password to every guest account that has none, and write
    the QR URLs. Idempotent: guests that already have a password keep it, so
    printed QR codes stay valid across restarts.
    """
    guests = (
        await session.exec(
            select(User).where(
                User.visibility == Visibility.GUEST,
                User.password_hash.is_(None),
            )
        )
    ).all()
    if not guests:
        return 0

    lines: list[str] = []
    for guest in guests:
        lines.extend(await _set_password_and_qr_lines(session, guest))
    await session.commit()

    _append_qr_urls(lines)
    logger.info("Guest passwords minted for %d company(ies); QR URLs written to %s.",
                len(guests), QR_URLS_FILE)
    return len(guests)


async def rotate_guest_password(company_id: str) -> list[str] | None:
    """
    Replace a company's guest password: every QR code of that company stops
    working immediately. Returns the new QR lines, or None if the company has
    no guest account. Existing guest sessions stay valid until they expire.
    """
    async with async_session_factory() as session:
        guest = (
            await session.exec(
                select(User).where(
                    User.company_id == company_id,
                    User.visibility == Visibility.GUEST,
                )
            )
        ).one_or_none()
        if guest is None:
            return None
        lines = await _set_password_and_qr_lines(session, guest)
        await session.commit()
    _append_qr_urls(lines)
    return lines


def _main() -> None:
    parser = argparse.ArgumentParser(description="Manage the per-company guest accounts.")
    sub = parser.add_subparsers(dest="command", required=True)
    rotate = sub.add_parser("rotate", help="Issue a new guest password for one company.")
    rotate.add_argument("company_id")
    args = parser.parse_args()

    lines = asyncio.run(rotate_guest_password(args.company_id))
    if lines is None:
        raise SystemExit(f"No guest account for company '{args.company_id}'.")
    print(f"New QR URLs for {args.company_id} (the previous ones no longer work):")
    print("\n".join(lines))


if __name__ == "__main__":
    _main()
