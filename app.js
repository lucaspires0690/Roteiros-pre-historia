// ============================================================
// CONFIGURAÇÃO DO FIREBASE
// Substitua os valores abaixo pelos do SEU projeto Firebase.
// (Firebase Console > ⚙️ Configurações do projeto > Seus apps > SDK setup and configuration)
// Esses valores NÃO são segredo — a segurança real vem das Regras do
// Firestore + do login obrigatório, não de esconder este objeto.
// ============================================================
const firebaseConfig = {
  apiKey: "AIzaSyAo9tWzi30ts5y5cNxpwljzHk3pF44zth4",
  authDomain: "roteiros-pre-historia.firebaseapp.com",
  projectId: "roteiros-pre-historia",
  storageBucket: "roteiros-pre-historia.firebasestorage.app",
  messagingSenderId: "787703137955",
  appId: "1:787703137955:web:aeb429b2b786da1ab86116",
};

import { initializeApp } from "https://www.gstatic.com/firebasejs/12.15.0/firebase-app.js";
import {
  getAuth,
  onAuthStateChanged,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
} from "https://www.gstatic.com/firebasejs/12.15.0/firebase-auth.js";
import {
  getFirestore,
  doc,
  getDoc,
  setDoc,
  collection,
  addDoc,
  query,
  orderBy,
  limit,
  startAfter,
  getDocs,
  serverTimestamp,
  Timestamp,
  writeBatch,
} from "https://www.gstatic.com/firebasejs/12.15.0/firebase-firestore.js";

import { TEMPLATE } from "./template.js";

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

// ---------- constantes do motor (idênticas ao script Python) ----------
const JANELA_REPETICAO = 6;
const QTD_ARQUETIPOS_SUGERIDOS = 6;
const QTD_CASOS_SUGERIDOS = 6;
const PPM_PADRAO = 150; // palavras por minuto — referência de TTS, ajustável na tela

// ---------- persistência local do PPM calibrado (não vai pro Firestore) ----------
const inputPpm = document.getElementById("input-ppm");
const ppmSalvo = localStorage.getItem("storyengine_ppm");
if (ppmSalvo) inputPpm.value = ppmSalvo;
inputPpm.addEventListener("change", () => {
  const valor = parseFloat(inputPpm.value);
  if (valor > 0) localStorage.setItem("storyengine_ppm", String(valor));
});

// ============================================================
// AUTENTICAÇÃO
// ============================================================
// Só este e-mail tem acesso ao app. Mesmo que alguém ache a URL e tente
// logar com outra conta Google, ele é deslogado automaticamente — e a
// regra do Firestore (firestore.rules) também bloqueia no banco de dados,
// que é onde a proteção de verdade está.
const EMAIL_PERMITIDO = "lucasserip1990@gmail.com";

const telaLogin = document.getElementById("tela-login");
const telaApp = document.getElementById("tela-app");
const btnGoogleLogin = document.getElementById("btn-google-login");
const loginErro = document.getElementById("login-erro");
const btnLogout = document.getElementById("btn-logout");

btnGoogleLogin.addEventListener("click", async () => {
  loginErro.textContent = "";
  try {
    await signInWithPopup(auth, new GoogleAuthProvider());
  } catch (err) {
    console.error(err);
    loginErro.textContent = "Não foi possível entrar com o Google. Tente novamente.";
  }
});

btnLogout.addEventListener("click", () => signOut(auth));

onAuthStateChanged(auth, async (user) => {
  if (user && user.email === EMAIL_PERMITIDO) {
    telaLogin.classList.add("oculto");
    telaApp.classList.remove("oculto");
    carregarPools();
    carregarHistorico(true);
  } else if (user) {
    // logou com uma conta Google diferente da autorizada
    loginErro.textContent = `O e-mail ${user.email} não tem acesso a este app.`;
    await signOut(auth);
  } else {
    telaApp.classList.add("oculto");
    telaLogin.classList.remove("oculto");
  }
});

// ============================================================
// NAVEGAÇÃO POR ABAS
// ============================================================
document.querySelectorAll(".aba").forEach((botao) => {
  botao.addEventListener("click", () => {
    document.querySelectorAll(".aba").forEach((b) => {
      b.classList.remove("ativa");
      b.setAttribute("aria-selected", "false");
    });
    botao.classList.add("ativa");
    botao.setAttribute("aria-selected", "true");
    const alvo = botao.dataset.aba;
    document.querySelectorAll(".painel").forEach((p) => {
      p.classList.toggle("oculto", p.dataset.painel !== alvo);
    });
  });
});

