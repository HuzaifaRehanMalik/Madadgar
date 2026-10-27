from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    database_url: str
    gemini_api_key: str
    whatsapp_verify_token: str
    whatsapp_access_token: str
    whatsapp_phone_number_id: str
    whatsapp_app_secret: str
    graph_version: str = "v21.0"   # check Meta's docs for the current version

settings = Settings()