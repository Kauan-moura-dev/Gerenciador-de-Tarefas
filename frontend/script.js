// URL base da API. Se o back-end rodar em outra porta/endereço, ajuste aqui.
const URL_API = "http://127.0.0.1:5000/tarefas";

// Elementos da página
const formulario = document.getElementById("form-tarefa");
const campoTitulo = document.getElementById("titulo");
const campoDescricao = document.getElementById("descricao");
const listaTarefas = document.getElementById("lista-tarefas");
const mensagemVazio = document.getElementById("mensagem-vazio");
const filtroStatus = document.getElementById("filtro-status");

// Guarda a última lista de tarefas recebida da API, para poder filtrar
// sem precisar buscar tudo de novo no servidor a cada troca de filtro.
let tarefasAtuais = [];

// Busca as tarefas na API e atualiza a tela
async function buscarTarefas() {
  try {
    const resposta = await fetch(URL_API);
    tarefasAtuais = await resposta.json();
    renderizarTarefas();
  } catch (erro) {
    console.error("Erro ao buscar tarefas:", erro);
    listaTarefas.innerHTML = "<li>Não foi possível conectar à API. Verifique se o back-end está rodando.</li>";
  }
}

// Desenha a lista de tarefas na tela, aplicando o filtro selecionado
function renderizarTarefas() {
  const filtro = filtroStatus.value;

  const tarefasFiltradas =
    filtro === "todas"
      ? tarefasAtuais
      : tarefasAtuais.filter((tarefa) => tarefa.status === filtro);

  listaTarefas.innerHTML = "";

  if (tarefasFiltradas.length === 0) {
    mensagemVazio.hidden = false;
  } else {
    mensagemVazio.hidden = true;
  }

  tarefasFiltradas.forEach((tarefa) => {
    listaTarefas.appendChild(criarElementoTarefa(tarefa));
  });
}

// Cria o elemento <li> correspondente a uma tarefa
function criarElementoTarefa(tarefa) {
  const estaConcluida = tarefa.status === "Concluída";

  const item = document.createElement("li");
  item.className = "tarefa" + (estaConcluida ? " concluida" : "");

  item.innerHTML = `
    <div class="tarefa-info">
      <p class="tarefa-titulo">${escaparHtml(tarefa.titulo)}</p>
      ${tarefa.descricao ? `<p class="tarefa-descricao">${escaparHtml(tarefa.descricao)}</p>` : ""}
      <span class="tarefa-status ${estaConcluida ? "concluida" : "pendente"}">
        ${tarefa.status}
      </span>
    </div>
    <div class="tarefa-acoes">
      <button class="botao-icone editar" data-id="${tarefa.id}">
        Editar
      </button>
      <button class="botao-icone concluir" data-id="${tarefa.id}">
        ${estaConcluida ? "Reabrir" : "Concluir"}
      </button>
      <button class="botao-icone excluir" data-id="${tarefa.id}">
        Excluir
      </button>
    </div>
  `;

  item.querySelector(".concluir").addEventListener("click", () => {
    alternarStatus(tarefa.id, estaConcluida ? "Pendente" : "Concluída");
  });

  item.querySelector(".excluir").addEventListener("click", () => {
    excluirTarefa(tarefa.id);
  });

  item.querySelector(".editar").addEventListener("click", () => {
    item.replaceWith(criarElementoEdicao(tarefa));
  });

  return item;
}

// Cria o <li> em modo de edição (título e descrição editáveis)
function criarElementoEdicao(tarefa) {
  const item = document.createElement("li");
  item.className = "tarefa tarefa-edicao";

  item.innerHTML = `
    <div class="tarefa-info">
      <div class="campo">
        <label>Título</label>
        <input type="text" class="editar-titulo" value="${escaparHtml(tarefa.titulo)}" maxlength="100" />
      </div>
      <div class="campo">
        <label>Descrição</label>
        <textarea class="editar-descricao" rows="2" maxlength="300">${escaparHtml(tarefa.descricao || "")}</textarea>
      </div>
    </div>
    <div class="tarefa-acoes">
      <button class="botao-icone salvar" data-id="${tarefa.id}">Salvar</button>
      <button class="botao-icone cancelar" data-id="${tarefa.id}">Cancelar</button>
    </div>
  `;

  const campoTituloEdicao = item.querySelector(".editar-titulo");
  const campoDescricaoEdicao = item.querySelector(".editar-descricao");

  item.querySelector(".salvar").addEventListener("click", () => {
    const novoTitulo = campoTituloEdicao.value.trim();

    if (!novoTitulo) {
      campoTituloEdicao.focus();
      return;
    }

    editarTarefa(tarefa.id, novoTitulo, campoDescricaoEdicao.value.trim());
  });

  item.querySelector(".cancelar").addEventListener("click", () => {
    item.replaceWith(criarElementoTarefa(tarefa));
  });

  return item;
}

// Evita que texto digitado pelo usuário quebre o HTML da página
function escaparHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}

// Envia uma nova tarefa para a API
async function criarTarefa(titulo, descricao) {
  try {
    await fetch(URL_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titulo, descricao }),
    });
    await buscarTarefas();
  } catch (erro) {
    console.error("Erro ao criar tarefa:", erro);
  }
}

// Altera o status de uma tarefa (Pendente <-> Concluída)
async function alternarStatus(id, novoStatus) {
  try {
    await fetch(`${URL_API}/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: novoStatus }),
    });
    await buscarTarefas();
  } catch (erro) {
    console.error("Erro ao alterar status:", erro);
  }
}

// Salva a edição de título/descrição de uma tarefa existente
async function editarTarefa(id, titulo, descricao) {
  try {
    await fetch(`${URL_API}/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titulo, descricao }),
    });
    await buscarTarefas();
  } catch (erro) {
    console.error("Erro ao editar tarefa:", erro);
  }
}

// Exclui uma tarefa
async function excluirTarefa(id) {
  try {
    await fetch(`${URL_API}/${id}`, { method: "DELETE" });
    await buscarTarefas();
  } catch (erro) {
    console.error("Erro ao excluir tarefa:", erro);
  }
}

// Envio do formulário de nova tarefa
formulario.addEventListener("submit", (evento) => {
  evento.preventDefault();

  const titulo = campoTitulo.value.trim();
  const descricao = campoDescricao.value.trim();

  if (!titulo) return;

  criarTarefa(titulo, descricao);

  formulario.reset();
  campoTitulo.focus();
});

// Troca de filtro
filtroStatus.addEventListener("change", renderizarTarefas);

// Carrega as tarefas assim que a página abre
buscarTarefas();
