from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.credential import Credential
from app.models.credential_item import CredentialItem


class CredentialRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, credential_id: int) -> Credential | None:
        stmt = (
            select(Credential)
            .options(selectinload(Credential.items))
            .where(Credential.id == credential_id)
        )
        return self.db.scalar(stmt)

    def get_by_label(self, label: str) -> Credential | None:
        stmt = select(Credential).where(Credential.label == label)
        return self.db.scalar(stmt)

    def list_all(self, skip=0, limit=100, active=None, repository_id=None):
        stmt = (
            select(Credential)
            .options(selectinload(Credential.items))
            .order_by(Credential.label)
        )

        if active is not None:
            stmt = stmt.where(Credential.active == active)

        if repository_id is not None:
            stmt = stmt.where(Credential.repository_id == repository_id)

        stmt = stmt.offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def create(self, **data):
        credential = Credential(**data)
        self.db.add(credential)
        self.db.commit()
        self.db.refresh(credential)
        return credential

    def update(self, credential, **data):
        for field, value in data.items():
            setattr(credential, field, value)

        self.db.add(credential)
        self.db.commit()
        self.db.refresh(credential)
        return credential

    def soft_delete(self, credential):
        credential.active = False
        self.db.commit()
        return credential

    # ---------- ITEMS ----------

    def get_item_by_id(self, item_id: int):
        stmt = select(CredentialItem).where(CredentialItem.id == item_id)
        return self.db.scalar(stmt)

    def get_item_by_key(self, credential_id: int, key_name: str):
        stmt = select(CredentialItem).where(
            CredentialItem.credential_id == credential_id,
            CredentialItem.key_name == key_name,
        )
        return self.db.scalar(stmt)

    def list_items(self, credential_id: int):
        stmt = (
            select(CredentialItem)
            .where(CredentialItem.credential_id == credential_id)
            .order_by(CredentialItem.key_name)
        )
        return list(self.db.scalars(stmt).all())

    def create_item(self, **data):
        item = CredentialItem(**data)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_item(self, item, **data):
        for field, value in data.items():
            setattr(item, field, value)

        self.db.commit()
        return item

    def delete_item(self, item):
        self.db.delete(item)
        self.db.commit()
        