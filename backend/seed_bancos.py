"""
Base de teste: quadros de bancos (BTG, ITAÚ, BRADESCO)
------------------------------------------------------
Cria três quadros com atividades bancárias realistas — responsáveis com nome,
sobrenome e cargo, datas de início e vencimento variadas (atrasadas, vencendo
hoje, prestes a vencer e futuras), subtarefas e comentários — para demonstrar
a aba Saúde, os filtros e o chatbot XCL Help com dados de verdade.

Uso (dentro da pasta backend, com as dependências instaladas):
    python seed_bancos.py                 -> usa/cria a conta demo (demo@xcl.com / demo123)
    python seed_bancos.py email@dominio   -> popula a conta já existente com esse e-mail

Rodar de novo é seguro: as tarefas dos quadros BTG/ITAÚ/BRADESCO são
recriadas do zero (os demais quadros do usuário não são tocados).
"""

import sqlite3
import sys
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

from app import agora_iso, create_app

EMAIL_DEMO = "demo@xcl.com"
SENHA_DEMO = "demo123"
NOME_DEMO = "Conta Demo XCL"


def dia(deslocamento):
    """Data ISO relativa a hoje (negativo = passado)."""
    return (date.today() + timedelta(days=deslocamento)).isoformat()


# Cada tarefa: (titulo, descricao, status, prioridade, categoria,
#               inicio, vencimento, responsavel (nome, sobrenome, cargo),
#               subtarefas [(titulo, concluida, responsavel)], comentarios)
QUADROS_BANCOS = {
    "BTG": [
        ("Conciliação diária de custódia",
         "Bater as posições de custódia com o relatório da B3 e apontar divergências.",
         "Em andamento", "Alta", "Operações",
         dia(-1), dia(0), ("Marina", "Albuquerque", "Analista de Operações"),
         [("Exportar posições da B3", True, ("Marina", "Albuquerque", "Analista de Operações")),
          ("Rodar planilha de batimento", False, ("Pedro", "Sales", "Assistente de Back Office")),
          ("Reportar divergências ao gestor", False, ("Marina", "Albuquerque", "Analista de Operações"))],
         ["Divergência de 3 ativos encontrada ontem — verificar eventos corporativos."]),
        ("Relatório mensal de risco de mercado",
         "Consolidar VaR, stress test e limites por mesa para o comitê de riscos.",
         "Pendente", "Alta", "Riscos",
         dia(-5), dia(-2), ("Rafael", "Nogueira", "Gerente de Riscos"),
         [("Coletar exposições das mesas", True, ("Luiza", "Prado", "Analista de Riscos")),
          ("Rodar cenários de stress", False, ("Luiza", "Prado", "Analista de Riscos"))],
         ["Comitê foi antecipado — priorizar!"]),
        ("Onboarding de cliente private",
         "Abertura de conta, KYC e perfil de investidor de novo cliente private.",
         "Em andamento", "Média", "Comercial",
         dia(-3), dia(2), ("Beatriz", "Fontes", "Banker Private"),
         [("Coletar documentação", True, ("Beatriz", "Fontes", "Banker Private")),
          ("Análise de compliance/KYC", False, ("Otávio", "Ramos", "Analista de Compliance")),
          ("Assinatura do termo de adesão", False, ("Beatriz", "Fontes", "Banker Private"))],
         []),
        ("Atualizar política de suitability",
         "Revisar a política conforme nova resolução CVM e publicar na intranet.",
         "Pendente", "Média", "Compliance",
         dia(1), dia(10), ("Otávio", "Ramos", "Analista de Compliance"),
         [("Mapear mudanças da resolução", False, ("Otávio", "Ramos", "Analista de Compliance"))],
         []),
        ("Fechamento da carteira administrada",
         "Apurar cotas, taxas e enviar extratos aos clientes da carteira administrada.",
         "Concluída", "Alta", "Operações",
         dia(-10), dia(-4), ("Marina", "Albuquerque", "Analista de Operações"),
         [("Apurar cotas do mês", True, ("Marina", "Albuquerque", "Analista de Operações")),
          ("Enviar extratos", True, ("Pedro", "Sales", "Assistente de Back Office"))],
         ["Fechamento sem pendências. 🎉"]),
        ("Treinamento da mesa de renda fixa",
         "Sessão interna sobre a nova plataforma de precificação de títulos.",
         "Pendente", "Baixa", "Pessoas",
         dia(5), dia(14), ("Rafael", "Nogueira", "Gerente de Riscos"),
         [], []),
    ],
    "ITAU": [
        ("Fechamento diário de câmbio",
         "Consolidar operações de câmbio comercial e enviar posição ao BACEN.",
         "Em andamento", "Alta", "Tesouraria",
         dia(0), dia(0), ("Camila", "Duarte", "Operadora de Câmbio"),
         [("Consolidar boletos do dia", False, ("Camila", "Duarte", "Operadora de Câmbio")),
          ("Transmitir ao BACEN", False, ("Henrique", "Vaz", "Analista de Tesouraria"))],
         []),
        ("Auditoria trimestral PLD/FT",
         "Revisar alertas de prevenção à lavagem de dinheiro do trimestre e formalizar dossiês.",
         "Pendente", "Alta", "Compliance",
         dia(-7), dia(-3), ("Sérgio", "Antunes", "Auditor Interno"),
         [("Extrair alertas do sistema", True, ("Sérgio", "Antunes", "Auditor Interno")),
          ("Analisar casos críticos", False, ("Paula", "Cardim", "Analista de PLD")),
          ("Formalizar dossiês", False, ("Paula", "Cardim", "Analista de PLD"))],
         ["Prazo regulatório — não pode atrasar mais."]),
        ("Atualização cadastral de clientes PJ",
         "Campanha de atualização de dados cadastrais das contas PJ da regional.",
         "Pendente", "Média", "Cadastro",
         dia(-2), dia(3), ("Fernanda", "Lopes", "Coordenadora de Cadastro"),
         [("Gerar lista de contas desatualizadas", True, ("Fernanda", "Lopes", "Coordenadora de Cadastro")),
          ("Disparar comunicação aos gerentes", False, ("Diego", "Farias", "Assistente Comercial"))],
         []),
        ("Migração do internet banking corporativo",
         "Apoiar a migração dos clientes corporate para a nova plataforma digital.",
         "Em andamento", "Média", "Tecnologia",
         dia(-4), dia(7), ("Thiago", "Bittencourt", "Gerente de Projetos TI"),
         [("Homologar ambiente", True, ("Aline", "Matos", "Analista de Sistemas")),
          ("Piloto com 10 clientes", False, ("Aline", "Matos", "Analista de Sistemas")),
          ("Plano de rollback", False, ("Thiago", "Bittencourt", "Gerente de Projetos TI"))],
         ["Piloto começa na próxima segunda."]),
        ("Relatório de metas da agência",
         "Consolidar resultado comercial do mês e apresentar à superintendência.",
         "Concluída", "Média", "Comercial",
         dia(-12), dia(-5), ("Diego", "Farias", "Assistente Comercial"),
         [("Consolidar planilha de metas", True, ("Diego", "Farias", "Assistente Comercial"))],
         []),
        ("Revisão de limites de crédito PJ",
         "Reavaliar limites das contas com rating rebaixado no último ciclo.",
         "Pendente", "Alta", "Crédito",
         dia(2), dia(6), ("Renata", "Siqueira", "Analista de Crédito Sênior"),
         [], []),
    ],
    "BRADESCO": [
        ("Campanha de crédito consignado",
         "Estruturar oferta de consignado para servidores públicos da região.",
         "Pendente", "Média", "Comercial",
         dia(-1), dia(4), ("Gustavo", "Peixoto", "Gerente Comercial"),
         [("Definir taxas da campanha", True, ("Gustavo", "Peixoto", "Gerente Comercial")),
          ("Treinar equipe de agências", False, ("Vanessa", "Rocha", "Supervisora de Vendas"))],
         []),
        ("Renovação de apólices empresariais",
         "Contatar clientes com apólices de seguro empresarial vencendo neste mês.",
         "Pendente", "Alta", "Seguros",
         dia(-6), dia(-1), ("Vanessa", "Rocha", "Supervisora de Vendas"),
         [("Gerar lista de apólices a vencer", True, ("Vanessa", "Rocha", "Supervisora de Vendas")),
          ("Agendar visitas prioritárias", False, ("Marcos", "Teles", "Consultor de Seguros"))],
         ["3 clientes grandes ainda sem retorno."]),
        ("Implantação do caixa 100% digital",
         "Projeto piloto de agência sem caixa físico no centro da cidade.",
         "Em andamento", "Alta", "Tecnologia",
         dia(-15), dia(15), ("Isabela", "Quintana", "Gerente de Inovação"),
         [("Instalar terminais de autoatendimento", True, ("Caio", "Moreira", "Técnico de Infraestrutura")),
          ("Treinar equipe de suporte", False, ("Isabela", "Quintana", "Gerente de Inovação")),
          ("Comunicar clientes da agência", False, ("Gustavo", "Peixoto", "Gerente Comercial"))],
         []),
        ("Comitê de crédito rural",
         "Preparar pauta e análises das propostas de crédito rural da semana.",
         "Pendente", "Alta", "Crédito",
         dia(0), dia(1), ("Larissa", "Brandão", "Analista de Crédito Rural"),
         [("Analisar 8 propostas pendentes", False, ("Larissa", "Brandão", "Analista de Crédito Rural"))],
         []),
        ("Fechamento contábil da regional",
         "Conferir lançamentos e enviar o pacote contábil ao corporativo.",
         "Concluída", "Média", "Contabilidade",
         dia(-9), dia(-3), ("Eduardo", "Pinho", "Contador"),
         [("Conferir lançamentos", True, ("Eduardo", "Pinho", "Contador")),
          ("Enviar pacote ao corporativo", True, ("Eduardo", "Pinho", "Contador"))],
         []),
        ("Programa de educação financeira",
         "Organizar palestras de educação financeira em escolas parceiras.",
         "Pendente", "Baixa", "Social",
         dia(7), dia(21), ("Isabela", "Quintana", "Gerente de Inovação"),
         [], []),
    ],
}


