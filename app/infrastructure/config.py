from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração da infraestrutura, lida do .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "partners"
    postgres_user: str = "app"
    postgres_password: str = "change-me"

    # "postgis" usa o banco; "memory" sobe a API sem dependência externa,
    # útil para uma demonstração rápida e para os testes de integração.
    repositorio: str = "postgis"

    app_env: str = "development"

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
