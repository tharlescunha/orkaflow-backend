from pydantic import BaseModel


class WorkerParameterRead(BaseModel):
    key: str
    value: str


class WorkerParameterRequest(BaseModel):
    uuid: str
    token: str