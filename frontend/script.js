// ===========================================================================
// Gerenciador de Tarefas - Front-end
// Consome a API Flask (backend/app.py). Sem frameworks, JavaScript puro.
// ===========================================================================

// URL base da API. Se o back-end rodar em outra porta/endereço, ajuste aqui.
const URL_API = "http://127.0.0.1:5000";

// ---------------------------------------------------------------------------
// Estado da aplicação
// ---------------------------------------------------------------------------

const estado = {
  token: localStorage.getItem("token"),
  usuario: null,
  tarefas: [],
  carregando: false,
  erroCarregamento: "",
  visao: "lista", // "lista" | "kanban" | "calendario" | "saude"
  filtros: {
    busca: "",
    status: "todas",
    prioridade: "todas",
    categoria: "todas",
    ordenacao: "recentes",
    inicioDe: "",
    inicioAte: "",
  },
  mesCalendario: {
    ano: new Date().getFullYear(),
    mes: new Date().getMonth(),
  },
  // Ids das tarefas com o painel de subtarefas aberto (sobrevive à re-renderização)
  expandidas: new Set(),
  // Ids das tarefas com o painel de comentários aberto
  comentariosAbertos: new Set(),
  // Quadros (boards) do usuário e o quadro em exibição
  quadros: [],
  quadroAtual: null,
  // Limites de WIP por coluna do kanban e filtros salvos (por usuário)
  limitesWip: {},
  filtrosSalvos: [],
  // Conversa com o chatbot XCL Help (vive só durante a sessão)
  chat: [],
};

// ---------------------------------------------------------------------------
// Elementos da página
// ---------------------------------------------------------------------------

const $ = (id) => document.getElementById(id);

const telaAuth = $("tela-auth");
const telaApp = $("tela-app");
const abaLogin = $("aba-login");
const abaRegistro = $("aba-registro");
const formLogin = $("form-login");
const formRegistro = $("form-registro");
const erroAuth = $("erro-auth");

const nomeUsuario = $("nome-usuario");
const botaoSair = $("botao-sair");

const formTarefa = $("form-tarefa");
const botaoAdicionar = $("botao-adicionar");
const listaTarefas = $("lista-tarefas");
const quadroKanban = $("quadro-kanban");
const dicaKanban = $("dica-kanban");
const calendario = $("calendario");
const calendarioTitulo = $("calendario-titulo");
const calendarioGrade = $("calendario-grade");
const mensagemVazio = $("mensagem-vazio");
const indicadorCarregando = $("carregando");

const campoBusca = $("busca");
const filtroStatus = $("filtro-status");
const filtroPrioridade = $("filtro-prioridade");
const filtroCategoria = $("filtro-categoria");
const seletorOrdenacao = $("ordenacao");
const filtroInicioDe = $("filtro-inicio-de");
const filtroInicioAte = $("filtro-inicio-ate");
const botaoLimparInicio = $("limpar-filtro-inicio");
const datalistCategorias = $("lista-categorias");
const painelSaude = $("painel-saude");

const modalEditar = $("modal-editar");
const formEditar = $("form-editar");
const modalConfirmar = $("modal-confirmar");
const textoConfirmar = $("texto-confirmar");

const areaToasts = $("area-toasts");

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------

// Evita que texto digitado pelo usuário quebre o HTML da página (XSS)
function escaparHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto ?? "";
  return div.innerHTML;
}

// Minúsculas e sem acentos — a busca acha "crédito" digitando "credito"
function semAcento(texto) {
  return (texto ?? "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

// Converte "AAAA-MM-DD" em Date local (evita o deslocamento de fuso do new Date)
function dataLocal(dataIso) {
  const [ano, mes, dia] = dataIso.split("-").map(Number);
  return new Date(ano, mes - 1, dia);
}

function dataIso(ano, mes, dia) {
  const pad = (numero) => String(numero).padStart(2, "0");
  return `${ano}-${pad(mes + 1)}-${pad(dia)}`;
}

// Diferença em dias entre a data de vencimento e hoje (negativo = atrasada)
function diasAteVencimento(dataVencimento) {
  const hoje = new Date();
  const inicioHoje = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
  return Math.round((dataLocal(dataVencimento) - inicioHoje) / 86400000);
}

// Texto e estilo da etiqueta de vencimento de uma tarefa
function infoVencimento(tarefa) {
  if (!tarefa.data_vencimento) return null;

  const dias = diasAteVencimento(tarefa.data_vencimento);
  const data = dataLocal(tarefa.data_vencimento);
  const mesmoAno = data.getFullYear() === new Date().getFullYear();
  const dataCurta = data.toLocaleDateString("pt-BR", {
    day: "numeric",
    month: "short",
    ...(mesmoAno ? {} : { year: "numeric" }),
  });

  if (tarefa.status === "Concluída") return { texto: dataCurta, classe: "" };
  if (dias < 0) {
    const atraso = Math.abs(dias);
    return {
      texto: atraso === 1 ? "Venceu ontem" : `Venceu há ${atraso} dias`,
      classe: "vencida",
    };
  }
  if (dias === 0) return { texto: "Hoje", classe: "hoje" };
  if (dias === 1) return { texto: "Amanhã", classe: "" };
  return { texto: dataCurta, classe: "" };
}

function tarefaVencida(tarefa) {
  return (
    tarefa.status !== "Concluída" &&
    tarefa.data_vencimento &&
    diasAteVencimento(tarefa.data_vencimento) < 0
  );
}

// "10 jul" (com ano se for de outro ano) — usado nas etiquetas de data
function dataCurta(dataIso) {
  const data = dataLocal(dataIso);
  const mesmoAno = data.getFullYear() === new Date().getFullYear();
  return data.toLocaleDateString("pt-BR", {
    day: "numeric",
    month: "short",
    ...(mesmoAno ? {} : { year: "numeric" }),
  });
}

// "Marina Albuquerque · Analista" — nome completo do responsável com o cargo
function nomeResponsavel(item) {
  const nome = [item.responsavel_nome, item.responsavel_sobrenome]
    .filter(Boolean)
    .join(" ");
  if (!nome && !item.responsavel_cargo) return "";
  return nome + (item.responsavel_cargo ? `${nome ? " · " : ""}${item.responsavel_cargo}` : "");
}

const ROTULOS_RECORRENCIA = {
  diaria: "Todo dia",
  semanal: "Toda semana",
  mensal: "Todo mês",
};

// "04/07 14:32" — usado em comentários e no histórico de atividade
function formatarDataHora(iso) {
  const data = new Date(iso);
  return (
    data.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }) +
    " " +
    data.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  );
}

// Duração amigável para o ciclo médio: "45min", "6h", "3d"
function formatarDuracao(ms) {
  const horas = ms / 3600000;
  if (horas < 1) return `${Math.max(1, Math.round(ms / 60000))}min`;
  if (horas < 48) return `${Math.round(horas)}h`;
  return `${Math.round(horas / 24)}d`;
}

// Uma tarefa pode ter várias categorias separadas por vírgula
function categoriasDaTarefa(tarefa) {
  return (tarefa.categoria || "")
    .split(",")
    .map((categoria) => categoria.trim())
    .filter(Boolean);
}

// Preferências locais por usuário (quadro atual, limites de WIP, filtros salvos)
function chavePreferencia(prefixo) {
  return `${prefixo}:${estado.usuario ? estado.usuario.id : "anon"}`;
}

function lerPreferencia(prefixo, padrao) {
  try {
    const valor = JSON.parse(localStorage.getItem(chavePreferencia(prefixo)));
    return valor === null || valor === undefined ? padrao : valor;
  } catch {
    return padrao;
  }
}

function salvarPreferencia(prefixo, valor) {
  localStorage.setItem(chavePreferencia(prefixo), JSON.stringify(valor));
}

// Notificação flutuante no canto da tela
function toast(mensagem, tipo = "info") {
  const elemento = document.createElement("div");
  elemento.className = `toast ${tipo}`;
  elemento.textContent = mensagem;
  areaToasts.appendChild(elemento);
  setTimeout(() => elemento.remove(), 4000);
}

// ---------------------------------------------------------------------------
// Comunicação com a API
// ---------------------------------------------------------------------------

