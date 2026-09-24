#!/usr/bin/env python3
"""Revisão independente do diff por um modelo de outro fornecedor.

Por que existe: o código deste repositório é escrito com apoio do Claude. Uma
revisão feita pelo mesmo modelo que escreveu herda os mesmos pontos cegos.
O Gemini é de outro fornecedor, treinado de outro jeito — serve como segundo
canal de validação, independente por construção.

Só depende da biblioteca padrão: nada para instalar no CI.

Uso:
    gemini_review.py --base origin/main --head HEAD --saida revisao.md
    gemini_review.py --dry-run          # testa o encanamento sem chave nem rede
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

API_RAIZ = "https://generativelanguage.googleapis.com/v1beta"
TIMEOUT_S = 180

# Limite de caracteres do diff enviado. Diff gigante estoura contexto e degrada
# a revisão; acima disso, trunca e avisa no relatório.
LIMITE_DO_DIFF = 120_000

# Severidades, da mais grave para a mais leve. Só a primeira reprova o CI.
SEVERIDADES = ("blocker", "major", "minor", "nit")
SEVERIDADE_QUE_REPROVA = "blocker"

EMOJI = {"blocker": "🔴", "major": "🟠", "minor": "🟡", "nit": "🔵"}

INSTRUCOES = """\
Você é um revisor de código sênior e cético. Revise o diff abaixo e reporte
apenas defeitos que você consegue justificar com um cenário concreto de falha.

Classifique cada achado em uma severidade:

- "blocker": defeito que causa comportamento incorreto, perda de dados, falha
  em produção ou vulnerabilidade de segurança. Exige um cenário concreto
  (entrada/estado -> resultado errado). Na dúvida, NÃO use blocker.
- "major": bug provável, contrato violado ou caso de borda não tratado, sem a
  certeza do blocker.
- "minor": problema real, mas de impacto limitado.
- "nit": estilo, nomenclatura, preferência pessoal.

Regras:
- Não reporte ausência de testes como blocker.
- Não reporte preferência de estilo como blocker ou major.
- Não invente problema para ter o que reportar: lista vazia é uma resposta
  legítima e esperada quando o diff está correto.
- Cada achado precisa de arquivo e, quando possível, linha.
- Responda em português.

Responda SOMENTE com um objeto JSON, sem cercas de código, neste formato:

{
  "resumo": "uma frase sobre o que o diff faz e a qualidade geral",
  "achados": [
    {
      "severidade": "blocker|major|minor|nit",
      "arquivo": "caminho/do/arquivo.py",
      "linha": 42,
      "titulo": "frase curta",
      "descricao": "o defeito",
      "cenario_de_falha": "entrada/estado concreto -> resultado errado"
    }
  ]
}
"""


# --- git --------------------------------------------------------------------


def obter_diff(base: str, head: str) -> tuple[str, bool]:
    """Devolve (diff, foi_truncado)."""
    try:
        diff = subprocess.run(
            ["git", "diff", "--unified=3", f"{base}...{head}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError:
        # `...` exige ancestral comum; num push isolado ele pode não existir.
        diff = subprocess.run(
            ["git", "diff", "--unified=3", base, head],
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    if len(diff) > LIMITE_DO_DIFF:
        return diff[:LIMITE_DO_DIFF], True
    return diff, False


# --- API --------------------------------------------------------------------


def _requisitar(url: str, chave: str, corpo: dict | None = None) -> dict:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    requisicao = urllib.request.Request(
        url,
        data=dados,
        headers={"x-goog-api-key": chave, "Content-Type": "application/json"},
        method="POST" if corpo is not None else "GET",
    )
    with urllib.request.urlopen(requisicao, timeout=TIMEOUT_S) as resposta:
        return json.loads(resposta.read().decode())


ESPECIALIZADOS = ("embedding", "image", "vision", "tts", "aqa", "live", "native-audio")
MAXIMO_DE_CANDIDATOS = 4

# Sobrecarga e cota são transitórios: vale reesperar no mesmo modelo antes de
# desistir dele. 404 não é transitório — o modelo saiu e não volta.
TRANSITORIOS = (429, 503)
TENTATIVAS_POR_MODELO = 2
ESPERA_ENTRE_TENTATIVAS_S = 3


def _pontuar(nome: str) -> tuple:
    """Ordena candidatos: capacidade, depois versão, depois estabilidade.

    Capacidade vem primeiro porque a tarefa é revisar código: um "pro" de
    versão anterior revisa melhor que um "flash" mais novo. Estabilidade vem
    por último — o estável de hoje é o aposentado de amanhã, e foi assim que a
    primeira execução falhou, com 404 num "pro" que já tinha saído. Hoje isso
    não trava mais: quem chama tenta o próximo candidato.
    """
    if any(t in nome for t in ESPECIALIZADOS):
        return (-1, 0.0, 0)
    capacidade = 2 if "pro" in nome else (1 if "flash" in nome else 0)
    casado = re.search(r"gemini-(\d+(?:\.\d+)?)", nome)
    versao = float(casado.group(1)) if casado else 0.0
    estavel = 0 if any(t in nome for t in ("preview", "exp")) else 1
    return (capacidade, versao, estavel)


def candidatos_de_modelo(chave: str, preferido: str | None) -> list[str]:
    """Modelos a tentar, do melhor para o pior.

    Nome cravado no código envelhece e quebra o CI sem aviso, então a lista vem
    da própria conta. Mas `ListModels` também devolve modelos aposentados, que
    o `generateContent` recusa — por isso é uma LISTA, e não uma escolha só:
    quem chama tenta o próximo quando um 404 diz que o modelo saiu.
    """
    resposta = _requisitar(f"{API_RAIZ}/models", chave)
    disponiveis = [
        m["name"].removeprefix("models/")
        for m in resposta.get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]
    if not disponiveis:
        raise RuntimeError("nenhum modelo com generateContent nesta conta")

    if preferido:
        if preferido not in disponiveis:
            raise RuntimeError(
                f"GEMINI_MODEL={preferido!r} não está disponível. "
                f"Disponíveis: {', '.join(sorted(disponiveis))}"
            )
        return [preferido]  # escolha explícita manda, sem fallback

    ordenados = [n for n in sorted(disponiveis, key=_pontuar, reverse=True)
                 if _pontuar(n)[0] >= 0]
    if not ordenados:
        raise RuntimeError(
            f"nenhum modelo de texto adequado. Disponíveis: {', '.join(disponiveis)}"
        )
    return ordenados[:MAXIMO_DE_CANDIDATOS]


def _extrair_json(texto: str) -> dict:
    """Tolera cercas de código e texto solto em volta do JSON."""
    limpo = texto.strip()
    if limpo.startswith("```"):
        limpo = re.sub(r"^```[a-zA-Z]*\n?", "", limpo)
        limpo = re.sub(r"\n?```$", "", limpo.strip())
    try:
        return json.loads(limpo)
    except json.JSONDecodeError:
        inicio, fim = limpo.find("{"), limpo.rfind("}")
        if inicio == -1 or fim <= inicio:
            raise
        return json.loads(limpo[inicio : fim + 1])


def revisar(chave: str, candidatos: list[str], diff: str) -> tuple[dict, str]:
    """Tenta cada candidato; um 404 significa modelo aposentado, então segue."""
    corpo = {
        "contents": [{"parts": [{"text": f"{INSTRUCOES}\n\n--- DIFF ---\n{diff}"}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }

    ultimo_erro = None
    for modelo in candidatos:
        for tentativa in range(1, TENTATIVAS_POR_MODELO + 1):
            try:
                resposta = _requisitar(
                    f"{API_RAIZ}/models/{modelo}:generateContent", chave, corpo
                )
            except urllib.error.HTTPError as erro:
                ultimo_erro = f"HTTP {erro.code}: {erro.read().decode()[:200]}"

                # 400 é erro de requisição — problema nosso. Sobe na hora, em
                # vez de ficar mascarado por uma varredura da lista inteira.
                if erro.code not in (404, *TRANSITORIOS):
                    raise

                if erro.code == 404:
                    print(f"::notice::{modelo} aposentado, tentando o próximo")
                    break  # não adianta reesperar: não volta

                if tentativa < TENTATIVAS_POR_MODELO:
                    print(f"::notice::{modelo} sobrecarregado, reesperando")
                    time.sleep(ESPERA_ENTRE_TENTATIVAS_S)
                    continue

                print(f"::notice::{modelo} segue sobrecarregado, tentando outro")
                break
            else:
                return _interpretar(resposta), modelo

    raise RuntimeError(
        f"nenhum modelo aceitou a requisição ({', '.join(candidatos)}): {ultimo_erro}"
    )


def _interpretar(resposta: dict) -> dict:
    candidatos = resposta.get("candidates") or []
    if not candidatos:
        # Normalmente é bloqueio por filtro de segurança.
        raise RuntimeError(f"resposta sem candidates: {json.dumps(resposta)[:500]}")

    partes = candidatos[0].get("content", {}).get("parts") or []
    texto = "".join(p.get("text", "") for p in partes)
    if not texto.strip():
        raise RuntimeError("resposta vazia do modelo")
    return _extrair_json(texto)


# --- relatório --------------------------------------------------------------


def _normalizar(resultado: dict) -> list[dict]:
    achados = resultado.get("achados")
    if not isinstance(achados, list):
        return []

    validos = []
    for achado in achados:
        if not isinstance(achado, dict):
            continue
        severidade = str(achado.get("severidade", "")).lower().strip()
        if severidade not in SEVERIDADES:
            severidade = "minor"  # severidade desconhecida não vira blocker
        # Blocker sem cenário concreto de falha não é blocker: é opinião.
        if severidade == SEVERIDADE_QUE_REPROVA and not str(
            achado.get("cenario_de_falha", "")
        ).strip():
            severidade = "major"
        validos.append({**achado, "severidade": severidade})
    return validos


def montar_markdown(resultado: dict, modelo: str, truncado: bool) -> str:
    achados = _normalizar(resultado)
    contagem = {s: sum(1 for a in achados if a["severidade"] == s) for s in SEVERIDADES}

    linhas = [
        "## 🔎 Revisão independente (Gemini)",
        "",
        f"_Segundo canal de validação, de outro fornecedor. Modelo: `{modelo}`._",
        "",
    ]
    if resumo := str(resultado.get("resumo", "")).strip():
        linhas += [f"> {resumo}", ""]
    if truncado:
        linhas += [
            f"⚠️ O diff excedeu {LIMITE_DO_DIFF:,} caracteres e foi truncado; "
            "a revisão cobriu apenas o começo.",
            "",
        ]

    if not achados:
        linhas.append("✅ Nenhum achado.")
        return "\n".join(linhas)

    placar = " · ".join(
        f"{EMOJI[s]} {contagem[s]} {s}" for s in SEVERIDADES if contagem[s]
    )
    linhas += [placar, ""]

    ordem = {s: i for i, s in enumerate(SEVERIDADES)}
    for achado in sorted(achados, key=lambda a: ordem[a["severidade"]]):
        local = str(achado.get("arquivo", "?"))
        if linha := achado.get("linha"):
            local += f":{linha}"
        linhas += [
            f"### {EMOJI[achado['severidade']]} {achado['severidade']} — "
            f"{achado.get('titulo', 'sem título')}",
            f"`{local}`",
            "",
            str(achado.get("descricao", "")).strip(),
        ]
        if cenario := str(achado.get("cenario_de_falha", "")).strip():
            linhas += ["", f"**Como falha:** {cenario}"]
        linhas.append("")

    if contagem[SEVERIDADE_QUE_REPROVA]:
        linhas += [
            "---",
            "",
            "🔴 **Este job reprova por achado `blocker`.** Se for falso positivo, "
            "aplique a etiqueta `gemini-override` no PR e rode de novo.",
        ]
    return "\n".join(linhas)


def decidir_saida(resultado: dict, override: bool) -> int:
    bloqueadores = [
        a for a in _normalizar(resultado) if a["severidade"] == SEVERIDADE_QUE_REPROVA
    ]
    if not bloqueadores:
        return 0
    if override:
        print(
            f"::warning::{len(bloqueadores)} achado(s) blocker ignorado(s) "
            "por etiqueta gemini-override"
        )
        return 0
    for achado in bloqueadores:
        print(
            f"::error file={achado.get('arquivo', '')}::"
            f"{achado.get('titulo', 'achado blocker')}"
        )
    return 1


# --- entrada ----------------------------------------------------------------


RESULTADO_DE_TESTE = {
    "resumo": "Execução de teste: nenhuma chamada de rede foi feita.",
    "achados": [
        {
            "severidade": "minor",
            "arquivo": "exemplo.py",
            "linha": 1,
            "titulo": "Achado de exemplo",
            "descricao": "Serve para conferir o encanamento do relatório.",
            "cenario_de_falha": "",
        }
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--saida", default="revisao-gemini.md")
    parser.add_argument(
        "--override",
        action="store_true",
        help="não reprova mesmo com achado blocker (etiqueta de escape)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="gera um relatório de exemplo, sem chave e sem rede",
    )
    args = parser.parse_args()

    if args.dry_run:
        markdown = montar_markdown(RESULTADO_DE_TESTE, "dry-run", truncado=False)
        print(markdown)
        return 0

    chave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not chave:
        raise SystemExit("GEMINI_API_KEY não definida")

    diff, truncado = obter_diff(args.base, args.head)
    if not diff.strip():
        print("Nenhuma mudança de código para revisar.")
        return 0

    candidatos = candidatos_de_modelo(
        chave, os.environ.get("GEMINI_MODEL", "").strip() or None
    )
    print(f"Candidatos: {', '.join(candidatos)} ({len(diff):,} caracteres de diff)")

    resultado, modelo = revisar(chave, candidatos, diff)
    print(f"Revisado por {modelo}")
    markdown = montar_markdown(resultado, modelo, truncado)

    with open(args.saida, "w", encoding="utf-8") as arquivo:
        arquivo.write(markdown)
    print(markdown)

    return decidir_saida(resultado, args.override)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as erro:
        # Falha de infraestrutura (rede, cota, chave, filtro) NÃO é defeito do
        # código e não deve travar o merge de todo mundo. Fica visível como
        # aviso; o gate continua valendo só para achado blocker de verdade.
        detalhe = erro.read().decode()[:500] if hasattr(erro, "read") else str(erro)
        print(f"::warning::revisão do Gemini indisponível: {detalhe}")
        sys.exit(0)