// ============================================================
// MOTOR DE GERAÇÃO — porte 1:1 das funções do gerar_prompt.py
// ============================================================

function itensUsadosRecentemente(historicoRecente, campo) {
  const usados = new Set();
  historicoRecente.forEach((r) => (r[campo] || []).forEach((item) => usados.add(item)));
  return usados;
}

function escolherNumeroSemRepetir(opcoes, historicoRecente, campo) {
  const recentes = historicoRecente.map((r) => r[campo]);
  let candidatos = opcoes.filter((o) => !recentes.includes(o));
  if (candidatos.length === 0) candidatos = [...opcoes];
  return candidatos[Math.floor(Math.random() * candidatos.length)];
}

function gerarDistribuicaoBlocos() {
  // Varia a % de palavras por bloco em até ±15% do valor base,
  // depois normaliza para a soma dar exatamente 100% — igual ao Python.
  const base = { B1: 10, B2: 12, B3: 33, B4: 10, B5: 11, B6: 12, B7: 12 };
  const variado = {};
  for (const bloco in base) {
    const pct = base[bloco];
    const margem = pct * 0.15;
    variado[bloco] = pct + (Math.random() * 2 - 1) * margem;
  }
  const soma = Object.values(variado).reduce((a, b) => a + b, 0);
  const fator = 100 / soma;
  for (const bloco in variado) {
    variado[bloco] = Math.round(variado[bloco] * fator * 10) / 10;
  }
  return variado;
}

