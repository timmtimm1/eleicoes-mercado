# Eleições e mercado — especificação

Escopo fechado com o Bernardo em 31/10/2026, em três rodadas de perguntas.
Cada fase termina num **gate**: ele confere e aprova antes da próxima.

## Objetivo

Medir como bolsa, dólar, juros e risco-país reagiram às eleições presidenciais
de 1994 a 2026, explicar a reação pelo vencedor, pela **surpresa** em relação às
pesquisas e pelas **propostas** de cada candidato, e montar cenários para os
próximos 14 meses (até 1 ano de governo).

O caso que motivou o estudo: em 2026 o Ibovespa subiu 7,7% no pregão seguinte ao
1º turno (Flávio Bolsonaro na frente, 47,0% × 45,2% dos votos válidos) e caiu
13,9% no pregão seguinte ao 2º turno (vitória do Lula, circuit breaker em
26/10/2026). Números da imprensa; a fase 1 confere com os dados brutos.

Vitrine pública. **Não é recomendação de investimento.**

## Decisões do Bernardo (31/10/2026)

| Tema | Escolha |
|---|---|
| Eleições | Presidenciais de **1994 a 2026** (9 eleições; 1994 e 1998 sem 2º turno) |
| Ativos | Ibovespa e dólar sempre + **juros**, **risco-país**, **estatais × privadas**, **setores** |
| Efeito do mundo | **Os dois lado a lado**: variação bruta e variação "só Brasil" (descontado o exterior) |
| Explicação | **Surpresa**: últimas pesquisas antes de cada turno × resultado oficial do TSE (Datafolha, Ibope/Ipec, Quaest e AtlasIntel na média) |
| Janelas | **Curtas + longas** (ver abaixo) |
| Projeção | **Cenários + histórico**: pessimista, base e otimista com gatilhos concretos; faixas tiradas das eleições passadas |
| Chances | **Sem %**: cada cenário é "se X, então faixa Y". Eu proponho, ele aprova |
| Horizonte | **Posse, 100 dias e 1 ano de governo** |
| Propostas | **Tabela por tema + marcos**: 6 temas, promessa × o que foi feito, fatos que mexeram no mercado |
| Entrega | **Repo novo + página no GitHub Pages + planilha**. Remote e publicação só com aprovação dele |
| Planilha | **Dados + Painel com fórmulas** (lista de eleição e janela). Precisa abrir no LibreOffice |
| Depois de pronta | **Foto datada** (fechamento de 30/10/2026) + comando que atualiza preços e compara projeção × realizado |
| Risco-país em 2026 | **Fica de fora**: EMBI+ só até 2022; em 2026 o medo aparece em juros, dólar e bolsa |
| Juros em 2002 | **Selic diária + swap DI × pré 360 dias mensal** (Ipeadata `BMF12_SWAPDI360F12`); sem janelas curtas nos juros longos |

## Calendário

| Ano | 1º turno | 2º turno | Vencedor × 2º colocado | Posse |
|---|---|---|---|---|
| 1994 | 03/10 | — | FHC × Lula | 01/01/1995 |
| 1998 | 04/10 | — | FHC × Lula (reeleição) | 01/01/1999 |
| 2002 | 06/10 | 27/10 | Lula × Serra | 01/01/2003 |
| 2006 | 01/10 | 29/10 | Lula × Alckmin (reeleição) | 01/01/2007 |
| 2010 | 03/10 | 31/10 | Dilma × Serra | 01/01/2011 |
| 2014 | 05/10 | 26/10 | Dilma × Aécio (reeleição) | 01/01/2015 |
| 2018 | 07/10 | 28/10 | Bolsonaro × Haddad | 01/01/2019 |
| 2022 | 02/10 | 30/10 | Lula × Bolsonaro | 01/01/2023 |
| 2026 | 04/10 | 25/10 | Lula × Flávio Bolsonaro (reeleição) | **05/01/2027** (EC 111/2021) |

Cada eleição recebe também a situação do vencedor (reeleição, continuidade ou
oposição; 1994 conta como continuidade, porque o FHC era o ministro da Fazenda
do Itamar), o candidato que o mercado preferia e quem era o favorito nas
pesquisas.

## Janelas

A base de cada janela é o fechamento do **último pregão antes do turno**.

| Janela | Do | Até |
|---|---|---|
| Corrida | pregão mais próximo de 60 dias corridos antes do 1º turno | último pregão antes do 1º turno |
| D+1, D+5, D+20 do 1º turno | último pregão antes do 1º turno | 1º, 5º e 20º pregão depois |
| Entre turnos | último pregão antes do 1º turno | último pregão antes do 2º turno |
| D+1, D+5, D+20 do 2º turno | último pregão antes do 2º turno | 1º, 5º e 20º pregão depois |
| Até a posse | último pregão antes do turno decisivo | último pregão antes da posse |
| 100 dias | idem | 100 dias corridos depois da posse |
| 1 ano | idem | 1 ano depois da posse |

Turno decisivo: o 1º em 1994 e 1998, o 2º nas demais.

## O que medir

