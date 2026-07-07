"""
Testes automatizados da API do Gerenciador de Tarefas.

Cobrem o fluxo principal de cada rota (criar, listar, editar, excluir),
além de validações básicas. Cada teste usa um arquivo tasks.json temporário
e isolado, para não interferir nos dados reais da aplicação.
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as app_module


@pytest.fixture
def client():
    """Cria um cliente de teste do Flask com um arquivo de dados temporário."""
    arquivo_temp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    arquivo_temp.write(b"[]")
    arquivo_temp.close()

    caminho_original = app_module.CAMINHO_DADOS
    app_module.CAMINHO_DADOS = arquivo_temp.name

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as cliente_teste:
        yield cliente_teste

    app_module.CAMINHO_DADOS = caminho_original
    os.unlink(arquivo_temp.name)


def test_listar_tarefas_vazio(client):
    """GET /tarefas deve retornar uma lista vazia quando não há tarefas."""
    resposta = client.get("/tarefas")
    assert resposta.status_code == 200
    assert resposta.get_json() == []


def test_criar_tarefa(client):
    """POST /tarefas deve criar uma tarefa com os valores padrão corretos."""
    resposta = client.post("/tarefas", json={"titulo": "Estudar Flask", "descricao": "Rever rotas"})
    dados = resposta.get_json()

    assert resposta.status_code == 201
    assert dados["titulo"] == "Estudar Flask"
    assert dados["status"] == "Pendente"
    assert dados["prioridade"] == "Média"
    assert dados["data_vencimento"] is None


def test_criar_tarefa_sem_titulo_retorna_erro(client):
    """POST /tarefas sem título deve retornar 400."""
    resposta = client.post("/tarefas", json={"descricao": "Sem titulo"})
    assert resposta.status_code == 400


def test_criar_tarefa_com_prioridade_e_data(client):
    """POST /tarefas deve aceitar prioridade e data de vencimento customizadas."""
    resposta = client.post(
        "/tarefas",
        json={"titulo": "Tarefa urgente", "prioridade": "Alta", "data_vencimento": "2026-07-08"},
    )
    dados = resposta.get_json()

    assert dados["prioridade"] == "Alta"
    assert dados["data_vencimento"] == "2026-07-08"


def test_alterar_status(client):
    """PATCH /tarefas/<id> deve alternar o status quando nada é enviado."""
    criada = client.post("/tarefas", json={"titulo": "Tarefa"}).get_json()

    resposta = client.patch(f"/tarefas/{criada['id']}", json={})
    dados = resposta.get_json()

    assert resposta.status_code == 200
    assert dados["status"] == "Concluída"


def test_editar_titulo_e_descricao(client):
    """PATCH /tarefas/<id> deve atualizar título e descrição."""
    criada = client.post("/tarefas", json={"titulo": "Titulo antigo"}).get_json()

    resposta = client.patch(
        f"/tarefas/{criada['id']}",
        json={"titulo": "Titulo novo", "descricao": "Descricao nova"},
    )
    dados = resposta.get_json()

    assert dados["titulo"] == "Titulo novo"
    assert dados["descricao"] == "Descricao nova"


def test_editar_titulo_vazio_retorna_erro(client):
    """PATCH /tarefas/<id> com título vazio deve retornar 400."""
    criada = client.post("/tarefas", json={"titulo": "Titulo"}).get_json()

    resposta = client.patch(f"/tarefas/{criada['id']}", json={"titulo": "   "})
    assert resposta.status_code == 400


def test_editar_tarefa_inexistente_retorna_404(client):
    """PATCH /tarefas/<id> com id inexistente deve retornar 404."""
    resposta = client.patch("/tarefas/9999", json={"status": "Concluída"})
    assert resposta.status_code == 404


def test_excluir_tarefa(client):
    """DELETE /tarefas/<id> deve remover a tarefa da lista."""
    criada = client.post("/tarefas", json={"titulo": "Tarefa a excluir"}).get_json()

    resposta = client.delete(f"/tarefas/{criada['id']}")
    assert resposta.status_code == 200

    lista = client.get("/tarefas").get_json()
    assert lista == []


def test_excluir_tarefa_inexistente_retorna_404(client):
    """DELETE /tarefas/<id> com id inexistente deve retornar 404."""
    resposta = client.delete("/tarefas/9999")
    assert resposta.status_code == 404


def test_ordenar_por_prioridade(client):
    """GET /tarefas?ordenar_por=prioridade deve ordenar da mais alta para a mais baixa."""
    client.post("/tarefas", json={"titulo": "Baixa", "prioridade": "Baixa"})
    client.post("/tarefas", json={"titulo": "Alta", "prioridade": "Alta"})
    client.post("/tarefas", json={"titulo": "Media", "prioridade": "Média"})

    resposta = client.get("/tarefas?ordenar_por=prioridade")
    titulos = [t["titulo"] for t in resposta.get_json()]

    assert titulos == ["Alta", "Media", "Baixa"]


def test_ordenar_por_data_vencimento(client):
    """GET /tarefas?ordenar_por=data_vencimento deve colocar tarefas sem data por ultimo."""
    client.post("/tarefas", json={"titulo": "Sem data"})
    client.post("/tarefas", json={"titulo": "Vence depois", "data_vencimento": "2026-07-20"})
    client.post("/tarefas", json={"titulo": "Vence primeiro", "data_vencimento": "2026-07-08"})

    resposta = client.get("/tarefas?ordenar_por=data_vencimento")
    titulos = [t["titulo"] for t in resposta.get_json()]

    assert titulos == ["Vence primeiro", "Vence depois", "Sem data"]
