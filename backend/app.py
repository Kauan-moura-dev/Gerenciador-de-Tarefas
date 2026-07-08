"""
Gerenciador de Tarefas - Back-end
----------------------------------
API REST feita com Flask. Os dados são armazenados em um banco SQLite
(tarefas.db), com suporte a múltiplos usuários autenticados por token.

Rotas disponíveis:
    POST   /auth/registrar           -> cria uma conta e retorna um token
    POST   /auth/login               -> autentica e retorna um token
    POST   /auth/logout              -> encerra a sessão atual
    GET    /auth/eu                  -> dados do usuário autenticado

    GET    /tarefas                  -> lista as tarefas do usuário (aceita filtros)
    POST   /tarefas                  -> cria uma nova tarefa
    PATCH  /tarefas/<id>             -> edita campos e/ou o status de uma tarefa
    DELETE /tarefas/<id>             -> exclui uma tarefa

    POST   /tarefas/<id>/subtarefas  -> adiciona uma subtarefa
    PATCH  /subtarefas/<id>          -> edita/alterna uma subtarefa
    DELETE /subtarefas/<id>          -> exclui uma subtarefa

    POST   /tarefas/sugestao         -> sugere prioridade e categoria (IA/heurística)
    POST   /chat                     -> chatbot XCL Help (IA com fallback de regras)
    GET    /categorias               -> categorias já usadas pelo usuário
    GET    /health                   -> verificação de saúde da API

Configuração por variáveis de ambiente:
    BANCO_DADOS          caminho do arquivo SQLite (padrão: backend/tarefas.db)
    ORIGENS_PERMITIDAS   origens liberadas no CORS, separadas por vírgula
                         (padrão: http://127.0.0.1:8080 e http://localhost:8080)
    FLASK_DEBUG          "1" para modo debug (nunca usar em produção)
    PORTA                porta do servidor (padrão: 5000)
    ANTHROPIC_API_KEY    opcional; se definida, a sugestão de prioridade e
                         categoria usa a API do Claude (senão, heurística local)
"""

import calendar
import json
import logging
import os
import re
import secrets
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Blueprint, Flask, current_app, g, jsonify, request
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

# ---------------------------------------------------------------------------
# Constantes e regras de negócio
# ---------------------------------------------------------------------------

CAMINHO_PADRAO_BANCO = os.path.join(os.path.dirname(__file__), "tarefas.db")

STATUS_VALIDOS = ("Pendente", "Em andamento", "Concluída")
PRIORIDADES = ("Alta", "Média", "Baixa")
RECORRENCIAS = ("nenhuma", "diaria", "semanal", "mensal")

TAMANHO_MAX_TITULO = 200
TAMANHO_MAX_DESCRICAO = 2000
TAMANHO_MAX_CATEGORIA = 100  # aceita várias categorias separadas por vírgula
TAMANHO_MAX_COMENTARIO = 500
TAMANHO_MAX_RESPONSAVEL = 80  # nome, sobrenome e cargo do responsável
TAMANHO_MAX_MENSAGEM_CHAT = 1000
TAMANHO_MAX_NOME_QUADRO = 60
NOME_QUADRO_PADRAO = "Meu quadro"
TAMANHO_MIN_SENHA = 6
TAMANHO_MAX_SENHA = 128
TAMANHO_MAX_NOME = 100
TAMANHO_MAX_EMAIL = 254  # limite prático de e-mail (RFC 5321)
TAMANHO_MAX_CORPO = 1024 * 1024  # 1 MB por requisição