function shuffle(array) {
  const a = [...array];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function escolherListaSemRepetir(pool, usadosRecentes, quantidade) {
  let disponiveis = pool.filter((item) => !usadosRecentes.has(item));
  if (disponiveis.length < quantidade) {
    // o pool "esgotou" dentro da janela de repetição — recomeça o ciclo
    disponiveis = [...pool];
  }
  return shuffle(disponiveis).slice(0, quantidade);
}

function calcularParametrosDeDuracao(minutos, ppm) {
  const palavrasAlvo = Math.round(minutos * ppm);
  const palavrasMin = Math.round(palavrasAlvo * 0.9);
  const palavrasMax = Math.round(palavrasAlvo * 1.1);
  const perguntasMin = Math.max(4, Math.round(palavrasAlvo / 300));
  const humorMin = Math.max(2, Math.round(palavrasAlvo / 700));
  return { minutos, ppm, palavrasAlvo, palavrasMin, palavrasMax, perguntasMin, humorMin };
}

function calcularPalavrasPorBloco(distribuicaoPct, palavrasAlvo) {
  const resultado = {};
  for (const bloco in distribuicaoPct) {
    resultado[bloco] = Math.round((palavrasAlvo * distribuicaoPct[bloco]) / 100);
  }
  return resultado;
}

function montarPrompt(params) {
  let texto = TEMPLATE;
  const substituicoes = {
    "<<TITULO>>": params.titulo,
    "<<MINUTOS>>": String(params.minutos),
    "<<PPM>>": String(params.ppm),
    "<<PALAVRAS_ALVO>>": String(params.palavrasAlvo),
    "<<PALAVRAS_MIN>>": String(params.palavrasMin),
    "<<PALAVRAS_MAX>>": String(params.palavrasMax),
    "<<PERGUNTAS_MIN>>": String(params.perguntasMin),
    "<<HUMOR_MIN>>": String(params.humorMin),
    "<<LIMITE_ANAFORA>>": String(params.limite_anafora),
    "<<B1>>": String(params.distribuicao.B1),
    "<<B2>>": String(params.distribuicao.B2),
    "<<B3>>": String(params.distribuicao.B3),
    "<<B4>>": String(params.distribuicao.B4),
    "<<B5>>": String(params.distribuicao.B5),
    "<<B6>>": String(params.distribuicao.B6),
    "<<B7>>": String(params.distribuicao.B7),
    "<<PALAVRAS_B1>>": String(params.palavrasPorBloco.B1),
    "<<PALAVRAS_B2>>": String(params.palavrasPorBloco.B2),
    "<<PALAVRAS_B3>>": String(params.palavrasPorBloco.B3),
    "<<PALAVRAS_B4>>": String(params.palavrasPorBloco.B4),
    "<<PALAVRAS_B5>>": String(params.palavrasPorBloco.B5),
    "<<PALAVRAS_B6>>": String(params.palavrasPorBloco.B6),
    "<<PALAVRAS_B7>>": String(params.palavrasPorBloco.B7),
    "<<ARQUETIPOS_EVITAR>>": params.arquetipos_evitar.map((a) => `- ${a}`).join("\n"),
    "<<CASOS_EVITAR>>": params.casos_evitar.map((c) => `- ${c}`).join("\n"),
  };
  for (const [chave, valor] of Object.entries(substituicoes)) {
    texto = texto.replaceAll(chave, valor);
  }
  return texto;
}

// ============================================================
// ABA: GERAR PROMPT
// ============================================================
const inputTitulo = document.getElementById("input-titulo");
const btnGerar = document.getElementById("btn-gerar");
const statusGerar = document.getElementById("status-gerar");
const cartaoResultado = document.getElementById("cartao-resultado");
const resultadoPrompt = document.getElementById("resultado-prompt");
const parametrosDetalhe = document.getElementById("parametros-detalhe");
const btnCopiar = document.getElementById("btn-copiar");

btnGerar.addEventListener("click", async () => {
  const titulo = inputTitulo.value.trim();
  const minutos = parseFloat(document.getElementById("input-minutos").value);
  const ppm = parseFloat(document.getElementById("input-ppm").value) || PPM_PADRAO;

  if (!titulo) {
    statusGerar.textContent = "Digite o título do vídeo.";
    statusGerar.className = "status erro";
    return;
  }
  if (!minutos || minutos <= 0) {
    statusGerar.textContent = "Digite uma duração válida em minutos.";
    statusGerar.className = "status erro";
    return;
  }
  btnGerar.disabled = true;
  statusGerar.textContent = "Gerando...";
  statusGerar.className = "status";
  try {
    const poolsSnap = await getDoc(doc(db, "pools", "default"));
    const pools = poolsSnap.exists()
      ? poolsSnap.data()
      : { arquetipos_personagens: [], casos_historicos: [] };

    const histSnap = await getDocs(
      query(collection(db, "historico"), orderBy("criadoEm", "desc"), limit(JANELA_REPETICAO))
    );
    const historicoRecente = histSnap.docs.map((d) => d.data());

    const arquetiposUsadosRecentes = itensUsadosRecentemente(historicoRecente, "arquetipos_usados");
    const casosUsadosRecentes = itensUsadosRecentemente(historicoRecente, "casos_usados");

    const duracao = calcularParametrosDeDuracao(minutos, ppm);
    const distribuicao = gerarDistribuicaoBlocos();

    const params = {
      titulo,
      ...duracao,
      limite_anafora: escolherNumeroSemRepetir([2, 3, 4], historicoRecente, "limite_anafora"),
      distribuicao,
      palavrasPorBloco: calcularPalavrasPorBloco(distribuicao, duracao.palavrasAlvo),
      arquetipos_evitar: escolherListaSemRepetir(
        pools.arquetipos_personagens || [],
        arquetiposUsadosRecentes,
        QTD_ARQUETIPOS_SUGERIDOS
      ),
      casos_evitar: escolherListaSemRepetir(
        pools.casos_historicos || [],
        casosUsadosRecentes,
        QTD_CASOS_SUGERIDOS
      ),
    };

    const promptFinal = montarPrompt(params);
    resultadoPrompt.value = promptFinal;
    parametrosDetalhe.textContent = JSON.stringify(
      {
        minutos: params.minutos,
        ppm: params.ppm,
        palavras_alvo: params.palavrasAlvo,
        palavras_min: params.palavrasMin,
        palavras_max: params.palavrasMax,
        perguntas_min: params.perguntasMin,
        humor_min: params.humorMin,
        limite_anafora: params.limite_anafora,
        distribuicao_blocos: params.distribuicao,
        arquetipos_evitar: params.arquetipos_evitar,
        casos_evitar: params.casos_evitar,
      },
      null,
      2
    );
    cartaoResultado.classList.remove("oculto");

    await addDoc(collection(db, "historico"), {
      titulo,
      criadoEm: serverTimestamp(),
      minutos: params.minutos,
      palavras_alvo: params.palavrasAlvo,
      limite_anafora: params.limite_anafora,
      distribuicao_blocos: params.distribuicao,
      arquetipos_usados: params.arquetipos_evitar.slice(0, 3),
      casos_usados: params.casos_evitar.slice(0, 3),
    });

    statusGerar.textContent = "Prompt gerado e histórico atualizado.";
    statusGerar.className = "status sucesso";
    carregarHistorico(true);
  } catch (err) {
    console.error(err);
    statusGerar.textContent = "Erro ao gerar: " + err.message;
    statusGerar.className = "status erro";
  } finally {
    btnGerar.disabled = false;
  }
});

btnCopiar.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(resultadoPrompt.value);
    btnCopiar.textContent = "Copiado!";
  } catch {
    resultadoPrompt.select();
    document.execCommand("copy");
    btnCopiar.textContent = "Copiado!";
  }
  setTimeout(() => {
    btnCopiar.textContent = "Copiar";
  }, 1500);
});

