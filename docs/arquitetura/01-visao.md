# 01 — Visão da arquitetura (Fase Preliminar + Fase A)

## Escopo

Serviço que mantém o cadastro de parceiros com sua **área de cobertura** e
responde, para uma coordenada qualquer, qual parceiro atende aquele ponto.

Fora do escopo: pedidos, pagamento, catálogo de produtos, roteirização.

## Stakeholders e suas preocupações

| Stakeholder | Preocupação | Como a arquitetura responde |
|-------------|-------------|------------------------------|
| Consumidor | Saber quem entrega no seu endereço | `GET /partners/search` filtra por cobertura antes de ordenar por distância |
| Operação comercial | Cadastrar parceiros e suas áreas sem duplicar | `document` e `id` únicos, garantidos no caso de uso e no índice do banco |
| Plataforma | Resposta rápida com a base crescendo | Índice GIST; a busca é uma consulta, não uma varredura |
| Pessoa desenvolvedora | Mudar sem medo | Clean Architecture, regra geométrica testável sem banco, CI bloqueando regressão |

## Princípios

1. **A regra geométrica é de negócio, não de banco.** Ela vive no domínio e é
   testável sem infraestrutura — ver [ADR-0002](adr/0002-regra-geometrica-no-dominio.md).
2. **O banco executa a regra em escala, sem redefini-la.** A equivalência é
   verificada por teste de paridade.
3. **Distância se mede em metros**, nunca em graus — ver
   [ADR-0001](adr/0001-postgis-geography.md).
4. **Dependência aponta para dentro.** Infraestrutura depende do domínio.
5. **O que não tem teste não está pronto.** Cobertura verificada no CI.

## Requisitos

### Funcionais (numerados como no desafio)

| ID | Requisito | Onde |
|----|-----------|------|
| RF-1.1 | Criar parceiro com `id` e `document` únicos, `coverageArea` MultiPolygon e `address` Point | `CriarParceiro` |
| RF-1.2 | Carregar parceiro por `id`, com todos os campos | `ObterParceiro` |
| RF-1.3 | Dada uma coordenada, devolver o parceiro mais próximo **entre os que cobrem** o ponto | `BuscarParceiroMaisProximo` |

### Não funcionais

| ID | Requisito | Verificação |
|----|-----------|-------------|
| RNF-01 | Busca resolvida por índice, não por varredura | `test_busca_usa_o_indice_gist` (lê o `EXPLAIN`) |
| RNF-02 | A regra no banco e no domínio dão a mesma resposta | `test_paridade_com_a_regra_de_dominio` (50 pontos sorteados) |
| RNF-03 | Ponto na fronteira conta como coberto | `test_fronteira_conta_como_coberta` |
| RNF-04 | Geometria malformada é rejeitada com 422 | `tests/unit/test_geo.py`, `test_geometria_invalida_devolve_422` |
| RNF-05 | Projeto multiplataforma, roda com um comando | `Dockerfile` + `docker-compose.yml` |
| RNF-06 | Suíte roda sem serviço externo | `tests/unit/`, `tests/integration/` |
