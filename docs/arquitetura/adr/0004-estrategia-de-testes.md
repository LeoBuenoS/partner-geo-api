# ADR-0004 — Pirâmide de testes, com o banco real num job à parte

**Status:** Aceita · **Data:** 2026-09 · **Contexto TOGAF:** Fase D

## Contexto

Depender do PostGIS para rodar qualquer teste é o caminho mais curto para
ninguém rodar teste antes de commitar. Testar só com adaptador em memória
esconde o que é específico do banco: `ST_Covers` na fronteira, distância em
metros, uso do índice.

## Decisão

| Nível | Pasta | Dependências | O que prova |
|-------|-------|--------------|-------------|
| Unidade (domínio) | `tests/unit/test_geo.py` | nenhuma | Ponto-em-polígono, buracos, validação GeoJSON, distância |
| Unidade (aplicação) | `tests/unit/test_casos_de_uso.py` | nenhuma | Filtro antes da ordenação, unicidade, erros |
| Integração (API) | `tests/integration/` | nenhuma | Contrato HTTP e status codes |
| Integração (banco) | `tests/db/` | PostGIS | Fronteira, metros, índice, **paridade** |

`tests/db/` é marcado com `@pytest.mark.db` e **pula sozinho** sem
`TEST_POSTGRES_URL`. No CI, um job dedicado sobe o PostGIS como *service*.

## O teste que mais importa: paridade

`test_paridade_com_a_regra_de_dominio` popula o adaptador em memória e o
PostGIS com a mesma base, sorteia 50 pontos com **semente fixa** (falha
reproduzível) e exige que os dois devolvam o mesmo parceiro. É o que impede
que a otimização no banco mude silenciosamente a regra de negócio.

## Sobre o piso de cobertura

O job rápido exige 90%, não 95%. O que falta para 95% é exatamente o adaptador
PostGIS, que não é exercitado sem banco — e é coberto no outro job.

A alternativa seria excluir esse arquivo da medição e exibir um número maior.
Seria esconder o dado. O piso menor, com a razão escrita aqui e no CI, diz a
verdade sobre o que o job rápido realmente cobre.

## Consequências

**A favor**

- `make test` roda a suíte inteira em segundos, sem Docker.
- A regra central é testada sem simular HTTP nem banco.
- O que só o banco prova continua testado, num job separado.

**Contra**

- Duas configurações de teste para manter.
- O adaptador em memória pode divergir do real — mitigado pelo teste de
  paridade, que é a razão de ele existir.
- O job com banco é mais lento e pode falhar por infraestrutura.