// ============================================================
// ABA: BANCOS (POOLS)
// ============================================================
let poolsAtual = { arquetipos_personagens: [], casos_historicos: [] };

async function carregarPools() {
  const snap = await getDoc(doc(db, "pools", "default"));
  poolsAtual = snap.exists()
    ? snap.data()
    : { arquetipos_personagens: [], casos_historicos: [] };
  if (!poolsAtual.arquetipos_personagens) poolsAtual.arquetipos_personagens = [];
  if (!poolsAtual.casos_historicos) poolsAtual.casos_historicos = [];
  renderizarLista("arquetipos_personagens");
  renderizarLista("casos_historicos");
}

function renderizarLista(campo) {
  const container =
    campo === "arquetipos_personagens"
      ? document.getElementById("lista-arquetipos")
      : document.getElementById("lista-casos");
  container.innerHTML = "";
  poolsAtual[campo].forEach((item, indice) => {
    const linha = document.createElement("div");
    linha.className = "item-lista";
    const texto = document.createElement("span");
    texto.textContent = item;
    const btnRemover = document.createElement("button");
    btnRemover.textContent = "Remover";
    btnRemover.addEventListener("click", () => removerItemPool(campo, indice));
    linha.appendChild(texto);
    linha.appendChild(btnRemover);
    container.appendChild(linha);
  });
}

async function salvarPools(mensagem) {
  await setDoc(doc(db, "pools", "default"), poolsAtual);
  const statusPools = document.getElementById("status-pools");
  statusPools.textContent = mensagem || "Salvo.";
  statusPools.className = "status sucesso";
}

async function removerItemPool(campo, indice) {
  poolsAtual[campo].splice(indice, 1);
  renderizarLista(campo);
  await salvarPools("Item removido.");
}

document.getElementById("btn-add-arquetipo").addEventListener("click", async () => {
  const input = document.getElementById("novo-arquetipo");
  const valor = input.value.trim();
  if (!valor) return;
  poolsAtual.arquetipos_personagens.push(valor);
  input.value = "";
  renderizarLista("arquetipos_personagens");
  await salvarPools("Arquétipo adicionado.");
});

document.getElementById("btn-add-caso").addEventListener("click", async () => {
  const input = document.getElementById("novo-caso");
  const valor = input.value.trim();
  if (!valor) return;
  poolsAtual.casos_historicos.push(valor);
  input.value = "";
  renderizarLista("casos_historicos");
  await salvarPools("Caso adicionado.");
});

// ---------- importação única de pools.json ----------
document.getElementById("btn-importar-pools").addEventListener("click", async () => {
  const arquivoInput = document.getElementById("arquivo-pools");
  const statusImportarPools = document.getElementById("status-importar-pools");
  if (!arquivoInput.files.length) {
    statusImportarPools.textContent = "Escolha um arquivo pools.json primeiro.";
    statusImportarPools.className = "status erro";
    return;
  }
  try {
    const texto = await arquivoInput.files[0].text();
    const dados = JSON.parse(texto);
    poolsAtual = {
      arquetipos_personagens: dados.arquetipos_personagens || [],
      casos_historicos: dados.casos_historicos || [],
    };
    await salvarPools();
    renderizarLista("arquetipos_personagens");
    renderizarLista("casos_historicos");
    statusImportarPools.textContent = "pools.json importado com sucesso.";
    statusImportarPools.className = "status sucesso";
  } catch (err) {
    console.error(err);
    statusImportarPools.textContent = "Erro ao importar: arquivo inválido.";
    statusImportarPools.className = "status erro";
  }
});