async function api(caminho, opcoes = {}) {
  let resposta;
  try {
    resposta = await fetch(URL_API + caminho, {
      ...opcoes,
      headers: {
        "Content-Type": "application/json",
        ...(estado.token ? { Authorization: `Bearer ${estado.token}` } : {}),
        ...(opcoes.headers || {}),
      },
    });
  } catch {
    throw new Error("Não foi possível conectar à API. Verifique se o back-end está rodando.");
  }

  // Sessão expirada/inválida: volta para a tela de login
  if (resposta.status === 401 && estado.token) {
    encerrarSessaoLocal();
    mostrarTelaAuth("Sua sessão expirou. Entre novamente.");
    throw new Error("Sessão expirada.");
  }

  const corpo = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    throw new Error(corpo?.erro || "Ocorreu um erro inesperado.");
  }
  return corpo;
}

// ---------------------------------------------------------------------------
// Autenticação
// ---------------------------------------------------------------------------

function mostrarTelaAuth(mensagemErro = "") {
  telaApp.hidden = true;
  telaAuth.hidden = false;
  erroAuth.hidden = !mensagemErro;
  erroAuth.textContent = mensagemErro;
  $("chatbot").hidden = true;
  fecharChatbot();
}

function mostrarTelaApp() {
  telaAuth.hidden = true;
  telaApp.hidden = false;
  nomeUsuario.textContent = estado.usuario ? `Olá, ${estado.usuario.nome}` : "";
  $("chatbot").hidden = false;
}

function encerrarSessaoLocal() {
  estado.token = null;
  estado.usuario = null;
  estado.tarefas = [];
  estado.quadros = [];
  estado.quadroAtual = null;
  estado.expandidas.clear();
  estado.comentariosAbertos.clear();
  estado.chat = [];
  localStorage.removeItem("token");
  localStorage.removeItem("usuario");
}

// Limpa busca, filtros e visão ao entrar — evita que preferências de uma
// conta "vazem" para a próxima pessoa que fizer login no mesmo navegador
function reiniciarPreferencias() {
  estado.filtros = {
    busca: "",
    status: "todas",
    prioridade: "todas",
    categoria: "todas",
    ordenacao: "recentes",
    inicioDe: "",
    inicioAte: "",
  };
  estado.expandidas.clear();
  estado.visao = "lista";
  campoBusca.value = "";
  filtroStatus.value = "todas";
  filtroPrioridade.value = "todas";
  seletorOrdenacao.value = "recentes";
  filtroInicioDe.value = "";
  filtroInicioAte.value = "";
  botaoLimparInicio.hidden = true;
  document.querySelectorAll(".aba-visao").forEach((botao) => {
    const ativa = botao.dataset.visao === "lista";
    botao.classList.toggle("ativa", ativa);
    botao.setAttribute("aria-selected", String(ativa));
  });
}

function iniciarSessao(token, usuario) {
  estado.token = token;
  estado.usuario = usuario;
  localStorage.setItem("token", token);
  localStorage.setItem("usuario", JSON.stringify(usuario));
  reiniciarPreferencias();
  mostrarTelaApp();
  iniciarDados();
}

const VISOES_VALIDAS = ["lista", "kanban", "calendario", "saude"];

// Marca a visão nos botões de aba (sem renderizar — quem chama decide)
function aplicarVisao(visao) {
  estado.visao = visao;
  document.querySelectorAll(".aba-visao").forEach((botao) => {
    const ativa = botao.dataset.visao === visao;
    botao.classList.toggle("ativa", ativa);
    botao.setAttribute("aria-selected", String(ativa));
  });
}

// Carrega tudo que depende do usuário logado: preferências, quadros e tarefas
async function iniciarDados() {
  estado.limitesWip = lerPreferencia("wip", {});
  sincronizarCamposWip();
  carregarFiltrosSalvos();
  // Restaura a última visão usada (como o quadro, persiste por usuário)
  const visaoSalva = lerPreferencia("visao", "lista");
  if (VISOES_VALIDAS.includes(visaoSalva)) aplicarVisao(visaoSalva);
  try {
    await carregarQuadros();
  } catch (erro) {
    toast(erro.message, "erro");
  }
  await carregarTarefas();
}

function alternarAbaAuth(aba) {
  const ehLogin = aba === "login";
  abaLogin.classList.toggle("ativa", ehLogin);
  abaRegistro.classList.toggle("ativa", !ehLogin);
  abaLogin.setAttribute("aria-selected", String(ehLogin));
  abaRegistro.setAttribute("aria-selected", String(!ehLogin));
  formLogin.hidden = !ehLogin;
  formRegistro.hidden = ehLogin;
  erroAuth.hidden = true;
}

abaLogin.addEventListener("click", () => alternarAbaAuth("login"));
abaRegistro.addEventListener("click", () => alternarAbaAuth("registro"));

formLogin.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const botao = formLogin.querySelector("button[type=submit]");
  botao.disabled = true;
  try {
    const corpo = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: $("login-email").value.trim(),
        senha: $("login-senha").value,
      }),
    });
    formLogin.reset();
    iniciarSessao(corpo.token, corpo.usuario);
  } catch (erro) {
    mostrarTelaAuth(erro.message);
  } finally {
    botao.disabled = false;
  }
});

formRegistro.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const botao = formRegistro.querySelector("button[type=submit]");
  botao.disabled = true;
  try {
    const corpo = await api("/auth/registrar", {
      method: "POST",
      body: JSON.stringify({
        nome: $("registro-nome").value.trim(),
        email: $("registro-email").value.trim(),
        senha: $("registro-senha").value,
      }),
    });
    formRegistro.reset();
    iniciarSessao(corpo.token, corpo.usuario);
  } catch (erro) {
    mostrarTelaAuth(erro.message);
  } finally {
    botao.disabled = false;
  }
});

botaoSair.addEventListener("click", async () => {
  try {
    await api("/auth/logout", { method: "POST" });
  } catch {
    // mesmo que a chamada falhe, encerra a sessão localmente
  }
  encerrarSessaoLocal();
  mostrarTelaAuth();
});

// ---------------------------------------------------------------------------
// Quadros (múltiplos boards, como projetos)
// ---------------------------------------------------------------------------

async function carregarQuadros() {
  estado.quadros = await api("/quadros");
  const salvo = lerPreferencia("quadro", null);
  estado.quadroAtual = estado.quadros.some((quadro) => quadro.id === salvo)
    ? salvo
    : estado.quadros[0].id;
  salvarPreferencia("quadro", estado.quadroAtual);
  renderizarQuadros();
}

function renderizarQuadros() {
  const seletor = $("seletor-quadro");
  seletor.innerHTML = estado.quadros
    .map((quadro) => `<option value="${quadro.id}">${escaparHtml(quadro.nome)}</option>`)
    .join("");
  seletor.value = String(estado.quadroAtual);
}

function quadroAtualObj() {
  return estado.quadros.find((quadro) => quadro.id === estado.quadroAtual);
}

$("seletor-quadro").addEventListener("change", async () => {
  estado.quadroAtual = Number($("seletor-quadro").value);
  salvarPreferencia("quadro", estado.quadroAtual);
  await carregarTarefas();
});

// Prompt cancelado devolve null (sai em silêncio); vazio ganha aviso
function pedirNome(mensagem, valorInicial = "") {
  const entrada = prompt(mensagem, valorInicial);
  if (entrada === null) return null;
  const nome = entrada.trim();
  if (!nome) {
    toast("O nome não pode ficar vazio.", "erro");
    return null;
  }
  return nome;
}

$("novo-quadro").addEventListener("click", async () => {
  const nome = pedirNome("Nome do novo quadro:");
  if (!nome) return;
  try {
    const novo = await api("/quadros", { method: "POST", body: JSON.stringify({ nome }) });
    estado.quadroAtual = novo.id;
    salvarPreferencia("quadro", novo.id);
    await carregarQuadros();
    await carregarTarefas();
    toast(`Quadro "${nome}" criado!`, "sucesso");
  } catch (erro) {
    toast(erro.message, "erro");
  }
});

$("renomear-quadro").addEventListener("click", async () => {
  const atual = quadroAtualObj();
  if (!atual) return;
  const nome = pedirNome("Novo nome do quadro:", atual.nome);
  if (!nome || nome === atual.nome) return;
  try {
    await api(`/quadros/${atual.id}`, { method: "PATCH", body: JSON.stringify({ nome }) });
    atual.nome = nome;
    renderizarQuadros();
    toast("Quadro renomeado!", "sucesso");
  } catch (erro) {
    toast(erro.message, "erro");
  }
});

