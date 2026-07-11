from pydantic import BaseModel, ConfigDict


class SystemResponse(BaseModel):
    model_config = ConfigDict(frozen=True)


class HealthResponse(SystemResponse):
    status: str


class VersionResponse(SystemResponse):
    name: str
    version: str
