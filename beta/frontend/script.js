// URL base da API. Se o back-end rodar em outra porta/endereço, ajuste aqui.
const URL_API = "http://127.0.0.1:5000/tarefas";

// Elementos da página
const formulario = document.getElementById("form-tarefa");
const campoTitulo = document.getElementById("titulo");
const campoDescricao = document.getElementById("descricao");
const campoPrioridade = document.getElementById("prioridade");
const campoDataVencimento = document.getElementById("data-vencimento");
const listaTarefas = document.getElementById("lista-tarefas");
const mensagemVazio = document.getElementById("mensagem-vazio");
const filtroStatus = document.getElementById("filtro-status");
const ordenarPor = document.getElementById("ordenar-por");

// Guarda a última lista de tarefas recebida da API, para poder filtrar
// sem precisar buscar tudo de novo no servidor a cada troca de filtro.
let tarefasAtuais = [];

// Busca as tarefas na API (já ordenadas, se selecionado) e atualiza a tela
async function buscarTarefas() {
  try {
    const ordenacao = ordenarPor.value;
    const url = ordenacao === "cadastro" ? URL_API : `${URL_API}?ordenar_por=${ordenacao}`;
    const resposta = await fetch(url);
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
  const prioridade = tarefa.prioridade || "Média";

  const item = document.createElement("li");
  item.className = "tarefa" + (estaConcluida ? " concluida" : "");

  item.innerHTML = `
    <div class="tarefa-info">
      <p class="tarefa-titulo">${escaparHtml(tarefa.titulo)}</p>
      ${tarefa.descricao ? `<p class="tarefa-descricao">${escaparHtml(tarefa.descricao)}</p>` : ""}
      <div class="tarefa-tags">
        <span class="tarefa-status ${estaConcluida ? "concluida" : "pendente"}">
          ${tarefa.status}
        </span>
        <span class="tarefa-prioridade prioridade-${prioridade}">
          ${prioridade}
        </span>
        ${tarefa.data_vencimento ? `<span class="tarefa-vencimento">${formatarData(tarefa.data_vencimento)}</span>` : ""}
      </div>
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

// Formata data AAAA-MM-DD para DD/MM/AAAA (mais natural para o usuário brasileiro)
function formatarData(dataISO) {
  const [ano, mes, dia] = dataISO.split("-");
  return `${dia}/${mes}/${ano}`;
}

// Cria o <li> em modo de edição (título, descrição, prioridade e vencimento editáveis)
function criarElementoEdicao(tarefa) {
  const item = document.createElement("li");
  item.className = "tarefa tarefa-edicao";
  const prioridadeAtual = tarefa.prioridade || "Média";

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
      <div class="campo-linha">
        <div class="campo">
          <label>Prioridade</label>
          <select class="editar-prioridade">
            <option value="Baixa" ${prioridadeAtual === "Baixa" ? "selected" : ""}>Baixa</option>
            <option value="Média" ${prioridadeAtual === "Média" ? "selected" : ""}>Média</option>
            <option value="Alta" ${prioridadeAtual === "Alta" ? "selected" : ""}>Alta</option>
          </select>
        </div>
        <div class="campo">
          <label>Vencimento</label>
          <input type="date" class="editar-vencimento" value="${tarefa.data_vencimento || ""}" />
        </div>
      </div>
    </div>
    <div class="tarefa-acoes">
      <button class="botao-icone salvar" data-id="${tarefa.id}">Salvar</button>
      <button class="botao-icone cancelar" data-id="${tarefa.id}">Cancelar</button>
    </div>
  `;

  const campoTituloEdicao = item.querySelector(".editar-titulo");
  const campoDescricaoEdicao = item.querySelector(".editar-descricao");
  const campoPrioridadeEdicao = item.querySelector(".editar-prioridade");
  const campoVencimentoEdicao = item.querySelector(".editar-vencimento");

  item.querySelector(".salvar").addEventListener("click", () => {
    const novoTitulo = campoTituloEdicao.value.trim();

    if (!novoTitulo) {
      campoTituloEdicao.focus();
      return;
    }

    editarTarefa(
      tarefa.id,
      novoTitulo,
      campoDescricaoEdicao.value.trim(),
      campoPrioridadeEdicao.value,
      campoVencimentoEdicao.value || null
    );
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
async function criarTarefa(titulo, descricao, prioridade, dataVencimento) {
  try {
    await fetch(URL_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titulo, descricao, prioridade, data_vencimento: dataVencimento }),
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

// Salva a edição de título/descrição/prioridade/vencimento de uma tarefa existente
async function editarTarefa(id, titulo, descricao, prioridade, dataVencimento) {
  try {
    await fetch(`${URL_API}/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titulo, descricao, prioridade, data_vencimento: dataVencimento }),
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
  const prioridade = campoPrioridade.value;
  const dataVencimento = campoDataVencimento.value || null;

  if (!titulo) return;

  criarTarefa(titulo, descricao, prioridade, dataVencimento);

  formulario.reset();
  campoTitulo.focus();
});

// Troca de filtro (não precisa buscar de novo, só re-renderiza)
filtroStatus.addEventListener("change", renderizarTarefas);

// Troca de ordenação (precisa buscar de novo, pois quem ordena é o back-end)
ordenarPor.addEventListener("change", buscarTarefas);

// Carrega as tarefas assim que a página abre
buscarTarefas();
