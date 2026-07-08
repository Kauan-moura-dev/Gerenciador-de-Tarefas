"""
Testes automatizados da API do Gerenciador de Tarefas.

Como rodar (dentro da pasta backend, com as dependências instaladas):
    pytest -v

Cada teste usa um banco SQLite temporário e isolado (fixture `cliente`),
então nada aqui toca o banco real da aplicação.
"""

from datetime import date, timedelta

import pytest

from app import create_app


@pytest.fixture
def cliente(tmp_path):
    """Cria uma aplicação com banco temporário e devolve um test client."""
    app = create_app(caminho_banco=str(tmp_path / "teste.db"))
    app.config["TESTING"] = True
    with app.test_client() as cliente:
        yield cliente


def registrar_usuario(cliente, email="kauan@example.com", nome="Kauan", senha="123456"):
    """Registra um usuário e devolve o cabeçalho de autenticação pronto."""
    resposta = cliente.post(
        "/auth/registrar", json={"nome": nome, "email": email, "senha": senha}
    )
    assert resposta.status_code == 201
    token = resposta.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def criar_tarefa(cliente, auth, **campos):
    """Atalho para criar uma tarefa nos testes."""
    dados = {"titulo": "Tarefa de teste", **campos}
    resposta = cliente.post("/tarefas", json=dados, headers=auth)
    assert resposta.status_code == 201
    return resposta.get_json()


# ---------------------------------------------------------------------------
# Saúde e autenticação
# ---------------------------------------------------------------------------

def teste_health(cliente):
    resposta = cliente.get("/health")
    assert resposta.status_code == 200
    assert resposta.get_json() == {"status": "ok"}


def teste_registrar_e_login(cliente):
    auth = registrar_usuario(cliente)
    assert "Authorization" in auth

    resposta = cliente.post(
        "/auth/login", json={"email": "kauan@example.com", "senha": "123456"}
    )
    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["usuario"]["nome"] == "Kauan"
    assert corpo["token"]


def teste_registrar_email_duplicado(cliente):
    registrar_usuario(cliente)
    resposta = cliente.post(
        "/auth/registrar",
        json={"nome": "Outro", "email": "kauan@example.com", "senha": "123456"},
    )
    assert resposta.status_code == 409


@pytest.mark.parametrize(
    "dados",
    [
        {"nome": "", "email": "a@b.com", "senha": "123456"},
        {"nome": "Kauan", "email": "email-invalido", "senha": "123456"},
        {"nome": "Kauan", "email": "a@b.com", "senha": "123"},
    ],
)
def teste_registrar_dados_invalidos(cliente, dados):
    resposta = cliente.post("/auth/registrar", json=dados)
    assert resposta.status_code == 400


def teste_login_senha_errada(cliente):
    registrar_usuario(cliente)
    resposta = cliente.post(
        "/auth/login", json={"email": "kauan@example.com", "senha": "errada"}
    )
    assert resposta.status_code == 401


def teste_rotas_exigem_token(cliente):
    assert cliente.get("/tarefas").status_code == 401
    assert cliente.post("/tarefas", json={"titulo": "x"}).status_code == 401
    assert cliente.patch("/tarefas/1", json={}).status_code == 401
    assert cliente.delete("/tarefas/1").status_code == 401
    assert cliente.get("/categorias").status_code == 401


def teste_logout_invalida_token(cliente):
    auth = registrar_usuario(cliente)
    assert cliente.post("/auth/logout", headers=auth).status_code == 200
    assert cliente.get("/tarefas", headers=auth).status_code == 401


def teste_auth_eu(cliente):
    auth = registrar_usuario(cliente)
    resposta = cliente.get("/auth/eu", headers=auth)
    assert resposta.status_code == 200
    assert resposta.get_json()["email"] == "kauan@example.com"


# ---------------------------------------------------------------------------
# CRUD de tarefas
# ---------------------------------------------------------------------------

