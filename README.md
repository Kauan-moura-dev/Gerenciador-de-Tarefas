# Gerenciador de Tarefas — XCL

Aplicação web completa para cadastrar e acompanhar tarefas do dia a dia, desenvolvida como desafio técnico do processo seletivo do Programa de Estágio da XCL — evoluída com funcionalidades inspiradas nos melhores gerenciadores do mercado (Todoist, TickTick, Trello) e com a **identidade visual oficial da XCL** ([xcl.digital](https://xcl.digital)): tema escuro, fonte **Gilroy** e o vermelho `#E7113C` da marca.

> **Versões:** esta pasta (`versao-2/`) contém a evolução completa do projeto. A **versão 1** — a entrega original e mais simples do desafio (JSON como armazenamento, CRUD básico) — está preservada na raiz do repositório, para mostrar a progressão do desenvolvimento.

## Funcionalidades

**Tarefas**
- Cadastrar, **editar**, concluir/reabrir e excluir tarefas (com confirmação antes de excluir)
- **Data de início e data de vencimento** com indicação de "Hoje", "Amanhã" e tarefas **vencidas**
- 👤 **Responsáveis** com nome, sobrenome e cargo em tarefas **e** subtarefas (etiqueta no cartão)
- **Prioridades** (Alta / Média / Baixa) com etiquetas coloridas
- **Categorias múltiplas** por tarefa (separadas por vírgula, com sugestão automática das já usadas)
- 💬 **Comentários** em cada tarefa, com **autor** e data (como no Jira)
- 📜 **Histórico de atividade**: cada criação e mudança (status, prioridade, prazo...) fica registrada e visível no modal de edição
- **Subtarefas** (checklist dentro de cada tarefa, com progresso `feitas/total`)
- **Tarefas recorrentes** (diária, semanal, mensal) — ao concluir, a próxima ocorrência é criada automaticamente e **herda o checklist** (subtarefas desmarcadas)
- 🤖 **Sugestão inteligente de prioridade e categoria**: enquanto você digita o título, o sistema sugere os campos automaticamente — via **API do Claude (Anthropic)** quando há chave configurada, ou por heurística local de palavras-chave (funciona offline)
- Carimbo de criação e de conclusão de cada tarefa

**Organização e visualização**
- 🗂️ **Quadros múltiplos** (boards): separe contextos como *Pessoal*, *Trabalho* e *Faculdade*, cada um com suas tarefas — criação, renomeação e exclusão pela interface
- 🚦 **Limite de WIP por coluna** do kanban: defina o máximo de tarefas em cada fase e a coluna avisa em vermelho quando estourar (o coração da metodologia Kanban)
- **Filtros salvos**: guarde combinações de busca + filtros com um nome e aplique com um clique
- ⏱️ **Ciclo médio** no painel de resumo: tempo médio entre criar e concluir (métrica de fluxo, como no Jira)
- **Busca** por título ou descrição, **insensível a acentos e caixa** ("credito" encontra "Crédito")
- **Filtros** por status, prioridade, categoria e **período da data de início** — com botão **Limpar filtros** que reseta tudo num clique
- **Ordenação** por data de criação, vencimento, **início**, prioridade ou ordem alfabética
- Quatro visões: **Lista**, **Kanban** com as três colunas da metodologia — *A fazer / Em andamento / Concluída* — e arrastar e soltar entre elas, **Calendário** mensal e 💚 **Saúde**
- 💚 **Aba Saúde**: índice de saúde do quadro (0–100%) com medidor visual e as tarefas agrupadas em **Atrasadas**, **Vencem hoje**, **Prestes a vencer** (até 3 dias), **Em dia** e **Sem data** — um raio-x do que precisa de atenção
- Fluxo de status completo: **Pendente → Em andamento → Concluída** (pelo kanban ou pelo modal de edição)
- Painel de resumo: pendentes, em andamento, vencidas e concluídas
- 🖥️ **Layout amplo em desktops**: em telas largas o formulário fica fixo à esquerda e as visões ocupam o restante da tela (até 1500px), aproveitando melhor monitores grandes

**Assistente e dados de demonstração**
- 💬 **Chatbot XCL Help** no canto da tela: tira dúvidas sobre qualquer função do organizador e responde perguntas sobre os seus quadros ("quantas tarefas atrasadas?", "como está o quadro BTG?") — via **API do Claude** quando há chave configurada, com fallback local por regras que funciona offline
- 🏦 **Base de teste dos bancos**: o script `backend/seed_bancos.py` cria os quadros **BTG**, **ITAU** e **BRADESCO** com atividades bancárias realistas (responsáveis com cargo, datas variadas, subtarefas e comentários) para demonstrar a aba Saúde, os filtros e o chatbot

**Conta e experiência**
- **Autenticação** com cadastro e login (senha com hash, sessão por token) — cada usuário vê apenas as próprias tarefas
- Interface **otimista**: as ações refletem na tela imediatamente e são revertidas se a API falhar
- Notificações (toasts) de sucesso e erro, estados de carregamento (skeletons) e mensagens de lista vazia contextuais
- O app **lembra o último quadro e a última visão** usados por usuário (sobrevivem ao F5)
- Exclusões sempre pedem **confirmação** — tarefas, quadros, subtarefas e comentários
- Acessibilidade: rótulos ARIA, `aria-live`, **focus trap** nos modais, fechamento com Esc, contraste AA nos textos secundários
- Layout responsivo (validado de 320px a 1600px, sem overflow horizontal)

## Tecnologias utilizadas

**Back-end**
- Python + Flask (API REST)
- SQLite (banco de dados embutido, sem servidor extra)
- Flask-CORS com **origens restritas** ao front-end
- Werkzeug para hash de senhas
- SDK oficial da **Anthropic** (integração opcional com a API do Claude para a sugestão inteligente)

**Front-end**
- HTML5, CSS3 e JavaScript puro (sem frameworks)
- Design system da XCL: paleta escura (`#0E0E10`), destaque vermelho (`#E7113C`), fonte Gilroy (auto-hospedada em `frontend/assets/fonts/`) e componentes no padrão do site oficial

**Qualidade e infraestrutura**
- Testes automatizados com **pytest** (77 testes cobrindo autenticação, CRUD, quadros, comentários, histórico, filtros, busca sem acentos, recorrência, subtarefas, responsáveis, data de início, chatbot, sugestão inteligente, isolamento entre usuários e casos de borda de robustez)
- **Auditoria QA completa** com browser real (Playwright + Chrome): 105 cenários em 13 módulos — ver `QA-REPORT-XCL.md`
- **Docker**: `docker compose up` sobe a aplicação completa (back-end com gunicorn + front-end com nginx)

## Arquitetura da solução

```
versao-2/
├── backend/
│   ├── app.py                -> API Flask (rotas, validação, regras de negócio, IA)
│   ├── seed_bancos.py        -> base de teste: quadros BTG/ITAU/BRADESCO
│   ├── test_app.py           -> testes automatizados (pytest)
│   ├── tarefas.db            -> banco SQLite (criado automaticamente, fora do git)
│   ├── requirements.txt      -> dependências de execução
│   ├── requirements-dev.txt  -> dependências de desenvolvimento (testes)
│   └── Dockerfile            -> imagem do back-end (gunicorn)
│
├── frontend/
│   ├── index.html            -> estrutura da página (auth, formulário, visões, modais)
│   ├── style.css             -> estilos (design system XCL)
│   ├── script.js             -> estado, consumo da API e renderização das visões
│   ├── assets/               -> logo XCL e fontes Gilroy auto-hospedadas
│   └── Dockerfile            -> imagem do front-end (nginx)
│
├── docker-compose.yml        -> sobe back-end + front-end com um comando
└── iniciar.bat               -> inicializador com dois cliques (Windows)
```

**Front-end:** responsável apenas pela interface. Toda leitura e escrita de dados passa pela API, com o token de sessão no cabeçalho `Authorization: Bearer <token>`.

**Back-end:** expõe uma API REST em Flask, responsável pela autenticação, validação, regras de negócio e persistência no SQLite.

### Rotas da API

| Método | Rota                        | Descrição                                        |
|--------|-----------------------------|--------------------------------------------------|
| POST   | /auth/registrar             | Cria uma conta e retorna um token                |
| POST   | /auth/login                 | Autentica e retorna um token                     |
| POST   | /auth/logout                | Encerra a sessão atual                           |
| GET    | /auth/eu                    | Dados do usuário autenticado                     |
| GET    | /tarefas                    | Lista as tarefas (filtros: `status`, `prioridade`, `categoria`, `busca`, `inicio_de`, `inicio_ate`) |
| POST   | /tarefas                    | Cria uma nova tarefa                             |
| PATCH  | /tarefas/\<id\>             | Edita campos e/ou o status de uma tarefa         |
| DELETE | /tarefas/\<id\>             | Exclui uma tarefa (subtarefas vão em cascata)    |
| POST   | /tarefas/\<id\>/subtarefas  | Adiciona uma subtarefa                           |
| PATCH  | /subtarefas/\<id\>          | Edita/alterna uma subtarefa                      |
| DELETE | /subtarefas/\<id\>          | Exclui uma subtarefa                             |
| POST   | /tarefas/sugestao           | 🤖 Sugere prioridade e categoria (IA/heurística) |
| POST   | /chat                       | 💬 Chatbot XCL Help (IA com fallback de regras)  |
| GET    | /quadros                    | Lista os quadros do usuário                      |
| POST   | /quadros                    | Cria um quadro                                   |
| PATCH  | /quadros/\<id\>             | Renomeia um quadro                               |
| DELETE | /quadros/\<id\>             | Exclui um quadro e as tarefas dele               |
| POST   | /tarefas/\<id\>/comentarios | Adiciona um comentário à tarefa                  |
| DELETE | /comentarios/\<id\>         | Exclui um comentário                             |
| GET    | /categorias                 | Categorias já usadas pelo usuário                |
| GET    | /health                     | Verificação de saúde da API                      |

Todas as rotas de tarefas exigem autenticação; cada usuário só acessa as próprias tarefas.

**Exemplo de tarefa (JSON):**
```json
{
  "id": 1,
  "titulo": "Estudar para o desafio XCL",
  "descricao": "Rever Flask e JS",
  "status": "Pendente",
  "prioridade": "Alta",
  "categoria": "Estudos",
  "data_inicio": "2026-07-05",
  "data_vencimento": "2026-07-10",
  "recorrencia": "semanal",
  "responsavel_nome": "Kauan",
  "responsavel_sobrenome": "Moura",
  "responsavel_cargo": "Estagiário",
  "criada_em": "2026-07-04T10:30:00",
  "concluida_em": null,
  "subtarefas": [
    { "id": 1, "titulo": "Rever rotas do Flask", "concluida": true,
      "responsavel_nome": "Kauan", "responsavel_sobrenome": "Moura", "responsavel_cargo": "Estagiário" }
  ]
}
```

## Como executar o projeto

> Todos os comandos abaixo são executados dentro da pasta `versao-2/`.

### Jeito rápido (Windows)

Dê dois cliques em **`iniciar.bat`**. Ele instala as dependências (só na primeira vez), sobe o back-end e o front-end em janelas próprias e abre o navegador em `http://127.0.0.1:8080`. Para encerrar, feche as duas janelas de servidor.

### Com Docker

```bash
docker compose up --build
```

Sobe o back-end (gunicorn, porta 5000) e o front-end (nginx, porta 8080) e cria um volume para o banco persistir entre reinicializações. Depois é só acessar `http://localhost:8080`.

### Jeito manual

#### 1. Back-end

```bash
cd backend
pip install -r requirements.txt
python app.py
```

O servidor sobe em `http://127.0.0.1:5000`. O banco `tarefas.db` é criado automaticamente na primeira execução.

#### 2. Front-end

Em outro terminal:

```bash
cd frontend
python -m http.server 8080
```

Depois, acesse `http://127.0.0.1:8080` no navegador e crie a sua conta.

> É necessário manter o back-end rodando enquanto usa o front-end, pois o front consome a API para todas as operações.

#### 3. Testes

```bash
cd backend
pip install -r requirements-dev.txt
pytest -v
```

Os testes usam um banco temporário isolado — nada toca o banco real.

#### 4. Base de teste dos bancos (opcional)

```bash
cd backend
python seed_bancos.py                  # cria/usa a conta demo (demo@xcl.com / demo123)
python seed_bancos.py seu@email.com    # ou adiciona os quadros à sua conta existente
```

Cria os quadros **BTG**, **ITAU** e **BRADESCO** com 18 atividades bancárias realistas — responsáveis com cargo, datas de início/vencimento variadas (atrasadas, vencendo hoje, futuras), subtarefas e comentários. Rodar de novo é seguro: as tarefas desses quadros são recriadas do zero, sem tocar nos seus demais quadros.

### Configuração (variáveis de ambiente, todas opcionais)

| Variável             | Padrão                                          | Descrição                          |
|----------------------|--------------------------------------------------|------------------------------------|
| `BANCO_DADOS`        | `backend/tarefas.db`                             | Caminho do arquivo SQLite          |
| `ORIGENS_PERMITIDAS` | `http://127.0.0.1:8080,http://localhost:8080`    | Origens liberadas no CORS          |
| `FLASK_DEBUG`        | `0`                                              | `1` liga o modo debug (só em dev)  |
| `PORTA`              | `5000`                                           | Porta do servidor                  |
| `ANTHROPIC_API_KEY`  | *(vazia)*                                        | Se definida, a sugestão de prioridade/categoria e o chatbot XCL Help usam a API do Claude; sem ela, usam a heurística/regras locais |

## Principais decisões tomadas durante o desenvolvimento

- **SQLite em vez de arquivo JSON:** o armazenamento original em JSON sofria com condições de corrida (duas requisições simultâneas podiam sobrescrever dados) e IDs reciclados. O SQLite resolve concorrência, integridade (chaves estrangeiras com exclusão em cascata) e IDs únicos (`AUTOINCREMENT`), sem exigir servidor de banco separado.
- **Autenticação por token com hash de senha:** senhas nunca são armazenadas em texto puro (hash via Werkzeug) e cada requisição é autorizada por token de sessão, garantindo isolamento total entre usuários.
- **Segurança por padrão:** modo debug desligado por padrão (liga-se por variável de ambiente) e CORS restrito às origens do front-end, em vez de aberto para qualquer site.
- **Interface otimista:** ações como concluir, excluir e marcar subtarefas atualizam a tela na hora e são revertidas com aviso caso a API falhe — mesma abordagem de apps como Todoist.
- **Recorrência ao concluir:** seguindo o padrão de mercado, concluir uma tarefa recorrente preserva o histórico (a tarefa concluída permanece) e agenda automaticamente a próxima ocorrência.
- **JavaScript puro no front-end:** mantido sem frameworks para preservar a simplicidade de entender e explicar o código, mesmo com três visões (lista, kanban e calendário).
- **Validação dupla:** todos os campos são validados no front-end (atributos HTML) e no back-end (limites de tamanho, formatos e valores permitidos), protegendo a API mesmo de requisições feitas diretamente.
- **Estudo do Jira aplicado ao contexto certo:** dos recursos do Jira, foram trazidos os que fazem sentido para um organizador pessoal — limite de WIP, comentários, histórico de atividade, quadros múltiplos, filtros salvos e ciclo médio — deixando de fora complexidade corporativa (sprints, story points, permissões) que pioraria a experiência.
- **Migração automática de banco:** a coluna `quadro_id`, o quadro padrão de cada usuário e as novas colunas de data de início e responsável são criados automaticamente na primeira execução após a atualização, sem perder nenhum dado existente.
- **IA com fallback:** a sugestão de prioridade/categoria e o chatbot XCL Help usam a API do Claude quando há chave configurada, mas caem automaticamente para heurísticas/regras locais se não houver chave ou se a chamada falhar — a funcionalidade nunca quebra a experiência e o app roda 100% offline. Structured outputs garantem que a resposta da IA seja sempre um JSON válido.
- **Aba Saúde calculada no front-end:** o diagnóstico (atrasadas, vencem hoje, prestes a vencer, em dia, sem data) é derivado das tarefas já carregadas, sem nova rota nem tráfego extra — e o índice pondera atraso (peso 1) e risco (peso 0,5) para dar um número honesto de 0 a 100%.
- **Chatbot com contexto dos quadros:** o XCL Help recebe um resumo estatístico dos quadros do usuário (contadores e títulos de tarefas atrasadas/próximas) a cada pergunta, então tanto a IA quanto o fallback de regras respondem sobre os projetos reais — sempre restritos ao usuário autenticado.
- **Versionamento em duas pastas:** a versão 1 (entrega original) foi preservada na raiz do repositório e a evolução vive em `versao-2/`, mantendo o histórico de progressão visível para os avaliadores.
- **Sem sincronização em tempo real entre abas (last-write-wins):** a fonte da verdade é sempre a API/SQLite; cada aba reflete o estado de quando carregou e a última escrita vence. Sincronização automática (polling/WebSocket) ficou de fora por simplicidade — trade-off documentado.

## 🤖 Uso de IA no desenvolvimento

Conforme incentivado pelo desafio, este projeto usou IA como ferramenta de desenvolvimento:

- **Ferramenta:** Claude Code (Anthropic), com o modelo Claude.
- **Como contribuiu:** análise comparativa com gerenciadores de mercado, implementação das funcionalidades da versão 2 (SQLite, autenticação, kanban/calendário, testes), aplicação da identidade visual da XCL a partir do site oficial e diagnóstico/correção de bugs (ex.: conflito de CSS entre `display: flex` e o atributo `hidden`).
- **Decisões técnicas tomadas a partir das sugestões:** manter JavaScript puro (sem frameworks) para preservar a simplicidade; escolher SQLite em vez de PostgreSQL pela portabilidade do desafio; preservar a versão 1 na raiz para evidenciar a evolução; e adotar o padrão "IA com fallback heurístico" para a sugestão inteligente funcionar sem depender de chave de API.
- **Além do desenvolvimento**, o produto final também **integra** IA: a rota `/tarefas/sugestao` consome a API do Claude para categorização automática e sugestão de prioridade — exatamente o exemplo citado nos diferenciais do desafio.

## Deploy (opcional)

O projeto está pronto para deploy:

1. **Back-end** (ex.: [Render](https://render.com) ou [Railway](https://railway.app)):
   - Adicione `gunicorn` ao `requirements.txt` e use o comando de start `gunicorn app:app`
   - Defina `ORIGENS_PERMITIDAS` com a URL pública do front-end
   - Observação: no plano gratuito dessas plataformas o disco pode ser efêmero; para persistência garantida, use um volume ou migre a string de conexão para PostgreSQL
2. **Front-end** (ex.: [Netlify](https://netlify.com) ou [Vercel](https://vercel.com)):
   - Publique a pasta `frontend/` como site estático
   - Ajuste a constante `URL_API` no topo do `script.js` para a URL pública do back-end

## Possíveis melhorias futuras

- Notificações/lembretes de vencimento (e-mail ou push)
- Compartilhamento de listas entre usuários
- Reordenação manual das tarefas (arrastar e soltar na lista)
- Migração para PostgreSQL em produção
- Expiração automática de sessões antigas

---

Desenvolvido por Kauan como parte do desafio técnico do Programa de Estágio XCL.
