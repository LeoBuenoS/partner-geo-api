# ADR-0003 — Clean Architecture com portas e adaptadores

**Status:** Aceita · **Data:** 2026-09 · **Contexto TOGAF:** Fase C (Aplicação)

## Contexto

O desafio avalia **manutenibilidade** ("quão fácil é adicionar novas
funcionalidades"), **testabilidade** e **separação de conceitos** como três dos
cinco critérios. Um projeto com a query PostGIS dentro do controller atende ao
requisito funcional e falha nos três.

## Decisão

Quatro camadas, dependência sempre para dentro:

```
interfaces/http  →  application/use_cases  →  domain
infrastructure   →  domain (implementa as portas)
```

- `domain/`: geometria, entidade `Partner`, erros de negócio e a porta
  `PartnerRepositorio` (um `typing.Protocol`).
- `application/`: uma classe por operação do desafio.
- `infrastructure/`: adaptadores PostGIS e memória, configuração.
- `interfaces/http/`: routers finos, schemas no contrato do desafio
  (camelCase) e o composition root em `deps.py`.

## Consequências

**A favor**

- Adicionar funcionalidade é adicionar caso de uso, não alterar o que existe.
- Trocar o adaptador é mudar uma linha no composition root.
- O contrato externo em camelCase não contamina o domínio, que usa
  `snake_case`: a conversão fica nos schemas.
- Os erros de domínio viram status HTTP num lugar único.

**Contra**

- Mais arquivos e uma indireção a mais do que uma API CRUD de três endpoints
  exigiria. É proporcional aos critérios de avaliação, não ao tamanho do
  código.
- Conversão entre linha do banco e entidade escrita à mão.

## Nota sobre ordem de rotas

`GET /partners/search` é declarada **antes** de `GET /partners/{partner_id}`.
O FastAPI resolve rotas na ordem de registro: invertidas, `/partners/search`
seria capturada como um parceiro de id `"search"`. Está comentado no código e
coberto por teste.