// ============================================================
// ABA: HISTÓRICO
// ============================================================
let ultimoDocHistorico = null;
const PAGINA_HISTORICO = 10;

function escaparHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}

async function carregarHistorico(reiniciar = false) {
  const lista = document.getElementById("lista-historico");
  const btnMais = document.getElementById("btn-mais-historico");
  if (reiniciar) {
    lista.innerHTML = "";
    ultimoDocHistorico = null;
  }
  let q;
  if (ultimoDocHistorico) {
    q = query(
      collection(db, "historico"),
      orderBy("criadoEm", "desc"),
      startAfter(ultimoDocHistorico),
      limit(PAGINA_HISTORICO)
    );
  } else {
    q = query(collection(db, "historico"), orderBy("criadoEm", "desc"), limit(PAGINA_HISTORICO));
  }
  const snap = await getDocs(q);
  snap.docs.forEach((docSnap) => {
    const r = docSnap.data();
    const item = document.createElement("div");
    item.className = "item-historico";
    const dataFormatada =
      r.criadoEm && r.criadoEm.toDate ? r.criadoEm.toDate().toLocaleString("pt-BR") : "—";
    const duracaoTexto = r.minutos
      ? `${r.minutos} min (${r.palavras_alvo ?? "?"} palavras) · `
      : "";
    item.innerHTML = `
      <div class="item-titulo">${escaparHtml(r.titulo || "(sem título)")}</div>
      <div class="item-meta">${dataFormatada} · ${duracaoTexto}anáfora ${r.limite_anafora ?? "—"} · arquétipos: ${escaparHtml(
      (r.arquetipos_usados || []).join(", ")
    )} · casos: ${escaparHtml((r.casos_usados || []).join(", "))}</div>
    `;
    lista.appendChild(item);
  });
  if (snap.docs.length > 0) {
    ultimoDocHistorico = snap.docs[snap.docs.length - 1];
  }
  btnMais.classList.toggle("oculto", snap.docs.length < PAGINA_HISTORICO);
}

document.getElementById("btn-recarregar-historico").addEventListener("click", () => carregarHistorico(true));
document.getElementById("btn-mais-historico").addEventListener("click", () => carregarHistorico(false));

// ---------- importação única de historico_roteiros.json ----------
document.getElementById("btn-importar-historico").addEventListener("click", async () => {
  const arquivoInput = document.getElementById("arquivo-historico");
  const statusImportarHistorico = document.getElementById("status-importar-historico");
  if (!arquivoInput.files.length) {
    statusImportarHistorico.textContent = "Escolha um arquivo historico_roteiros.json primeiro.";
    statusImportarHistorico.className = "status erro";
    return;
  }
  try {
    const texto = await arquivoInput.files[0].text();
    const dados = JSON.parse(texto);
    const roteiros = dados.roteiros || [];
    let lote = writeBatch(db);
    let contador = 0;
    for (const r of roteiros) {
      const novaRef = doc(collection(db, "historico"));
      const dataRegistro = r.data ? Timestamp.fromDate(new Date(r.data)) : serverTimestamp();
      lote.set(novaRef, {
        titulo: r.titulo || null,
        criadoEm: dataRegistro,
        limite_anafora: r.limite_anafora ?? null,
        distribuicao_blocos: r.distribuicao_blocos || null,
        arquetipos_usados: r.arquetipos_usados || [],
        casos_usados: r.casos_usados || [],
      });
      contador++;
      if (contador % 450 === 0) {
        await lote.commit();
        lote = writeBatch(db);
      }
    }
    await lote.commit();
    statusImportarHistorico.textContent = `${contador} roteiro(s) importado(s) com sucesso.`;
    statusImportarHistorico.className = "status sucesso";
    carregarHistorico(true);
  } catch (err) {
    console.error(err);
    statusImportarHistorico.textContent = "Erro ao importar: arquivo inválido.";
    statusImportarHistorico.className = "status erro";
  }
});
