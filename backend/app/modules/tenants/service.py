import re
import secrets
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.tenants.models import Tenant


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:40].strip("-")
    return slug or "empresa"


def create_tenant(db: Session, name: str) -> Tenant:
    base = slugify(name)
    slug = base
    while db.scalar(select(Tenant.id).where(Tenant.slug == slug)) is not None:
        slug = f"{base}-{secrets.token_hex(3)}"
    tenant = Tenant(name=name, slug=slug)
    db.add(tenant)
    db.flush()
    return tenant