def teste_criar_tarefa_com_valores_padrao(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(cliente, auth, titulo="Estudar Flask")

    assert tarefa["titulo"] == "Estudar Flask"
    assert tarefa["status"] == "Pendente"
    assert tarefa["prioridade"] == "Média"
    assert tarefa["categoria"] == ""
    assert tarefa["data_inicio"] is None
    assert tarefa["data_vencimento"] is None
    assert tarefa["recorrencia"] == "nenhuma"
    assert tarefa["responsavel_nome"] == ""
    assert tarefa["responsavel_sobrenome"] == ""
    assert tarefa["responsavel_cargo"] == ""
    assert tarefa["criada_em"]
    assert tarefa["concluida_em"] is None
    assert tarefa["subtarefas"] == []


def teste_criar_tarefa_completa(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(
        cliente,
        auth,
        titulo="Prova de POO",
        descricao="Capítulos 1 a 4",
        prioridade="Alta",
        categoria="Estudos",
        data_vencimento="2026-07-10",
        recorrencia="semanal",
    )
    assert tarefa["prioridade"] == "Alta"
    assert tarefa["categoria"] == "Estudos"
    assert tarefa["data_vencimento"] == "2026-07-10"
    assert tarefa["recorrencia"] == "semanal"


@pytest.mark.parametrize(
    "dados",
    [
        {},                                            # sem título
        {"titulo": "   "},                             # título em branco
        {"titulo": "x" * 201},                         # título longo demais
        {"titulo": "ok", "prioridade": "Urgente"},     # prioridade inválida
        {"titulo": "ok", "data_vencimento": "10/07"},  # data em formato errado
        {"titulo": "ok", "data_inicio": "10/07"},      # data de início em formato errado
        {"titulo": "ok", "recorrencia": "anual"},      # recorrência inválida
        {"titulo": "ok", "responsavel_nome": "x" * 81},  # responsável longo demais
        {"titulo": "ok", "data_inicio": "2026-07-10",    # início depois do vencimento
         "data_vencimento": "2026-07-05"},
    ],
)
def teste_criar_tarefa_dados_invalidos(cliente, dados):
    auth = registrar_usuario(cliente)
    resposta = cliente.post("/tarefas", json=dados, headers=auth)
    assert resposta.status_code == 400


# ---------------------------------------------------------------------------
# Data de início e responsáveis
# ---------------------------------------------------------------------------

def teste_criar_tarefa_com_inicio_e_responsavel(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(
        cliente,
        auth,
        titulo="Conciliação de custódia",
        data_inicio="2026-07-01",
        data_vencimento="2026-07-10",
        responsavel_nome="Marina",
        responsavel_sobrenome="Albuquerque",
        responsavel_cargo="Analista de Operações",
    )
    assert tarefa["data_inicio"] == "2026-07-01"
    assert tarefa["responsavel_nome"] == "Marina"
    assert tarefa["responsavel_sobrenome"] == "Albuquerque"
    assert tarefa["responsavel_cargo"] == "Analista de Operações"


def teste_editar_inicio_e_responsavel(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(cliente, auth)

    corpo = cliente.patch(
        f"/tarefas/{tarefa['id']}",
        json={
            "data_inicio": "2026-07-03",
            "responsavel_nome": "Rafael",
            "responsavel_cargo": "Gerente",
        },
        headers=auth,
    ).get_json()
    assert corpo["data_inicio"] == "2026-07-03"
    assert corpo["responsavel_nome"] == "Rafael"
    assert corpo["responsavel_cargo"] == "Gerente"
    assert "Início definido para 2026-07-03" in [e["descricao"] for e in corpo["historico"]]

    # Remover a data de início
    corpo = cliente.patch(
        f"/tarefas/{tarefa['id']}", json={"data_inicio": None}, headers=auth
    ).get_json()
    assert corpo["data_inicio"] is None


def teste_filtro_por_data_de_inicio(cliente):
    auth = registrar_usuario(cliente)
    criar_tarefa(cliente, auth, titulo="Antiga", data_inicio="2026-06-01")
    criar_tarefa(cliente, auth, titulo="Recente", data_inicio="2026-07-01")
    criar_tarefa(cliente, auth, titulo="Sem início")

    def listar(query):
        resposta = cliente.get("/tarefas", query_string=query, headers=auth)
        assert resposta.status_code == 200
        return [t["titulo"] for t in resposta.get_json()]

    assert listar({"inicio_de": "2026-06-15"}) == ["Recente"]
    assert listar({"inicio_ate": "2026-06-15"}) == ["Antiga"]
    assert listar({"inicio_de": "2026-05-01", "inicio_ate": "2026-07-31"}) == ["Recente", "Antiga"]
    assert cliente.get(
        "/tarefas", query_string={"inicio_de": "15/06"}, headers=auth
    ).status_code == 400


def teste_recorrencia_desloca_inicio_e_copia_responsavel(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(
        cliente,
        auth,
        titulo="Fechamento semanal",
        data_inicio="2026-07-01",
        data_vencimento="2026-07-06",
        recorrencia="semanal",
        responsavel_nome="Camila",
        responsavel_sobrenome="Duarte",
        responsavel_cargo="Operadora",
    )
    resposta = cliente.patch(
        f"/tarefas/{tarefa['id']}", json={"status": "Concluída"}, headers=auth
    ).get_json()

    proxima = resposta["proxima_ocorrencia"]
    assert proxima["data_inicio"] == "2026-07-08"
    assert proxima["data_vencimento"] == "2026-07-13"
    assert proxima["responsavel_nome"] == "Camila"
    assert proxima["responsavel_cargo"] == "Operadora"


def teste_subtarefa_com_responsavel(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(cliente, auth)

    criada = cliente.post(
        f"/tarefas/{tarefa['id']}/subtarefas",
        json={
            "titulo": "Analisar propostas",
            "responsavel_nome": "Larissa",
            "responsavel_sobrenome": "Brandão",
            "responsavel_cargo": "Analista",
        },
        headers=auth,
    )
    assert criada.status_code == 201
    subtarefa = criada.get_json()
    assert subtarefa["responsavel_nome"] == "Larissa"
    assert subtarefa["responsavel_cargo"] == "Analista"

    # PATCH atualiza só o cargo e preserva o restante
    editada = cliente.patch(
        f"/subtarefas/{subtarefa['id']}",
        json={"responsavel_cargo": "Analista Sênior"},
        headers=auth,
    ).get_json()
    assert editada["responsavel_cargo"] == "Analista Sênior"
    assert editada["responsavel_nome"] == "Larissa"

    # O responsável aparece na listagem embutida
    listada = cliente.get("/tarefas", headers=auth).get_json()[0]
    assert listada["subtarefas"][0]["responsavel_sobrenome"] == "Brandão"

    # Responsável longo demais é recusado
    assert cliente.post(
        f"/tarefas/{tarefa['id']}/subtarefas",
        json={"titulo": "ok", "responsavel_cargo": "x" * 81},
        headers=auth,
    ).status_code == 400


def teste_editar_tarefa(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(cliente, auth)

    resposta = cliente.patch(
        f"/tarefas/{tarefa['id']}",
        json={"titulo": "Novo título", "descricao": "Nova descrição", "prioridade": "Baixa"},
        headers=auth,
    )
    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["titulo"] == "Novo título"
    assert corpo["descricao"] == "Nova descrição"
    assert corpo["prioridade"] == "Baixa"


def teste_concluir_e_reabrir_tarefa(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(cliente, auth)

    concluida = cliente.patch(
        f"/tarefas/{tarefa['id']}", json={"status": "Concluída"}, headers=auth
    ).get_json()
    assert concluida["status"] == "Concluída"
    assert concluida["concluida_em"] is not None

    reaberta = cliente.patch(
        f"/tarefas/{tarefa['id']}", json={"status": "Pendente"}, headers=auth
    ).get_json()
    assert reaberta["status"] == "Pendente"
    assert reaberta["concluida_em"] is None


def teste_fluxo_em_andamento(cliente):
    """Kanban de três colunas: Pendente -> Em andamento -> Concluída."""
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(cliente, auth)

    andamento = cliente.patch(
        f"/tarefas/{tarefa['id']}", json={"status": "Em andamento"}, headers=auth
    ).get_json()
    assert andamento["status"] == "Em andamento"
    assert andamento["concluida_em"] is None

    concluida = cliente.patch(
        f"/tarefas/{tarefa['id']}", json={"status": "Concluída"}, headers=auth
    ).get_json()
    assert concluida["concluida_em"] is not None

    # Voltar de Concluída para Em andamento limpa o carimbo de conclusão
    retomada = cliente.patch(
        f"/tarefas/{tarefa['id']}", json={"status": "Em andamento"}, headers=auth
    ).get_json()
    assert retomada["status"] == "Em andamento"
    assert retomada["concluida_em"] is None

    # O filtro da listagem reconhece o novo status
    filtradas = cliente.get(
        "/tarefas", query_string={"status": "Em andamento"}, headers=auth
    ).get_json()
    assert [t["id"] for t in filtradas] == [tarefa["id"]]


def teste_editar_tarefa_inexistente(cliente):
    auth = registrar_usuario(cliente)
    resposta = cliente.patch("/tarefas/999", json={"titulo": "x"}, headers=auth)
    assert resposta.status_code == 404


def teste_excluir_tarefa(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(cliente, auth)

    assert cliente.delete(f"/tarefas/{tarefa['id']}", headers=auth).status_code == 200
    assert cliente.delete(f"/tarefas/{tarefa['id']}", headers=auth).status_code == 404
    assert cliente.get("/tarefas", headers=auth).get_json() == []


def teste_isolamento_entre_usuarios(cliente):
    auth_a = registrar_usuario(cliente, email="a@example.com")
    auth_b = registrar_usuario(cliente, email="b@example.com")

    tarefa = criar_tarefa(cliente, auth_a, titulo="Só do usuário A")

    # Usuário B não vê nem consegue mexer na tarefa de A
    assert cliente.get("/tarefas", headers=auth_b).get_json() == []
    assert (
        cliente.patch(f"/tarefas/{tarefa['id']}", json={"titulo": "invadida"}, headers=auth_b)
        .status_code
        == 404
    )
    assert cliente.delete(f"/tarefas/{tarefa['id']}", headers=auth_b).status_code == 404


# ---------------------------------------------------------------------------
# Filtros da listagem
# ---------------------------------------------------------------------------

def teste_filtros_da_listagem(cliente):
    auth = registrar_usuario(cliente)
    criar_tarefa(cliente, auth, titulo="Estudar para a prova", categoria="Estudos")
    pendente = criar_tarefa(cliente, auth, titulo="Lavar a louça", categoria="Casa")
    criar_tarefa(cliente, auth, titulo="Pagar contas", prioridade="Alta")
    cliente.patch(f"/tarefas/{pendente['id']}", json={"status": "Concluída"}, headers=auth)

    def listar(query):
        return cliente.get(f"/tarefas?{query}", headers=auth).get_json()

    assert len(listar("status=Pendente")) == 2
    assert len(listar("status=Concluída")) == 1
    assert len(listar("prioridade=Alta")) == 1
    assert len(listar("categoria=Estudos")) == 1
    assert [t["titulo"] for t in listar("busca=prova")] == ["Estudar para a prova"]


# ---------------------------------------------------------------------------
# Recorrência
# ---------------------------------------------------------------------------

def teste_concluir_tarefa_recorrente_cria_proxima_ocorrencia(cliente):
    auth = registrar_usuario(cliente)
    vencimento = date(2026, 7, 6)
    tarefa = criar_tarefa(
        cliente,
        auth,
        titulo="Regar as plantas",
        data_vencimento=vencimento.isoformat(),
        recorrencia="semanal",
    )

    resposta = cliente.patch(
        f"/tarefas/{tarefa['id']}", json={"status": "Concluída"}, headers=auth
    ).get_json()

    proxima = resposta["proxima_ocorrencia"]
    assert proxima["titulo"] == "Regar as plantas"
    assert proxima["status"] == "Pendente"
    assert proxima["recorrencia"] == "semanal"
    assert proxima["data_vencimento"] == (vencimento + timedelta(weeks=1)).isoformat()

    # A lista agora tem a concluída + a próxima ocorrência
    assert len(cliente.get("/tarefas", headers=auth).get_json()) == 2


def teste_recorrencia_mensal_ajusta_fim_de_mes(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(
        cliente,
        auth,
        titulo="Fechamento do mês",
        data_vencimento="2026-01-31",
        recorrencia="mensal",
    )
    resposta = cliente.patch(
        f"/tarefas/{tarefa['id']}", json={"status": "Concluída"}, headers=auth
    ).get_json()
    # Janeiro 31 -> Fevereiro 28 (2026 não é bissexto)
    assert resposta["proxima_ocorrencia"]["data_vencimento"] == "2026-02-28"


def teste_tarefa_sem_recorrencia_nao_duplica(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(cliente, auth)
    resposta = cliente.patch(
        f"/tarefas/{tarefa['id']}", json={"status": "Concluída"}, headers=auth
    ).get_json()
    assert "proxima_ocorrencia" not in resposta
    assert len(cliente.get("/tarefas", headers=auth).get_json()) == 1


# ---------------------------------------------------------------------------
# Subtarefas
# ---------------------------------------------------------------------------

def teste_crud_de_subtarefas(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(cliente, auth)

    criada = cliente.post(
        f"/tarefas/{tarefa['id']}/subtarefas", json={"titulo": "Passo 1"}, headers=auth
    )
    assert criada.status_code == 201
    subtarefa = criada.get_json()
    assert subtarefa["concluida"] is False

    # A subtarefa aparece embutida na listagem de tarefas
    listada = cliente.get("/tarefas", headers=auth).get_json()[0]
    assert listada["subtarefas"][0]["titulo"] == "Passo 1"

    alternada = cliente.patch(
        f"/subtarefas/{subtarefa['id']}", json={"concluida": True}, headers=auth
    )
    assert alternada.status_code == 200
    assert alternada.get_json()["concluida"] is True

    assert cliente.delete(f"/subtarefas/{subtarefa['id']}", headers=auth).status_code == 200
    assert cliente.delete(f"/subtarefas/{subtarefa['id']}", headers=auth).status_code == 404


def teste_subtarefa_sem_titulo(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(cliente, auth)
    resposta = cliente.post(
        f"/tarefas/{tarefa['id']}/subtarefas", json={"titulo": ""}, headers=auth
    )
    assert resposta.status_code == 400


def teste_excluir_tarefa_remove_subtarefas_em_cascata(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(cliente, auth)
    subtarefa = cliente.post(
        f"/tarefas/{tarefa['id']}/subtarefas", json={"titulo": "Passo 1"}, headers=auth
    ).get_json()

    cliente.delete(f"/tarefas/{tarefa['id']}", headers=auth)
    resposta = cliente.patch(
        f"/subtarefas/{subtarefa['id']}", json={"concluida": True}, headers=auth
    )
    assert resposta.status_code == 404


def teste_subtarefa_de_outro_usuario(cliente):
    auth_a = registrar_usuario(cliente, email="a@example.com")
    auth_b = registrar_usuario(cliente, email="b@example.com")
    tarefa = criar_tarefa(cliente, auth_a)
    subtarefa = cliente.post(
        f"/tarefas/{tarefa['id']}/subtarefas", json={"titulo": "Privada"}, headers=auth_a
    ).get_json()

    assert (
        cliente.patch(f"/subtarefas/{subtarefa['id']}", json={"concluida": True}, headers=auth_b)
        .status_code
        == 404
    )


# ---------------------------------------------------------------------------
# Categorias
# ---------------------------------------------------------------------------

def teste_listar_categorias(cliente):
    auth = registrar_usuario(cliente)
    criar_tarefa(cliente, auth, categoria="Estudos")
    criar_tarefa(cliente, auth, categoria="Casa")
    criar_tarefa(cliente, auth, categoria="Estudos")
    criar_tarefa(cliente, auth)  # sem categoria

    resposta = cliente.get("/categorias", headers=auth)
    assert resposta.status_code == 200
    assert resposta.get_json() == ["Casa", "Estudos"]


# ---------------------------------------------------------------------------
# Sugestão de prioridade e categoria
# ---------------------------------------------------------------------------

@pytest.fixture
def sem_chave_ia(monkeypatch):
    """Garante que os testes usem a heurística local, nunca a API externa."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def teste_sugestao_exige_token(cliente):
    assert cliente.post("/tarefas/sugestao", json={"titulo": "x"}).status_code == 401


def teste_sugestao_sem_titulo(cliente, sem_chave_ia):
    auth = registrar_usuario(cliente)
    resposta = cliente.post("/tarefas/sugestao", json={"titulo": " "}, headers=auth)
    assert resposta.status_code == 400


@pytest.mark.parametrize(
    ("titulo", "prioridade", "categoria"),
    [
        ("Pagar o boleto do aluguel", "Alta", "Financeiro"),
        ("Consulta com o dentista", "Alta", "Saúde"),
        ("Assistir um filme no fim de semana", "Baixa", "Lazer"),
        ("Estudar para o vestibular", "Média", "Estudos"),
        ("Lavar a roupa", "Média", "Casa"),
        ("Preparar a apresentação do projeto", "Alta", "Trabalho"),
    ],
)
def teste_sugestao_heuristica(cliente, sem_chave_ia, titulo, prioridade, categoria):
    auth = registrar_usuario(cliente)
    resposta = cliente.post("/tarefas/sugestao", json={"titulo": titulo}, headers=auth)
    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["prioridade"] == prioridade
    assert corpo["categoria"] == categoria
    assert corpo["origem"] == "heuristica"


def teste_sugestao_sem_palavras_conhecidas(cliente, sem_chave_ia):
    auth = registrar_usuario(cliente)
    corpo = cliente.post(
        "/tarefas/sugestao", json={"titulo": "Fazer aquilo combinado"}, headers=auth
    ).get_json()
    assert corpo == {"prioridade": "Média", "categoria": "", "origem": "heuristica"}


def teste_sugestao_considera_descricao(cliente, sem_chave_ia):
    auth = registrar_usuario(cliente)
    corpo = cliente.post(
        "/tarefas/sugestao",
        json={"titulo": "Compromisso importante", "descricao": "consulta com o médico"},
        headers=auth,
    ).get_json()
    assert corpo["prioridade"] == "Alta"
    assert corpo["categoria"] == "Saúde"


# ---------------------------------------------------------------------------
# Quadros (múltiplos boards)
# ---------------------------------------------------------------------------

def teste_registro_cria_quadro_padrao(cliente):
    auth = registrar_usuario(cliente)
    quadros = cliente.get("/quadros", headers=auth).get_json()
    assert len(quadros) == 1
    assert quadros[0]["nome"] == "Meu quadro"


def teste_crud_de_quadros(cliente):
    auth = registrar_usuario(cliente)

    criado = cliente.post("/quadros", json={"nome": "Trabalho"}, headers=auth)
    assert criado.status_code == 201
    quadro = criado.get_json()

    renomeado = cliente.patch(f"/quadros/{quadro['id']}", json={"nome": "Faculdade"}, headers=auth)
    assert renomeado.get_json()["nome"] == "Faculdade"

    assert cliente.delete(f"/quadros/{quadro['id']}", headers=auth).status_code == 200
    assert len(cliente.get("/quadros", headers=auth).get_json()) == 1


def teste_quadro_com_nome_duplicado_e_recusado(cliente):
    auth = registrar_usuario(cliente)
    assert cliente.post("/quadros", json={"nome": "BTG"}, headers=auth).status_code == 201
    # duplicado exato e com caixa diferente são recusados
    assert cliente.post("/quadros", json={"nome": "BTG"}, headers=auth).status_code == 409
    assert cliente.post("/quadros", json={"nome": "btg"}, headers=auth).status_code == 409

    outro = cliente.post("/quadros", json={"nome": "ITAU"}, headers=auth).get_json()
    # renomear para um nome já usado também é recusado...
    assert cliente.patch(
        f"/quadros/{outro['id']}", json={"nome": "BTG"}, headers=auth
    ).status_code == 409
    # ...mas renomear para o próprio nome (ex: mudar caixa) é permitido
    assert cliente.patch(
        f"/quadros/{outro['id']}", json={"nome": "Itau"}, headers=auth
    ).status_code == 200


def teste_nao_exclui_o_ultimo_quadro(cliente):
    auth = registrar_usuario(cliente)
    quadro = cliente.get("/quadros", headers=auth).get_json()[0]
    assert cliente.delete(f"/quadros/{quadro['id']}", headers=auth).status_code == 400


def teste_tarefas_separadas_por_quadro(cliente):
    auth = registrar_usuario(cliente)
    padrao = cliente.get("/quadros", headers=auth).get_json()[0]
    trabalho = cliente.post("/quadros", json={"nome": "Trabalho"}, headers=auth).get_json()

    criar_tarefa(cliente, auth, titulo="Pessoal")  # sem quadro_id -> quadro padrão
    criar_tarefa(cliente, auth, titulo="Relatório", quadro_id=trabalho["id"])

    do_padrao = cliente.get(
        "/tarefas", query_string={"quadro_id": padrao["id"]}, headers=auth
    ).get_json()
    do_trabalho = cliente.get(
        "/tarefas", query_string={"quadro_id": trabalho["id"]}, headers=auth
    ).get_json()

    assert [t["titulo"] for t in do_padrao] == ["Pessoal"]
    assert [t["titulo"] for t in do_trabalho] == ["Relatório"]
    assert do_trabalho[0]["quadro_id"] == trabalho["id"]


def teste_excluir_quadro_remove_as_tarefas_dele(cliente):
    auth = registrar_usuario(cliente)
    quadro = cliente.post("/quadros", json={"nome": "Temporário"}, headers=auth).get_json()
    criar_tarefa(cliente, auth, titulo="Some comigo", quadro_id=quadro["id"])

    cliente.delete(f"/quadros/{quadro['id']}", headers=auth)
    assert cliente.get("/tarefas", headers=auth).get_json() == []


def teste_quadro_de_outro_usuario(cliente):
    auth_a = registrar_usuario(cliente, email="a@example.com")
    auth_b = registrar_usuario(cliente, email="b@example.com")
    quadro_a = cliente.get("/quadros", headers=auth_a).get_json()[0]

    resposta = cliente.post(
        "/tarefas", json={"titulo": "Invasão", "quadro_id": quadro_a["id"]}, headers=auth_b
    )
    assert resposta.status_code == 404
    assert cliente.delete(f"/quadros/{quadro_a['id']}", headers=auth_b).status_code == 404


# ---------------------------------------------------------------------------
# Comentários
# ---------------------------------------------------------------------------

def teste_crud_de_comentarios(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(cliente, auth)

    criado = cliente.post(
        f"/tarefas/{tarefa['id']}/comentarios", json={"texto": "Começar amanhã"}, headers=auth
    )
    assert criado.status_code == 201
    comentario = criado.get_json()
    assert comentario["criado_em"]
    assert comentario["autor"] == "Kauan"  # nome de quem comentou

    listada = cliente.get("/tarefas", headers=auth).get_json()[0]
    assert [c["texto"] for c in listada["comentarios"]] == ["Começar amanhã"]
    assert listada["comentarios"][0]["autor"] == "Kauan"

    assert cliente.delete(f"/comentarios/{comentario['id']}", headers=auth).status_code == 200
    assert cliente.delete(f"/comentarios/{comentario['id']}", headers=auth).status_code == 404


def teste_comentario_invalido(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(cliente, auth)
    url = f"/tarefas/{tarefa['id']}/comentarios"

    assert cliente.post(url, json={"texto": "  "}, headers=auth).status_code == 400
    assert cliente.post(url, json={"texto": "x" * 501}, headers=auth).status_code == 400


def teste_comentario_de_outro_usuario(cliente):
    auth_a = registrar_usuario(cliente, email="a@example.com")
    auth_b = registrar_usuario(cliente, email="b@example.com")
    tarefa = criar_tarefa(cliente, auth_a)
    comentario = cliente.post(
        f"/tarefas/{tarefa['id']}/comentarios", json={"texto": "Privado"}, headers=auth_a
    ).get_json()

    assert cliente.post(
        f"/tarefas/{tarefa['id']}/comentarios", json={"texto": "Oi"}, headers=auth_b
    ).status_code == 404
    assert cliente.delete(f"/comentarios/{comentario['id']}", headers=auth_b).status_code == 404


# ---------------------------------------------------------------------------
# Histórico de atividade
# ---------------------------------------------------------------------------

def teste_historico_registra_criacao_e_mudancas(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(cliente, auth)
    assert [e["descricao"] for e in tarefa["historico"]] == ["Tarefa criada"]

    cliente.patch(f"/tarefas/{tarefa['id']}", json={"status": "Em andamento"}, headers=auth)
    atualizada = cliente.patch(
        f"/tarefas/{tarefa['id']}",
        json={"prioridade": "Alta", "data_vencimento": "2026-07-10"},
        headers=auth,
    ).get_json()

    descricoes = [e["descricao"] for e in atualizada["historico"]]
    assert descricoes[0] == "Tarefa criada"
    assert "Status: Pendente → Em andamento" in descricoes
    assert "Prioridade: Média → Alta" in descricoes
    assert "Vencimento definido para 2026-07-10" in descricoes


def teste_historico_ignora_edicao_sem_mudanca(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(cliente, auth, titulo="Fixa")
    atualizada = cliente.patch(
        f"/tarefas/{tarefa['id']}", json={"titulo": "Fixa"}, headers=auth
    ).get_json()
    assert [e["descricao"] for e in atualizada["historico"]] == ["Tarefa criada"]


def teste_historico_da_ocorrencia_recorrente(cliente):
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(
        cliente, auth, titulo="Semanal", data_vencimento="2026-07-06", recorrencia="semanal"
    )
    resposta = cliente.patch(
        f"/tarefas/{tarefa['id']}", json={"status": "Concluída"}, headers=auth
    ).get_json()
    descricoes = [e["descricao"] for e in resposta["proxima_ocorrencia"]["historico"]]
    assert descricoes == ["Criada automaticamente pela recorrência"]


# ---------------------------------------------------------------------------
# Chatbot XCL Help
# ---------------------------------------------------------------------------

def teste_chat_exige_token(cliente):
    assert cliente.post("/chat", json={"mensagem": "oi"}).status_code == 401


def teste_chat_mensagem_invalida(cliente, sem_chave_ia):
    auth = registrar_usuario(cliente)
    assert cliente.post("/chat", json={"mensagem": "  "}, headers=auth).status_code == 400
    assert cliente.post(
        "/chat", json={"mensagem": "x" * 1001}, headers=auth
    ).status_code == 400


def teste_chat_saudacao_tem_resposta_propria(cliente, sem_chave_ia):
    auth = registrar_usuario(cliente)
    corpo = cliente.post("/chat", json={"mensagem": "Oi!"}, headers=auth).get_json()
    assert "ajudar" in corpo["resposta"].lower()


def teste_chat_responde_duvida_sobre_o_app(cliente, sem_chave_ia):
    auth = registrar_usuario(cliente)
    corpo = cliente.post(
        "/chat", json={"mensagem": "O que é limite de WIP?"}, headers=auth
    ).get_json()
    assert corpo["origem"] == "regras"
    assert "WIP" in corpo["resposta"]


def teste_chat_responde_status_do_quadro(cliente, sem_chave_ia):
    auth = registrar_usuario(cliente)
    quadro = cliente.get("/quadros", headers=auth).get_json()[0]
    criar_tarefa(cliente, auth, titulo="Boleto vencido", data_vencimento="2020-01-01")
    criar_tarefa(cliente, auth, titulo="Sem prazo")

    corpo = cliente.post(
        "/chat",
        json={"mensagem": "Quantas tarefas atrasadas?", "quadro_id": quadro["id"]},
        headers=auth,
    ).get_json()
    assert "Boleto vencido" in corpo["resposta"]
    assert "2 tarefa(s)" in corpo["resposta"]


def teste_chat_responde_sobre_quadro_citado_pelo_nome(cliente, sem_chave_ia):
    auth = registrar_usuario(cliente)
    btg = cliente.post("/quadros", json={"nome": "BTG"}, headers=auth).get_json()
    criar_tarefa(cliente, auth, titulo="Conciliação", quadro_id=btg["id"])

    corpo = cliente.post(
        "/chat", json={"mensagem": "como está o quadro btg?"}, headers=auth
    ).get_json()
    assert '"BTG"' in corpo["resposta"]
    assert "1 tarefa(s)" in corpo["resposta"]


def teste_chat_nao_vaza_quadros_de_outro_usuario(cliente, sem_chave_ia):
    auth_a = registrar_usuario(cliente, email="a@example.com")
    auth_b = registrar_usuario(cliente, email="b@example.com")
    secreto = cliente.post("/quadros", json={"nome": "Secreto"}, headers=auth_a).get_json()
    criar_tarefa(cliente, auth_a, titulo="Confidencial", quadro_id=secreto["id"])

    corpo = cliente.post(
        "/chat", json={"mensagem": "resumo de todos os quadros"}, headers=auth_b
    ).get_json()
    assert "Secreto" not in corpo["resposta"]
    assert "Confidencial" not in corpo["resposta"]


# ---------------------------------------------------------------------------
# Robustez (casos de borda encontrados em QA)
# ---------------------------------------------------------------------------

def teste_corpo_json_nao_objeto_nao_quebra(cliente):
    """Um corpo JSON válido mas que não é objeto (lista, string, número)
    não pode derrubar a API com erro 500."""
    auth = registrar_usuario(cliente)

    assert cliente.post("/tarefas", json=[1, 2, 3], headers=auth).status_code == 400
    assert cliente.post("/tarefas", json="texto", headers=auth).status_code == 400
    assert cliente.post("/auth/registrar", json=42).status_code == 400
    assert cliente.post("/auth/login", json=[]).status_code == 401

    tarefa = criar_tarefa(cliente, auth)
    assert (
        cliente.patch(f"/tarefas/{tarefa['id']}", json=["x"], headers=auth).status_code
        == 400
    )


def teste_registro_respeita_limites_de_tamanho(cliente):
    def registrar(nome="Ana", email="ana@example.com", senha="123456"):
        return cliente.post(
            "/auth/registrar", json={"nome": nome, "email": email, "senha": senha}
        ).status_code

    assert registrar(nome="x" * 101) == 400
    assert registrar(email="a" * 250 + "@example.com") == 400
    assert registrar(senha="x" * 129) == 400
    assert registrar() == 201  # dentro dos limites continua funcionando


def teste_busca_ignora_acentos_e_caixa(cliente):
    """"credito" precisa encontrar "Crédito" (e vice-versa)."""
    auth = registrar_usuario(cliente)
    criar_tarefa(cliente, auth, titulo="Comitê de crédito rural")
    criar_tarefa(cliente, auth, titulo="Outra coisa", descricao="Reunião de operações")

    def buscar(termo):
        return [
            t["titulo"]
            for t in cliente.get("/tarefas", query_string={"busca": termo}, headers=auth).get_json()
        ]

    assert buscar("credito") == ["Comitê de crédito rural"]
    assert buscar("CRÉDITO") == ["Comitê de crédito rural"]
    assert buscar("comite") == ["Comitê de crédito rural"]
    assert buscar("reuniao") == ["Outra coisa"]  # acento na descrição


def teste_busca_trata_curingas_como_texto(cliente):
    """% e _ digitados na busca são texto literal, não curingas do LIKE."""
    auth = registrar_usuario(cliente)
    criar_tarefa(cliente, auth, titulo="Projeto 100% concluído")
    criar_tarefa(cliente, auth, titulo="Outra tarefa qualquer")

    com_percentual = cliente.get(
        "/tarefas", query_string={"busca": "100%"}, headers=auth
    ).get_json()
    assert [t["titulo"] for t in com_percentual] == ["Projeto 100% concluído"]

    so_percentual = cliente.get(
        "/tarefas", query_string={"busca": "%"}, headers=auth
    ).get_json()
    assert [t["titulo"] for t in so_percentual] == ["Projeto 100% concluído"]


def teste_corpo_gigante_e_recusado(cliente):
    """Payloads acima de 1 MB são recusados com 413 (proteção da API)."""
    auth = registrar_usuario(cliente)
    resposta = cliente.post(
        "/tarefas",
        json={"titulo": "ok", "descricao": "x" * (2 * 1024 * 1024)},
        headers=auth,
    )
    assert resposta.status_code == 413
    assert "erro" in resposta.get_json()


def teste_recorrencia_copia_subtarefas_desmarcadas(cliente):
    """A próxima ocorrência de uma tarefa recorrente herda o checklist,
    com todas as subtarefas desmarcadas."""
    auth = registrar_usuario(cliente)
    tarefa = criar_tarefa(
        cliente, auth,
        titulo="Fechamento semanal",
        data_vencimento="2026-07-06",
        recorrencia="semanal",
    )
    cliente.post(f"/tarefas/{tarefa['id']}/subtarefas", json={"titulo": "Passo 1"}, headers=auth)
    passo2 = cliente.post(
        f"/tarefas/{tarefa['id']}/subtarefas", json={"titulo": "Passo 2"}, headers=auth
    ).get_json()
    cliente.patch(f"/subtarefas/{passo2['id']}", json={"concluida": True}, headers=auth)

    resposta = cliente.patch(
        f"/tarefas/{tarefa['id']}", json={"status": "Concluída"}, headers=auth
    ).get_json()

    proxima = resposta["proxima_ocorrencia"]
    assert [s["titulo"] for s in proxima["subtarefas"]] == ["Passo 1", "Passo 2"]
    assert all(not s["concluida"] for s in proxima["subtarefas"])