$("excluir-quadro").addEventListener("click", () => {
  const atual = quadroAtualObj();
  if (!atual) return;
  if (estado.quadros.length <= 1) {
    toast("Você precisa manter ao menos um quadro.", "erro");
    return;
  }
  abrirConfirmacao(
    `Excluir o quadro "${atual.nome}" e todas as tarefas dele? Essa ação não pode ser desfeita.`,
    async () => {
      try {
        await api(`/quadros/${atual.id}`, { method: "DELETE" });
        salvarPreferencia("quadro", null);
        await carregarQuadros();
        await carregarTarefas();
        toast("Quadro excluído.", "sucesso");
      } catch (erro) {
        toast(erro.message, "erro");
      }
    }
  );
});

// ---------------------------------------------------------------------------
// Carregamento e renderização
// ---------------------------------------------------------------------------

async function carregarTarefas() {
  estado.carregando = true;
  estado.erroCarregamento = "";
  mensagemVazio.hidden = true;
  renderizar(); // mostra os skeletons de carregamento na lista
  try {
    estado.tarefas = await api(
      estado.quadroAtual ? `/tarefas?quadro_id=${estado.quadroAtual}` : "/tarefas"
    );
  } catch (erro) {
    // a mensagem fica na tela com um botão de repetição (ver renderizarLista)
    estado.erroCarregamento = erro.message;
  } finally {
    estado.carregando = false;
    renderizar();
  }
}

// Aplica busca, filtros e ordenação sobre a lista em memória
function filtrarTarefas({ ignorarStatus = false } = {}) {
  const { busca, status, prioridade, categoria, ordenacao, inicioDe, inicioAte } = estado.filtros;
  const termo = semAcento(busca.trim());

  const filtradas = estado.tarefas.filter((tarefa) => {
    if (!ignorarStatus && status !== "todas" && tarefa.status !== status) return false;
    if (prioridade !== "todas" && tarefa.prioridade !== prioridade) return false;
    if (categoria !== "todas" && !categoriasDaTarefa(tarefa).includes(categoria)) return false;
    // Período da data de início (datas ISO comparam certo como texto)
    if ((inicioDe || inicioAte) && !tarefa.data_inicio) return false;
    if (inicioDe && tarefa.data_inicio < inicioDe) return false;
    if (inicioAte && tarefa.data_inicio > inicioAte) return false;
    if (
      termo &&
      !semAcento(tarefa.titulo).includes(termo) &&
      !semAcento(tarefa.descricao).includes(termo)
    ) {
      return false;
    }
    return true;
  });

  const pesoPrioridade = { Alta: 0, "Média": 1, Baixa: 2 };
  const porData = (campo) => (a, b) => {
    if (!a[campo] && !b[campo]) return 0;
    if (!a[campo]) return 1; // sem data vai para o fim
    if (!b[campo]) return -1;
    return a[campo].localeCompare(b[campo]);
  };
  const comparadores = {
    recentes: (a, b) => (b.criada_em || "").localeCompare(a.criada_em || "") || b.id - a.id,
    vencimento: porData("data_vencimento"),
    inicio: porData("data_inicio"),
    prioridade: (a, b) => pesoPrioridade[a.prioridade] - pesoPrioridade[b.prioridade],
    alfabetica: (a, b) => a.titulo.localeCompare(b.titulo, "pt-BR"),
  };

  return filtradas.sort(comparadores[ordenacao] || comparadores.recentes);
}

function renderizar() {
  atualizarResumo();
  atualizarCategorias();

  listaTarefas.hidden = estado.visao !== "lista";
  quadroKanban.hidden = estado.visao !== "kanban";
  dicaKanban.hidden = estado.visao !== "kanban";
  calendario.hidden = estado.visao !== "calendario";
  painelSaude.hidden = estado.visao !== "saude";
  mensagemVazio.hidden = true;

  if (estado.visao === "lista") renderizarLista();
  if (estado.visao === "kanban") renderizarKanban();
  if (estado.visao === "calendario") renderizarCalendario();
  if (estado.visao === "saude") renderizarSaude();
}

function atualizarResumo() {
  const porStatus = (status) => estado.tarefas.filter((t) => t.status === status).length;
  $("contador-pendentes").textContent = porStatus("Pendente");
  $("contador-andamento").textContent = porStatus("Em andamento");
  $("contador-vencidas").textContent = estado.tarefas.filter(tarefaVencida).length;
  $("contador-concluidas").textContent = porStatus("Concluída");

  // Ciclo médio: tempo entre criar e concluir (métrica de fluxo, como no Jira)
  const concluidas = estado.tarefas.filter(
    (t) => t.status === "Concluída" && t.criada_em && t.concluida_em
  );
  $("contador-ciclo").textContent = concluidas.length
    ? formatarDuracao(
        concluidas.reduce(
          (soma, t) => soma + (new Date(t.concluida_em) - new Date(t.criada_em)),
          0
        ) / concluidas.length
      )
    : "—";
}

// Recalcula as opções de categoria (datalist do formulário + filtro)
function atualizarCategorias() {
  const categorias = [...new Set(estado.tarefas.flatMap(categoriasDaTarefa))].sort((a, b) =>
    a.localeCompare(b, "pt-BR")
  );

  datalistCategorias.innerHTML = categorias
    .map((categoria) => `<option value="${escaparHtml(categoria)}"></option>`)
    .join("");

  const selecionada = estado.filtros.categoria;
  filtroCategoria.innerHTML =
    '<option value="todas">Todas as categorias</option>' +
    categorias
      .map((categoria) => `<option value="${escaparHtml(categoria)}">${escaparHtml(categoria)}</option>`)
      .join("");

  if (selecionada !== "todas" && !categorias.includes(selecionada)) {
    estado.filtros.categoria = "todas";
  }
  filtroCategoria.value = estado.filtros.categoria;
}

// ---------------------------------------------------------------------------
// Visão: lista
// ---------------------------------------------------------------------------

function renderizarLista() {
  const tarefas = filtrarTarefas();
  listaTarefas.innerHTML = "";

  // Skeletons com o formato dos cartões enquanto a API responde
  if (estado.carregando) {
    for (let i = 0; i < 3; i++) {
      const item = document.createElement("li");
      item.className = "tarefa tarefa-esqueleto";
      item.setAttribute("aria-hidden", "true");
      item.innerHTML = `
        <span class="esqueleto-circulo"></span>
        <div class="tarefa-info esqueleto-linhas">
          <div class="esqueleto-bloco" style="width: 45%"></div>
          <div class="esqueleto-bloco" style="width: 72%"></div>
          <div class="esqueleto-bloco" style="width: 30%"></div>
        </div>`;
      listaTarefas.appendChild(item);
    }
    return;
  }

  if (estado.erroCarregamento) {
    mensagemVazio.hidden = false;
    mensagemVazio.innerHTML = `<span class="vazio-icone">📡</span>${escaparHtml(estado.erroCarregamento)}<br /><button type="button" id="tentar-novamente" class="botao-icone">Tentar novamente</button>`;
    $("tentar-novamente").addEventListener("click", carregarTarefas);
    return;
  }

  if (tarefas.length === 0) {
    mensagemVazio.hidden = false;
    mensagemVazio.innerHTML =
      estado.tarefas.length === 0
        ? '<span class="vazio-icone">🗂️</span>Nenhuma tarefa por aqui ainda.<br />Cadastre a primeira no formulário ao lado.'
        : '<span class="vazio-icone">🔍</span>Nenhuma tarefa encontrada com a busca e os filtros atuais.';
    return;
  }

  tarefas.forEach((tarefa) => listaTarefas.appendChild(criarCartaoTarefa(tarefa)));
}

