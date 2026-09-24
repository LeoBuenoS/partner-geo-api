"""Tradução de erro de domínio para HTTP, num lugar só."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain.errors import (
    ConflitoDeDados,
    DadosInvalidos,
    ErroDeDominio,
    RecursoNaoEncontrado,
)

STATUS_POR_ERRO: dict[type[ErroDeDominio], int] = {
    RecursoNaoEncontrado: status.HTTP_404_NOT_FOUND,
    ConflitoDeDados: status.HTTP_409_CONFLICT,
    DadosInvalidos: status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def registrar_tratadores(app: FastAPI) -> None:
    @app.exception_handler(ErroDeDominio)
    async def tratar_erro_de_dominio(_: Request, erro: ErroDeDominio) -> JSONResponse:
        codigo = STATUS_POR_ERRO.get(type(erro), status.HTTP_400_BAD_REQUEST)
        return JSONResponse(status_code=codigo, content={"detail": str(erro)})
