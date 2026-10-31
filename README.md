# Eleições e mercado: bolsa, dólar e juros de 1994 a 2026

Como a bolsa, o dólar e os juros reagiram a cada eleição para presidente desde o Plano Real,
por que reagiram assim e o que o histórico diz sobre os próximos meses depois da eleição de
2026. Dados até 30/10/2026.

Página com os gráficos: https://timmtimm1.github.io/eleicoes-mercado/ · Planilha:
`saida/eleicoes_mercado.xlsx`

<!-- resumo:inicio -->
Em 2026 a bolsa teve, nos dois turnos, as reações mais fortes a uma eleição desde 1994. No
dia seguinte ao 1º turno, o Ibovespa subiu 7,7%. O Flávio Bolsonaro tinha ficado em
primeiro, e as pesquisas davam o Lula na frente. No dia seguinte ao 2º turno, com a vitória
do Lula, a bolsa caiu 13,9%. Até então, a maior queda em um dia pós-eleição tinha sido de
4,5%, em 1998. O dólar subiu 9,2% e o Tesouro de 10 anos foi de 12,90% para 15,42% ao ano.

O motivo principal é a surpresa. As três pesquisas da véspera davam o Flávio na frente no 2º
turno, e o mercado já tinha subido apostando nele. Nas eleições passadas, quanto maior a
surpresa a favor do candidato preferido pelo mercado, mais a bolsa sobe no dia seguinte, e
o contrário também vale.

O que vem depois depende menos de quem ganhou e mais do sinal fiscal dos primeiros meses. O
histórico mostra os dois caminhos: em 2002 a bolsa subiu 122% no primeiro ano de governo, e
em 2014 caiu 16,5% enquanto o dólar subia 57%. Os três cenários deste estudo vão de um dólar
entre R$ 4,49 e R$ 4,60 em janeiro de 2028, se vier um sinal fiscal crível, a um dólar entre
R$ 7,93 e R$ 8,18, se vier uma crise de confiança nas contas.
<!-- resumo:fim -->

## Como foi feito

- **9 eleições**, de 1994 a 2026. Dados diários do Banco Central (dólar e Selic), da B3
  (Ibovespa e as ações uma a uma, pelo arquivo COTAHIST), do Tesouro Direto (juros), do
  Ipeadata (risco-país), da MSCI (bolsas emergentes) e do Yahoo (S&P 500, índice do dólar e
  juros dos EUA). Resultados do TSE e as últimas pesquisas de Datafolha, Ibope/Ipec, Quaest
  e AtlasIntel.
- **11 janelas por eleição**: os 60 dias de campanha, o dia seguinte e as semanas depois de
  cada turno, até a posse, 100 dias e 1 ano de governo.
- **"Só Brasil"**: cada variação aparece também sem o que o resto do mundo fez no mesmo
  período. A bolsa em dólar é comparada com as bolsas emergentes, o dólar com o dólar no
  mundo e os juros com os juros dos EUA.
- **Surpresa**: a margem do candidato preferido pelo mercado no resultado do TSE, menos a
  margem dele nas pesquisas da véspera.
- **Estatais e setores**: as 60 empresas mais negociadas antes de cada eleição, separadas
  por setor e por estatal ou privada na data do 1º turno, em carteiras de peso igual.
- **Cenários**: três caminhos para 2026, cada um com os gatilhos que o colocariam em jogo e
  a faixa que bolsa, dólar e juros fizeram em duas eleições parecidas.

O passo a passo, as decisões e os limites estão em `SPEC.md`.

<!-- analise:inicio -->
### O que aconteceu em 2026

No 1º turno, em 4 de outubro, o Flávio Bolsonaro teve 47,03% dos votos válidos e o Lula,
45,16%. As últimas pesquisas davam o contrário: Datafolha 45% a 42% para o Lula, Quaest 46%
a 45% e AtlasIntel 47,0% a 44,1%. No dia seguinte o Ibovespa subiu 7,7% e fechou em 206.912
pontos, recorde. O dólar caiu 4,6% e o Tesouro de 10 anos caiu 1,2 ponto. Foi a maior alta
pós-1º turno da série (a anterior era de 5,5%, em 2022).

