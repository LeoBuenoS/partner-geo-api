"""Composition root: o único lugar onde interface e infraestrutura se encontram.

Trocar PostGIS por outro banco se resolve aqui — nem o domínio nem os casos
de uso mudam.
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.use_cases import partners as casos
from app.infrastructure.config import settings
from app.infrastructure.db.postgres import get_db
from app.infrastructure.repositories.partner_memory import PartnerRepositorioMemoria
from app.infrastructure.repositories.partner_postgis import PartnerRepositorioPostGIS

# Estado do processo, usado só quando APP_REPOSITORIO=memory.
_memoria = PartnerRepositorioMemoria()


def repositorio(db: Session = Depends(get_db)):
    if settings.repositorio == "memory":
        return _memoria
    return PartnerRepositorioPostGIS(db)


def criar_parceiro(repo=Depends(repositorio)) -> casos.CriarParceiro:
    return casos.CriarParceiro(repo)


def obter_parceiro(repo=Depends(repositorio)) -> casos.ObterParceiro:
    return casos.ObterParceiro(repo)


def buscar_parceiro(repo=Depends(repositorio)) -> casos.BuscarParceiroMaisProximo:
    return casos.BuscarParceiroMaisProximo(repo)