// Cria o <li> de uma tarefa (usado na lista e no kanban)
function criarCartaoTarefa(tarefa, { arrastavel = false } = {}) {
  const concluida = tarefa.status === "Concluída";
  const emAndamento = tarefa.status === "Em andamento";
  const vencida = tarefaVencida(tarefa);

  const item = document.createElement("li");
  item.className =
    "tarefa" +
    (concluida ? " concluida" : "") +
    (emAndamento ? " andamento" : "") +
    (vencida ? " vencida" : "");

  const etiquetas = [];

  if (emAndamento) {
    etiquetas.push('<span class="etiqueta etiqueta-andamento">Em andamento</span>');
  }

  const classePrioridade = { Alta: "alta", "Média": "media", Baixa: "baixa" }[tarefa.prioridade];
  etiquetas.push(
    `<span class="etiqueta etiqueta-prioridade ${classePrioridade}">${tarefa.prioridade}</span>`
  );

  categoriasDaTarefa(tarefa).forEach((categoria) => {
    etiquetas.push(`<span class="etiqueta etiqueta-categoria">${escaparHtml(categoria)}</span>`);
  });

  if (tarefa.data_inicio) {
    etiquetas.push(
      `<span class="etiqueta etiqueta-data" title="Data de início">▶ ${dataCurta(tarefa.data_inicio)}</span>`
    );
  }

  const vencimento = infoVencimento(tarefa);
  if (vencimento) {
    etiquetas.push(
      `<span class="etiqueta etiqueta-data ${vencimento.classe}" title="Vencimento">${vencimento.texto}</span>`
    );
  }

  const responsavel = nomeResponsavel(tarefa);
  if (responsavel) {
    etiquetas.push(
      `<span class="etiqueta etiqueta-responsavel" title="Responsável">👤 ${escaparHtml(responsavel)}</span>`
    );
  }

  if (tarefa.recorrencia !== "nenhuma") {
    etiquetas.push(
      `<span class="etiqueta etiqueta-recorrencia">↻ ${ROTULOS_RECORRENCIA[tarefa.recorrencia]}</span>`
    );
  }

  const totalSubtarefas = tarefa.subtarefas.length;
  const subtarefasFeitas = tarefa.subtarefas.filter((subtarefa) => subtarefa.concluida).length;
  const expandida = estado.expandidas.has(tarefa.id);
  const comentariosAbertos = estado.comentariosAbertos.has(tarefa.id);

  item.innerHTML = `
    <button type="button" class="alternar-status"
      aria-label="${concluida ? "Reabrir" : "Concluir"} tarefa: ${escaparHtml(tarefa.titulo)}"
      title="${concluida ? "Reabrir" : "Concluir"}">${concluida ? "✓" : ""}</button>

    <div class="tarefa-info">
      <p class="tarefa-titulo" title="${escaparHtml(tarefa.titulo)}">${escaparHtml(tarefa.titulo)}</p>
      ${tarefa.descricao ? `<p class="tarefa-descricao">${escaparHtml(tarefa.descricao)}</p>` : ""}
      <div class="tarefa-etiquetas">${etiquetas.join("")}</div>

      <div class="subtarefas">
        <button type="button" class="subtarefas-alternar" aria-expanded="${expandida}">
          Subtarefas (${subtarefasFeitas}/${totalSubtarefas}) ${expandida ? "▴" : "▾"}
        </button>
        <div class="subtarefas-painel" ${expandida ? "" : "hidden"}>
          <ul class="subtarefas-lista"></ul>
          <form class="subtarefa-form">
            <div class="subtarefa-form-linha">
              <input type="text" class="subtarefa-campo-titulo" placeholder="Nova subtarefa..." maxlength="200" required
                aria-label="Título da nova subtarefa" />
              <button type="submit">Adicionar</button>
            </div>
            <div class="subtarefa-form-responsavel">
              <input type="text" class="subtarefa-campo-nome" placeholder="Nome" maxlength="80"
                aria-label="Nome do responsável pela subtarefa" />
              <input type="text" class="subtarefa-campo-sobrenome" placeholder="Sobrenome" maxlength="80"
                aria-label="Sobrenome do responsável pela subtarefa" />
              <input type="text" class="subtarefa-campo-cargo" placeholder="Cargo" maxlength="80"
                aria-label="Cargo do responsável pela subtarefa" />
            </div>
          </form>
        </div>
      </div>

      <div class="comentarios">
        <button type="button" class="subtarefas-alternar comentarios-alternar" aria-expanded="${comentariosAbertos}">
          💬 Comentários (${tarefa.comentarios.length}) ${comentariosAbertos ? "▴" : "▾"}
        </button>
        <div class="comentarios-painel" ${comentariosAbertos ? "" : "hidden"}>
          <ul class="comentarios-lista"></ul>
          <form class="subtarefa-form comentario-form">
            <input type="text" placeholder="Escreva um comentário..." maxlength="500" required
              aria-label="Novo comentário" />
            <button type="submit">Comentar</button>
          </form>
        </div>
      </div>
    </div>

    <div class="tarefa-acoes">
      <button type="button" class="botao-icone editar" aria-label="Editar tarefa: ${escaparHtml(tarefa.titulo)}">Editar</button>
      <button type="button" class="botao-icone excluir" aria-label="Excluir tarefa: ${escaparHtml(tarefa.titulo)}">Excluir</button>
    </div>
  `;

  // Subtarefas (montadas via DOM para ligar os eventos de cada item)
  const listaSubtarefas = item.querySelector(".subtarefas-lista");
  tarefa.subtarefas.forEach((subtarefa) => {
    listaSubtarefas.appendChild(criarElementoSubtarefa(tarefa, subtarefa));
  });

  // Eventos do cartão
  item.querySelector(".alternar-status").addEventListener("click", () => alternarStatus(tarefa));
  item.querySelector(".editar").addEventListener("click", () => abrirModalEditar(tarefa));
  item.querySelector(".excluir").addEventListener("click", () => confirmarExclusao(tarefa));

  item.querySelector(".subtarefas-alternar").addEventListener("click", () => {
    if (estado.expandidas.has(tarefa.id)) {
      estado.expandidas.delete(tarefa.id);
    } else {
      estado.expandidas.add(tarefa.id);
    }
    renderizar();
  });

  item.querySelector(".subtarefa-form").addEventListener("submit", (evento) => {
    evento.preventDefault();
    const formulario = evento.target;
    const valor = (seletor) => formulario.querySelector(seletor).value.trim();
    adicionarSubtarefa(tarefa, {
      titulo: valor(".subtarefa-campo-titulo"),
      responsavel_nome: valor(".subtarefa-campo-nome"),
      responsavel_sobrenome: valor(".subtarefa-campo-sobrenome"),
      responsavel_cargo: valor(".subtarefa-campo-cargo"),
    });
    formulario.reset();
  });

  // Comentários
  const listaComentarios = item.querySelector(".comentarios-lista");
  tarefa.comentarios.forEach((comentario) => {
    listaComentarios.appendChild(criarElementoComentario(tarefa, comentario));
  });

  item.querySelector(".comentarios-alternar").addEventListener("click", () => {
    if (estado.comentariosAbertos.has(tarefa.id)) {
      estado.comentariosAbertos.delete(tarefa.id);
    } else {
      estado.comentariosAbertos.add(tarefa.id);
    }
    renderizar();
  });

  item.querySelector(".comentario-form").addEventListener("submit", (evento) => {
    evento.preventDefault();
    const campo = evento.target.querySelector("input");
    adicionarComentario(tarefa, campo.value.trim());
    campo.value = "";
  });

  // Arrastar e soltar (kanban)
  if (arrastavel) {
    item.draggable = true;
    item.addEventListener("dragstart", (evento) => {
      evento.dataTransfer.setData("text/plain", String(tarefa.id));
      evento.dataTransfer.effectAllowed = "move";
      item.classList.add("arrastando");
    });
    item.addEventListener("dragend", () => item.classList.remove("arrastando"));
  }

  return item;
}

// ---------------------------------------------------------------------------
// Visão: kanban
// ---------------------------------------------------------------------------

const CONTADORES_KANBAN = {
  "Pendente": "kanban-contador-pendente",
  "Em andamento": "kanban-contador-andamento",
  "Concluída": "kanban-contador-concluida",
};

function renderizarKanban() {
  // As colunas já representam o status, então o filtro de status é ignorado aqui
  const tarefas = filtrarTarefas({ ignorarStatus: true });

  quadroKanban.querySelectorAll(".coluna-kanban").forEach((colunaEl) => {
    const status = colunaEl.dataset.status;
    const lista = colunaEl.querySelector(".coluna-lista");
    lista.innerHTML = "";

    const doStatus = tarefas.filter((tarefa) => tarefa.status === status);
    doStatus.forEach((tarefa) =>
      lista.appendChild(criarCartaoTarefa(tarefa, { arrastavel: true }))
    );

    // Limite de WIP: mostra "atual/limite" e destaca a coluna quando estourar
    const limite = estado.limitesWip[status];
    $(CONTADORES_KANBAN[status]).textContent = limite
      ? `${doStatus.length}/${limite}`
      : doStatus.length;
    colunaEl.classList.toggle("estourou-wip", Boolean(limite && doStatus.length > limite));
  });
}

