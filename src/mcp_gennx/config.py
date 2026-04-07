from pydantic_settings import BaseSettings


class GennxSettings(BaseSettings):
    gennx_api_base_url: str = "http://localhost:8080"
    gennx_api_timeout: float = 30.0
    gennx_mapi_key: str = ""
    toolsets: str = "default"
    read_only: bool = False
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_prefix": ""}
