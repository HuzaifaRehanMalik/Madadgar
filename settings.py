from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    gemini_api_key: str

    # "qr" = link your own WhatsApp by scanning a QR code (neonize)
    # "cloud" = official WhatsApp Cloud API webhook (needs the tokens below)
    whatsapp_mode: str = "qr"

    # Set OWNER_PHONE in .env: WhatsApp number(s) that get an alert when a call is booked.
    # Country code, digits only; separate several numbers with commas.
    owner_phone: str = ""

    # When you take calls (Pakistan time). The bot only books free slots inside these hours.
    call_days: str = "Mon,Tue,Wed,Thu,Fri,Sat"
    call_start_hour: int = 10
    call_end_hour: int = 19
    call_minutes: int = 30

    # Optional: only for the official WhatsApp Cloud API
    whatsapp_verify_token: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_app_secret: str = ""
    graph_version: str = "v21.0"

settings = Settings()