// Campos de limite de WIP nos cabeçalhos das colunas (persistidos por usuário)
function sincronizarCamposWip() {
  quadroKanban.querySelectorAll(".coluna-kanban").forEach((coluna) => {
    coluna.querySelector(".wip-limite").value = estado.limitesWip[coluna.dataset.status] || "";
  });
}

quadroKanban.querySelectorAll(".wip-limite").forEach((campo) => {
  campo.addEventListener("change", () => {
    const status = campo.closest(".coluna-kanban").dataset.status;
    const valor = Number(campo.value);
    if (valor > 0) {
      estado.limitesWip[status] = valor;
    } else {
      delete estado.limitesWip[status];
      campo.value = "";
    }
    salvarPreferencia("wip", estado.limitesWip);
    renderizarKanban();
  });
});

// Zonas de soltura das colunas (ligadas uma única vez)
quadroKanban.querySelectorAll(".coluna-kanban").forEach((coluna) => {
  coluna.addEventListener("dragover", (evento) => {
    evento.preventDefault();
    coluna.classList.add("arrastando-sobre");
  });
  coluna.addEventListener("dragleave", (evento) => {
    // só remove o destaque ao sair da coluna de verdade (não ao passar sobre um cartão filho)
    if (!coluna.contains(evento.relatedTarget)) coluna.classList.remove("arrastando-sobre");
  });
  coluna.addEventListener("drop", (evento) => {
    evento.preventDefault();
    coluna.classList.remove("arrastando-sobre");
    const id = Number(evento.dataTransfer.getData("text/plain"));
    const tarefa = estado.tarefas.find((t) => t.id === id);
    if (tarefa) {
      definirStatus(tarefa, coluna.dataset.status);
    }
  });
});

// ---------------------------------------------------------------------------
// Visão: calendário
// ---------------------------------------------------------------------------

function renderizarCalendario() {
  const { ano, mes } = estado.mesCalendario;
  const tarefas = filtrarTarefas();

  calendarioTitulo.textContent = new Date(ano, mes, 1).toLocaleDateString("pt-BR", {
    month: "long",
    year: "numeric",
  });

  calendarioGrade.innerHTML = "";

  ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"].forEach((dia) => {
    const celula = document.createElement("div");
    celula.className = "calendario-dia-semana";
    celula.textContent = dia;
    calendarioGrade.appendChild(celula);
  });

  const primeiroDiaSemana = new Date(ano, mes, 1).getDay();
  const totalDias = new Date(ano, mes + 1, 0).getDate();
  const hoje = new Date();

  for (let i = 0; i < primeiroDiaSemana; i++) {
    const vazia = document.createElement("div");
    vazia.className = "calendario-dia fora-do-mes";
    calendarioGrade.appendChild(vazia);
  }

  for (let dia = 1; dia <= totalDias; dia++) {
    const celula = document.createElement("div");
    const ehHoje =
      dia === hoje.getDate() && mes === hoje.getMonth() && ano === hoje.getFullYear();
    celula.className = "calendario-dia" + (ehHoje ? " hoje" : "");

    const numero = document.createElement("span");
    numero.className = "calendario-dia-numero";
    numero.textContent = dia;
    celula.appendChild(numero);

    const doDia = tarefas.filter((tarefa) => tarefa.data_vencimento === dataIso(ano, mes, dia));
    doDia.forEach((tarefa) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className =
        "calendario-chip" +
        (tarefa.status === "Concluída"
          ? " concluida"
          : tarefa.prioridade === "Alta"
            ? " alta"
            : "");
      chip.textContent = tarefa.titulo;
      chip.title = tarefa.titulo;
      chip.addEventListener("click", () => abrirModalEditar(tarefa));
      celula.appendChild(chip);
    });

    calendarioGrade.appendChild(celula);
  }
}

$("mes-anterior").addEventListener("click", () => {
  const calendarioAtual = estado.mesCalendario;
  calendarioAtual.mes -= 1;
  if (calendarioAtual.mes < 0) {
    calendarioAtual.mes = 11;
    calendarioAtual.ano -= 1;
  }
  renderizarCalendario();
});

$("mes-proximo").addEventListener("click", () => {
  const calendarioAtual = estado.mesCalendario;
  calendarioAtual.mes += 1;
  if (calendarioAtual.mes > 11) {
    calendarioAtual.mes = 0;
    calendarioAtual.ano += 1;
  }
  renderizarCalendario();
});

// ---------------------------------------------------------------------------
// Visão: saúde das tarefas
// ---------------------------------------------------------------------------

// Agrupa as tarefas do quadro por situação de prazo
function diagnosticoDeSaude() {
  const ativas = estado.tarefas.filter((tarefa) => tarefa.status !== "Concluída");
  const grupos = {
    atrasadas: [],
    hoje: [],
    emRisco: [], // vencem em 1 a 3 dias
    emDia: [],
    semData: [],
  };

  ativas.forEach((tarefa) => {
    if (!tarefa.data_vencimento) {
      grupos.semData.push(tarefa);
      return;
    }
    const dias = diasAteVencimento(tarefa.data_vencimento);
    if (dias < 0) grupos.atrasadas.push(tarefa);
    else if (dias === 0) grupos.hoje.push(tarefa);
    else if (dias <= 3) grupos.emRisco.push(tarefa);
    else grupos.emDia.push(tarefa);
  });

  // Índice de saúde: atrasada pesa 1, vencendo hoje ou em risco pesa 0,5
  const penalidade = grupos.atrasadas.length + 0.5 * (grupos.hoje.length + grupos.emRisco.length);
  const indice = ativas.length
    ? Math.max(0, Math.round(100 * (1 - penalidade / ativas.length)))
    : 100;

  return { grupos, indice, totalAtivas: ativas.length };
}

const SECOES_SAUDE = [
  ["atrasadas", "🔴 Atrasadas", "atrasada"],
  ["hoje", "🟡 Vencem hoje", "hoje"],
  ["emRisco", "🟠 Prestes a vencer (até 3 dias)", "risco"],
  ["emDia", "🟢 Em dia", "em-dia"],
  ["semData", "⚪ Sem data de vencimento", "sem-data"],
];

function renderizarSaude() {
  const { grupos, indice, totalAtivas } = diagnosticoDeSaude();
  painelSaude.innerHTML = "";

  const faixa = indice >= 80 ? "boa" : indice >= 50 ? "atencao" : "critica";
  const rotulo =
    totalAtivas === 0
      ? "Nenhuma tarefa ativa neste quadro"
      : { boa: "Quadro saudável", atencao: "Quadro pede atenção", critica: "Quadro em estado crítico" }[faixa];

  const hero = document.createElement("div");
  hero.className = `saude-hero ${faixa}`;
  hero.innerHTML = `
    <div class="saude-indice">
      <span class="saude-numero">${indice}%</span>
      <span class="saude-rotulo">${rotulo}</span>
    </div>
    <div class="saude-medidor" role="img" aria-label="Índice de saúde: ${indice}%">
      <div class="saude-medidor-preenchimento" style="width: ${indice}%"></div>
    </div>
    <p class="saude-descricao">
      ${grupos.atrasadas.length} atrasada(s) · ${grupos.hoje.length} vence(m) hoje ·
      ${grupos.emRisco.length} prestes a vencer · ${grupos.emDia.length} em dia ·
      ${grupos.semData.length} sem data
    </p>
  `;
  painelSaude.appendChild(hero);

  SECOES_SAUDE.forEach(([chave, titulo, classe]) => {
    const tarefas = grupos[chave];
    if (tarefas.length === 0) return;

    const secao = document.createElement("section");
    secao.className = `saude-secao ${classe}`;
    secao.innerHTML = `<h3>${titulo} <span class="coluna-contador">${tarefas.length}</span></h3>`;

    const lista = document.createElement("ul");
    lista.className = "saude-lista";
    tarefas.forEach((tarefa) => {
      const item = document.createElement("li");
      item.className = "saude-item";
      const vencimento = infoVencimento(tarefa);
      const responsavel = nomeResponsavel(tarefa);
      item.innerHTML = `
        <button type="button" class="saude-item-botao" title="Clique para editar">
          <span class="saude-item-titulo">${escaparHtml(tarefa.titulo)}</span>
          <span class="saude-item-detalhes">
            ${tarefa.status === "Em andamento" ? '<span class="etiqueta etiqueta-andamento">Em andamento</span>' : ""}
            ${vencimento ? `<span class="etiqueta etiqueta-data ${vencimento.classe}">${vencimento.texto}</span>` : ""}
            ${responsavel ? `<span class="etiqueta etiqueta-responsavel">👤 ${escaparHtml(responsavel)}</span>` : ""}
          </span>
        </button>
      `;
      item.querySelector("button").addEventListener("click", () => abrirModalEditar(tarefa));
      lista.appendChild(item);
    });

    secao.appendChild(lista);
    painelSaude.appendChild(secao);
  });

  if (totalAtivas === 0 && estado.tarefas.length > 0) {
    const nota = document.createElement("p");
    nota.className = "mensagem-vazio";
    nota.textContent = "Todas as tarefas deste quadro estão concluídas. 🎉";
    painelSaude.appendChild(nota);
  }
}

