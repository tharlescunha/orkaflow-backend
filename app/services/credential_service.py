from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.core.security import (
    build_masked_preview,
    decrypt_credential_value,
    encrypt_credential_value,
)
from app.repositories.credential_repository import CredentialRepository
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.credential import (
    CredentialCreate,
    CredentialItemCreate,
    CredentialItemUpdate,
    CredentialUpdate,
)


class CredentialService:
    def __init__(self, db: Session):
        self.repo = CredentialRepository(db)
        self.repository_repo = RepositoryRepository(db)

    def list(
        self,
        skip: int = 0,
        limit: int = 100,
        active: bool | None = None,
        repository_id: int | None = None,
    ):
        return self.repo.list_all(
            skip=skip,
            limit=limit,
            active=active,
            repository_id=repository_id,
        )

    def get(self, credential_id: int):
        credential = self.repo.get_by_id(credential_id)
        if not credential:
            raise NotFoundException("Credencial não encontrada.")
        return credential

    def create(self, data: CredentialCreate):
        repository = self.repository_repo.get_by_id(data.repository_id)
        if not repository:
            raise NotFoundException("Repositório não encontrado.")

        existing = self.repo.get_by_name(data.name)
        if existing:
            raise ConflictException("Já existe uma credencial com esse nome.")

        return self.repo.create(**data.model_dump())

    def update(self, credential_id: int, data: CredentialUpdate):
        credential = self.get(credential_id)
        update_data = data.model_dump(exclude_unset=True)

        if "repository_id" in update_data:
            repository = self.repository_repo.get_by_id(update_data["repository_id"])
            if not repository:
                raise NotFoundException("Repositório não encontrado.")

        if "name" in update_data and update_data["name"] != credential.name:
            existing = self.repo.get_by_name(update_data["name"])
            if existing:
                raise ConflictException("Já existe uma credencial com esse nome.")

        return self.repo.update(credential, **update_data)

    def delete(self, credential_id: int):
        credential = self.get(credential_id)
        return self.repo.soft_delete(credential)

    def list_items(self, credential_id: int, active: bool | None = None):
        self.get(credential_id)
        return self.repo.list_items(credential_id, active=active)

    def get_item(self, credential_id: int, item_id: int):
        self.get(credential_id)
        item = self.repo.get_item_by_id(item_id)
        if not item or item.credential_id != credential_id:
            raise NotFoundException("Item da credencial não encontrado.")
        return item

    def create_item(self, credential_id: int, data: CredentialItemCreate):
        self.get(credential_id)

        existing = self.repo.get_item_by_key(credential_id, data.key)
        if existing:
            raise ConflictException("Já existe um item com essa chave nesta credencial.")

        encrypted_value = encrypt_credential_value(data.value)
        masked_preview = build_masked_preview(data.value)

        payload = data.model_dump(exclude={"value"})
        payload["credential_id"] = credential_id
        payload["encrypted_value"] = encrypted_value
        payload["masked_preview"] = masked_preview

        return self.repo.create_item(**payload)

    def update_item(self, credential_id: int, item_id: int, data: CredentialItemUpdate):
        item = self.get_item(credential_id, item_id)
        update_data = data.model_dump(exclude_unset=True)

        if "key" in update_data and update_data["key"] != item.key:
            existing = self.repo.get_item_by_key(credential_id, update_data["key"])
            if existing:
                raise ConflictException("Já existe um item com essa chave nesta credencial.")

        if "value" in update_data:
            raw_value = update_data.pop("value")
            if raw_value is not None:
                update_data["encrypted_value"] = encrypt_credential_value(raw_value)
                update_data["masked_preview"] = build_masked_preview(raw_value)

        return self.repo.update_item(item, **update_data)

    def delete_item(self, credential_id: int, item_id: int):
        item = self.get_item(credential_id, item_id)
        return self.repo.soft_delete_item(item)

    def reveal_item_secret(self, credential_id: int, item_id: int):
        item = self.get_item(credential_id, item_id)

        return {
            "id": item.id,
            "credential_id": item.credential_id,
            "key": item.key,
            "value_type": item.value_type,
            "value": decrypt_credential_value(item.encrypted_value),
            "active": item.active,
        }
    