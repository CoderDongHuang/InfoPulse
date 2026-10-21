"""Offline operator recovery for unsupported legacy SSO/MFA policies.

Use the instance's normal database configuration and explicit organization/owner
UUIDs. This never enables identity enforcement or grants membership.
"""
import argparse
import asyncio
from uuid import UUID
from app.core.database import _get_sessionmaker, close_db
from app.models.enterprise import Organization, TenantPolicy
from app.services.enterprise import set_db_context


async def recover(organization_id, owner_id):
    try:
        async with _get_sessionmaker()() as db:
            await set_db_context(db, owner_id, organization_id)
            organization = await db.get(Organization, organization_id)
            if not organization or organization.created_by != owner_id:
                raise SystemExit("Organization/owner mismatch; no policy changed")
            policy = await db.get(TenantPolicy, organization_id)
            if not policy:
                raise SystemExit("Policy not found; no policy changed")
            policy.require_sso = False
            policy.require_mfa = False
            await db.commit()
            print("Unsupported identity requirements disabled for the specified organization")
    finally:
        await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization-id", required=True, type=UUID)
    parser.add_argument("--owner-id", required=True, type=UUID)
    args = parser.parse_args()
    asyncio.run(recover(str(args.organization_id), str(args.owner_id)))