REGEX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Palavras-chave da heurística local de sugestão (fallback quando não há
# ANTHROPIC_API_KEY). A primeira categoria com palavra encontrada vence.
PALAVRAS_CATEGORIA = (
    ("Estudos", ("estudar", "estudo", "prova", "aula", "curso", "faculdade",
                 "tcc", "vestibular", "enem", "simulado", "lição", "licao")),
    ("Trabalho", ("reunião", "reuniao", "cliente", "relatório", "relatorio",
                  "apresentação", "apresentacao", "entrevista", "projeto",
                  "e-mail", "email", "chefe")),
    ("Financeiro", ("pagar", "conta", "boleto", "imposto", "banco", "fatura",
                    "aluguel", "pix", "salário", "salario")),
    ("Saúde", ("médico", "medico", "dentista", "consulta", "exame", "academia",
               "treino", "remédio", "remedio", "vacina")),
    ("Casa", ("limpar", "lavar", "arrumar", "consertar", "mercado", "compra",
              "faxina", "louça", "louca", "roupa", "cozinhar")),
    ("Lazer", ("filme", "série", "serie", "jogo", "jogar", "viagem", "festa",
               "aniversário", "aniversario", "praia", "show")),
)

PALAVRAS_PRIORIDADE_ALTA = (
    "urgente", "hoje", "agora", "prazo", "vence", "entrega", "prova", "pagar",
    "boleto", "imposto", "consulta", "entrevista", "apresentação",
    "apresentacao", "reunião", "reuniao", "médico", "medico",
)

PALAVRAS_PRIORIDADE_BAIXA = (
    "algum dia", "quando der", "talvez", "assistir", "filme", "série", "serie",
    "jogar", "hobby",
)

SQL_SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    senha_hash  TEXT NOT NULL,
    criado_em   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessoes (
    token       TEXT PRIMARY KEY,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    criada_em   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quadros (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nome        TEXT NOT NULL,
    criado_em   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tarefas (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id             INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    quadro_id              INTEGER REFERENCES quadros(id) ON DELETE CASCADE,
    titulo                 TEXT NOT NULL,
    descricao              TEXT NOT NULL DEFAULT '',
    status                 TEXT NOT NULL DEFAULT 'Pendente',
    prioridade             TEXT NOT NULL DEFAULT 'Média',
    categoria              TEXT NOT NULL DEFAULT '',
    data_inicio            TEXT,
    data_vencimento        TEXT,
    recorrencia            TEXT NOT NULL DEFAULT 'nenhuma',
    responsavel_nome       TEXT NOT NULL DEFAULT '',
    responsavel_sobrenome  TEXT NOT NULL DEFAULT '',
    responsavel_cargo      TEXT NOT NULL DEFAULT '',
    criada_em              TEXT NOT NULL,
    concluida_em           TEXT
);

CREATE TABLE IF NOT EXISTS subtarefas (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    tarefa_id              INTEGER NOT NULL REFERENCES tarefas(id) ON DELETE CASCADE,
    titulo                 TEXT NOT NULL,
    concluida              INTEGER NOT NULL DEFAULT 0,
    responsavel_nome       TEXT NOT NULL DEFAULT '',
    responsavel_sobrenome  TEXT NOT NULL DEFAULT '',
    responsavel_cargo      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS comentarios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tarefa_id  INTEGER NOT NULL REFERENCES tarefas(id) ON DELETE CASCADE,
    texto      TEXT NOT NULL,
    autor      TEXT NOT NULL DEFAULT '',
    criado_em  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS historico (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tarefa_id  INTEGER NOT NULL REFERENCES tarefas(id) ON DELETE CASCADE,
    descricao  TEXT NOT NULL,
    criado_em  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tarefas_usuario ON tarefas(usuario_id);
CREATE INDEX IF NOT EXISTS idx_subtarefas_tarefa ON subtarefas(tarefa_id);
CREATE INDEX IF NOT EXISTS idx_quadros_usuario ON quadros(usuario_id);
CREATE INDEX IF NOT EXISTS idx_comentarios_tarefa ON comentarios(tarefa_id);
CREATE INDEX IF NOT EXISTS idx_historico_tarefa ON historico(tarefa_id);
"""

api = Blueprint("api", __name__)


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------

def sem_acento(texto):
    """Minúsculas e sem diacríticos — para busca insensível a acentos."""
    decomposto = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in decomposto if not unicodedata.combining(c)).lower()


def obter_banco():
    """Abre (uma vez por requisição) a conexão com o SQLite."""
    if "banco" not in g:
        g.banco = sqlite3.connect(current_app.config["BANCO"])
        g.banco.row_factory = sqlite3.Row
        g.banco.execute("PRAGMA foreign_keys = ON")
        # Função usada na busca para ignorar acentos e caixa (ex: "credito" acha "Crédito")
        g.banco.create_function("sem_acento", 1, sem_acento, deterministic=True)
    return g.banco


def fechar_banco(_excecao=None):
    """Fecha a conexão ao final da requisição."""
    banco = g.pop("banco", None)
    if banco is not None:
        banco.close()


def agora_iso():
    """Data e hora atuais em formato ISO (sem microssegundos)."""
    return datetime.now().isoformat(timespec="seconds")


def corpo_json():
    """Corpo JSON da requisição, sempre como dicionário.

    Um corpo válido porém não-objeto (lista, string, número) viraria
    AttributeError nas rotas; aqui ele é normalizado para {}.
    """
    dados = request.get_json(silent=True)
    return dados if isinstance(dados, dict) else {}


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

def criar_sessao(usuario_id):
    """Gera um token de sessão para o usuário e o persiste."""
    token = secrets.token_hex(32)
    banco = obter_banco()
    banco.execute(
        "INSERT INTO sessoes (token, usuario_id, criada_em) VALUES (?, ?, ?)",
        (token, usuario_id, agora_iso()),
    )
    banco.commit()
    return token


def exigir_login(funcao):
    """Decorator que valida o token Bearer e injeta g.usuario_id."""

    @wraps(funcao)
    def wrapper(*args, **kwargs):
        cabecalho = request.headers.get("Authorization", "")
        token = cabecalho.removeprefix("Bearer ").strip()

        if not token:
            return jsonify({"erro": "Autenticação necessária."}), 401

        sessao = obter_banco().execute(
            "SELECT usuario_id FROM sessoes WHERE token = ?", (token,)
        ).fetchone()

        if sessao is None:
            return jsonify({"erro": "Sessão inválida ou expirada."}), 401

        g.usuario_id = sessao["usuario_id"]
        g.token = token
        return funcao(*args, **kwargs)

    return wrapper


@api.route("/auth/registrar", methods=["POST"])
def registrar():
    """Cria uma conta nova e já devolve um token de sessão."""
    dados = corpo_json()
    nome = str(dados.get("nome") or "").strip()
    email = str(dados.get("email") or "").strip().lower()
    senha = str(dados.get("senha") or "")

    if not nome or not email or not senha:
        return jsonify({"erro": "Nome, e-mail e senha são obrigatórios."}), 400
    if len(nome) > TAMANHO_MAX_NOME:
        return jsonify({"erro": f"O nome pode ter no máximo {TAMANHO_MAX_NOME} caracteres."}), 400
    if len(email) > TAMANHO_MAX_EMAIL or not REGEX_EMAIL.match(email):
        return jsonify({"erro": "E-mail inválido."}), 400
    if not (TAMANHO_MIN_SENHA <= len(senha) <= TAMANHO_MAX_SENHA):
        return jsonify(
            {"erro": f"A senha deve ter entre {TAMANHO_MIN_SENHA} e {TAMANHO_MAX_SENHA} caracteres."}
        ), 400

    banco = obter_banco()
    try:
        cursor = banco.execute(
            "INSERT INTO usuarios (nome, email, senha_hash, criado_em) VALUES (?, ?, ?, ?)",
            (nome, email, generate_password_hash(senha), agora_iso()),
        )
        banco.commit()
    except sqlite3.IntegrityError:
        return jsonify({"erro": "Já existe uma conta com esse e-mail."}), 409

    usuario_id = cursor.lastrowid
    banco.execute(
        "INSERT INTO quadros (usuario_id, nome, criado_em) VALUES (?, ?, ?)",
        (usuario_id, NOME_QUADRO_PADRAO, agora_iso()),
    )
    banco.commit()

    token = criar_sessao(usuario_id)
    return jsonify(
        {"token": token, "usuario": {"id": usuario_id, "nome": nome, "email": email}}
    ), 201


@api.route("/auth/login", methods=["POST"])
def login():
    """Autentica por e-mail e senha e devolve um token de sessão."""
    dados = corpo_json()
    email = str(dados.get("email") or "").strip().lower()
    senha = str(dados.get("senha") or "")

    usuario = obter_banco().execute(
        "SELECT * FROM usuarios WHERE email = ?", (email,)
    ).fetchone()

    if usuario is None or not check_password_hash(usuario["senha_hash"], senha):
        return jsonify({"erro": "E-mail ou senha incorretos."}), 401

    token = criar_sessao(usuario["id"])
    return jsonify(
        {
            "token": token,
            "usuario": {"id": usuario["id"], "nome": usuario["nome"], "email": usuario["email"]},
        }
    ), 200


@api.route("/auth/logout", methods=["POST"])
@exigir_login
def logout():
    """Invalida o token da sessão atual."""
    banco = obter_banco()
    banco.execute("DELETE FROM sessoes WHERE token = ?", (g.token,))
    banco.commit()
    return jsonify({"mensagem": "Sessão encerrada."}), 200


@api.route("/auth/eu", methods=["GET"])
@exigir_login
def quem_sou():
    """Retorna os dados do usuário dono do token (usado ao reabrir a página)."""
    usuario = obter_banco().execute(
        "SELECT id, nome, email FROM usuarios WHERE id = ?", (g.usuario_id,)
    ).fetchone()
    return jsonify(dict(usuario)), 200


# ---------------------------------------------------------------------------
# Validação e serialização de tarefas
# ---------------------------------------------------------------------------

CAMPOS_RESPONSAVEL = ("responsavel_nome", "responsavel_sobrenome", "responsavel_cargo")

ROTULOS_RESPONSAVEL = {
    "responsavel_nome": "nome do responsável",
    "responsavel_sobrenome": "sobrenome do responsável",
    "responsavel_cargo": "cargo do responsável",
}


def validar_responsavel(dados):
    """Valida os campos de responsável presentes em `dados`.

    Retorna (campos, erro) apenas com os campos enviados, já normalizados.
    """
    campos = {}
    for nome_campo in CAMPOS_RESPONSAVEL:
        if nome_campo not in dados:
            continue
        valor = str(dados.get(nome_campo) or "").strip()
        if len(valor) > TAMANHO_MAX_RESPONSAVEL:
            return None, (
                f"O {ROTULOS_RESPONSAVEL[nome_campo]} pode ter no máximo "
                f"{TAMANHO_MAX_RESPONSAVEL} caracteres."
            )
        campos[nome_campo] = valor
    return campos, None


def validar_dados_tarefa(dados, parcial=False):
    """Valida e normaliza os campos de uma tarefa.

    Retorna (campos, erro): `campos` contém apenas os campos presentes e já
    normalizados; `erro` é uma mensagem de erro ou None.
    Com parcial=True (PATCH), campos ausentes não são exigidos.
    """
    campos = {}

    if "titulo" in dados or not parcial:
        titulo = str(dados.get("titulo") or "").strip()
        if not titulo:
            return None, "O campo 'titulo' é obrigatório."
        if len(titulo) > TAMANHO_MAX_TITULO:
            return None, f"O título pode ter no máximo {TAMANHO_MAX_TITULO} caracteres."
        campos["titulo"] = titulo

    if "descricao" in dados:
        descricao = str(dados.get("descricao") or "").strip()
        if len(descricao) > TAMANHO_MAX_DESCRICAO:
            return None, f"A descrição pode ter no máximo {TAMANHO_MAX_DESCRICAO} caracteres."
        campos["descricao"] = descricao

    if "status" in dados:
        if dados.get("status") not in STATUS_VALIDOS:
            return None, f"Status inválido. Use um destes: {', '.join(STATUS_VALIDOS)}."
        campos["status"] = dados["status"]

    if "prioridade" in dados:
        if dados.get("prioridade") not in PRIORIDADES:
            return None, f"Prioridade inválida. Use uma destas: {', '.join(PRIORIDADES)}."
        campos["prioridade"] = dados["prioridade"]

    if "categoria" in dados:
        categoria = str(dados.get("categoria") or "").strip()
        if len(categoria) > TAMANHO_MAX_CATEGORIA:
            return None, f"A categoria pode ter no máximo {TAMANHO_MAX_CATEGORIA} caracteres."
        campos["categoria"] = categoria

    for nome_campo, rotulo in (("data_inicio", "início"), ("data_vencimento", "vencimento")):
        if nome_campo in dados:
            valor = dados.get(nome_campo)
            if valor in (None, ""):
                campos[nome_campo] = None
            else:
                try:
                    date.fromisoformat(str(valor))
                except ValueError:
                    return None, f"Data de {rotulo} inválida (use o formato AAAA-MM-DD)."
                campos[nome_campo] = str(valor)

    # Coerência entre as datas quando as duas vêm na mesma requisição
    if campos.get("data_inicio") and campos.get("data_vencimento"):
        if campos["data_inicio"] > campos["data_vencimento"]:
            return None, "A data de início não pode ser depois da data de vencimento."

    if "recorrencia" in dados:
        if dados.get("recorrencia") not in RECORRENCIAS:
            return None, f"Recorrência inválida. Use uma destas: {', '.join(RECORRENCIAS)}."
        campos["recorrencia"] = dados["recorrencia"]

    responsavel, erro = validar_responsavel(dados)
    if erro:
        return None, erro
    campos.update(responsavel)

    return campos, None


def buscar_subtarefas(tarefa_ids):
    """Retorna um dicionário {tarefa_id: [subtarefas]} para as tarefas dadas."""
    agrupadas = {tarefa_id: [] for tarefa_id in tarefa_ids}
    if not tarefa_ids:
        return agrupadas

    marcadores = ",".join("?" for _ in tarefa_ids)
    linhas = obter_banco().execute(
        f"SELECT * FROM subtarefas WHERE tarefa_id IN ({marcadores}) ORDER BY id",
        tuple(tarefa_ids),
    ).fetchall()

    for linha in linhas:
        agrupadas[linha["tarefa_id"]].append(serializar_subtarefa(linha))
    return agrupadas


def serializar_subtarefa(linha):
    """Converte uma linha de subtarefa no JSON exposto pela API."""
    return {
        "id": linha["id"],
        "titulo": linha["titulo"],
        "concluida": bool(linha["concluida"]),
        "responsavel_nome": linha["responsavel_nome"],
        "responsavel_sobrenome": linha["responsavel_sobrenome"],
        "responsavel_cargo": linha["responsavel_cargo"],
    }


def buscar_comentarios(tarefa_ids):
    """Retorna um dicionário {tarefa_id: [comentários]} para as tarefas dadas."""
    agrupados = {tarefa_id: [] for tarefa_id in tarefa_ids}
    if not tarefa_ids:
        return agrupados

    marcadores = ",".join("?" for _ in tarefa_ids)
    linhas = obter_banco().execute(
        f"SELECT * FROM comentarios WHERE tarefa_id IN ({marcadores}) ORDER BY id",
        tuple(tarefa_ids),
    ).fetchall()

    for linha in linhas:
        agrupados[linha["tarefa_id"]].append(
            {
                "id": linha["id"],
                "texto": linha["texto"],
                "autor": linha["autor"],
                "criado_em": linha["criado_em"],
            }
        )
    return agrupados


def buscar_historico(tarefa_ids):
    """Retorna um dicionário {tarefa_id: [eventos]} com a atividade das tarefas."""
    agrupados = {tarefa_id: [] for tarefa_id in tarefa_ids}
    if not tarefa_ids:
        return agrupados

    marcadores = ",".join("?" for _ in tarefa_ids)
    linhas = obter_banco().execute(
        f"SELECT * FROM historico WHERE tarefa_id IN ({marcadores}) ORDER BY id",
        tuple(tarefa_ids),
    ).fetchall()

    for linha in linhas:
        agrupados[linha["tarefa_id"]].append(
            {"descricao": linha["descricao"], "criado_em": linha["criado_em"]}
        )
    return agrupados


def registrar_historico(tarefa_id, descricao):
    """Grava um evento no histórico de atividade da tarefa (commit é do chamador)."""
    obter_banco().execute(
        "INSERT INTO historico (tarefa_id, descricao, criado_em) VALUES (?, ?, ?)",
        (tarefa_id, descricao, agora_iso()),
    )


ROTULOS_CAMPO = {
    "titulo": "Título",
    "descricao": "Descrição",
    "categoria": "Categoria",
    "responsavel_nome": "Responsável",
    "responsavel_sobrenome": "Responsável",
    "responsavel_cargo": "Cargo do responsável",
}


def descrever_mudanca(campo, antigo, novo):
    """Texto amigável de um evento de edição para o histórico."""
    if campo in ("status", "prioridade", "recorrencia"):
        nome = {"status": "Status", "prioridade": "Prioridade", "recorrencia": "Recorrência"}[campo]
        return f"{nome}: {antigo} → {novo}"
    if campo == "data_vencimento":
        return f"Vencimento definido para {novo}" if novo else "Vencimento removido"
    if campo == "data_inicio":
        return f"Início definido para {novo}" if novo else "Início removido"
    return f"{ROTULOS_CAMPO[campo]} alterado(a)"


def serializar_tarefa(linha, subtarefas=None, comentarios=None, historico=None):
    """Converte uma linha do banco no JSON exposto pela API."""
    return {
        "id": linha["id"],
        "quadro_id": linha["quadro_id"],
        "titulo": linha["titulo"],
        "descricao": linha["descricao"],
        "status": linha["status"],
        "prioridade": linha["prioridade"],
        "categoria": linha["categoria"],
        "data_inicio": linha["data_inicio"],
        "data_vencimento": linha["data_vencimento"],
        "recorrencia": linha["recorrencia"],
        "responsavel_nome": linha["responsavel_nome"],
        "responsavel_sobrenome": linha["responsavel_sobrenome"],
        "responsavel_cargo": linha["responsavel_cargo"],
        "criada_em": linha["criada_em"],
        "concluida_em": linha["concluida_em"],
        "subtarefas": subtarefas if subtarefas is not None else [],
        "comentarios": comentarios if comentarios is not None else [],
        "historico": historico if historico is not None else [],
    }


def serializar_tarefa_por_id(tarefa_id):
    """Serializa uma tarefa do usuário com subtarefas, comentários e histórico."""
    linha = buscar_tarefa_do_usuario(tarefa_id)
    return serializar_tarefa(
        linha,
        buscar_subtarefas([tarefa_id])[tarefa_id],
        buscar_comentarios([tarefa_id])[tarefa_id],
        buscar_historico([tarefa_id])[tarefa_id],
    )


def buscar_quadro_do_usuario(quadro_id):
    """Busca um quadro pelo id garantindo que pertence ao usuário logado."""
    return obter_banco().execute(
        "SELECT * FROM quadros WHERE id = ? AND usuario_id = ?",
        (quadro_id, g.usuario_id),
    ).fetchone()


def quadro_padrao_id():
    """Id do primeiro quadro do usuário, criando um se ainda não existir."""
    banco = obter_banco()
    quadro = banco.execute(
        "SELECT id FROM quadros WHERE usuario_id = ? ORDER BY id LIMIT 1",
        (g.usuario_id,),
    ).fetchone()
    if quadro is not None:
        return quadro["id"]

    cursor = banco.execute(
        "INSERT INTO quadros (usuario_id, nome, criado_em) VALUES (?, ?, ?)",
        (g.usuario_id, NOME_QUADRO_PADRAO, agora_iso()),
    )
    banco.commit()
    return cursor.lastrowid


def buscar_tarefa_do_usuario(tarefa_id):
    """Busca uma tarefa pelo id garantindo que pertence ao usuário logado."""
    return obter_banco().execute(
        "SELECT * FROM tarefas WHERE id = ? AND usuario_id = ?",
        (tarefa_id, g.usuario_id),
    ).fetchone()


def proxima_data(data_base, recorrencia):
    """Calcula a próxima data de vencimento de uma tarefa recorrente."""
    if recorrencia == "diaria":
        return data_base + timedelta(days=1)
    if recorrencia == "semanal":
        return data_base + timedelta(weeks=1)
    # mensal: mesmo dia do mês seguinte (ajustando meses mais curtos)
    ano = data_base.year + (1 if data_base.month == 12 else 0)
    mes = data_base.month % 12 + 1
    dia = min(data_base.day, calendar.monthrange(ano, mes)[1])
    return date(ano, mes, dia)


def criar_proxima_ocorrencia(tarefa):
    """Cria a próxima ocorrência de uma tarefa recorrente recém-concluída.

    O checklist é herdado: as subtarefas são copiadas desmarcadas.
    """
    base = (
        date.fromisoformat(tarefa["data_vencimento"])
        if tarefa["data_vencimento"]
        else date.today()
    )
    nova_data = proxima_data(base, tarefa["recorrencia"]).isoformat()

    # A data de início (se houver) desloca-se junto com o vencimento
    novo_inicio = None
    if tarefa["data_inicio"]:
        novo_inicio = proxima_data(
            date.fromisoformat(tarefa["data_inicio"]), tarefa["recorrencia"]
        ).isoformat()

    banco = obter_banco()
    cursor = banco.execute(
        """
        INSERT INTO tarefas
            (usuario_id, quadro_id, titulo, descricao, status, prioridade, categoria,
             data_inicio, data_vencimento, recorrencia,
             responsavel_nome, responsavel_sobrenome, responsavel_cargo, criada_em)
        VALUES (?, ?, ?, ?, 'Pendente', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            g.usuario_id,
            tarefa["quadro_id"],
            tarefa["titulo"],
            tarefa["descricao"],
            tarefa["prioridade"],
            tarefa["categoria"],
            novo_inicio,
            nova_data,
            tarefa["recorrencia"],
            tarefa["responsavel_nome"],
            tarefa["responsavel_sobrenome"],
            tarefa["responsavel_cargo"],
            agora_iso(),
        ),
    )
    nova_id = cursor.lastrowid

    subtarefas = banco.execute(
        "SELECT * FROM subtarefas WHERE tarefa_id = ? ORDER BY id",
        (tarefa["id"],),
    ).fetchall()
    banco.executemany(
        """
        INSERT INTO subtarefas
            (tarefa_id, titulo, responsavel_nome, responsavel_sobrenome, responsavel_cargo)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                nova_id,
                subtarefa["titulo"],
                subtarefa["responsavel_nome"],
                subtarefa["responsavel_sobrenome"],
                subtarefa["responsavel_cargo"],
            )
            for subtarefa in subtarefas
        ],
    )
    registrar_historico(nova_id, "Criada automaticamente pela recorrência")
    banco.commit()

    return serializar_tarefa_por_id(nova_id)


# ---------------------------------------------------------------------------
# Rotas de tarefas
# ---------------------------------------------------------------------------

@api.route("/tarefas", methods=["GET"])
@exigir_login
def listar_tarefas():
    """Lista as tarefas do usuário. Filtros opcionais via query string:
    ?status=Pendente  ?prioridade=Alta  ?categoria=Estudos  ?busca=prova
    """
    consulta = "SELECT * FROM tarefas WHERE usuario_id = ?"
    parametros = [g.usuario_id]

    quadro_id = request.args.get("quadro_id", type=int)
    if quadro_id:
        consulta += " AND quadro_id = ?"
        parametros.append(quadro_id)

    status = request.args.get("status")
    if status in STATUS_VALIDOS:
        consulta += " AND status = ?"
        parametros.append(status)

    prioridade = request.args.get("prioridade")
    if prioridade in PRIORIDADES:
        consulta += " AND prioridade = ?"
        parametros.append(prioridade)

    categoria = request.args.get("categoria")
    if categoria:
        consulta += " AND categoria = ?"
        parametros.append(categoria)

    # Filtro por período da data de início (uma ou as duas pontas)
    for parametro, operador in (("inicio_de", ">="), ("inicio_ate", "<=")):
        valor = request.args.get(parametro)
        if valor:
            try:
                date.fromisoformat(valor)
            except ValueError:
                return jsonify(
                    {"erro": f"Parâmetro '{parametro}' inválido (use o formato AAAA-MM-DD)."}
                ), 400
            consulta += f" AND data_inicio IS NOT NULL AND data_inicio {operador} ?"
            parametros.append(valor)

    busca = request.args.get("busca")
    if busca:
        # % e _ digitados pelo usuário são texto literal, não curingas do LIKE;
        # a comparação ignora acentos e caixa dos dois lados (sem_acento)
        padrao = sem_acento(busca).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        consulta += (
            r" AND (sem_acento(titulo) LIKE ? ESCAPE '\'"
            r" OR sem_acento(descricao) LIKE ? ESCAPE '\')"
        )
        parametros.extend([f"%{padrao}%", f"%{padrao}%"])

    consulta += " ORDER BY criada_em DESC, id DESC"
    linhas = obter_banco().execute(consulta, tuple(parametros)).fetchall()

    ids = [linha["id"] for linha in linhas]
    subtarefas = buscar_subtarefas(ids)
    comentarios = buscar_comentarios(ids)
    historico = buscar_historico(ids)
    return jsonify(
        [
            serializar_tarefa(
                linha, subtarefas[linha["id"]], comentarios[linha["id"]], historico[linha["id"]]
            )
            for linha in linhas
        ]
    ), 200


@api.route("/tarefas", methods=["POST"])
@exigir_login
def criar_tarefa():
    """Cria uma nova tarefa a partir do JSON enviado no corpo da requisição."""
    dados = corpo_json()
    campos, erro = validar_dados_tarefa(dados)
    if erro:
        return jsonify({"erro": erro}), 400

    quadro_id = dados.get("quadro_id")
    if quadro_id is not None:
        if not isinstance(quadro_id, int) or buscar_quadro_do_usuario(quadro_id) is None:
            return jsonify({"erro": "Quadro não encontrado."}), 404
    else:
        quadro_id = quadro_padrao_id()

    banco = obter_banco()
    cursor = banco.execute(
        """
        INSERT INTO tarefas
            (usuario_id, quadro_id, titulo, descricao, status, prioridade, categoria,
             data_inicio, data_vencimento, recorrencia,
             responsavel_nome, responsavel_sobrenome, responsavel_cargo, criada_em)
        VALUES (?, ?, ?, ?, 'Pendente', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            g.usuario_id,
            quadro_id,
            campos["titulo"],
            campos.get("descricao", ""),
            campos.get("prioridade", "Média"),
            campos.get("categoria", ""),
            campos.get("data_inicio"),
            campos.get("data_vencimento"),
            campos.get("recorrencia", "nenhuma"),
            campos.get("responsavel_nome", ""),
            campos.get("responsavel_sobrenome", ""),
            campos.get("responsavel_cargo", ""),
            agora_iso(),
        ),
    )
    registrar_historico(cursor.lastrowid, "Tarefa criada")
    banco.commit()

    return jsonify(serializar_tarefa_por_id(cursor.lastrowid)), 201


@api.route("/tarefas/<int:tarefa_id>", methods=["PATCH"])
@exigir_login
def editar_tarefa(tarefa_id):
    """Edita qualquer campo de uma tarefa (título, descrição, status, etc.).

    Ao concluir uma tarefa recorrente, a próxima ocorrência é criada
    automaticamente e devolvida no campo extra `proxima_ocorrencia`.
    """
    tarefa = buscar_tarefa_do_usuario(tarefa_id)
    if tarefa is None:
        return jsonify({"erro": "Tarefa não encontrada."}), 404

    dados = corpo_json()
    campos, erro = validar_dados_tarefa(dados, parcial=True)
    if erro:
        return jsonify({"erro": erro}), 400
    if not campos:
        return jsonify({"erro": "Nenhum campo válido para atualizar."}), 400

    # Controle do carimbo de conclusão nas mudanças de status
    concluindo = campos.get("status") == "Concluída" and tarefa["status"] != "Concluída"
    reabrindo = (
        "status" in campos
        and campos["status"] != "Concluída"
        and tarefa["status"] == "Concluída"
    )
    if concluindo:
        campos["concluida_em"] = agora_iso()
    elif reabrindo:
        campos["concluida_em"] = None

    banco = obter_banco()
    atribuicoes = ", ".join(f"{nome} = ?" for nome in campos)  # nomes vêm da validação
    banco.execute(
        f"UPDATE tarefas SET {atribuicoes} WHERE id = ?",
        (*campos.values(), tarefa_id),
    )

    # Registra na atividade o que de fato mudou
    for nome_campo, novo_valor in campos.items():
        if nome_campo == "concluida_em" or tarefa[nome_campo] == novo_valor:
            continue
        registrar_historico(tarefa_id, descrever_mudanca(nome_campo, tarefa[nome_campo], novo_valor))
    banco.commit()

    atualizada = buscar_tarefa_do_usuario(tarefa_id)
    resposta = serializar_tarefa_por_id(tarefa_id)

    # Tarefa recorrente concluída -> agenda a próxima ocorrência
    if concluindo and atualizada["recorrencia"] != "nenhuma":
        resposta["proxima_ocorrencia"] = criar_proxima_ocorrencia(atualizada)

    return jsonify(resposta), 200


@api.route("/tarefas/<int:tarefa_id>", methods=["DELETE"])
@exigir_login
def excluir_tarefa(tarefa_id):
    """Remove uma tarefa (e suas subtarefas, em cascata) pelo id."""
    tarefa = buscar_tarefa_do_usuario(tarefa_id)
    if tarefa is None:
        return jsonify({"erro": "Tarefa não encontrada."}), 404

    banco = obter_banco()
    banco.execute("DELETE FROM tarefas WHERE id = ?", (tarefa_id,))
    banco.commit()
    return jsonify({"mensagem": "Tarefa excluída com sucesso."}), 200


# ---------------------------------------------------------------------------
# Rotas de subtarefas
# ---------------------------------------------------------------------------

@api.route("/tarefas/<int:tarefa_id>/subtarefas", methods=["POST"])
@exigir_login
def criar_subtarefa(tarefa_id):
    """Adiciona uma subtarefa (item de checklist) a uma tarefa."""
    tarefa = buscar_tarefa_do_usuario(tarefa_id)
    if tarefa is None:
        return jsonify({"erro": "Tarefa não encontrada."}), 404

    dados = corpo_json()
    titulo = str(dados.get("titulo") or "").strip()
    if not titulo:
        return jsonify({"erro": "O campo 'titulo' é obrigatório."}), 400
    if len(titulo) > TAMANHO_MAX_TITULO:
        return jsonify(
            {"erro": f"O título pode ter no máximo {TAMANHO_MAX_TITULO} caracteres."}
        ), 400

    responsavel, erro = validar_responsavel(dados)
    if erro:
        return jsonify({"erro": erro}), 400

    banco = obter_banco()
    cursor = banco.execute(
        """
        INSERT INTO subtarefas
            (tarefa_id, titulo, responsavel_nome, responsavel_sobrenome, responsavel_cargo)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            tarefa_id,
            titulo,
            responsavel.get("responsavel_nome", ""),
            responsavel.get("responsavel_sobrenome", ""),
            responsavel.get("responsavel_cargo", ""),
        ),
    )
    banco.commit()
    subtarefa = banco.execute(
        "SELECT * FROM subtarefas WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return jsonify(serializar_subtarefa(subtarefa)), 201


def buscar_subtarefa_do_usuario(subtarefa_id):
    """Busca uma subtarefa garantindo que a tarefa-mãe é do usuário logado."""
    return obter_banco().execute(
        """
        SELECT s.* FROM subtarefas s
        JOIN tarefas t ON t.id = s.tarefa_id
        WHERE s.id = ? AND t.usuario_id = ?
        """,
        (subtarefa_id, g.usuario_id),
    ).fetchone()


@api.route("/subtarefas/<int:subtarefa_id>", methods=["PATCH"])
@exigir_login
def editar_subtarefa(subtarefa_id):
    """Edita o título e/ou alterna a conclusão de uma subtarefa."""
    subtarefa = buscar_subtarefa_do_usuario(subtarefa_id)
    if subtarefa is None:
        return jsonify({"erro": "Subtarefa não encontrada."}), 404

    dados = corpo_json()
    titulo = subtarefa["titulo"]
    concluida = bool(subtarefa["concluida"])

    if "titulo" in dados:
        titulo = str(dados.get("titulo") or "").strip()
        if not titulo:
            return jsonify({"erro": "O campo 'titulo' é obrigatório."}), 400
        if len(titulo) > TAMANHO_MAX_TITULO:
            return jsonify(
                {"erro": f"O título pode ter no máximo {TAMANHO_MAX_TITULO} caracteres."}
            ), 400

    if "concluida" in dados:
        concluida = bool(dados.get("concluida"))

    responsavel, erro = validar_responsavel(dados)
    if erro:
        return jsonify({"erro": erro}), 400
    valores = {campo: subtarefa[campo] for campo in CAMPOS_RESPONSAVEL}
    valores.update(responsavel)

    banco = obter_banco()
    banco.execute(
        """
        UPDATE subtarefas
        SET titulo = ?, concluida = ?,
            responsavel_nome = ?, responsavel_sobrenome = ?, responsavel_cargo = ?
        WHERE id = ?
        """,
        (
            titulo,
            int(concluida),
            valores["responsavel_nome"],
            valores["responsavel_sobrenome"],
            valores["responsavel_cargo"],
            subtarefa_id,
        ),
    )
    banco.commit()
    atualizada = banco.execute(
        "SELECT * FROM subtarefas WHERE id = ?", (subtarefa_id,)
    ).fetchone()
    return jsonify(serializar_subtarefa(atualizada)), 200


@api.route("/subtarefas/<int:subtarefa_id>", methods=["DELETE"])
@exigir_login
def excluir_subtarefa(subtarefa_id):
    """Remove uma subtarefa pelo id."""
    subtarefa = buscar_subtarefa_do_usuario(subtarefa_id)
    if subtarefa is None:
        return jsonify({"erro": "Subtarefa não encontrada."}), 404

    banco = obter_banco()
    banco.execute("DELETE FROM subtarefas WHERE id = ?", (subtarefa_id,))
    banco.commit()
    return jsonify({"mensagem": "Subtarefa excluída com sucesso."}), 200


# ---------------------------------------------------------------------------
# Rotas de quadros (múltiplos boards, como projetos no Jira)
# ---------------------------------------------------------------------------

def validar_nome_quadro(dados):
    """Valida o nome de um quadro; retorna (nome, erro)."""
    nome = str(dados.get("nome") or "").strip()
    if not nome:
        return None, "O campo 'nome' é obrigatório."
    if len(nome) > TAMANHO_MAX_NOME_QUADRO:
        return None, f"O nome pode ter no máximo {TAMANHO_MAX_NOME_QUADRO} caracteres."
    return nome, None


def quadro_com_mesmo_nome(nome, ignorar_id=None):
    """Verifica se o usuário já tem um quadro com esse nome (ignorando caixa)."""
    consulta = "SELECT id FROM quadros WHERE usuario_id = ? AND nome = ? COLLATE NOCASE"
    parametros = [g.usuario_id, nome]
    if ignorar_id is not None:
        consulta += " AND id != ?"
        parametros.append(ignorar_id)
    return obter_banco().execute(consulta, tuple(parametros)).fetchone() is not None


@api.route("/quadros", methods=["GET"])
@exigir_login
def listar_quadros():
    """Lista os quadros do usuário (todo usuário tem ao menos um)."""
    quadro_padrao_id()  # garante o quadro padrão para contas antigas
    linhas = obter_banco().execute(
        "SELECT id, nome, criado_em FROM quadros WHERE usuario_id = ? ORDER BY id",
        (g.usuario_id,),
    ).fetchall()
    return jsonify([dict(linha) for linha in linhas]), 200


@api.route("/quadros", methods=["POST"])
@exigir_login
def criar_quadro():
    """Cria um novo quadro de tarefas."""
    nome, erro = validar_nome_quadro(corpo_json())
    if erro:
        return jsonify({"erro": erro}), 400
    if quadro_com_mesmo_nome(nome):
        return jsonify({"erro": "Você já tem um quadro com esse nome."}), 409

    banco = obter_banco()
    cursor = banco.execute(
        "INSERT INTO quadros (usuario_id, nome, criado_em) VALUES (?, ?, ?)",
        (g.usuario_id, nome, agora_iso()),
    )
    banco.commit()
    return jsonify({"id": cursor.lastrowid, "nome": nome}), 201


@api.route("/quadros/<int:quadro_id>", methods=["PATCH"])
@exigir_login
def renomear_quadro(quadro_id):
    """Renomeia um quadro."""
    if buscar_quadro_do_usuario(quadro_id) is None:
        return jsonify({"erro": "Quadro não encontrado."}), 404

    nome, erro = validar_nome_quadro(corpo_json())
    if erro:
        return jsonify({"erro": erro}), 400
    if quadro_com_mesmo_nome(nome, ignorar_id=quadro_id):
        return jsonify({"erro": "Você já tem um quadro com esse nome."}), 409

    banco = obter_banco()
    banco.execute("UPDATE quadros SET nome = ? WHERE id = ?", (nome, quadro_id))
    banco.commit()
    return jsonify({"id": quadro_id, "nome": nome}), 200


@api.route("/quadros/<int:quadro_id>", methods=["DELETE"])
@exigir_login
def excluir_quadro(quadro_id):
    """Exclui um quadro e todas as tarefas dele (mantendo ao menos um quadro)."""
    if buscar_quadro_do_usuario(quadro_id) is None:
        return jsonify({"erro": "Quadro não encontrado."}), 404

    banco = obter_banco()
    total = banco.execute(
        "SELECT COUNT(*) AS n FROM quadros WHERE usuario_id = ?", (g.usuario_id,)
    ).fetchone()["n"]
    if total <= 1:
        return jsonify({"erro": "Você precisa manter ao menos um quadro."}), 400

    banco.execute(
        "DELETE FROM tarefas WHERE quadro_id = ? AND usuario_id = ?",
        (quadro_id, g.usuario_id),
    )
    banco.execute("DELETE FROM quadros WHERE id = ?", (quadro_id,))
    banco.commit()
    return jsonify({"mensagem": "Quadro excluído com sucesso."}), 200


# ---------------------------------------------------------------------------
# Rotas de comentários
# ---------------------------------------------------------------------------

@api.route("/tarefas/<int:tarefa_id>/comentarios", methods=["POST"])
@exigir_login
def criar_comentario(tarefa_id):
    """Adiciona um comentário a uma tarefa."""
    if buscar_tarefa_do_usuario(tarefa_id) is None:
        return jsonify({"erro": "Tarefa não encontrada."}), 404

    texto = str(corpo_json().get("texto") or "").strip()
    if not texto:
        return jsonify({"erro": "O campo 'texto' é obrigatório."}), 400
    if len(texto) > TAMANHO_MAX_COMENTARIO:
        return jsonify(
            {"erro": f"O comentário pode ter no máximo {TAMANHO_MAX_COMENTARIO} caracteres."}
        ), 400

    banco = obter_banco()
    criado_em = agora_iso()
    autor = banco.execute(
        "SELECT nome FROM usuarios WHERE id = ?", (g.usuario_id,)
    ).fetchone()["nome"]
    cursor = banco.execute(
        "INSERT INTO comentarios (tarefa_id, texto, autor, criado_em) VALUES (?, ?, ?, ?)",
        (tarefa_id, texto, autor, criado_em),
    )
    banco.commit()
    return jsonify(
        {"id": cursor.lastrowid, "texto": texto, "autor": autor, "criado_em": criado_em}
    ), 201


@api.route("/comentarios/<int:comentario_id>", methods=["DELETE"])
@exigir_login
def excluir_comentario(comentario_id):
    """Remove um comentário pelo id."""
    comentario = obter_banco().execute(
        """
        SELECT c.id FROM comentarios c
        JOIN tarefas t ON t.id = c.tarefa_id
        WHERE c.id = ? AND t.usuario_id = ?
        """,
        (comentario_id, g.usuario_id),
    ).fetchone()
    if comentario is None:
        return jsonify({"erro": "Comentário não encontrado."}), 404

    banco = obter_banco()
    banco.execute("DELETE FROM comentarios WHERE id = ?", (comentario_id,))
    banco.commit()
    return jsonify({"mensagem": "Comentário excluído com sucesso."}), 200


# ---------------------------------------------------------------------------
# Sugestão de prioridade e categoria (IA com fallback heurístico)
# ---------------------------------------------------------------------------

def sugerir_com_heuristica(titulo, descricao):
    """Sugere prioridade e categoria por palavras-chave, sem depender de rede."""
    texto = f"{titulo} {descricao}".lower()

    categoria = ""
    for nome, palavras in PALAVRAS_CATEGORIA:
        if any(palavra in texto for palavra in palavras):
            categoria = nome
            break

    if any(palavra in texto for palavra in PALAVRAS_PRIORIDADE_ALTA):
        prioridade = "Alta"
    elif any(palavra in texto for palavra in PALAVRAS_PRIORIDADE_BAIXA):
        prioridade = "Baixa"
    else:
        prioridade = "Média"

    return {"prioridade": prioridade, "categoria": categoria, "origem": "heuristica"}


def sugerir_com_claude(titulo, descricao):
    """Classifica a tarefa com a API do Claude (Anthropic).

    Usa structured outputs para garantir JSON válido. Retorna None em caso
    de qualquer falha, para que a heurística local assuma.
    """
    try:
        import anthropic

        cliente = anthropic.Anthropic()  # lê ANTHROPIC_API_KEY do ambiente
        resposta = cliente.messages.create(
            model="claude-opus-4-8",
            max_tokens=256,
            output_config={
                "effort": "low",  # classificação simples: prioriza latência
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "prioridade": {"type": "string", "enum": list(PRIORIDADES)},
                            "categoria": {
                                "type": "string",
                                "description": "Categoria curta em português, ex: Estudos, Trabalho, Casa, Saúde, Financeiro, Lazer",
                            },
                        },
                        "required": ["prioridade", "categoria"],
                        "additionalProperties": False,
                    },
                },
            },
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Classifique esta tarefa de um gerenciador de tarefas pessoal, "
                        "sugerindo prioridade e uma categoria curta.\n"
                        f"Título: {titulo}\n"
                        f"Descrição: {descricao or '(sem descrição)'}"
                    ),
                }
            ],
        )
        texto = next(bloco.text for bloco in resposta.content if bloco.type == "text")
        dados = json.loads(texto)
        if dados.get("prioridade") not in PRIORIDADES:
            return None
        return {
            "prioridade": dados["prioridade"],
            "categoria": str(dados.get("categoria") or "").strip()[:TAMANHO_MAX_CATEGORIA],
            "origem": "ia",
        }
    except Exception:
        current_app.logger.warning(
            "Falha na sugestão via IA; usando a heurística local.", exc_info=True
        )
        return None


@api.route("/tarefas/sugestao", methods=["POST"])
@exigir_login
def sugerir_classificacao():
    """Sugere prioridade e categoria para uma tarefa a partir do título/descrição.

    Com ANTHROPIC_API_KEY definida, usa a API do Claude; caso contrário (ou em
    caso de falha), usa uma heurística local de palavras-chave.
    """
    dados = corpo_json()
    titulo = str(dados.get("titulo") or "").strip()
    descricao = str(dados.get("descricao") or "").strip()

    if not titulo:
        return jsonify({"erro": "O campo 'titulo' é obrigatório."}), 400

    sugestao = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        sugestao = sugerir_com_claude(titulo, descricao)
    if sugestao is None:
        sugestao = sugerir_com_heuristica(titulo, descricao)

    return jsonify(sugestao), 200


# ---------------------------------------------------------------------------
# Chatbot XCL Help (IA com fallback de regras locais)
# ---------------------------------------------------------------------------

RESPOSTAS_AJUDA = (
    (("criar", "tarefa"), (
        "Para criar uma tarefa, preencha o formulário \"Nova tarefa\": título (obrigatório), "
        "descrição, datas de início e vencimento, prioridade, categoria, responsável e "
        "recorrência. A prioridade e a categoria são sugeridas automaticamente enquanto "
        "você digita o título. ✨"
    )),
    (("subtarefa",), (
        "Cada tarefa tem um checklist de subtarefas: clique em \"Subtarefas\" no cartão para "
        "abrir o painel, digite o título e, se quiser, o nome, sobrenome e cargo do "
        "responsável. O progresso aparece como feitas/total."
    )),
    (("kanban", "arrastar", "coluna"), (
        "Na visão Kanban há três colunas — A fazer, Em andamento e Concluídas. Arraste um "
        "cartão entre as colunas para mudar o status. Você também pode definir um limite de "
        "WIP no campo ∞ do cabeçalho de cada coluna."
    )),
    (("wip",), (
        "O limite de WIP (Work In Progress) controla o máximo de tarefas por coluna do "
        "kanban. Defina o número no campo ∞ do cabeçalho: quando a coluna passar do limite, "
        "ela fica destacada em vermelho — sinal de que é hora de concluir antes de puxar "
        "mais trabalho."
    )),
    (("recorr", "repetir"), (
        "Tarefas recorrentes (diária, semanal ou mensal) criam a próxima ocorrência "
        "automaticamente quando você conclui a atual — herdando o checklist com as "
        "subtarefas desmarcadas e o mesmo responsável."
    )),
    (("filtro", "busca", "ordena"), (
        "Você pode buscar por título/descrição e filtrar por status, prioridade, categoria e "
        "período da data de início. Também dá para ordenar por criação, vencimento, início, "
        "prioridade ou A–Z, e salvar combinações de filtros com um nome para reaplicar depois."
    )),
    (("responsáve", "responsave", "cargo"), (
        "Tarefas e subtarefas aceitam um responsável com nome, sobrenome e cargo. Preencha "
        "os campos no formulário de nova tarefa, no modal de edição ou no formulário de "
        "subtarefa — o responsável aparece como etiqueta 👤 no cartão."
    )),
    (("calendário", "calendario"), (
        "A visão Calendário mostra as tarefas no mês pela data de vencimento. Use as setas "
        "para navegar entre meses e clique em uma tarefa para editá-la."
    )),
    (("saúde", "saude", "health"), (
        "A aba Saúde avalia as tarefas do quadro: mostra um índice geral e agrupa em "
        "Atrasadas, Vencem hoje, Prestes a vencer (3 dias), Em dia e Sem data. É o jeito "
        "mais rápido de ver se o quadro está sob controle."
    )),
)


def estatisticas_dos_quadros():
    """Resumo por quadro do usuário, usado pelo chatbot (regras e IA)."""
    banco = obter_banco()
    hoje = date.today()
    quadros = banco.execute(
        "SELECT id, nome FROM quadros WHERE usuario_id = ? ORDER BY id", (g.usuario_id,)
    ).fetchall()

    resumo = []
    for quadro in quadros:
        tarefas = banco.execute(
            """
            SELECT titulo, status, data_vencimento, responsavel_nome, responsavel_sobrenome
            FROM tarefas WHERE usuario_id = ? AND quadro_id = ? ORDER BY id
            """,
            (g.usuario_id, quadro["id"]),
        ).fetchall()

        atrasadas, vencem_hoje, proximas = [], [], []
        contadores = {"Pendente": 0, "Em andamento": 0, "Concluída": 0}
        for tarefa in tarefas:
            contadores[tarefa["status"]] += 1
            if tarefa["status"] == "Concluída" or not tarefa["data_vencimento"]:
                continue
            vencimento = date.fromisoformat(tarefa["data_vencimento"])
            if vencimento < hoje:
                atrasadas.append(tarefa["titulo"])
            elif vencimento == hoje:
                vencem_hoje.append(tarefa["titulo"])
            elif (vencimento - hoje).days <= 3:
                proximas.append(tarefa["titulo"])

        resumo.append(
            {
                "id": quadro["id"],
                "nome": quadro["nome"],
                "total": len(tarefas),
                "pendentes": contadores["Pendente"],
                "em_andamento": contadores["Em andamento"],
                "concluidas": contadores["Concluída"],
                "atrasadas": atrasadas,
                "vencem_hoje": vencem_hoje,
                "proximas": proximas,
            }
        )
    return resumo


def formatar_status_quadro(quadro):
    """Texto de status de um quadro para as respostas do chatbot."""
    linhas = [
        f"📋 Quadro \"{quadro['nome']}\": {quadro['total']} tarefa(s) — "
        f"{quadro['pendentes']} pendente(s), {quadro['em_andamento']} em andamento, "
        f"{quadro['concluidas']} concluída(s)."
    ]
    if quadro["atrasadas"]:
        exemplos = ", ".join(quadro["atrasadas"][:5])
        linhas.append(f"🔴 Atrasadas ({len(quadro['atrasadas'])}): {exemplos}.")
    if quadro["vencem_hoje"]:
        linhas.append(
            f"🟡 Vencem hoje ({len(quadro['vencem_hoje'])}): "
            + ", ".join(quadro["vencem_hoje"][:5]) + "."
        )
    if quadro["proximas"]:
        linhas.append(
            f"🟠 Prestes a vencer — próximos 3 dias ({len(quadro['proximas'])}): "
            + ", ".join(quadro["proximas"][:5]) + "."
        )
    if not (quadro["atrasadas"] or quadro["vencem_hoje"] or quadro["proximas"]):
        linhas.append("🟢 Nenhuma tarefa atrasada ou perto de vencer. Tudo em dia!")
    return "\n".join(linhas)


SAUDACOES = frozenset((
    "oi", "oii", "oiii", "ola", "olá", "opa", "hey", "eai", "e ai", "e aí",
    "salve", "bom dia", "boa tarde", "boa noite", "oi tudo bem", "olá tudo bem",
))


def responder_chat_com_regras(mensagem, quadro_id):
    """Resposta local do XCL Help, sem depender de rede (fallback da IA)."""
    texto = mensagem.lower()
    resumo = estatisticas_dos_quadros()

    # Saudação pura (mensagem inteira) tem resposta própria e curta —
    # comparar a mensagem completa evita falsos positivos por substring
    if texto.strip(" !?,.:;") in SAUDACOES:
        return (
            "Oi! 👋 Em que posso ajudar? Toque numa sugestão aqui embaixo ou pergunte, "
            "por exemplo, \"quantas tarefas atrasadas?\" ou \"o que é limite de WIP?\"."
        )

    if "obrigad" in texto or "valeu" in texto:
        return "De nada! 😊 Qualquer outra dúvida sobre o organizador ou seus quadros, é só chamar."

    # Pergunta sobre um quadro citado pelo nome tem prioridade
    citados = [quadro for quadro in resumo if quadro["nome"].lower() in texto]
    if citados:
        return "\n\n".join(formatar_status_quadro(quadro) for quadro in citados)

    # Situação/saúde das tarefas (atrasadas, em dia, status do quadro atual)
    palavras_status = ("atrasad", "vencid", "em dia", "status", "situação", "situacao",
                       "resumo", "saúde", "saude", "health", "pendente", "andamento",
                       "como está", "como esta", "prestes", "a vencer")
    if any(palavra in texto for palavra in palavras_status):
        if "todos" in texto or "quadros" in texto:
            return "\n\n".join(formatar_status_quadro(quadro) for quadro in resumo)
        atual = next((quadro for quadro in resumo if quadro["id"] == quadro_id), None)
        if atual:
            return formatar_status_quadro(atual)
        return "\n\n".join(formatar_status_quadro(quadro) for quadro in resumo)

    if "quadro" in texto:
        nomes = ", ".join(f"\"{quadro['nome']}\"" for quadro in resumo)
        return (
            f"Você tem {len(resumo)} quadro(s): {nomes}. Use a barra \"Quadro\" no topo para "
            "trocar, criar, renomear ou excluir quadros. Pergunte, por exemplo, "
            "\"como está o quadro BTG?\" para ver o status de um deles."
        )

    for palavras, resposta in RESPOSTAS_AJUDA:
        if any(palavra in texto for palavra in palavras):
            return resposta

    return (
        "Não tenho certeza se entendi 🤔 Você pode me perguntar coisas como:\n"
        "• \"Como criar uma tarefa recorrente?\"\n"
        "• \"O que é limite de WIP?\"\n"
        "• \"Quantas tarefas atrasadas neste quadro?\"\n"
        "• \"Como está o quadro BTG?\""
    )


def responder_chat_com_claude(mensagem, quadro_id):
    """Resposta do XCL Help via API do Claude; None em caso de falha."""
    try:
        import anthropic

        resumo = estatisticas_dos_quadros()
        atual = next((quadro for quadro in resumo if quadro["id"] == quadro_id), None)
        contexto = json.dumps(
            {"quadro_em_exibicao": atual["nome"] if atual else None, "quadros": resumo},
            ensure_ascii=False,
        )

        cliente = anthropic.Anthropic()
        resposta = cliente.messages.create(
            model="claude-opus-4-8",
            max_tokens=600,
            system=(
                "Você é o XCL Help, assistente do Gerenciador de Tarefas XCL. Responda em "
                "português do Brasil, de forma curta e amigável. Funcionalidades do app: "
                "tarefas com título, descrição, data de início, data de vencimento, "
                "prioridade (Alta/Média/Baixa), categorias múltiplas, responsável (nome, "
                "sobrenome e cargo), recorrência (diária/semanal/mensal); subtarefas com "
                "responsável; comentários; histórico de atividade; quadros múltiplos; visões "
                "Lista, Kanban (com limite de WIP por coluna), Calendário e Saúde (tarefas "
                "em dia, prestes a vencer e atrasadas); busca, filtros (status, prioridade, "
                "categoria, período de início) e filtros salvos. Use os dados dos quadros do "
                "usuário abaixo para responder perguntas sobre os projetos dele.\n\n"
                f"Dados dos quadros do usuário (JSON): {contexto}"
            ),
            messages=[{"role": "user", "content": mensagem}],
        )
        return next(bloco.text for bloco in resposta.content if bloco.type == "text")
    except Exception:
        current_app.logger.warning(
            "Falha no chat via IA; usando as regras locais.", exc_info=True
        )
        return None


@api.route("/chat", methods=["POST"])
@exigir_login
def chat_ajuda():
    """Chatbot XCL Help: tira dúvidas sobre o app e responde sobre os quadros.

    Com ANTHROPIC_API_KEY definida usa a API do Claude; sem chave (ou em caso
    de falha), responde com regras locais baseadas em palavras-chave.
    """
    dados = corpo_json()
    mensagem = str(dados.get("mensagem") or "").strip()
    if not mensagem:
        return jsonify({"erro": "O campo 'mensagem' é obrigatório."}), 400
    if len(mensagem) > TAMANHO_MAX_MENSAGEM_CHAT:
        return jsonify(
            {"erro": f"A mensagem pode ter no máximo {TAMANHO_MAX_MENSAGEM_CHAT} caracteres."}
        ), 400

    quadro_id = dados.get("quadro_id")
    if not isinstance(quadro_id, int):
        quadro_id = None

    resposta, origem = None, "regras"
    if os.environ.get("ANTHROPIC_API_KEY"):
        resposta = responder_chat_com_claude(mensagem, quadro_id)
        if resposta is not None:
            origem = "ia"
    if resposta is None:
        resposta = responder_chat_com_regras(mensagem, quadro_id)

    return jsonify({"resposta": resposta, "origem": origem}), 200


# ---------------------------------------------------------------------------
# Rotas auxiliares
# ---------------------------------------------------------------------------

@api.route("/categorias", methods=["GET"])
@exigir_login
def listar_categorias():
    """Lista as categorias distintas já usadas pelo usuário."""
    linhas = obter_banco().execute(
        """
        SELECT DISTINCT categoria FROM tarefas
        WHERE usuario_id = ? AND categoria != ''
        ORDER BY categoria COLLATE NOCASE
        """,
        (g.usuario_id,),
    ).fetchall()
    return jsonify([linha["categoria"] for linha in linhas]), 200


@api.route("/health", methods=["GET"])
def health():
    """Verificação simples de saúde da API (útil para monitoramento/deploy)."""
    return jsonify({"status": "ok"}), 200


# ---------------------------------------------------------------------------
# Criação da aplicação
# ---------------------------------------------------------------------------

def create_app(caminho_banco=None):
    """Fábrica da aplicação. `caminho_banco` permite banco isolado nos testes."""
    app = Flask(__name__)
    app.config["BANCO"] = caminho_banco or os.environ.get("BANCO_DADOS", CAMINHO_PADRAO_BANCO)
    app.config["JSON_SORT_KEYS"] = False
    app.config["MAX_CONTENT_LENGTH"] = TAMANHO_MAX_CORPO  # recusa payloads gigantes

    # CORS restrito às origens do front-end (configurável por env)
    origens = os.environ.get(
        "ORIGENS_PERMITIDAS", "http://127.0.0.1:8080,http://localhost:8080"
    )
    CORS(app, origins=[origem.strip() for origem in origens.split(",") if origem.strip()])

    app.register_blueprint(api)
    app.teardown_appcontext(fechar_banco)

    # Respostas de erro sempre em JSON (em vez das páginas HTML padrão)
    @app.errorhandler(404)
    def rota_nao_encontrada(_erro):
        return jsonify({"erro": "Rota não encontrada."}), 404

    @app.errorhandler(405)
    def metodo_nao_permitido(_erro):
        return jsonify({"erro": "Método não permitido para esta rota."}), 405

    @app.errorhandler(413)
    def corpo_grande_demais(_erro):
        return jsonify({"erro": "Requisição grande demais (limite de 1 MB)."}), 413

    @app.errorhandler(500)
    def erro_interno(erro):
        app.logger.exception("Erro interno: %s", erro)
        return jsonify({"erro": "Erro interno do servidor."}), 500

    # Garante que as tabelas existem e aplica migrações leves
    with app.app_context():
        banco = obter_banco()
        banco.executescript(SQL_SCHEMA)
        migrar_banco(banco)
        banco.commit()

    return app


def migrar_banco(banco):
    """Migrações para bancos criados em versões anteriores do app."""
    colunas = {linha["name"] for linha in banco.execute("PRAGMA table_info(tarefas)")}
    if "quadro_id" not in colunas:
        banco.execute("ALTER TABLE tarefas ADD COLUMN quadro_id INTEGER REFERENCES quadros(id)")

    # Novas colunas de data de início e responsável (tarefas e subtarefas)
    if "data_inicio" not in colunas:
        banco.execute("ALTER TABLE tarefas ADD COLUMN data_inicio TEXT")
    for coluna in CAMPOS_RESPONSAVEL:
        if coluna not in colunas:
            banco.execute(f"ALTER TABLE tarefas ADD COLUMN {coluna} TEXT NOT NULL DEFAULT ''")

    colunas_sub = {linha["name"] for linha in banco.execute("PRAGMA table_info(subtarefas)")}
    for coluna in CAMPOS_RESPONSAVEL:
        if coluna not in colunas_sub:
            banco.execute(f"ALTER TABLE subtarefas ADD COLUMN {coluna} TEXT NOT NULL DEFAULT ''")

    colunas_com = {linha["name"] for linha in banco.execute("PRAGMA table_info(comentarios)")}
    if "autor" not in colunas_com:
        banco.execute("ALTER TABLE comentarios ADD COLUMN autor TEXT NOT NULL DEFAULT ''")

    # Todo usuário ganha um quadro padrão; tarefas antigas são movidas para ele
    for usuario in banco.execute("SELECT id FROM usuarios").fetchall():
        quadro = banco.execute(
            "SELECT id FROM quadros WHERE usuario_id = ? ORDER BY id LIMIT 1",
            (usuario["id"],),
        ).fetchone()
        if quadro is None:
            cursor = banco.execute(
                "INSERT INTO quadros (usuario_id, nome, criado_em) VALUES (?, ?, ?)",
                (usuario["id"], NOME_QUADRO_PADRAO, agora_iso()),
            )
            quadro_id = cursor.lastrowid
        else:
            quadro_id = quadro["id"]
        banco.execute(
            "UPDATE tarefas SET quadro_id = ? WHERE usuario_id = ? AND quadro_id IS NULL",
            (quadro_id, usuario["id"]),
        )


app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Debug desligado por padrão; ligue com FLASK_DEBUG=1 apenas em desenvolvimento
    modo_debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    porta = int(os.environ.get("PORTA", "5000"))
    app.run(debug=modo_debug, port=porta)