// ---------------------------------------------------------------------------
// Ações sobre tarefas (com atualização otimista da interface)
// ---------------------------------------------------------------------------

async function criarTarefa() {
  botaoAdicionar.disabled = true;
  botaoAdicionar.textContent = "Adicionando...";
  try {
    const nova = await api("/tarefas", {
      method: "POST",
      body: JSON.stringify({
        quadro_id: estado.quadroAtual,
        titulo: $("titulo").value.trim(),
        descricao: $("descricao").value.trim(),
        data_inicio: $("data-inicio").value || null,
        data_vencimento: $("data-vencimento").value || null,
        prioridade: $("prioridade").value,
        categoria: $("categoria").value.trim(),
        recorrencia: $("recorrencia").value,
        responsavel_nome: $("responsavel-nome").value.trim(),
        responsavel_sobrenome: $("responsavel-sobrenome").value.trim(),
        responsavel_cargo: $("responsavel-cargo").value.trim(),
      }),
    });
    estado.tarefas.unshift(nova);
    formTarefa.reset();
    reiniciarSugestao();
    $("titulo").focus();
    renderizar();
    toast("Tarefa criada!", "sucesso");
  } catch (erro) {
    toast(erro.message, "erro");
  } finally {
    botaoAdicionar.disabled = false;
    botaoAdicionar.textContent = "Adicionar tarefa";
  }
}

// Muda o status de forma otimista (reverte se a API falhar)
async function definirStatus(tarefa, novoStatus) {
  if (tarefa.status === novoStatus) return;
  const statusAnterior = tarefa.status;
  const conclusaoAnterior = tarefa.concluida_em;

  tarefa.status = novoStatus;
  tarefa.concluida_em = novoStatus === "Concluída" ? new Date().toISOString() : null;
  renderizar();

  try {
    const resposta = await api(`/tarefas/${tarefa.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: novoStatus }),
    });

    const { proxima_ocorrencia: proximaOcorrencia, ...dadosServidor } = resposta;
    Object.assign(tarefa, dadosServidor);

    // Tarefa recorrente concluída: a API devolve a próxima ocorrência
    if (proximaOcorrencia) {
      estado.tarefas.unshift(proximaOcorrencia);
      const info = infoVencimento(proximaOcorrencia);
      toast(`Próxima ocorrência criada${info ? ` para ${info.texto.toLowerCase()}` : ""}.`, "sucesso");
    }
    renderizar();
  } catch (erro) {
    tarefa.status = statusAnterior;
    tarefa.concluida_em = conclusaoAnterior;
    renderizar();
    toast(erro.message, "erro");
  }
}

// Botão redondo do cartão: alterna entre Concluída e Pendente
function alternarStatus(tarefa) {
  definirStatus(tarefa, tarefa.status === "Concluída" ? "Pendente" : "Concluída");
}

// Exclusão otimista, com confirmação antes e reversão em caso de falha
function confirmarExclusao(tarefa) {
  abrirConfirmacao(`Excluir a tarefa "${tarefa.titulo}"? Essa ação não pode ser desfeita.`, async () => {
    const indice = estado.tarefas.indexOf(tarefa);
    estado.tarefas.splice(indice, 1);
    renderizar();

    try {
      await api(`/tarefas/${tarefa.id}`, { method: "DELETE" });
      toast("Tarefa excluída.", "sucesso");
    } catch (erro) {
      estado.tarefas.splice(indice, 0, tarefa); // desfaz a remoção local
      renderizar();
      toast(erro.message, "erro");
    }
  });
}

// ---------------------------------------------------------------------------
// Subtarefas
// ---------------------------------------------------------------------------

function criarElementoSubtarefa(tarefa, subtarefa) {
  const item = document.createElement("li");
  item.className = "subtarefa" + (subtarefa.concluida ? " concluida" : "");
  const responsavel = nomeResponsavel(subtarefa);
  item.innerHTML = `
    <input type="checkbox" ${subtarefa.concluida ? "checked" : ""}
      aria-label="Concluir subtarefa: ${escaparHtml(subtarefa.titulo)}" />
    <span class="subtarefa-titulo">${escaparHtml(subtarefa.titulo)}${
      responsavel
        ? ` <span class="subtarefa-responsavel" title="Responsável">👤 ${escaparHtml(responsavel)}</span>`
        : ""
    }</span>
    <button type="button" class="subtarefa-excluir"
      aria-label="Excluir subtarefa: ${escaparHtml(subtarefa.titulo)}">✕</button>
  `;

  item.querySelector("input").addEventListener("change", async (evento) => {
    const valorAnterior = subtarefa.concluida;
    subtarefa.concluida = evento.target.checked;
    renderizar();
    try {
      await api(`/subtarefas/${subtarefa.id}`, {
        method: "PATCH",
        body: JSON.stringify({ concluida: subtarefa.concluida }),
      });
    } catch (erro) {
      subtarefa.concluida = valorAnterior;
      renderizar();
      toast(erro.message, "erro");
    }
  });

  item.querySelector(".subtarefa-excluir").addEventListener("click", () => {
    abrirConfirmacao(`Excluir a subtarefa "${subtarefa.titulo}"?`, async () => {
      const indice = tarefa.subtarefas.indexOf(subtarefa);
      tarefa.subtarefas.splice(indice, 1);
      renderizar();
      try {
        await api(`/subtarefas/${subtarefa.id}`, { method: "DELETE" });
      } catch (erro) {
        tarefa.subtarefas.splice(indice, 0, subtarefa);
        renderizar();
        toast(erro.message, "erro");
      }
    });
  });

  return item;
}

function criarElementoComentario(tarefa, comentario) {
  const item = document.createElement("li");
  item.className = "comentario";
  const assinatura = comentario.autor ? `${escaparHtml(comentario.autor)} · ` : "";
  item.innerHTML = `
    <div class="comentario-corpo">
      <p class="comentario-texto">${escaparHtml(comentario.texto)}</p>
      <span class="comentario-data">${assinatura}${formatarDataHora(comentario.criado_em)}</span>
    </div>
    <button type="button" class="subtarefa-excluir" aria-label="Excluir comentário">✕</button>
  `;

  item.querySelector("button").addEventListener("click", () => {
    abrirConfirmacao("Excluir este comentário?", async () => {
      const indice = tarefa.comentarios.indexOf(comentario);
      tarefa.comentarios.splice(indice, 1);
      renderizar();
      try {
        await api(`/comentarios/${comentario.id}`, { method: "DELETE" });
      } catch (erro) {
        tarefa.comentarios.splice(indice, 0, comentario);
        renderizar();
        toast(erro.message, "erro");
      }
    });
  });

  return item;
}

async function adicionarComentario(tarefa, texto) {
  if (!texto) return;
  try {
    const novo = await api(`/tarefas/${tarefa.id}/comentarios`, {
      method: "POST",
      body: JSON.stringify({ texto }),
    });
    tarefa.comentarios.push(novo);
    estado.comentariosAbertos.add(tarefa.id);
    renderizar();
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

async function adicionarSubtarefa(tarefa, dados) {
  if (!dados.titulo) return;
  try {
    const nova = await api(`/tarefas/${tarefa.id}/subtarefas`, {
      method: "POST",
      body: JSON.stringify(dados),
    });
    tarefa.subtarefas.push(nova);
    estado.expandidas.add(tarefa.id);
    renderizar();
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

// ---------------------------------------------------------------------------
// Modais
// ---------------------------------------------------------------------------

let tarefaEmEdicao = null;
let acaoConfirmada = null;
let elementoComFocoAnterior = null;

function abrirModal(modal) {
  elementoComFocoAnterior = document.activeElement;
  modal.hidden = false;
  const primeiroCampo = modal.querySelector("input, button");
  if (primeiroCampo) primeiroCampo.focus();
}

function fecharModais() {
  modalEditar.hidden = true;
  modalConfirmar.hidden = true;
  tarefaEmEdicao = null;
  acaoConfirmada = null;
  if (elementoComFocoAnterior) {
    elementoComFocoAnterior.focus();
    elementoComFocoAnterior = null;
  }
}

function abrirModalEditar(tarefa) {
  tarefaEmEdicao = tarefa;
  $("editar-status").value = tarefa.status;
  $("editar-titulo").value = tarefa.titulo;
  $("editar-descricao").value = tarefa.descricao;
  $("editar-inicio").value = tarefa.data_inicio || "";
  $("editar-data").value = tarefa.data_vencimento || "";
  $("editar-prioridade").value = tarefa.prioridade;
  $("editar-categoria").value = tarefa.categoria;
  $("editar-recorrencia").value = tarefa.recorrencia;
  $("editar-responsavel-nome").value = tarefa.responsavel_nome || "";
  $("editar-responsavel-sobrenome").value = tarefa.responsavel_sobrenome || "";
  $("editar-responsavel-cargo").value = tarefa.responsavel_cargo || "";

  // Histórico de atividade (mais recente primeiro)
  $("lista-atividade").innerHTML =
    [...tarefa.historico]
      .reverse()
      .map(
        (evento) =>
          `<li><span class="atividade-data">${formatarDataHora(evento.criado_em)}</span>${escaparHtml(evento.descricao)}</li>`
      )
      .join("") || "<li>Sem atividade registrada.</li>";

  abrirModal(modalEditar);
}

formEditar.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (!tarefaEmEdicao) return;

  const botao = formEditar.querySelector("button[type=submit]");
  botao.disabled = true;
  try {
    const resposta = await api(`/tarefas/${tarefaEmEdicao.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        status: $("editar-status").value,
        titulo: $("editar-titulo").value.trim(),
        descricao: $("editar-descricao").value.trim(),
        data_inicio: $("editar-inicio").value || null,
        data_vencimento: $("editar-data").value || null,
        prioridade: $("editar-prioridade").value,
        categoria: $("editar-categoria").value.trim(),
        recorrencia: $("editar-recorrencia").value,
        responsavel_nome: $("editar-responsavel-nome").value.trim(),
        responsavel_sobrenome: $("editar-responsavel-sobrenome").value.trim(),
        responsavel_cargo: $("editar-responsavel-cargo").value.trim(),
      }),
    });
    // Concluir uma tarefa recorrente pelo modal também gera a próxima ocorrência
    const { proxima_ocorrencia: proximaOcorrencia, ...dadosServidor } = resposta;
    Object.assign(tarefaEmEdicao, dadosServidor);
    if (proximaOcorrencia) {
      estado.tarefas.unshift(proximaOcorrencia);
      const info = infoVencimento(proximaOcorrencia);
      toast(`Próxima ocorrência criada${info ? ` para ${info.texto.toLowerCase()}` : ""}.`, "sucesso");
    }
    fecharModais();
    renderizar();
    toast("Tarefa atualizada!", "sucesso");
  } catch (erro) {
    toast(erro.message, "erro");
  } finally {
    botao.disabled = false;
  }
});

