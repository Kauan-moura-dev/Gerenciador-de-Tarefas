"""
Gerenciador de Tarefas - Back-end
----------------------------------
API REST feita com Flask. Os dados são armazenados em um arquivo JSON
(tasks.json), conforme permitido no desafio.

Rotas disponíveis:
    GET    /tarefas          -> lista todas as tarefas (aceita ?ordenar_por=)
    POST   /tarefas          -> cria uma nova tarefa
    PATCH  /tarefas/<id>     -> altera status, titulo, descricao, prioridade e/ou data de vencimento
    DELETE /tarefas/<id>     -> exclui uma tarefa
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)  # permite que o front-end (rodando em outra porta) acesse a API

# Caminho do arquivo onde as tarefas ficam salvas
CAMINHO_DADOS = os.path.join(os.path.dirname(__file__), "tasks.json")

# Prioridades aceitas e seu peso para ordenação (quanto maior, mais prioritário)
PRIORIDADES_VALIDAS = ("Baixa", "Média", "Alta")
PESO_PRIORIDADE = {"Alta": 3, "Média": 2, "Baixa": 1}


def carregar_tarefas():
    """Lê o arquivo JSON e retorna a lista de tarefas."""
    if not os.path.exists(CAMINHO_DADOS):
        return []
    with open(CAMINHO_DADOS, "r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def salvar_tarefas(tarefas):
    """Escreve a lista de tarefas no arquivo JSON."""
    with open(CAMINHO_DADOS, "w", encoding="utf-8") as arquivo:
        json.dump(tarefas, arquivo, ensure_ascii=False, indent=2)


@app.route("/tarefas", methods=["GET"])
def listar_tarefas():
    """Retorna todas as tarefas cadastradas.

    Aceita o parâmetro opcional ?ordenar_por=prioridade ou ?ordenar_por=data_vencimento.
    Sem esse parâmetro, retorna na ordem em que foram cadastradas.
    """
    tarefas = carregar_tarefas()
    ordenar_por = request.args.get("ordenar_por")

    if ordenar_por == "prioridade":
        tarefas = sorted(
            tarefas, key=lambda t: PESO_PRIORIDADE.get(t.get("prioridade", "Média"), 2), reverse=True
        )
    elif ordenar_por == "data_vencimento":
        # Tarefas sem data de vencimento vão para o final da lista
        tarefas = sorted(
            tarefas, key=lambda t: (t.get("data_vencimento") is None, t.get("data_vencimento") or "")
        )

    return jsonify(tarefas), 200


@app.route("/tarefas", methods=["POST"])
def criar_tarefa():
    """Cria uma nova tarefa a partir do JSON enviado no corpo da requisição."""
    dados = request.get_json()

    if not dados or not dados.get("titulo"):
        return jsonify({"erro": "O campo 'titulo' é obrigatório."}), 400

    prioridade = dados.get("prioridade", "Média")
    if prioridade not in PRIORIDADES_VALIDAS:
        prioridade = "Média"

    tarefas = carregar_tarefas()

    novo_id = (max((t["id"] for t in tarefas), default=0)) + 1

    nova_tarefa = {
        "id": novo_id,
        "titulo": dados.get("titulo"),
        "descricao": dados.get("descricao", ""),
        "status": "Pendente",
        "prioridade": prioridade,
        "data_vencimento": dados.get("data_vencimento") or None,
    }

    tarefas.append(nova_tarefa)
    salvar_tarefas(tarefas)

    return jsonify(nova_tarefa), 201


@app.route("/tarefas/<int:tarefa_id>", methods=["PATCH"])
def atualizar_tarefa(tarefa_id):
    """Atualiza uma tarefa existente.

    Aceita, de forma independente:
    - status: define ou alterna Pendente/Concluída
    - titulo: novo título (não pode ser vazio)
    - descricao: nova descrição
    - prioridade: Baixa, Média ou Alta
    - data_vencimento: data no formato AAAA-MM-DD, ou null para remover
    """
    dados = request.get_json() or {}
    tarefas = carregar_tarefas()

    for tarefa in tarefas:
        if tarefa["id"] == tarefa_id:
            if "titulo" in dados:
                novo_titulo = dados.get("titulo", "").strip()
                if not novo_titulo:
                    return jsonify({"erro": "O campo 'titulo' não pode ficar vazio."}), 400
                tarefa["titulo"] = novo_titulo

            if "descricao" in dados:
                tarefa["descricao"] = dados.get("descricao", "")

            if "prioridade" in dados:
                nova_prioridade = dados.get("prioridade")
                if nova_prioridade in PRIORIDADES_VALIDAS:
                    tarefa["prioridade"] = nova_prioridade

            if "data_vencimento" in dados:
                tarefa["data_vencimento"] = dados.get("data_vencimento") or None

            if "status" in dados:
                novo_status = dados.get("status")
                if novo_status in ("Pendente", "Concluída"):
                    tarefa["status"] = novo_status
            elif len(dados) == 0:
                tarefa["status"] = (
                    "Concluída" if tarefa["status"] == "Pendente" else "Pendente"
                )

            salvar_tarefas(tarefas)
            return jsonify(tarefa), 200

    return jsonify({"erro": "Tarefa não encontrada."}), 404


@app.route("/tarefas/<int:tarefa_id>", methods=["DELETE"])
def excluir_tarefa(tarefa_id):
    """Remove uma tarefa da lista pelo id."""
    tarefas = carregar_tarefas()
    tarefas_restantes = [t for t in tarefas if t["id"] != tarefa_id]

    if len(tarefas_restantes) == len(tarefas):
        return jsonify({"erro": "Tarefa não encontrada."}), 404

    salvar_tarefas(tarefas_restantes)
    return jsonify({"mensagem": "Tarefa excluída com sucesso."}), 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)