def obter_ou_criar_usuario(banco, email):
    """Devolve o id do usuário; cria a conta demo se o e-mail não existir."""
    usuario = banco.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone()
    if usuario is not None:
        return usuario["id"], False

    if email != EMAIL_DEMO:
        raise SystemExit(
            f"Nenhuma conta com o e-mail '{email}'. Crie a conta pela interface "
            "primeiro, ou rode sem argumentos para usar a conta demo."
        )

    cursor = banco.execute(
        "INSERT INTO usuarios (nome, email, senha_hash, criado_em) VALUES (?, ?, ?, ?)",
        (NOME_DEMO, EMAIL_DEMO, generate_password_hash(SENHA_DEMO), agora_iso()),
    )
    return cursor.lastrowid, True


def obter_ou_criar_quadro(banco, usuario_id, nome):
    """Devolve o id do quadro do usuário, criando-o se necessário."""
    quadro = banco.execute(
        "SELECT id FROM quadros WHERE usuario_id = ? AND nome = ?", (usuario_id, nome)
    ).fetchone()
    if quadro is not None:
        return quadro["id"]
    cursor = banco.execute(
        "INSERT INTO quadros (usuario_id, nome, criado_em) VALUES (?, ?, ?)",
        (usuario_id, nome, agora_iso()),
    )
    return cursor.lastrowid