function abrirConfirmacao(texto, aoConfirmar) {
  textoConfirmar.textContent = texto;
  acaoConfirmada = aoConfirmar;
  abrirModal(modalConfirmar);
}

$("confirmar-exclusao").addEventListener("click", () => {
  const acao = acaoConfirmada;
  fecharModais();
  if (acao) acao();
});

$("cancelar-edicao").addEventListener("click", fecharModais);
$("cancelar-exclusao").addEventListener("click", fecharModais);

// Fecha os modais com Esc ou clique no fundo escurecido
document.addEventListener("keydown", (evento) => {
  if (evento.key === "Escape") fecharModais();
});

// Focus trap: com um modal aberto, Tab circula apenas dentro dele
document.addEventListener("keydown", (evento) => {
  if (evento.key !== "Tab") return;
  const modal = [modalEditar, modalConfirmar].find((m) => !m.hidden);
  if (!modal) return;

  const focaveis = modal.querySelectorAll(
    "button, input, select, textarea, a[href], [tabindex]:not([tabindex='-1'])"
  );
  if (focaveis.length === 0) return;
  const primeiro = focaveis[0];
  const ultimo = focaveis[focaveis.length - 1];

  if (evento.shiftKey && document.activeElement === primeiro) {
    evento.preventDefault();
    ultimo.focus();
  } else if (
    (!evento.shiftKey && document.activeElement === ultimo) ||
    !modal.contains(document.activeElement)
  ) {
    evento.preventDefault();
    primeiro.focus();
  }
});

[modalEditar, modalConfirmar].forEach((modal) => {
  modal.addEventListener("click", (evento) => {
    if (evento.target === modal) fecharModais();
  });
});

// ---------------------------------------------------------------------------
// Eventos gerais (formulário, busca, filtros, visões)
// ---------------------------------------------------------------------------

formTarefa.addEventListener("submit", (evento) => {
  evento.preventDefault();
  if (!$("titulo").value.trim()) return;
  criarTarefa();
});

// ---------------------------------------------------------------------------
// Sugestão automática de prioridade e categoria (IA/heurística do back-end)
// ---------------------------------------------------------------------------

const dicaSugestao = $("dica-sugestao");
let usuarioAjustouPrioridade = false;
let usuarioAjustouCategoria = false;
let ultimoTituloSugerido = "";

// Se a pessoa mexeu nos campos, a sugestão não sobrescreve a escolha dela
$("prioridade").addEventListener("change", () => {
  usuarioAjustouPrioridade = true;
});
$("categoria").addEventListener("input", () => {
  usuarioAjustouCategoria = true;
});

function reiniciarSugestao() {
  usuarioAjustouPrioridade = false;
  usuarioAjustouCategoria = false;
  ultimoTituloSugerido = "";
  dicaSugestao.hidden = true;
}

async function sugerirClassificacao() {
  const titulo = $("titulo").value.trim();
  if (titulo.length < 5 || titulo === ultimoTituloSugerido) return;
  if (usuarioAjustouPrioridade && usuarioAjustouCategoria) return;
  ultimoTituloSugerido = titulo;

  try {
    const sugestao = await api("/tarefas/sugestao", {
      method: "POST",
      body: JSON.stringify({ titulo, descricao: $("descricao").value.trim() }),
    });

    let aplicou = false;
    if (!usuarioAjustouPrioridade && sugestao.prioridade) {
      $("prioridade").value = sugestao.prioridade;
      aplicou = true;
    }
    if (!usuarioAjustouCategoria && sugestao.categoria && !$("categoria").value.trim()) {
      $("categoria").value = sugestao.categoria;
      aplicou = true;
    }
    if (aplicou) dicaSugestao.hidden = false;
  } catch {
    // a sugestão é opcional: em caso de erro, o formulário segue normal
  }
}

let temporizadorSugestao = null;
$("titulo").addEventListener("input", () => {
  clearTimeout(temporizadorSugestao);
  temporizadorSugestao = setTimeout(sugerirClassificacao, 700);
});
$("titulo").addEventListener("blur", sugerirClassificacao);

let temporizadorBusca = null;
campoBusca.addEventListener("input", () => {
  clearTimeout(temporizadorBusca);
  temporizadorBusca = setTimeout(() => {
    estado.filtros.busca = campoBusca.value;
    renderizar();
  }, 200);
});

filtroStatus.addEventListener("change", () => {
  estado.filtros.status = filtroStatus.value;
  renderizar();
});

