# 05 — Lacunas e roadmap (Fases E e F)

Este repositório é um **esqueleto funcional**: as três operações do desafio
rodam fim a fim, com testes. O que ainda não existe está listado aqui, porque
lacuna registrada é decisão, e lacuna omitida é dívida escondida.

## Lacunas

| # | Lacuna | Risco | Esforço |
|---|--------|-------|---------|
| L1 | Sem autenticação: qualquer um cadastra parceiro | Alto | Baixo |
| L2 | Sem atualizar nem remover parceiro (o desafio não pede, a operação vai pedir) | Médio | Baixo |
| L3 | Sem carga em massa: cadastrar milhares de parceiros exige um request por parceiro | Médio | Baixo |
| L4 | `GET /partners/search` devolve um só parceiro; a operação costuma querer os N mais próximos | Médio | Baixo |
| L5 | Sem medição de latência sob carga — o `EXPLAIN` prova o índice, não o tempo | Médio | Médio |
| L6 | Ray casting do domínio não trata anti-meridiano nem geodésicas | Baixo | Médio |
| L7 | Sem observabilidade: log estruturado, métricas, tracing | Médio | Médio |
| L8 | `/health` não verifica o banco — responde ok com o PostGIS fora | Médio | Baixo |
| L9 | Sem cache para pontos consultados com frequência | Baixo | Médio |
| L10 | Sem paginação nem listagem de parceiros | Baixo | Baixo |

## Roadmap

### Incremento 1 — completar o CRUD e proteger a escrita

- **L2**: `PUT` e `DELETE`, com os mesmos cuidados de unicidade.
- **L1**: autenticação nos endpoints de escrita, leitura pública.
- **L8**: `/health` com checagem real do PostGIS.

### Incremento 2 — escala de dados

- **L3**: endpoint de carga em massa com `COPY`, que é a via rápida do
  PostgreSQL para volume.
- **L4**: parâmetro `limit` na busca, devolvendo os N mais próximos.
- **L5**: script de carga (100 mil parceiros) medindo p50/p95 da busca, com o
  resultado no README — é o que dá substância ao critério de performance.

### Incremento 3 — operação

- **L7**: log estruturado com correlation id e métricas Prometheus.
- **L9**: cache por célula geográfica (geohash) para consultas repetidas.
- **L6**: substituir o ray casting por uma biblioteca geodésica se o domínio
  passar a cruzar o anti-meridiano.

## Princípio para a evolução

Nada acima exige reescrever o domínio. Autenticação entra como dependência na
interface, carga em massa como método novo no adaptador, cache como decorador
de porta. É o teste real da separação em camadas.