| Série | Fonte | Desde | "Só Brasil" descontado de |
|---|---|---|---|
| Ibovespa | Yahoo `^BVSP`, conferido com Ipeadata `GM366_IBVSP366` | 1993 | MSCI Emergentes em dólar (1997+); S&P 500 em 1994 |
| Dólar | BCB SGS 1 (venda) | 1984 | índice do dólar no mundo (DXY) |
| Juros curtos | BCB SGS (Selic/CDI) | 1986 | juros dos EUA |
| Juros prefixados | Tesouro Direto (prefixados) | 31/12/2004 | Treasury 10 anos |
| Juros 2002 | Ipeadata swap DI × pré 360 dias, fim de mês | mensal | — |
| Risco-país | Ipeadata EMBI+ `JPM366_EMBI366` (1994–2022; 2026 fora, decisão dele) | abr/1994 a jul/2024 | já é diferença sobre os EUA |
| Estatais × privadas | COTAHIST da B3 | 1986 | uma contra a outra |
| Setores | COTAHIST da B3 | 1986 | Ibovespa |
| MSCI Emergentes | API pública do MSCI (índice 891800) | 1997 | — |

**"Só Brasil"**: modelo de mercado do estudo de evento. Ajusto o beta do
Brasil contra o exterior em 250 pregões que terminam antes da corrida e
desconto da variação o que o exterior explica. Mostro sempre ao lado da
variação bruta.

**Estatais × privadas**: carteira de peso igual com as estatais listadas na data
de cada eleição (a lista muda: Vale até 1997, Telebras até 1998, Eletrobras até
2022, Sabesp até 2024) contra as privadas mais negociadas. Só preço, sem
dividendos, nos dois lados (comparação justa).

**Setores**: bancos, petróleo, mineração e siderurgia, elétricas e saneamento,
varejo e consumo, construção e imóveis. As ações mais negociadas de cada setor
nos 12 meses antes da eleição. Tabela de classificação à mão em `dados/`.

**Surpresa**: média das últimas pesquisas (Datafolha, Ibope/Ipec, e Quaest e
AtlasIntel quando houver) antes de cada turno, em votos válidos, contra o
resultado do TSE. A AtlasIntel entrou na média por decisão dele em 31/10/2026.
A surpresa é medida **a favor do candidato que o mercado preferia** (dos dois
primeiros, o de fora do PT, em todas as eleições): margem dele no TSE menos a
margem dele nas pesquisas. Assim o sinal da surpresa bate com o da reação da
bolsa (decisão de 31/10/2026; campo `candidato_mercado` em `dados/eleicoes.yaml`).

## Propostas (qualitativo)

Para os 2 principais candidatos de cada eleição, 6 temas:

1. Gastos e regra fiscal
2. Privatizações
3. Petrobras e estatais
4. Banco Central e juros
5. Reformas (previdência, tributária, trabalhista)
6. Câmbio e comércio exterior

Para o vencedor: promessa × o que foi feito. Mais os **marcos** que mexeram no
mercado, com data (ex.: Carta ao Povo Brasileiro em 22/06/2002, anúncio do
ministro da Fazenda) e a reação nos dias seguintes.

Fontes: programa de governo registrado no TSE (obrigatório desde 2010),
imprensa e estudos da época, com link em cada linha.

## Projeção

Três cenários para 2026–2028, cada um com gatilhos concretos (nome e sinais da
Fazenda, meta fiscal, Selic e Banco Central, contestação do resultado) e a
faixa de Ibovespa, dólar e juros na posse (05/01/2027), nos 100 dias e em 1 ano
de governo. As faixas saem das eleições passadas parecidas, aplicadas aos
preços de 30/10/2026. Sem probabilidade em %. Premissas em YAML com
`status: proposta` até ele aprovar.

## Entrega

- Repo `~/Projects/eleicoes-mercado`, Python + uv, comando `eleicoes`. Português.
- Página (GitHub Pages) em 8 seções: resumo; 2026 agora; histórico por janela
  (bruto × só Brasil); surpresa; estatais e setores; propostas; cenários;
  limites e fontes. Linguagem simples.
- Planilha `.xlsx`: séries diárias, tabelas prontas e aba Painel (escolhe
  eleição e janela em lista, fórmulas calculam). Conferida no LibreOffice.
- `eleicoes atualizar`: baixa preços novos e compara a projeção com o que
  aconteceu. Ele decide quando rodar.

## Fases

| Fase | Entrega | Gate |
|---|---|---|
| F1 Dados | séries, calendário, resultados do TSE, pesquisas | tabela de conferência com a imprensa (26/10/2026 etc.) |
| F2 Estudo de evento | janelas × séries, bruto e só Brasil | tabela das 9 eleições |
| F3 Estatais e setores | carteiras e reação por janela | listas de ações por eleição |
| F4 Propostas | tabela por tema, promessa × realidade, marcos | texto revisado por ele |
| F5 Cenários | gatilhos e faixas | premissas aprovadas |
| F6 Página e planilha | site, xlsx, README | leitura dele |
| F7 Atualizar | comando de atualização | rodada de teste |

Cada fase numa branch, commits separados por assunto, tag na `main` ao fim.

## Limites já conhecidos

- **9 eleições é amostra pequena.** As faixas mostram o que já aconteceu, não
  preveem.
- **1994**: o Real tinha 3 meses e não há MSCI Emergentes diário; o controle é o
  S&P 500.
- **Juros prefixados**: o Tesouro Direto começa em 31/12/2004. 1994 e 1998 só
  têm Selic. 2002 tem Selic diária e swap de 360 dias só mensal.
- **Risco-país**: o EMBI+ acabou em julho de 2024 e o CDS de 5 anos está em
  sites que bloqueiam download automático. 2026 fica sem risco-país.
- Carteiras de estatais e setores: só preço, sem dividendos.
- MSCI Emergentes inclui o Brasil (~5% do índice), o que puxa o "só Brasil" um
  pouco para zero em dias de queda forte.
