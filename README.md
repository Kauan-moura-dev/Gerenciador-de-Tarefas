# Gerenciador de Tarefas

Aplicação web simples para cadastrar e acompanhar tarefas do dia a dia, desenvolvida como desafio técnico do processo seletivo do Programa de Estágio da XCL.

## Tecnologias utilizadas

**Back-end**
- Python
- Flask
- Flask-CORS (para permitir a comunicação entre front-end e back-end)

**Front-end**
- HTML5
- CSS3
- JavaScript (puro, sem frameworks)

**Armazenamento**
- Arquivo JSON (`backend/tasks.json`), conforme permitido no desafio

## Arquitetura da solução

O projeto segue uma arquitetura separada entre front-end e back-end, que se comunicam por meio de uma API REST:

```
gerenciador-tarefas/
├── backend/
│   ├── app.py            -> API Flask (rotas do CRUD)
│   ├── tasks.json         -> "banco de dados" em arquivo JSON
│   └── requirements.txt   -> dependências do back-end
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
| GET    | /tarefas        | Lista todas as tarefas            |
| POST   | /tarefas        | Cria uma nova tarefa              |
| PATCH  | /tarefas/\<id\>  | Altera o status, título e/ou descrição de uma tarefa |
| DELETE | /tarefas/\<id\>  | Exclui uma tarefa                 |

**Exemplo de tarefa (JSON):**
```json
{
  "id": 1,
  "titulo": "Estudar para o desafio XCL",
  "descricao": "Rever Flask e JS",
  "status": "Pendente"
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

## Funcionalidades

- Cadastrar tarefa (título e descrição)
- Listar todas as tarefas
- Editar título e descrição de uma tarefa já cadastrada
- Alterar status entre Pendente e Concluída
- Excluir tarefa
- Filtrar tarefas por status (Todas / Pendentes / Concluídas)
- Layout responsivo (adaptado para telas menores)

## Principais decisões tomadas durante o desenvolvimento

- **Armazenamento em JSON:** optei por um arquivo JSON em vez de banco de dados para manter a solução simples e focar no aprendizado da comunicação entre front-end e back-end, já que essa opção é permitida pelo desafio.
- **Flask no back-end:** escolhido por ser um framework leve e direto, adequado ao escopo do projeto sem adicionar complexidade desnecessária.
- **JavaScript puro no front-end:** evitei frameworks (como React) para manter o projeto simples de entender e explicar, já que o requisito era apenas separar front-end e back-end, sem exigir uma tecnologia específica.
- **Flask-CORS:** necessário porque front-end e back-end rodam em portas diferentes durante o desenvolvimento local.
- **Validação básica:** o campo "título" é obrigatório tanto no front-end (atributo `required`) quanto no back-end (validação na rota de criação e na de edição), evitando cadastro ou edição de tarefas sem título mesmo em requisições feitas diretamente à API.
- **Edição parcial (PATCH):** a rota de edição aceita atualizar título, descrição e status de forma independente — o cliente envia só o que quer alterar, sem precisar reenviar a tarefa inteira. Isso manteve compatibilidade com o comportamento já existente de alternar status automaticamente quando nenhum campo é enviado.

## Possíveis melhorias futuras

- Migrar o armazenamento de JSON para um banco de dados relacional (SQLite/PostgreSQL)
- Adicionar testes automatizados para as rotas da API
- Adicionar autenticação de usuários
- Deploy da aplicação (back-end e front-end) em serviço de nuvem

---

Desenvolvido por Kauan como parte do desafio técnico do Programa de Estágio XCL.
