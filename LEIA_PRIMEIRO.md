# Entrega 1 — navegação e detalhamento

Este é um pacote de atualização da revisão integrada anterior, não um aplicativo autônomo.

## Base necessária
Mantenha os seguintes arquivos DO ZIP DA REVISÃO INTEGRADA ANTERIOR:
- data_loader.py (fornece Nome da máquina, Rótulo da máquina e Seleção da máquina)
- filters.py (retorna quatro itens, incluindo spec; contém apply_filters e COLUMNS)
- kpis.py (calculate_kpis e render_kpi_cards)
- charts.py (inclui render_cut_donut e evolução com parâmetro period)
- pdf_export.py (aceita charts_per_page)
- packages.txt (chromium)
NÃO use as versões antigas dos trechos do início da conversa: as assinaturas são diferentes.

## Arquivos desta atualização
Substitua app.py e requirements.txt; adicione ui.py e a pasta views inteira.
Mantenha .streamlit/config.toml na pasta .streamlit.
O app de entrada do Cloud continua sendo app.py, na mesma pasta da base anterior.
Não coloque estes arquivos dentro de uma subpasta extra sem ajustar o ponto de entrada.

## Comportamento
- Cinco páginas reais via st.navigation(position='top').
- Filtros comuns são executados no app.py, preservando widgets entre páginas.
- Seleções locais usam cópias de estado persistentes para sobreviver à remoção de widgets de outras páginas.
- Top N global compartilhado; ajustes individuais separados por visual/página.
- Sem KPIs/gráficos selecionados inicialmente.
- Corretivas restringe a base local, sem mudar silenciosamente o filtro global.
- Técnicos/Qualidade/Garantia avançada não aparecem no menu.
- Funções das roscas não foram substituídas.
- Detalhamento: corte antes de Código do patrimônio, preservando Garantia.
- Se esse cabeçalho não for reconhecido, lista conservadora de colunas essenciais e aviso explícito.
- Remove auxiliares Rótulo da máquina/Seleção da máquina da exibição.
- Paginação retorna a 1 quando o recorte, página de análise ou tamanho muda.
- Exportação continua com escolha entre figuras renderizadas na página ativa; não exporta análises invisíveis.

## Ainda fora desta entrega
Comparação A/B, todos os universos originalmente planejados, matriz integral KPI/gráfico, autenticação.
A regra histórica de garantia continua pendente. O link e o CSV publicado não são protegidos por este código.
Layout e comportamento precisam ser conferidos no Cloud. Não foi feito teste de navegação em navegador.

## Testes após deploy
1. Menu superior com as cinco páginas mesmo antes de aplicar filtros.
2. Aplicar período e máquina; navegar em todas as páginas: os filtros não devem desaparecer.
3. Escolher KPIs/gráficos em Monitoramento, ir a Máquinas e voltar: seleção preservada.
4. Em Máquinas, escolher outros KPIs: não deve alterar os do Monitoramento.
5. Alterar Top N global e navegar; um Top N individual deve permanecer independente.
6. Abrir Corretivas com filtro Preventiva: resultado vazio com mensagem, sem trocar o filtro por conta própria.
7. Conferir roscas e acumulado como antes.
8. Conferir corte na coluna patrimonial e Garantia preservada.
9. Ir à segunda página da tabela, mudar filtro: volta à primeira página.
10. Exportar PDF de KPIs e depois gráficos; verificar Chromium nos logs.

Validação local desta entrega: sintaxe dos novos arquivos, resolução de módulos/páginas e testes da função de seleção de colunas. Não é validação de integração no Cloud.
