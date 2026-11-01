"use strict";
/* Gráficos em SVG puro (sem biblioteca). Cada gráfico:
   - é redesenhado na largura real do cartão, para o texto manter o tamanho;
   - tem dica (mouse e teclado), com o texto sempre inserido por textContent;
   - tem "Ver tabela", a tabela com os mesmos números. */

const NS = "http://www.w3.org/2000/svg";

// ------------------------------------------------------------------ DOM
function aplicar(el, atributos, filhos) {
  for (const [k, v] of Object.entries(atributos || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "texto") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const f of filhos.flat()) {
    if (f === null || f === undefined || f === false) continue;
    el.append(f.nodeType ? f : document.createTextNode(String(f)));
  }
  return el;
}
const h = (tag, atributos, ...filhos) => aplicar(document.createElement(tag), atributos, filhos);
const s = (tag, atributos, ...filhos) => aplicar(document.createElementNS(NS, tag), atributos, filhos);

// ------------------------------------------------------------------ números em português
const formatadores = {};
function nf(casas) {
  formatadores[casas] ||= new Intl.NumberFormat("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
  return formatadores[casas];
}
function num(v, casas = 1, sinal = false) {
  if (!Number.isFinite(v)) return "–";
  let r = Math.round(v * 10 ** casas) / 10 ** casas;
  if (Object.is(r, -0)) r = 0;
  const texto = nf(casas).format(Math.abs(r));
  if (r < 0) return "−" + texto;
  return sinal && r > 0 ? "+" + texto : texto;
}
const pct = (v, casas = 1) => (Number.isFinite(v) ? num(v, casas, true) + "%" : "–");
const pctSimples = (v, casas = 1) => (Number.isFinite(v) ? num(v, casas, false) + "%" : "–");
const pontos = (v, casas = 1) => (Number.isFinite(v) ? num(v, casas, true) + " pontos" : "–");
function comUnidade(v, unidade, casas) {
  if (!Number.isFinite(v)) return "–";
  if (unidade === "%") return pct(v, casas ?? 1);
  if (unidade === "p.p.") return num(v, casas ?? 2, true) + " p.p.";
  if (unidade === "p.b.") return num(v, casas ?? 0, true) + " p.b.";
  return num(v, casas ?? 1, true);
}
function dataBR(iso) {
  if (!iso) return "";
  const [a, m, d] = String(iso).slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
}
const DIAS = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
function dataComDia(iso) {
  const [a, m, d] = iso.split("-").map(Number);
  return `${DIAS[new Date(Date.UTC(a, m - 1, d)).getUTCDay()]}., ${dataBR(iso)}`;
}

// Só links http(s) viram <a>: o texto vem de arquivos de dados.
function ligacao(url, texto) {
  if (typeof url === "string" && /^https?:\/\//.test(url.trim())) {
    return h("a", { href: url.trim(), target: "_blank", rel: "noopener", texto });
  }
  return null;
}

// ------------------------------------------------------------------ dica
const Dica = {
  caixa: null,
  iniciar() {
    this.caixa = document.getElementById("dica");
    document.addEventListener("pointerdown", (e) => {
      if (!e.target.closest("[data-dica]")) this.esconder();
    });
    window.addEventListener("scroll", () => this.esconder(), { passive: true });
  },
  mostrar(conteudo, x, y) {
    const c = this.caixa;
    c.replaceChildren();
    if (conteudo.titulo) c.append(h("div", { class: "dica-titulo", texto: conteudo.titulo }));
    for (const l of conteudo.linhas || []) {
      c.append(
        h("div", { class: "dica-linha" },
          l.cor ? h("span", { class: "dica-chave", style: `background:${l.cor}` }) : null,
          h("strong", { texto: l.valor }),
          l.rotulo ? h("span", { class: "dica-rotulo", texto: l.rotulo }) : null)
      );
    }
    if (conteudo.nota) c.append(h("div", { class: "dica-nota", texto: conteudo.nota }));
    c.hidden = false;
    const larg = c.offsetWidth, alt = c.offsetHeight;
    const esquerda = Math.max(6, Math.min(x + 14, innerWidth - larg - 6));
    let topo = y + 16;
    if (topo + alt > innerHeight - 6) topo = Math.max(6, y - alt - 12);
    c.style.left = esquerda + "px";
    c.style.top = topo + "px";
  },
  esconder() {
    if (this.caixa) this.caixa.hidden = true;
  },
  // Dica de um elemento: mouse, toque e foco do teclado mostram o mesmo conteúdo.
  ligar(alvo, conteudoDe) {
    alvo.setAttribute("data-dica", "1");
    const sobre = () => { const r = alvo.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; };
    alvo.addEventListener("pointermove", (e) => this.mostrar(conteudoDe(), e.clientX, e.clientY));
    alvo.addEventListener("pointerdown", (e) => this.mostrar(conteudoDe(), e.clientX, e.clientY));
    alvo.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") this.esconder(); });
    alvo.addEventListener("focus", () => this.mostrar(conteudoDe(), ...sobre()));
    alvo.addEventListener("blur", () => this.esconder());
  },
};

// ------------------------------------------------------------------ escalas
function linear(d0, d1, r0, r1) {
  const k = (r1 - r0) / (d1 - d0 || 1);
  const f = (v) => r0 + (v - d0) * k;
  f.inversa = (y) => d0 + (y - r0) / k;
  return f;
}
function passoBonito(min, max, alvo) {
  const bruto = (max - min || 1) / alvo;
  const pot = 10 ** Math.floor(Math.log10(bruto));
  const f = bruto / pot;
  return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * pot;
}
// Domínio arredondado para múltiplos do passo, com os marcadores do eixo.
function dominioBonito(min, max, alvo = 5) {
  const passo = passoBonito(min, max, alvo);
  const lo = Math.floor(min / passo + 1e-9) * passo, hi = Math.ceil(max / passo - 1e-9) * passo;
  const marcas = [];
  for (let v = lo; v <= hi + passo / 1e6; v += passo) marcas.push(Math.round(v / passo) * passo);
  return { lo, hi, marcas, passo };
}
const larguraTexto = (t, tamanho = 11) => String(t).length * tamanho * 0.58;

// ------------------------------------------------------------------ moldura: título, legenda, gráfico e tabela
function chaveDaLegenda(item) {
  if (item.tipo === "linha") return h("i", { class: "chave chave-linha", style: `background:${item.cor}` });
  if (item.tipo === "ponto") return h("i", { class: "chave chave-ponto", style: `background:${item.cor}` });
  return h("i", { class: "chave", style: `background:${item.cor}` });
}

function tabelaSimples(cabecalho, linhas, opcoes = {}) {
  const t = h("table", { class: opcoes.classe || "" });
  if (opcoes.legenda) t.append(h("caption", { class: "so-leitor", texto: opcoes.legenda }));
  t.append(h("thead", {}, h("tr", {}, cabecalho.map((c, i) => h("th", { scope: "col", class: i && !(opcoes.texto || []).includes(i) ? "num" : "texto", texto: c })))));
  t.append(h("tbody", {}, linhas.map((l) => h("tr", {}, l.map((c, i) => {
    const td = h("td", { class: i && !(opcoes.texto || []).includes(i) ? "num" : "texto" });
    if (c && c.nodeType) td.append(c); else td.textContent = c ?? "–";
    return td;
  })))));
  return h("div", { class: "rolagem" }, t);
}

// `fabrica()` devolve {titulo, nota, legenda, descricao, svg(largura), tabela()} e é chamada a cada desenho.
function criarGrafico(host, fabrica) {
  const cabeca = h("div", { class: "grafico-cab" });
  const legenda = h("div", { class: "legenda" });
  const area = h("div", { class: "grafico-area" });
  const caixaTabela = h("div", { class: "grafico-tabela", hidden: true });
  const botao = h("button", { type: "button", class: "ver-tabela", "aria-expanded": "false" }, "Ver tabela");
  botao.addEventListener("click", () => {
    const aberta = caixaTabela.hidden;
    caixaTabela.hidden = !aberta;
    botao.setAttribute("aria-expanded", String(aberta));
    botao.textContent = aberta ? "Esconder tabela" : "Ver tabela";
  });
  host.replaceChildren(h("figure", { class: "grafico" }, cabeca, legenda, area, h("div", { class: "grafico-rodape" }, botao), caixaTabela));

  let larguraAtual = 0;
  const g = {
    render() {
      const spec = fabrica();
      cabeca.replaceChildren(...[h("figcaption", { class: "eyebrow", texto: spec.titulo }), spec.nota ? h("p", { class: "nota", texto: spec.nota }) : null].filter(Boolean));
      legenda.replaceChildren(...(spec.legenda && spec.legenda.length >= 2 ? spec.legenda.map((i) => h("span", {}, chaveDaLegenda(i), i.nome)) : []));
      legenda.hidden = legenda.childElementCount === 0;
      larguraAtual = Math.floor(area.clientWidth) || 320;
      const svg = spec.svg(Math.max(240, larguraAtual));
      svg.setAttribute("role", "group");
      svg.setAttribute("aria-label", spec.descricao || spec.titulo);
      area.replaceChildren(svg);
      caixaTabela.replaceChildren(spec.tabela());
      Dica.esconder();
    },
  };
  if (window.ResizeObserver) {
    new ResizeObserver(() => {
      if (Math.abs(Math.floor(area.clientWidth) - larguraAtual) > 2 && area.clientWidth > 0) g.render();
    }).observe(area);
  }
  g.render();
  return g;
}

// ------------------------------------------------------------------ gráfico de linha com mira
// pontos: [{data:"2026-08-03", y}], marcas: [{data, rotulo}]
function desenharLinha(w, spec) {
  const alt = w < 480 ? 230 : 280;
  const m = { e: 54, d: 62, t: 26, b: 28 };
  const pontos = spec.pontos.map((p) => ({ ...p, t: Date.parse(p.data + "T12:00:00Z") }));
  const ys = pontos.map((p) => p.y);
  const folga = (Math.max(...ys) - Math.min(...ys)) * 0.1;
  const dom = dominioBonito(Math.min(...ys) - folga, Math.max(...ys) + folga, 4);
  const x = linear(pontos[0].t, pontos[pontos.length - 1].t, m.e, w - m.d);
  const y = linear(dom.lo, dom.hi, alt - m.b, m.t);
  const svg = s("svg", { width: w, height: alt, viewBox: `0 0 ${w} ${alt}`, tabindex: "0" });

  for (const v of dom.marcas) {
    svg.append(s("line", { class: "grade", x1: m.e, x2: w - m.d, y1: y(v), y2: y(v) }));
    svg.append(s("text", { class: "eixo-y", x: m.e - 6, y: y(v) + 4, "text-anchor": "end", texto: spec.formatoY(v) }));
  }
  // Marcadores do eixo x: dia 1 de cada mês e o último dia.
  const inicio = new Date(pontos[0].t), fim = new Date(pontos[pontos.length - 1].t);
  const rotulosX = [];
  for (let d = new Date(Date.UTC(inicio.getUTCFullYear(), inicio.getUTCMonth(), 1)); d <= fim; d = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1))) {
    if (d >= inicio) rotulosX.push(d.getTime());
  }
  rotulosX.push(fim.getTime());
  for (const t of rotulosX) {
    const iso = new Date(t).toISOString().slice(0, 10);
    svg.append(s("text", { class: "eixo-x", x: x(t), y: alt - 8, "text-anchor": t === fim.getTime() ? "end" : "middle", texto: dataBR(iso).slice(0, 5) }));
  }
  for (const marca of spec.marcas || []) {
    const t = Date.parse(marca.data + "T12:00:00Z");
    if (t < pontos[0].t || t > pontos[pontos.length - 1].t) continue;
    svg.append(s("line", { class: "marca-vertical", x1: x(t), x2: x(t), y1: m.t - 4, y2: alt - m.b }));
    svg.append(s("text", { class: "rotulo-marca", x: x(t), y: m.t - 9, "text-anchor": "middle", texto: marca.rotulo }));
  }
  const caminho = pontos.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.y).toFixed(1)}`).join("");
  svg.append(s("path", { d: caminho, fill: "none", stroke: spec.cor, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));

  // Rótulos diretos: último valor, máximo e mínimo.
  const ultimo = pontos[pontos.length - 1];
  const imax = ys.indexOf(Math.max(...ys)), imin = ys.indexOf(Math.min(...ys));
  const rotulados = [[pontos.length - 1, "fim"], [imax, "max"], [imin, "min"]].filter(([i], k, a) => a.findIndex(([j]) => j === i) === k);
  for (const [i, tipo] of rotulados) {
    const p = pontos[i];
    svg.append(s("circle", { cx: x(p.t), cy: y(p.y), r: 4, fill: spec.cor, stroke: "var(--superficie)", "stroke-width": 2 }));
    const texto = spec.formatoRotulo(p.y);
    if (tipo === "fim") {
      svg.append(s("text", { class: "rotulo-valor", x: x(p.t) + 8, y: y(p.y) + 4, texto }));
    } else {
      const acima = tipo === "max";
      svg.append(s("text", { class: "rotulo-valor", x: Math.min(Math.max(x(p.t), m.e + larguraTexto(texto, 10.5) / 2), w - m.d - larguraTexto(texto, 10.5) / 2), y: y(p.y) + (acima ? -9 : 17), "text-anchor": "middle", texto }));
    }
  }

  // Mira: linha vertical que segue o ponteiro e se prende ao dia mais próximo.
  const mira = s("g", { class: "mira", visibility: "hidden" },
    s("line", { class: "mira-linha", y1: m.t - 4, y2: alt - m.b }),
    s("circle", { r: 5, fill: spec.cor, stroke: "var(--superficie)", "stroke-width": 2 }));
  svg.append(mira);
  let ativo = pontos.length - 1;
  function mostrar(i, ancora) {
    ativo = Math.max(0, Math.min(pontos.length - 1, i));
    const p = pontos[ativo];
    mira.setAttribute("visibility", "visible");
    mira.firstChild.setAttribute("x1", x(p.t)); mira.firstChild.setAttribute("x2", x(p.t));
    mira.lastChild.setAttribute("cx", x(p.t)); mira.lastChild.setAttribute("cy", y(p.y));
    const ret = svg.getBoundingClientRect();
    const [ax, ay] = ancora || [ret.left + x(p.t), ret.top + y(p.y)];
    const anterior = ativo > 0 ? pontos[ativo - 1].y : null;
    const linhas = [{ cor: spec.cor, valor: spec.formatoValor(p.y), rotulo: spec.nome }];
    if (anterior !== null) linhas.push({ valor: pct((p.y / anterior - 1) * 100, 1), rotulo: "no dia" });
    Dica.mostrar({ titulo: dataComDia(p.data), linhas }, ax, ay);
  }
  const sobre = s("rect", { x: m.e, y: m.t - 4, width: w - m.d - m.e, height: alt - m.b - m.t + 4, fill: "transparent", "data-dica": "1" });
  const mover = (e) => {
    const ret = svg.getBoundingClientRect();
    const t = x.inversa(e.clientX - ret.left);
    let melhor = 0;
    pontos.forEach((p, i) => { if (Math.abs(p.t - t) < Math.abs(pontos[melhor].t - t)) melhor = i; });
    mostrar(melhor, [ret.left + x(pontos[melhor].t), e.clientY]);
  };
  sobre.addEventListener("pointermove", mover);
  sobre.addEventListener("pointerdown", mover);
  sobre.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") { mira.setAttribute("visibility", "hidden"); Dica.esconder(); } });
  svg.append(sobre);
  svg.addEventListener("keydown", (e) => {
    const passo = { ArrowLeft: -1, ArrowRight: 1, Home: -9999, End: 9999 }[e.key];
    if (passo === undefined) return;
    e.preventDefault();
    mostrar(ativo + passo);
  });
  svg.addEventListener("focus", () => mostrar(ativo));
  svg.addEventListener("blur", () => { mira.setAttribute("visibility", "hidden"); Dica.esconder(); });
  return svg;
}

// ------------------------------------------------------------------ barras agrupadas (colunas)
function caminhoBarraV(x, largura, yBase, yValor, r = 4) {
  const alto = Math.abs(yBase - yValor);
  if (alto < 0.5) return `M${x},${yBase}h${largura}`;
  const rr = Math.min(r, largura / 2, alto);
  if (yValor < yBase) {
    return `M${x},${yBase}V${yValor + rr}Q${x},${yValor} ${x + rr},${yValor}H${x + largura - rr}Q${x + largura},${yValor} ${x + largura},${yValor + rr}V${yBase}Z`;
  }
  return `M${x},${yBase}V${yValor - rr}Q${x},${yValor} ${x + rr},${yValor}H${x + largura - rr}Q${x + largura},${yValor} ${x + largura},${yValor - rr}V${yBase}Z`;
}

// categorias: [{rotulo, itens:[valor|null por série], motivos:[texto|null por série]}]
// series: [{nome, cor}]; rotular(ci, si, valor) decide quais barras levam o valor escrito.
function desenharBarras(w, spec) {
  const alt = w < 480 ? 250 : 290;
  const rotulosY = (v) => spec.formatoEixo(v);
  const valores = spec.categorias.flatMap((c) => c.itens).filter(Number.isFinite);
  const dom = dominioBonito(Math.min(0, ...valores), Math.max(0, ...valores), 5);
  const m = { e: Math.max(...dom.marcas.map((v) => larguraTexto(rotulosY(v)))) + 14, d: 8, t: 12, b: 28 };
  const y = linear(dom.lo, dom.hi, alt - m.b - 16, m.t + 16);
  const nCat = spec.categorias.length, nSer = spec.series.length;
  const grupo = (w - m.e - m.d) / nCat;
  const larguraBarra = Math.max(6, Math.min(22, (grupo - 8) / (nSer + 0.4)));
  const folga = 2;
  const svg = s("svg", { width: w, height: alt, viewBox: `0 0 ${w} ${alt}` });
  const yTopo = y(dom.hi) - 16, yFundo = y(dom.lo) + 16;
  for (const v of dom.marcas) {
    svg.append(s("line", { class: "grade", x1: m.e, x2: w - m.d, y1: y(v), y2: y(v) }));
    svg.append(s("text", { class: "eixo-y", x: m.e - 6, y: y(v) + 4, "text-anchor": "end", texto: rotulosY(v) }));
  }
  svg.append(s("line", { class: "eixo-base", x1: m.e, x2: w - m.d, y1: y(0), y2: y(0) }));

  // Quais barras levam o valor escrito: a última categoria e os extremos de cada série.
  const rotular = new Set();
  rotulo: for (let si = 0; si < nSer; si++) {
    const col = spec.categorias.map((c) => c.itens[si]);
    const vs = col.filter(Number.isFinite);
    if (!vs.length) continue rotulo;
    rotular.add(`${col.indexOf(Math.max(...vs))}|${si}`);
    rotular.add(`${col.indexOf(Math.min(...vs))}|${si}`);
    if (Number.isFinite(col[nCat - 1])) rotular.add(`${nCat - 1}|${si}`);
  }

  spec.categorias.forEach((cat, ci) => {
    const x0 = m.e + ci * grupo;
    const centro = x0 + grupo / 2;
    const larguraTotal = nSer * larguraBarra + (nSer - 1) * folga;
    const g = s("g", { class: "grupo" });
    g.append(s("rect", { class: "realce", x: x0 + 1, y: yTopo, width: grupo - 2, height: yFundo - yTopo, rx: 4 }));
    cat.itens.forEach((v, si) => {
      if (!Number.isFinite(v)) return;
      const bx = centro - larguraTotal / 2 + si * (larguraBarra + folga);
      g.append(s("path", { d: caminhoBarraV(bx, larguraBarra, y(0), y(v)), fill: spec.series[si].cor }));
      if (rotular.has(`${ci}|${si}`)) {
        const texto = spec.formatoValor(v);
        const largT = larguraTexto(texto, 10.5);
        // Com duas séries os valores se abrem para os lados, para não se sobreporem.
        let ancora = "middle", tx = bx + larguraBarra / 2;
        if (nSer === 2) { ancora = si === 0 ? "end" : "start"; tx = si === 0 ? bx + larguraBarra - 2 : bx + 2; }
        const minX = m.e + 2, maxX = w - 2;
        if (ancora === "end") tx = Math.max(tx, minX + largT);
        else if (ancora === "start") tx = Math.min(tx, maxX - largT);
        g.append(s("text", { class: "rotulo-valor", x: tx, y: v >= 0 ? y(v) - 6 : y(v) + 14, "text-anchor": ancora, texto }));
      }
    });
    g.append(s("text", { class: "eixo-x", x: centro, y: alt - 8, "text-anchor": "middle", texto: cat.rotulo }));
    const alvo = s("rect", { class: "alvo", x: x0, y: yTopo, width: grupo, height: yFundo - yTopo + 20, fill: "transparent", tabindex: "0", "aria-label": spec.descricaoDaCategoria(cat) });
    Dica.ligar(alvo, () => spec.dicaDaCategoria(cat, ci));
    g.append(alvo);
    svg.append(g);
  });
  return svg;
}

// ------------------------------------------------------------------ barras horizontais (uma série, em ordem)
function desenharBarrasH(w, spec) {
  const itens = spec.itens;
  const passo = 28, topo = 8;
  const alt = topo * 2 + itens.length * passo;
  const maxRotulo = Math.min(w * 0.42, Math.max(...itens.map((i) => larguraTexto(i.rotulo, 11))) + 8);
  const letras = Math.floor(maxRotulo / (11 * 0.58));
  const vs = itens.map((i) => i.valor);
  const lo = Math.min(0, ...vs), hi = Math.max(0, ...vs);
  const margemRotulo = 46;
  const x0 = maxRotulo + 8 + (lo < 0 ? margemRotulo : 0);
  const x1 = w - 16 - (hi > 0 ? margemRotulo : 0);
  const x = linear(lo, hi, x0, x1);
  const svg = s("svg", { width: w, height: alt, viewBox: `0 0 ${w} ${alt}` });
  svg.append(s("line", { class: "eixo-base", x1: x(0), x2: x(0), y1: topo, y2: alt - topo }));
  itens.forEach((it, i) => {
    const cy = topo + i * passo + passo / 2;
    const g = s("g", { class: "grupo" });
    g.append(s("rect", { class: "realce", x: 0, y: cy - passo / 2, width: w, height: passo, rx: 4 }));
    const rotulo = it.rotulo.length > letras ? it.rotulo.slice(0, Math.max(1, letras - 1)) + "…" : it.rotulo;
    g.append(s("text", { class: "rotulo-cat", x: maxRotulo, y: cy + 4, "text-anchor": "end", texto: rotulo }));
    const ponta = x(it.valor), base = x(0);
    const barra = s("path", { d: caminhoBarraH(base, ponta, cy - 7, 14, 4), fill: spec.cor });
    g.append(barra);
    const negativo = it.valor < 0;
    g.append(s("text", { class: "rotulo-valor", x: ponta + (negativo ? -6 : 6), y: cy + 4, "text-anchor": negativo ? "end" : "start", texto: spec.formatoValor(it.valor) }));
    const alvo = s("rect", { class: "alvo", x: 0, y: cy - passo / 2, width: w, height: passo, fill: "transparent", tabindex: "0", "aria-label": `${it.rotulo}: ${spec.formatoValor(it.valor)}` });
    Dica.ligar(alvo, () => spec.dica(it));
    g.append(alvo);
    svg.append(g);
  });
  return svg;
}
function caminhoBarraH(base, ponta, y0, alto, r) {
  const largura = Math.abs(ponta - base);
  if (largura < 0.5) return `M${base},${y0}v${alto}`;
  const rr = Math.min(r, largura, alto / 2);
  const y1 = y0 + alto;
  if (ponta > base) return `M${base},${y0}H${ponta - rr}Q${ponta},${y0} ${ponta},${y0 + rr}V${y1 - rr}Q${ponta},${y1} ${ponta - rr},${y1}H${base}Z`;
  return `M${base},${y0}H${ponta + rr}Q${ponta},${y0} ${ponta},${y0 + rr}V${y1 - rr}Q${ponta},${y1} ${ponta + rr},${y1}H${base}Z`;
}

// ------------------------------------------------------------------ dispersão com reta de tendência
// pontos: [{x, y, serie:0|1, rotulo, texto?, dica}], series: [{nome, cor}]
function desenharDispersao(w, spec) {
  const alt = w < 480 ? 300 : 360;
  const xs = spec.pontos.map((p) => p.x), ys = spec.pontos.map((p) => p.y);
  const dx = dominioBonito(Math.min(0, ...xs) - 1, Math.max(0, ...xs) + 1, 6);
  const dy = dominioBonito(Math.min(0, ...ys) - 1, Math.max(0, ...ys) + 1, 5);
  const m = { e: Math.max(...dy.marcas.map((v) => larguraTexto(spec.formatoY(v)))) + 28, d: 12, t: 12, b: 44 };
  const x = linear(dx.lo, dx.hi, m.e, w - m.d);
  const y = linear(dy.lo, dy.hi, alt - m.b, m.t);
  const svg = s("svg", { width: w, height: alt, viewBox: `0 0 ${w} ${alt}` });
  for (const v of dy.marcas) {
    svg.append(s("line", { class: "grade", x1: m.e, x2: w - m.d, y1: y(v), y2: y(v) }));
    svg.append(s("text", { class: "eixo-y", x: m.e - 6, y: y(v) + 4, "text-anchor": "end", texto: spec.formatoY(v) }));
  }
  for (const v of dx.marcas) {
    svg.append(s("line", { class: "grade", x1: x(v), x2: x(v), y1: m.t, y2: alt - m.b }));
    svg.append(s("text", { class: "eixo-x", x: x(v), y: alt - m.b + 16, "text-anchor": "middle", texto: num(v, 0) }));
  }
  svg.append(s("line", { class: "eixo-base", x1: m.e, x2: w - m.d, y1: y(0), y2: y(0) }));
  svg.append(s("line", { class: "eixo-base", x1: x(0), x2: x(0), y1: m.t, y2: alt - m.b }));
  svg.append(s("text", { class: "titulo-eixo", x: (m.e + w - m.d) / 2, y: alt - 6, "text-anchor": "middle", texto: spec.tituloX }));
  svg.append(s("text", { class: "titulo-eixo", transform: `translate(12 ${(m.t + alt - m.b) / 2}) rotate(-90)`, "text-anchor": "middle", texto: spec.tituloY }));

  const reta = spec.tendencia;
  const xa = Math.max(dx.lo, Math.min(...xs) - 0.5), xb = Math.min(dx.hi, Math.max(...xs) + 0.5);
  svg.append(s("line", { class: "tendencia", x1: x(xa), y1: y(reta.intercepto + reta.inclinacao * xa), x2: x(xb), y2: y(reta.intercepto + reta.inclinacao * xb) }));

  // Quais pontos levam nome: 2026 e os extremos dos dois eixos.
  const nomeados = new Set();
  spec.pontos.forEach((p, i) => { if (p.destaque) nomeados.add(i); });
  for (const lista of [xs, ys]) {
    nomeados.add(lista.indexOf(Math.max(...lista)));
    nomeados.add(lista.indexOf(Math.min(...lista)));
  }
  const ocupados = [];
  spec.pontos.forEach((p, i) => {
    svg.append(s("circle", { cx: x(p.x), cy: y(p.y), r: 5, fill: spec.series[p.serie].cor, stroke: "var(--superficie)", "stroke-width": 2 }));
    if (!nomeados.has(i)) return;
    const largT = larguraTexto(p.rotulo, 10.5);
    // Tenta à direita do ponto, depois à esquerda, subindo ou descendo até não bater em outro nome.
    const candidatos = [];
    for (const lado of ["start", "end"]) for (const dy of [0, -14, 14, -28, 28]) candidatos.push([lado, dy]);
    let escolhido = null;
    for (const [lado, dy] of candidatos) {
      const tx = lado === "start" ? x(p.x) + 9 : x(p.x) - 9;
      const caixa = { x0: lado === "start" ? tx : tx - largT, x1: lado === "start" ? tx + largT : tx, y: y(p.y) + 4 + dy };
      const dentro = caixa.x0 > m.e && caixa.x1 < w - 2;
      const bate = ocupados.some((o) => Math.abs(o.y - caixa.y) < 13 && o.x0 < caixa.x1 && o.x1 > caixa.x0);
      if (dentro && !bate) { escolhido = [lado, tx, caixa]; break; }
    }
    if (!escolhido) return;
    const [ancora, tx, caixa] = escolhido;
    const ty = caixa.y;
    ocupados.push(caixa);
    svg.append(s("text", { class: "rotulo-valor", x: tx, y: ty, "text-anchor": ancora, texto: p.rotulo }));
  });

  // Um alvo de 28 px em volta de cada ponto: dá para acertar com o dedo e com o teclado.
  spec.pontos.forEach((p) => {
    const alvo = s("circle", { class: "alvo-ponto", cx: x(p.x), cy: y(p.y), r: 14, fill: "transparent", tabindex: "0", "aria-label": p.rotulo + ": " + p.texto });
    Dica.ligar(alvo, () => p.dica);
    svg.append(alvo);
  });
  return svg;
}

// ------------------------------------------------------------------ faixas dos cenários
// categorias: ["Hoje", "Posse", ...]; base: nível de hoje; series: [{nome, curto, cor, faixas:[{minimo,central,maximo}|null por horizonte]}]
function desenharFaixas(w, spec) {
  const alt = w < 480 ? 280 : 320;
  const todos = [spec.base, ...spec.series.flatMap((s_) => s_.faixas.filter(Boolean).flatMap((f) => [f.minimo, f.maximo]))].filter(Number.isFinite);
  const dom = dominioBonito(Math.min(...todos), Math.max(...todos), 5);
  const m = { e: Math.max(...dom.marcas.map((v) => larguraTexto(spec.formatoEixo(v)))) + 14, d: 8, t: 22, b: 30 };
  const y = linear(dom.lo, dom.hi, alt - m.b - 6, m.t + 6);
  const nCat = spec.categorias.length;
  const grupo = (w - m.e - m.d) / nCat;
  const n = spec.series.length;
  const espaco = Math.min(40, grupo / (n + 0.15));
  const svg = s("svg", { width: w, height: alt, viewBox: `0 0 ${w} ${alt}` });
  for (const v of dom.marcas) {
    svg.append(s("line", { class: "grade", x1: m.e, x2: w - m.d, y1: y(v), y2: y(v) }));
    svg.append(s("text", { class: "eixo-y", x: m.e - 6, y: y(v) + 4, "text-anchor": "end", texto: spec.formatoEixo(v) }));
  }
  // Nível de hoje: linha fina no mesmo eixo.
  svg.append(s("line", { class: "nivel-hoje", x1: m.e, x2: w - m.d, y1: y(spec.base), y2: y(spec.base) }));
  svg.append(s("text", { class: "rotulo-cat", x: m.e + 4, y: y(spec.base) - 12, "text-anchor": "start", texto: "Hoje: " + spec.formatoValor(spec.base) }));

  const mostrarNomes = espaco >= 26;
  spec.categorias.forEach((nome, ci) => {
    const x0 = m.e + ci * grupo, centro = x0 + grupo / 2;
    const g = s("g", { class: "grupo" });
    g.append(s("rect", { class: "realce", x: x0 + 1, y: m.t - 4, width: grupo - 2, height: alt - m.b - m.t + 8, rx: 4 }));
    if (ci === 0) {
      g.append(s("circle", { cx: centro, cy: y(spec.base), r: 5, fill: "var(--ink)", stroke: "var(--superficie)", "stroke-width": 2 }));
    } else {
      spec.series.forEach((serie, si) => {
        const f = serie.faixas[ci - 1];
        if (!f || !Number.isFinite(f.minimo)) return;
        const cx = centro + (si - (n - 1) / 2) * espaco;
        const topo = y(f.maximo), fundo = y(f.minimo);
        g.append(s("rect", { x: cx - 4, y: topo, width: 8, height: Math.max(fundo - topo, 2), rx: 4, fill: serie.cor }));
        g.append(s("circle", { cx, cy: y(f.central), r: 5, fill: "var(--superficie)", stroke: serie.cor, "stroke-width": 2 }));
        if (ci === nCat - 1 && mostrarNomes) {
          g.append(s("text", { class: "rotulo-cat", x: cx, y: topo - 7, "text-anchor": "middle", texto: serie.curto }));
        }
      });
    }
    g.append(s("text", { class: "eixo-x", x: centro, y: alt - 10, "text-anchor": "middle", texto: nome }));
    const alvo = s("rect", { class: "alvo", x: x0, y: m.t - 4, width: grupo, height: alt - m.t - m.b + 8, fill: "transparent", tabindex: "0", "aria-label": spec.descricaoDaCategoria(ci) });
    Dica.ligar(alvo, () => spec.dicaDaCategoria(ci));
    g.append(alvo);
    svg.append(g);
  });
  return svg;
}

// ------------------------------------------------------------------ mapa de calor (tabela HTML colorida)
function corCSS(nome) {
  return getComputedStyle(document.documentElement).getPropertyValue(nome).trim();
}
function hexParaRgb(hex) {
  const t = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(t.slice(i, i + 2), 16));
}
function luminancia([r, g, b]) {
  const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}
function contraste(a, b) {
  const [l1, l2] = [luminancia(a), luminancia(b)].sort((p, q) => q - p);
  return (l1 + 0.05) / (l2 + 0.05);
}
// Cor da célula: cinza no meio, azul para cima e vermelho para baixo, mais forte quanto maior o valor.
function corDaCelula(valor, teto) {
  const meio = hexParaRgb(corCSS("--div-meio"));
  const polo = hexParaRgb(corCSS(valor >= 0 ? "--div-alto" : "--div-baixo"));
  const t = Math.min(1, Math.abs(valor) / teto);
  const rgb = meio.map((c, i) => Math.round(c + (polo[i] - c) * t));
  const claro = [255, 255, 255], escuro = [11, 11, 11];
  const texto = contraste(rgb, claro) >= contraste(rgb, escuro) ? "#ffffff" : "#0b0b0b";
  return { fundo: `rgb(${rgb.join(",")})`, texto, rgb };
}
function gradienteDaLegenda(teto) {
  const passos = [-1, -0.5, 0, 0.5, 1].map((f) => corDaCelula(f * teto, teto).fundo);
  return `linear-gradient(90deg, ${passos.join(", ")})`;
}
