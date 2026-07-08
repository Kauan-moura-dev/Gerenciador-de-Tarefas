# Gerenciador de Tarefas

Aplicação web simples para cadastrar e acompanhar tarefas do dia a dia, desenvolvida como desafio técnico do processo seletivo do Programa de Estágio da XCL.

## Tecnologias utilizadas

**Back-end**
- Python
- Flask
- Flask-CORS (para permitir a comunicação entre front-end e back-end)

**Front-end**
- HTML5
- CSS3 (tema escuro inspirado na identidade visual da XCL, com Google Fonts Space Grotesk + Inter)
- JavaScript (puro, sem frameworks)

**Armazenamento**
- Arquivo JSON (`backend/tasks.json`), conforme permitido no desafio

**Testes**
- Pytest (testes automatizados das rotas da API)

## Arquitetura da solução

O projeto segue uma arquitetura separada entre front-end e back-end, que se comunicam por meio de uma API REST:

```
gerenciador-tarefas/
├── backend/
│   ├── app.py                -> API Flask (rotas do CRUD)
│   ├── tasks.json            -> "banco de dados" em arquivo JSON
│   ├── requirements.txt      -> dependências de produção
│   ├── requirements-dev.txt  -> dependências de desenvolvimento (pytest)
│   └── tests/
│       └── test_app.py       -> testes automatizados das rotas da API
│
└── frontend/
    ├── index.html          -> estrutura da página
    ├── style.css           -> estilos
    └── script.js           -> lógica de consumo da API (fetch)
```

**Front-end:** responsável apenas pela interface. Não acessa o arquivo JSON diretamente — toda leitura e escrita de dados passa pela API.

**Back-end:** expõe uma API REST em Flask, responsável por toda a regra de negócio e pela persistência dos dados no arquivo `tasks.json`.

### Rotas da API

| Método | Rota            | Descrição                        |
|--------|-----------------|-----------------------------------|
| GET    | /tarefas        | Lista todas as tarefas (aceita `?ordenar_por=prioridade` ou `?ordenar_por=data_vencimento`) |
| POST   | /tarefas        | Cria uma nova tarefa              |
| PATCH  | /tarefas/\<id\>  | Altera status, título, descrição, prioridade e/ou data de vencimento |
| DELETE | /tarefas/\<id\>  | Exclui uma tarefa                 |

**Exemplo de tarefa (JSON):**
```json
{
  "id": 1,
  "titulo": "Estudar para o desafio XCL",
  "descricao": "Rever Flask e JS",
  "status": "Pendente",
  "prioridade": "Alta",
  "data_vencimento": "2026-07-08"
}
```

## Como executar o projeto

### 1. Back-end

```bash
cd backend
pip install -r requirements.txt
python app.py
```

O servidor sobe em `http://127.0.0.1:5000`.

### 2. Front-end

Em outro terminal:

```bash
cd frontend
python -m http.server 8080
```

Depois, acesse `http://127.0.0.1:8080` no navegador.

> É necessário manter o back-end rodando enquanto usa o front-end, pois o front consome a API para listar, criar, alterar e excluir tarefas.

### 3. Testes automatizados (opcional)

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/ -v
```

Os testes cobrem todas as rotas da API (criação, listagem, edição, exclusão, ordenação e validações) e usam um arquivo de dados temporário, sem interferir no `tasks.json` real.

## Funcionalidades

- Cadastrar tarefa (título, descrição, prioridade e data de vencimento opcionais)
- Listar todas as tarefas
- Editar título, descrição, prioridade e data de vencimento de uma tarefa já cadastrada
- Alterar status entre Pendente e Concluída
- Excluir tarefa
- Filtrar tarefas por status (Todas / Pendentes / Concluídas)
- Ordenar tarefas por prioridade ou por data de vencimento
- Layout responsivo (adaptado para telas menores)
- Testes automatizados cobrindo todas as rotas da API (12 testes com Pytest)

## Principais decisões tomadas durante o desenvolvimento

- **Armazenamento em JSON:** optei por um arquivo JSON em vez de banco de dados para manter a solução simples e focar no aprendizado da comunicação entre front-end e back-end, já que essa opção é permitida pelo desafio.
- **Flask no back-end:** escolhido por ser um framework leve e direto, adequado ao escopo do projeto sem adicionar complexidade desnecessária.
- **JavaScript puro no front-end:** evitei frameworks (como React) para manter o projeto simples de entender e explicar, já que o requisito era apenas separar front-end e back-end, sem exigir uma tecnologia específica.
- **Flask-CORS:** necessário porque front-end e back-end rodam em portas diferentes durante o desenvolvimento local.
- **Validação básica:** o campo "título" é obrigatório tanto no front-end (atributo `required`) quanto no back-end (validação na rota de criação e na de edição), evitando cadastro ou edição de tarefas sem título mesmo em requisições feitas diretamente à API.
- **Edição parcial (PATCH):** a rota de edição aceita atualizar título, descrição, status, prioridade e data de vencimento de forma independente — o cliente envia só o que quer alterar, sem precisar reenviar a tarefa inteira. Isso manteve compatibilidade com o comportamento já existente de alternar status automaticamente quando nenhum campo é enviado.
- **Prioridade e data de vencimento:** adicionei esses dois campos após comparar a aplicação com gerenciadores de tarefas do mercado (Todoist, Trello, Microsoft To Do), nos quais eles são recursos centrais. Optei por manter apenas 3 níveis de prioridade (Baixa/Média/Alta) e uma data opcional, evitando recursos mais complexos (categorias, subtarefas, colaboração) que fugiriam do escopo do desafio.
- **Ordenação no back-end:** a ordenação por prioridade e por data de vencimento é feita na API (`?ordenar_por=`), e não no front-end, para manter a regra de negócio centralizada no back-end.
- **Identidade visual XCL:** redesenhei o front-end com um tema escuro inspirado na identidade visual da própria XCL (fundo próximo de preto, tipografia Space Grotesk/Inter e um único tom de destaque), em vez de manter um layout genérico.
- **Testes automatizados isolados:** os testes usam um arquivo `tasks.json` temporário, trocado apenas durante a execução dos testes, para não sobrescrever os dados reais da aplicação nem exigir um banco de dados dedicado a testes.

## Possíveis melhorias futuras

- Migrar o armazenamento de JSON para um banco de dados relacional (SQLite/PostgreSQL)
- Adicionar autenticação de usuários
- Deploy da aplicação (back-end e front-end) em serviço de nuvem
- Containerizar a aplicação com Docker

---

Desenvolvido por Kauan como parte do desafio técnico do Programa de Estágio XCL.