filtroPrioridade.addEventListener("change", () => {
  estado.filtros.prioridade = filtroPrioridade.value;
  renderizar();
});

filtroCategoria.addEventListener("change", () => {
  estado.filtros.categoria = filtroCategoria.value;
  renderizar();
});

seletorOrdenacao.addEventListener("change", () => {
  estado.filtros.ordenacao = seletorOrdenacao.value;
  renderizar();
});

// Filtro por período da data de início
function aplicarFiltroInicio() {
  estado.filtros.inicioDe = filtroInicioDe.value;
  estado.filtros.inicioAte = filtroInicioAte.value;
  botaoLimparInicio.hidden = !filtroInicioDe.value && !filtroInicioAte.value;
  renderizar();
}

filtroInicioDe.addEventListener("change", aplicarFiltroInicio);
filtroInicioAte.addEventListener("change", aplicarFiltroInicio);

botaoLimparInicio.addEventListener("click", () => {
  filtroInicioDe.value = "";
  filtroInicioAte.value = "";
  aplicarFiltroInicio();
});

// Reset completo: busca, todos os filtros e a ordenação num clique
$("limpar-filtros").addEventListener("click", () => {
  estado.filtros = {
    busca: "",
    status: "todas",
    prioridade: "todas",
    categoria: "todas",
    ordenacao: "recentes",
    inicioDe: "",
    inicioAte: "",
  };
  sincronizarControlesDeFiltro();
  filtroCategoria.value = "todas";
  renderizar();
});

// ---------------------------------------------------------------------------
// Filtros salvos (combinações nomeadas de busca + filtros, por usuário)
// ---------------------------------------------------------------------------

function carregarFiltrosSalvos() {
  estado.filtrosSalvos = lerPreferencia("filtros", []);
  renderizarFiltrosSalvos();
}

function renderizarFiltrosSalvos() {
  $("filtros-salvos").innerHTML =
    '<option value="">Filtros salvos…</option>' +
    estado.filtrosSalvos
      .map((filtro, indice) => `<option value="${indice}">${escaparHtml(filtro.nome)}</option>`)
      .join("");
}

function sincronizarControlesDeFiltro() {
  campoBusca.value = estado.filtros.busca;
  filtroStatus.value = estado.filtros.status;
  filtroPrioridade.value = estado.filtros.prioridade;
  seletorOrdenacao.value = estado.filtros.ordenacao;
  filtroInicioDe.value = estado.filtros.inicioDe || "";
  filtroInicioAte.value = estado.filtros.inicioAte || "";
  botaoLimparInicio.hidden = !filtroInicioDe.value && !filtroInicioAte.value;
  // o seletor de categoria é reconstruído em atualizarCategorias()
}

$("salvar-filtro").addEventListener("click", () => {
  const nome = pedirNome("Nome para esta combinação de filtros:");
  if (!nome) return;
  estado.filtrosSalvos = estado.filtrosSalvos.filter((filtro) => filtro.nome !== nome);
  estado.filtrosSalvos.push({ nome, filtros: { ...estado.filtros } });
  salvarPreferencia("filtros", estado.filtrosSalvos);
  renderizarFiltrosSalvos();
  $("filtros-salvos").value = String(estado.filtrosSalvos.length - 1);
  toast(`Filtro "${nome}" salvo!`, "sucesso");
});

$("filtros-salvos").addEventListener("change", () => {
  const indice = $("filtros-salvos").value;
  if (indice === "") return;
  estado.filtros = { ...estado.filtrosSalvos[Number(indice)].filtros };
  sincronizarControlesDeFiltro();
  renderizar();
});

$("excluir-filtro").addEventListener("click", () => {
  const indice = $("filtros-salvos").value;
  if (indice === "") {
    toast("Selecione um filtro salvo para excluir.", "erro");
    return;
  }
  const [removido] = estado.filtrosSalvos.splice(Number(indice), 1);
  salvarPreferencia("filtros", estado.filtrosSalvos);
  renderizarFiltrosSalvos();
  toast(`Filtro "${removido.nome}" excluído.`, "sucesso");
});

document.querySelectorAll(".aba-visao").forEach((botao) => {
  botao.addEventListener("click", () => {
    aplicarVisao(botao.dataset.visao);
    salvarPreferencia("visao", estado.visao);
    renderizar();
  });
});

// ---------------------------------------------------------------------------
// Chatbot XCL Help (canto inferior direito)
// ---------------------------------------------------------------------------

const chatbotPainel = $("chatbot-painel");
const chatbotBotao = $("chatbot-abrir");
const chatbotMensagens = $("chatbot-mensagens");
const chatbotForm = $("chatbot-form");
const chatbotCampo = $("chatbot-campo");
let chatbotAguardando = false;

const MENSAGEM_BOAS_VINDAS =
  "Olá! Eu sou o XCL Help 🤖 Tiro dúvidas sobre o organizador e respondo sobre os " +
  "seus quadros. Toque numa sugestão abaixo ou escreva sua pergunta.";

function renderizarChat() {
  chatbotMensagens.innerHTML = "";
  estado.chat.forEach((mensagem) => {
    const bolha = document.createElement("div");
    bolha.className = `chatbot-mensagem ${mensagem.autor}`;
    bolha.textContent = mensagem.texto;
    chatbotMensagens.appendChild(bolha);
  });
  if (chatbotAguardando) {
    const digitando = document.createElement("div");
    digitando.className = "chatbot-mensagem bot digitando";
    digitando.setAttribute("aria-label", "XCL Help está digitando");
    digitando.innerHTML =
      '<span class="ponto"></span><span class="ponto"></span><span class="ponto"></span>';
    chatbotMensagens.appendChild(digitando);
  }
  chatbotMensagens.scrollTop = chatbotMensagens.scrollHeight;
}

function abrirChatbot() {
  chatbotPainel.hidden = false;
  chatbotBotao.setAttribute("aria-expanded", "true");
  if (estado.chat.length === 0) {
    estado.chat.push({ autor: "bot", texto: MENSAGEM_BOAS_VINDAS });
  }
  renderizarChat();
  chatbotCampo.focus();
}

function fecharChatbot() {
  chatbotPainel.hidden = true;
  chatbotBotao.setAttribute("aria-expanded", "false");
}

chatbotBotao.addEventListener("click", () => {
  if (chatbotPainel.hidden) abrirChatbot();
  else fecharChatbot();
});

$("chatbot-fechar").addEventListener("click", fecharChatbot);

async function enviarMensagemChat(mensagem) {
  if (!mensagem || chatbotAguardando) return;

  estado.chat.push({ autor: "usuario", texto: mensagem });
  chatbotCampo.value = "";
  chatbotAguardando = true;
  renderizarChat();

  try {
    const corpo = await api("/chat", {
      method: "POST",
      body: JSON.stringify({ mensagem, quadro_id: estado.quadroAtual }),
    });
    estado.chat.push({ autor: "bot", texto: corpo.resposta });
  } catch (erro) {
    estado.chat.push({
      autor: "bot",
      texto: `Não consegui responder agora (${erro.message}) — tente de novo em instantes.`,
    });
  } finally {
    chatbotAguardando = false;
    renderizarChat();
    chatbotCampo.focus();
  }
}

chatbotForm.addEventListener("submit", (evento) => {
  evento.preventDefault();
  enviarMensagemChat(chatbotCampo.value.trim());
});

// Sugestões de pergunta com um toque
document.querySelectorAll(".chatbot-chip").forEach((chip) => {
  chip.addEventListener("click", () => enviarMensagemChat(chip.textContent.trim()));
});

// ---------------------------------------------------------------------------
// Inicialização: restaura a sessão salva (se houver) e carrega as tarefas
// ---------------------------------------------------------------------------

async function iniciar() {
  if (!estado.token) {
    mostrarTelaAuth();
    return;
  }
  try {
    estado.usuario = await api("/auth/eu");
    localStorage.setItem("usuario", JSON.stringify(estado.usuario));
    mostrarTelaApp();
    iniciarDados();
  } catch {
    // token inválido ou API fora do ar: api() já tratou a sessão expirada
    if (!estado.token) return; // encerrarSessaoLocal já mostrou a tela de login
    mostrarTelaAuth("Não foi possível conectar à API. Verifique se o back-end está rodando.");
  }
}

iniciar();
