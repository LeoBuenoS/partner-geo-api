"""As três operações do desafio, como endpoints REST."""

from fastapi import APIRouter, Depends, Query, status

from app.application.use_cases import partners as casos
from app.domain.geo import Ponto
from app.interfaces.http import deps
from app.interfaces.http.schemas.partner import PartnerIn, PartnerOut

router = APIRouter(prefix="/partners", tags=["partners"])


@router.post("", response_model=PartnerOut, status_code=status.HTTP_201_CREATED)
def criar(
    payload: PartnerIn,
    caso: casos.CriarParceiro = Depends(deps.criar_parceiro),
):
    """1.1 — Criar parceiro."""
    return PartnerOut.de_entidade(caso.executar(payload.para_entidade()))


@router.get("/search", response_model=PartnerOut)
def buscar(
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    caso: casos.BuscarParceiroMaisProximo = Depends(deps.buscar_parceiro),
):
    """1.3 — Parceiro mais próximo cuja área de cobertura inclui o ponto.

    Declarada antes de `/{partner_id}` de propósito: o FastAPI resolve as
    rotas em ordem, e `/search` cairia na rota de id se viesse depois.
    """
    return PartnerOut.de_entidade(caso.executar(Ponto(longitude=lon, latitude=lat)))


@router.get("/{partner_id}", response_model=PartnerOut)
def obter(
    partner_id: str,
    caso: casos.ObterParceiro = Depends(deps.obter_parceiro),
):
    """1.2 — Carregar parceiro pelo id."""
    return PartnerOut.de_entidade(caso.executar(partner_id))
