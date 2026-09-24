"""Contrato HTTP das três operações do desafio."""

from tests.integration.conftest import AREA_UNITARIA, PAYLOAD


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_criar_devolve_201_com_os_campos_do_desafio(client):
    resposta = client.post("/partners", json=PAYLOAD)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["id"]
    assert corpo["tradingName"] == PAYLOAD["tradingName"]
    assert corpo["ownerName"] == PAYLOAD["ownerName"]
    assert corpo["document"] == PAYLOAD["document"]
    assert corpo["coverageArea"] == AREA_UNITARIA
    assert corpo["address"] == PAYLOAD["address"]


def test_criar_aceita_id_informado(client):
    resposta = client.post("/partners", json={**PAYLOAD, "id": "parceiro-1"})

    assert resposta.status_code == 201
    assert resposta.json()["id"] == "parceiro-1"


def test_documento_duplicado_devolve_409(client):
    client.post("/partners", json=PAYLOAD)

    assert client.post("/partners", json=PAYLOAD).status_code == 409


def test_geometria_invalida_devolve_422(client):
    invalido = {**PAYLOAD, "coverageArea": {"type": "Point", "coordinates": [0, 0]}}

    assert client.post("/partners", json=invalido).status_code == 422


def test_obter_por_id(client):
    criado = client.post("/partners", json=PAYLOAD).json()

    resposta = client.get(f"/partners/{criado['id']}")

    assert resposta.status_code == 200
    assert resposta.json() == criado


def test_obter_inexistente_devolve_404(client):
    assert client.get("/partners/nao-existe").status_code == 404


def test_busca_devolve_o_mais_proximo_que_cobre(client):
    area_grande = {
        "type": "MultiPolygon",
        "coordinates": [[[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]],
    }
    longe = client.post(
        "/partners",
        json={
            **PAYLOAD,
            "document": "longe/0001",
            "coverageArea": area_grande,
            "address": {"type": "Point", "coordinates": [1.9, 1.9]},
        },
    ).json()
    perto = client.post(
        "/partners",
        json={
            **PAYLOAD,
            "document": "perto/0001",
            "coverageArea": area_grande,
            "address": {"type": "Point", "coordinates": [0.55, 0.55]},
        },
    ).json()

    resposta = client.get("/partners/search", params={"lon": 0.5, "lat": 0.5})

    assert resposta.status_code == 200
    assert resposta.json()["id"] == perto["id"]
    assert resposta.json()["id"] != longe["id"]


def test_busca_sem_cobertura_devolve_404(client):
    client.post("/partners", json=PAYLOAD)

    assert (
        client.get("/partners/search", params={"lon": 50, "lat": 50}).status_code == 404
    )


def test_busca_com_coordenada_fora_do_intervalo_devolve_422(client):
    assert (
        client.get("/partners/search", params={"lon": 200, "lat": 0}).status_code == 422
    )