def inserir_tarefas(banco, usuario_id, quadro_id, tarefas):
    """Insere as tarefas de um quadro (com subtarefas, comentários e histórico)."""
    for (titulo, descricao, status, prioridade, categoria, inicio, vencimento,
         responsavel, subtarefas, comentarios) in tarefas:
        concluida_em = agora_iso() if status == "Concluída" else None
        cursor = banco.execute(
            """
            INSERT INTO tarefas
                (usuario_id, quadro_id, titulo, descricao, status, prioridade, categoria,
                 data_inicio, data_vencimento, recorrencia,
                 responsavel_nome, responsavel_sobrenome, responsavel_cargo,
                 criada_em, concluida_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'nenhuma', ?, ?, ?, ?, ?)
            """,
            (usuario_id, quadro_id, titulo, descricao, status, prioridade, categoria,
             inicio, vencimento, responsavel[0], responsavel[1], responsavel[2],
             agora_iso(), concluida_em),
        )
        tarefa_id = cursor.lastrowid

        for sub_titulo, sub_concluida, sub_responsavel in subtarefas:
            banco.execute(
                """
                INSERT INTO subtarefas
                    (tarefa_id, titulo, concluida,
                     responsavel_nome, responsavel_sobrenome, responsavel_cargo)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (tarefa_id, sub_titulo, int(sub_concluida),
                 sub_responsavel[0], sub_responsavel[1], sub_responsavel[2]),
            )

        for texto in comentarios:
            banco.execute(
                "INSERT INTO comentarios (tarefa_id, texto, criado_em) VALUES (?, ?, ?)",
                (tarefa_id, texto, agora_iso()),
            )

        banco.execute(
            "INSERT INTO historico (tarefa_id, descricao, criado_em) VALUES (?, ?, ?)",
            (tarefa_id, "Tarefa criada (base de teste dos bancos)", agora_iso()),
        )


def main():
    email = sys.argv[1].strip().lower() if len(sys.argv) > 1 else EMAIL_DEMO

    # create_app() garante o schema e as migrações antes de popular
    app = create_app()
    banco = sqlite3.connect(app.config["BANCO"])
    banco.row_factory = sqlite3.Row
    banco.execute("PRAGMA foreign_keys = ON")

    usuario_id, criou_conta = obter_ou_criar_usuario(banco, email)

    for nome_quadro, tarefas in QUADROS_BANCOS.items():
        quadro_id = obter_ou_criar_quadro(banco, usuario_id, nome_quadro)
        # Reexecutar o seed recria as tarefas do quadro do zero (idempotente)
        banco.execute(
            "DELETE FROM tarefas WHERE quadro_id = ? AND usuario_id = ?",
            (quadro_id, usuario_id),
        )
        inserir_tarefas(banco, usuario_id, quadro_id, tarefas)
        print(f"Quadro {nome_quadro}: {len(tarefas)} tarefas criadas.")

    banco.commit()
    banco.close()

    print("\nBase de teste dos bancos criada com sucesso!")
    if criou_conta or email == EMAIL_DEMO:
        print(f"Entre com: {EMAIL_DEMO} / senha: {SENHA_DEMO}")
    else:
        print(f"Os quadros foram adicionados à conta {email}.")


if __name__ == "__main__":
    main()
