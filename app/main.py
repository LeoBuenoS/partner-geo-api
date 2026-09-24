"""Ponto de entrada: monta a aplicação a partir das camadas.

Dependência aponta só para dentro:
    interfaces → application → domain
    infrastructure → domain   (implementa as portas)
"""

from fastapi import FastAPI

from app.interfaces.http.errors import registrar_tratadores
from app.interfaces.http.routers import partners


def criar_app() -> FastAPI:
    app = FastAPI(
        title="Partner Geo API — parceiro mais próximo que cobre a localização",
        version="0.1.0",
    )

    registrar_tratadores(app)
    app.include_router(partners.router)

    @app.get("/health", tags=["health"])
    def health():
        return {"status": "ok"}

    return app


app = criar_app()
