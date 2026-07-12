from pydantic import BaseModel, ConfigDict


class SystemResponse(BaseModel):
    model_config = ConfigDict(frozen=True)


class HealthResponse(SystemResponse):
    status: str


class ReadinessResponse(SystemResponse):
    status: str
    dependencies: dict[str, str]


class VersionResponse(SystemResponse):
    name: str
    version: str
