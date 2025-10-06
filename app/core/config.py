from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, Field
from typing import List
import os

class Settings(BaseSettings):
    servicENow_instance: str = Field(alias="SERVICENOW_INSTANCE")
    servicENow_username: str = Field(alias="SERVICENOW_USERNAME")
    servicENow_password: str = Field(alias="SERVICENOW_PASSWORD")
    servicENow_api_version: str = Field(default="now", alias="SERVICENOW_API_VERSION")
    servicENow_timeout: int = Field(default=30000, alias="SERVICENOW_TIMEOUT")  # ms
    log_level: str = Field(default="info", alias="LOG_LEVEL")
    incident_fields: str | None = Field(default=None, alias="SERVICENOW_INCIDENT_FIELDS")
    servicENow_api_base_path: str = Field(default="/api", alias="SERVICENOW_API_BASE_PATH")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def base_url(self) -> str:
        # Standard ServiceNow REST: https://instance.service-now.com/api/now
        base_path = self.servicENow_api_base_path.strip('/')
        return f"https://{self.servicENow_instance}/{base_path}/{self.servicENow_api_version}".rstrip('/')

    @property
    def incident_table_url(self) -> str:
        return f"{self.base_url}/table/incident"

    def get_incident_fields(self) -> List[str]:
        if self.incident_fields:
            return [f.strip() for f in self.incident_fields.split(',') if f.strip()]
        return [
            "number","short_description","priority","state","sys_created_on","sys_updated_on",
            "assignment_group","assigned_to","category","subcategory","caller_id"
        ]

@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore
