import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.repositories.runner_repository import RunnerRepository
from app.schemas.runner import RunnerConfigUpdate, RunnerCreate, RunnerUpdate


class RunnerService:
    def __init__(self, db: Session):
        self.repo = RunnerRepository(db)

    def create(self, data: RunnerCreate):
        if self.repo.get_by_name(data.name):
            raise ConflictException("Já existe um runner com esse nome.")

        payload = data.model_dump(exclude={"config"})

        # 🔥 gera uuid automaticamente
        payload["uuid"] = str(uuid.uuid4())

        runner = self.repo.create(**payload)
        
        if data.config:
            self.repo.create_config(runner_id=runner.id, **data.config.model_dump())

        return self.repo.get_by_id(runner.id)

    def list(
        self,
        skip: int = 0,
        limit: int = 100,
        enabled: bool | None = None,
        status: str | None = None,
    ):
        return self.repo.list_all(skip=skip, limit=limit, enabled=enabled, status=status)

    def get(self, runner_id: int):
        runner = self.repo.get_by_id(runner_id)
        if not runner:
            raise NotFoundException("Runner não encontrado.")
        return runner

    def update(self, runner_id: int, data: RunnerUpdate):
        runner = self.get(runner_id)
        update_data = data.model_dump(exclude_unset=True)

        if "name" in update_data and update_data["name"] != runner.name:
            if self.repo.get_by_name(update_data["name"]):
                raise ConflictException("Já existe um runner com esse nome.")

        return self.repo.update(runner, **update_data)

    def disable(self, runner_id: int):
        runner = self.get(runner_id)
        return self.repo.disable(runner)

    def get_config(self, runner_id: int):
        self.get(runner_id)
        config = self.repo.get_config(runner_id)
        if not config:
            raise NotFoundException("Configuração do runner não encontrada.")
        return config

    def update_config(self, runner_id: int, data: RunnerConfigUpdate):
        self.get(runner_id)
        config = self.repo.get_config(runner_id)
        if not config:
            raise NotFoundException("Configuração do runner não encontrada.")

        update_data = data.model_dump(exclude_unset=True)

        if "max_concurrency" in update_data and update_data["max_concurrency"] < 1:
            raise ValidationException("max_concurrency deve ser maior ou igual a 1.")

        if "polling_interval" in update_data and update_data["polling_interval"] < 5:
            raise ValidationException("polling_interval deve ser maior ou igual a 5.")

        return self.repo.update_config(config, **update_data)
    