Entre os turnos a bolsa segurou a maior parte da alta: na véspera do 2º turno estava 6,8%
acima do nível de antes do 1º. O mercado passou a trabalhar com a vitória do Flávio, e as
três pesquisas da véspera o colocavam na frente: Datafolha e Quaest com 51% a 49%,
AtlasIntel com 50,8% a 49,2%.

O Lula ganhou com 51,79%, uma diferença de 4,4 milhões de votos. Em 26 de outubro a bolsa
caiu 13,9%, com o circuit breaker acionado. O dólar foi de R$ 5,04 para R$ 5,50, alta de
9,2%, e o Tesouro de 10 anos subiu 2,5 pontos, para 15,42% ao ano. Em cinco pregões a bolsa
perdeu 18,1%. No discurso da vitória não houve sinal sobre a meta fiscal, e o Flávio disse
que não reconhecia o resultado (no dia seguinte o PL reconheceu, e ele passou a falar em
pedir a cassação da chapa). Em 26 e 27 de outubro o ministro da Fazenda, Dario Durigan, disse
que o governo vai mudar a lei ou mandar uma PEC para buscar o centro da meta, com um pacote
de pelo menos R$ 39,8 bilhões, e que a equipe do novo mandato ainda não está definida.

### Por que subiu e por que caiu: a surpresa

O mercado não reage ao vencedor; reage ao que não esperava. Em 2026 o candidato preferido
pelo mercado foi 4,2 pontos melhor do que as pesquisas no 1º turno e 5,4 pontos pior no 2º.
É a maior surpresa da série, e foi o único 2º turno, entre os seis com pesquisas na nossa
base, em que o favorito das pesquisas perdeu.

O padrão vem de antes. Nos 14 turnos com pesquisa, a correlação entre a surpresa e o
Ibovespa no dia seguinte é de 0,69. Sem 2026, fica em 0,54, com cerca de 0,5% de bolsa para
cada ponto de surpresa. Em todos os 1º turnos em que o candidato do PT liderava as
pesquisas (2002, 2006, 2010, 2014, 2022 e 2026), ele teve menos votos do que elas indicavam,
e em cinco desses seis a bolsa subiu no dia seguinte (2014 +4,7%, 2022 +5,5%, 2026 +7,7%; a
exceção foi 2002, −4,3%). São poucos casos: é um indício forte, não uma lei.

Uma parte do tamanho da queda vem da aposta anterior: a alta da campanha foi desfeita num
dia só, e em 26 de outubro o Ibovespa fechou abaixo do nível de antes do 1º turno.

### O que o histórico diz sobre quem ganha

O nome do vencedor explica pouco do que vem depois. Nos cinco primeiros anos de governo do
PT na série, a bolsa fez de tudo: +122% (2002), +62% (2006), −20% (2010), −16,5% (2014) e
+17% (2022). O que separa um caso do outro é o sinal fiscal e a equipe econômica:

- Em **2002** o mercado temia o Lula. Vieram a Carta ao Povo Brasileiro, o Palocci na
  Fazenda, o Meirelles no Banco Central e um superávit maior que o pedido pelo FMI. Em um
  ano de governo a bolsa subiu 122% e o dólar caiu 24%.
- Em **2014** a Dilma foi reeleita por pouco, com o mercado apostando no Aécio. O Levy foi
  para a Fazenda, mas as contas pioraram e veio a recessão. Em um ano a bolsa caiu 16,5% e
  o dólar subiu 57%.
- Em **2022** a bolsa caiu 3,9% até a posse, com a PEC da Transição e o discurso contra o
  teto. Depois do arcabouço fiscal, fechou o primeiro ano com alta de 17%.

### Estatais, privadas e setores

Em 2014 e em 2022, no dia seguinte à vitória do PT, as estatais ficaram 5,1 pontos atrás
das privadas. Em 2026 aconteceu o contrário: estatais −10,3%, privadas −19,0%. O choque
desta vez foi de juros e de consumo interno, e não de medo de intervenção. Varejo caiu
30,9%, construção 27,3%, bancos e elétricas 17,8% cada, petróleo 14,9%. A mineração caiu só
4,4%: a Vale subiu 4% no dia, porque exportadora ganha com o dólar alto.

O medo da eleição também nem sempre se confirma depois. Um ano depois da posse de 2022, a
estatal típica tinha subido 21% e a privada típica, 1,5%. Em 2010, a privada típica caiu
30%, contra 3% da estatal. Em 2014 o contrário: estatais −33%, privadas −21%.

### O que vem pela frente: três cenários

Os cenários partem de 30/10/2026: Ibovespa em 167.922 pontos, dólar a R$ 5,42 e Tesouro de
10 anos a 15,23%. Cada faixa é o que bolsa, dólar e juros fizeram, do mesmo ponto do
calendário em diante, em duas eleições parecidas, sem o efeito do resto do mundo.

| Em 1 ano de governo (jan/2028) | Otimista | Base | Pessimista |
|---|---|---|---|
| Parecido com | 2002 e 2006 | 2010 e 2022 | 1998 e 2014 |
| Bolsa em dólar | +5% a +41% | −3% a +7% | −31% a −25% |
| Ibovespa (pontos) | 150 a 196 mil | 174 a 185 mil | 170 a 189 mil |
| Dólar | R$ 4,49 a 4,60 | R$ 5,61 a 5,77 | R$ 7,93 a 8,18 |
| Tesouro 10 anos | ~15,1% (só 2006) | 13,8% a 14,5% | ~19,5% (só 2014) |

- **Otimista, sinal fiscal crível**: um nome para a Fazenda visto como comprometido com a
  meta (ou o Durigan mantido com o pacote), a lei ou PEC do centro da meta enviada antes da
  posse, um Copom sem perder a confiança e a contestação encerrada no TSE.
- **Base, continuidade com ruído**: a equipe demora a ser definida, a meta fica no papel e
  o centro é adiado, o Copom para de cortar a Selic.
- **Pessimista, crise de confiança fiscal**: a meta reduzida ou uma PEC de gastos,
  interferência na Petrobras ou nos bancos públicos, contestação que se arrasta e o Copom
  obrigado a voltar a subir os juros.

Até a posse, os três cenários ficam próximos: a separação aparece nos 100 dias e no
primeiro ano. No pessimista o Ibovespa quase não cai em pontos porque o real perde valor;
em dólar a bolsa cai de 25% a 31%. Nos juros há um caso só no otimista e no pessimista (o
histórico do Tesouro começa em dezembro de 2004), então esses números valem menos que os de
bolsa e dólar. Não há chance em %: com 9 eleições, um número seria chute. E o mundo está
parado nas contas: um ano de bolsas emergentes em queda, ou um novo choque do petróleo (o
conflito no Golfo fechou o Estreito de Ormuz em fevereiro), soma por cima.

### O que acompanhar

- O nome do ministro da Fazenda e o envio da lei ou PEC do centro da meta.
- O Copom de 4 de novembro e o de dezembro, e as expectativas de inflação no boletim Focus.
- O pedido de cassação da chapa no TSE.
- A política de preços da Petrobras e o uso dos bancos públicos.
<!-- analise:fim -->

## Comandos

Na pasta do projeto, com [uv](https://docs.astral.sh/uv/):

```
uv run eleicoes extrair      # séries de mercado (BCB, Ipeadata, Yahoo, MSCI, Tesouro)
uv run eleicoes conferir     # confere os dados com números da imprensa
uv run eleicoes janelas      # 11 janelas por eleição, bruto e só Brasil, e a surpresa
uv run eleicoes liquidez     # as 60 empresas mais negociadas antes de cada eleição (COTAHIST)
uv run eleicoes carteiras    # estatais, privadas e setores
uv run eleicoes cenarios     # faixas dos três cenários (premissas/cenarios.yaml)
uv run eleicoes pagina       # site/index.html
uv run eleicoes planilha     # saida/eleicoes_mercado.xlsx
```

Testes: `uv run ruff format --check && uv run ruff check && uv run pytest -q`.

## Aviso

Não é recomendação de investimento. É uma análise com dados públicos (B3, Banco Central,
Tesouro, Ipeadata, MSCI, Yahoo, TSE e institutos de pesquisa) e simulações com dados reais e
projetados.
