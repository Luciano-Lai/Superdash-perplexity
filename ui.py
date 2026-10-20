import hashlib
import math
import unicodedata
import streamlit as st

from charts import (render_evolution_chart, render_horizontal_ranking, render_donut_chart,
                    render_cut_donut, render_pareto_chart, render_abc_donut, abc_table,
                    category_counts)
from filters import apply_filters, COLUMNS
from kpis import calculate_kpis, render_kpi_cards, occurrence_frame
from pdf_export import generate_pdf_report
from comparison import comparison_base, split_machines, comparison_evolution, comparison_bars, comparison_share, comparison_occurrences


def apply_theme():
    st.markdown("""<style>
.block-container{max-width:1550px;padding-top:2rem;padding-bottom:3rem}
.kpi-card{background:var(--secondary-background-color,#fff);border:1px solid #DCE4EC;border-radius:12px;padding:18px;min-height:145px;box-sizing:border-box;margin-bottom:14px}
.kpi-label{font-size:.83rem;opacity:.8;margin-bottom:12px}
.kpi-value{font-weight:650;line-height:1.25;overflow-wrap:anywhere}
</style>""", unsafe_allow_html=True)


def widget(kind,label,key,**kwargs):
    saved=key+"_saved"
    if saved in st.session_state:
        value=st.session_state[saved]
        options=kwargs.get("options")
        if options is not None:
            if kind=="multiselect":
                value=[v for v in value if v in options]
            elif len(options) and value not in options:
                value=options[0]
        st.session_state[key]=value
        kwargs.pop("default",None)
        kwargs.pop("value",None)
    def save():
        st.session_state[saved]=st.session_state[key]
    result=getattr(st,kind)(label,key=key,on_change=save,**kwargs)
    st.session_state[saved]=result
    return result


def context(page_id,title,subtitle,corrective=False):
    st.title(title)
    st.caption(subtitle)
    ctx=st.session_state.get("_page_context")
    if ctx is None:
        st.error("Abra o aplicativo pelo app.py da revisão com menu superior.")
        return None
    if not ctx["valid"] or not ctx["additional"]:
        st.info("Selecione o período e pelo menos um filtro adicional na barra lateral.")
        return None
    data=ctx["cut"].copy()
    if corrective:
        data=data.loc[data["Tipo"].eq("Corretiva")].copy()
    if data.empty and page_id!="maquinas":
        st.info("Nenhum registro encontrado neste recorte.")
        return None
    spec=ctx["spec"]
    start,end=spec["period"]
    st.caption(f"{start:%d/%m/%Y} a {end:%d/%m/%Y} • {len(data)} tarefas no recorte global")
    labels=dict(zip(ctx["raw"]["Máquina"],ctx["raw"]["Seleção da máquina"]))
    active=[]
    for col in ["Tipo"]+list(COLUMNS):
        selected=spec.get(col)
        if not selected or (isinstance(selected,str) and selected=="Todas"):
            continue
        if isinstance(selected,str):
            text=selected
        else:
            text=", ".join(labels.get(v,v) if col=="Máquina" else str(v) for v in selected)
        active.append(col+": "+text)
    if active: st.caption(" | ".join(active))
    return {"id":page_id,"raw":ctx["raw"],"spec":spec,"df":data,"figures":{},"associations":{},"key":"dash_"+page_id+"_"}


def registry(c,name,fig,kpis):
    if fig is None:
        st.info("Sem ocorrências válidas para esta análise.")
        return
    c["figures"][name]=fig
    c["associations"][name]=set(kpis)
    st.plotly_chart(fig,use_container_width=True)


def configuration(c,kpi_options,chart_options):
    values=calculate_kpis(c["df"])
    with st.expander("Indicadores, análises e PDF",expanded=True):
        selected_kpis=widget("multiselect","Indicadores desta página",c["key"]+"kpis",options=[k for k in kpi_options if k in values],default=[])
        selected=widget("multiselect","Análises desta página",c["key"]+"analyses",options=chart_options,default=[],disabled=not selected_kpis)
        left,right=st.columns(2)
        if left.button("Selecionar todas as análises",key=c["key"]+"all",disabled=not selected_kpis):
            st.session_state[c["key"]+"analyses_saved"]=list(chart_options)
            st.rerun()
        if right.button("Limpar análises",key=c["key"]+"none"):
            st.session_state[c["key"]+"analyses_saved"]=[]
            st.rerun()
        top=widget("number_input","Top N padrão global","dash_global_top",min_value=1,max_value=100,value=10)
        export_slot=st.container()
    c.update(values=values,kpis=selected_kpis,selected=selected if selected_kpis else [],top=top,export_slot=export_slot)
    if selected_kpis:
        st.subheader("Indicadores do recorte")
        render_kpi_cards(selected_kpis,values)
    else:
        st.info("Selecione indicadores para habilitar as análises desta página.")
    if any("garantia" in name.lower() for name in selected_kpis):
        st.warning("Garantia representa a situação atual da data limite. A cobertura histórica da chamada ainda não foi definida.")
    return c


def chart_key(c,name):
    return c["key"]+hashlib.sha1(name.encode()).hexdigest()[:10]


def evolution(c,name="Evolução no período"):
    key=chart_key(c,name)
    left,right=st.columns(2)
    with left:
        gran=widget("selectbox","Agrupamento",key+"gran",options=["Diária","Semanal","Mensal"])
    with right:
        visual=widget("selectbox","Visual",key+"visual",options=["Barras","Linha","Barras + linha acumulada"])
    fig=render_evolution_chart(c["df"],gran,visual,c["spec"]["period"])
    registry(c,name,fig,{"Total de tarefas","Preventivas","Corretivas","% Preventivas","% Corretivas"})


def ranking(c,column,title,associated,kind=None):
    source=c["df"]
    if kind: source=source.loc[source["Tipo"].eq(kind)]
    if column not in source or source.empty:
        st.info("Não há registros para "+title.lower()+".")
        return
    if column in {"Problema","Peça"}:
        valid=occurrence_frame(source,column)
    else:
        valid=source.loc[source[column].fillna("").astype(str).str.strip().ne("")]
    if valid.empty:
        st.info("Não há ocorrências válidas para "+title.lower()+".")
        return
    key=chart_key(c,title)
    st.markdown("### "+title)
    with st.expander("Ajustes — "+title):
        override=widget("checkbox","Definir Top N individual",key+"override",value=False)
        n=widget("number_input","Top N individual",key+"n",min_value=1,max_value=100,value=10) if override else c["top"]
        pair=widget("checkbox","Mostrar distribuição ao lado",key+"pair",value=False)
        others=widget("checkbox","Agrupar restante em Outras",key+"others",value=True)
    fig=render_horizontal_ranking(source,column,title,n)
    if pair:
        left,right=st.columns([1.35,1])
        with left: registry(c,title,fig,associated)
        with right: registry(c,title+" — distribuição",render_donut_chart(source,column,"Distribuição no recorte",n,others),associated)
    else: registry(c,title,fig,associated)


def participation(c):
    key=c["key"]+"universe"
    st.markdown("### Recorte × universo")
    mode=widget("selectbox","Universo de comparação",key,options=["Todas as tarefas no período","Mesmo tipo no período","Personalizado"])
    spec={"period":c["spec"]["period"],"Tipo":"Todas"}
    if mode=="Mesmo tipo no período":
        types=c["df"]["Tipo"].unique()
        spec["Tipo"]=types[0] if len(types)==1 else c["spec"]["Tipo"]
    elif mode=="Personalizado":
        candidates=[col for col in ["Tipo"]+list(COLUMNS) if c["spec"].get(col) and c["spec"].get(col)!="Todas"]
        keep=widget("multiselect","Manter filtros no universo",key+"keep",options=candidates,default=[])
        for col in keep: spec[col]=c["spec"][col]
    universe=apply_filters(c["raw"],spec)
    st.caption(f"{len(c['df'])} tarefas no recorte / {len(universe)} no universo • mesmo período")
    registry(c,"Participação do recorte no universo",render_cut_donut(universe,c["df"]),{"Total de tarefas"})


def composition(c,title):
    registry(c,title,render_donut_chart(c["df"],"Tipo",title,10,True),{"Total de tarefas","Preventivas","Corretivas","% Preventivas","% Corretivas"})


def _filter_column(column):
    return "Máquina" if column=="Rótulo da máquina" else column


def _category_rows(df,column,members):
    if column in {"Problema","Peça"}:
        data=occurrence_frame(df,column)
    else:
        data=df.loc[df[column].fillna("").astype(str).str.strip().ne("")].copy()
    return data.loc[data[column].isin(members)].copy()


def concentration(c,column,title,associated,kind=None,drilldown=()):
    source=c["df"]
    if kind: source=source.loc[source["Tipo"].eq(kind)]
    if column not in source or source.empty:
        st.info("Não há registros para "+title.lower()+".")
        return
    key=chart_key(c,title)
    st.markdown("### "+title)
    with st.expander("Ajustes — "+title):
        base=widget("selectbox","Base da análise",key+"base",
                    options=["Recorte atual","Universo de comparação"])
        override=widget("checkbox","Definir Top N individual",key+"override",value=False)
        n=widget("number_input","Top N individual",key+"n",min_value=1,max_value=100,value=10) if override else c["top"]
        left,right=st.columns(2)
        a=left.number_input("Limite da classe A (%)",min_value=50,max_value=95,value=80,step=1,key=key+"a")
        b=right.number_input("Limite da classe B (%)",min_value=55,max_value=100,value=95,step=1,key=key+"b")
        a,b=a/100,b/100
        if b<=a: b=min(1.0,a+0.05)
    analysis=source.copy()
    highlight=None
    if base=="Universo de comparação":
        filter_column="Máquina" if column=="Rótulo da máquina" else column
        universe=apply_filters(c["raw"],c["spec"],ignore=(filter_column,))
        if kind: universe=universe.loc[universe["Tipo"].eq(kind)]
        analysis=universe
        highlight=set(category_counts(source,column).index)
    counts=category_counts(analysis,column)
    if counts.empty:
        st.info("Não há categorias válidas para esta análise.")
        return
    abc=abc_table(counts,a,b)
    pareto=render_pareto_chart(counts,title,n,highlight,a,b)
    donut=render_abc_donut(abc,title+" — classes A, B e C")
    left,right=st.columns([1.55,1])
    with left: registry(c,title,pareto,associated)
    with right: registry(c,title+" — classes",donut,associated)
    total=int(abc["Quantidade"].sum())
    st.caption(f"Base da ABC: {base.lower()} • {len(abc)} categorias • {total:,} {('tarefas' if column not in {'Problema','Peça'} else 'ocorrências').replace(',', '.')}".replace(",", "."))
    summary=abc.groupby("Classe",as_index=False).agg(Categorias=("Categoria","nunique"),Volume=("Quantidade","sum"))
    summary=summary.set_index("Classe").reindex(["A","B","C"]).fillna(0)
    columns=st.columns(3)
    for slot,letter in zip(columns,["A","B","C"]):
        with slot:
            volume=int(summary.loc[letter,"Volume"])
            items=int(summary.loc[letter,"Categorias"])
            share=volume/total*100 if total else 0
            st.metric("Classe "+letter,f"{volume:,}".replace(",","."),
                      f"{items} categoria(s) • {share:.1f}%")
    available=[letter for letter in ["A","B","C"] if int(summary.loc[letter,"Categorias"])>0]
    if not drilldown or not available:
        return
    st.markdown("#### Detalhar uma classe")
    selected=widget("selectbox","Classe para detalhar",key+"class",options=available,
                    format_func=lambda letter:"Classe "+letter)
    members=abc.loc[abc["Classe"].eq(selected),"Categoria"].tolist()
    subset=_category_source= _category_rows(analysis,column,members)
    if subset.empty:
        st.info("Não há registros na classe selecionada.")
        return
    st.caption(f"Classe {selected}: {len(members)} categoria(s) • {len(subset):,} registro(s) relacionados.".replace(",", "."))
    breakdown=widget("selectbox","Analisar a classe por",key+"breakdown",
                     options=[item for item in drilldown if item in subset.columns])
    if not breakdown:
        return
    inner_counts=category_counts(subset,breakdown)
    if inner_counts.empty:
        st.info("Não há ocorrências válidas para este detalhamento.")
        return
    inner_title=(f"Classe {selected} — {breakdown.lower()}")
    inner=render_pareto_chart(inner_counts,inner_title,c["top"],None,a,b)
    registry(c,inner_title,inner,{"Corretivas"} if kind=="Corretiva" else {"Total de tarefas"})


def norm_header(value):
    text=unicodedata.normalize("NFKD",str(value).strip().lower())
    return " ".join("".join(ch for ch in text if not unicodedata.combining(ch)).split())


def detail_columns(columns):
    markers={"codigo do patrimonio","codigo de patrimonio","codigo patrimonio","cod. patrimonio","cod patrimonio"}
    cutoff=next((i for i,col in enumerate(columns) if norm_header(col) in markers),None)
    if cutoff is not None:
        shown=[col for col in columns[:cutoff] if col not in {"Rótulo da máquina","Seleção da máquina"}]
    else:
        preferred=["Data da tarefa","Nome da máquina","Máquina","Tipo","Técnico","Cliente","Cidade","Região","Estado","Problema","Tarefa","Peça","Observações"]
        shown=[col for col in preferred if col in columns]
    if "Garantia" in columns and "Garantia" not in shown: shown.append("Garantia")
    return shown,cutoff is not None


def details(c):
    with st.expander("Detalhamento dos registros",expanded=False):
        data=c["df"]
        shown,found=detail_columns(list(data.columns))
        if not found: st.caption("Cabeçalho patrimonial não localizado; exibindo somente as colunas essenciais.")
        prefix=c["key"]+"detail"
        size=st.selectbox("Registros por página",[15,25,50,100],key=prefix+"size")
        signature=hashlib.sha1((repr(c["spec"])+repr(data.index.tolist())+str(size)).encode()).hexdigest()
        pages=max(1,math.ceil(len(data)/size))
        if st.session_state.get(prefix+"signature")!=signature:
            st.session_state[prefix+"page"]=1
            st.session_state[prefix+"signature"]=signature
        if not 1<=st.session_state.get(prefix+"page",1)<=pages: st.session_state[prefix+"page"]=1
        page=int(st.number_input("Página",min_value=1,max_value=pages,step=1,key=prefix+"page"))
        ordered=data.sort_values("Data da tarefa",ascending=False)
        st.caption(f"{len(data)} registros • página {page} de {pages}")
        st.dataframe(ordered.iloc[(page-1)*size:page*size][shown],hide_index=True,use_container_width=True)


def finish(c):
    with c["export_slot"]:
        st.markdown("#### Exportação PDF")
        key=c["key"]+"pdf"
        names=widget("multiselect","Gráficos para o PDF",key+"charts",options=list(c["figures"]),default=[])
        allowed=set(c["values"]) if not names else set().union(*(c["associations"][name] for name in names))
        selected=widget("multiselect","Indicadores para o PDF",key+"kpis",options=[k for k in c["values"] if k in allowed],default=[])
        st.caption("Sem gráficos, escolha livre de indicadores. Com gráficos, somente os associados. Na comparação, os cartões PDF são os do recorte A + B; os gráficos identificam A e B.")
        count=widget("selectbox","Gráficos por página",key+"count",options=[1,2,3,4])
        if st.button("Gerar PDF",key=key+"generate",disabled=not(names or selected)):
            try:
                pdf=generate_pdf_report(c["values"],selected,{n:c["figures"][n] for n in names},count)
                st.download_button("Baixar PDF",pdf,"painel_"+c["id"]+".pdf","application/pdf",key=key+"download")
            except Exception as error:
                st.error("Não foi possível gerar o PDF. Confira Kaleido e Chromium no servidor.")
                st.code(str(error))
    details(c)


def render_monitoramento():
    c=context("monitoramento","Monitoramento","Como está a operação? Visão consolidada de volume, composição e concentração de corretivas.")
    if c is None: return
    configuration(c,["Total de tarefas","Preventivas","Corretivas","% Preventivas","% Corretivas","Máquinas atendidas","Técnicos envolvidos"],
                  ["Evolução da operação","Composição das manutenções","Equipamentos com mais corretivas","Concentração de corretivas por equipamento","Recorte × universo"])
    if "Evolução da operação" in c["selected"]:
        st.subheader("Ritmo da operação")
        evolution(c,"Evolução da operação")
    left,right=st.columns([1,1.4])
    with left:
        if "Composição das manutenções" in c["selected"]: composition(c,"Preventivas × corretivas")
    with right:
        if "Equipamentos com mais corretivas" in c["selected"]: ranking(c,"Rótulo da máquina","Equipamentos com mais corretivas",{"Corretivas","Máquinas atendidas"},"Corretiva")
    if "Concentração de corretivas por equipamento" in c["selected"]:
        concentration(c,"Rótulo da máquina","Concentração de corretivas por equipamento",
                      {"Corretivas","Máquinas atendidas"},"Corretiva",
                      ["Problema","Peça","Tarefa"])
    if "Recorte × universo" in c["selected"]: participation(c)
    finish(c)


def render_analise_tarefas():
    c=context("analise_tarefas","Análise de tarefas","O que foi feito? Serviços executados, responsáveis e volume ao longo do período.")
    if c is None: return
    configuration(c,["Total de tarefas","Preventivas","Corretivas","% Preventivas","% Corretivas","Técnicos envolvidos","Máquinas atendidas"],
                  ["Serviços executados","Ritmo dos atendimentos","Distribuição por responsável","Distribuição por equipamento","Concentração de tarefas por equipamento","Concentração de tarefas por responsável"])
    if "Serviços executados" in c["selected"]: ranking(c,"Tarefa","Serviços executados",{"Total de tarefas","Preventivas","Corretivas"})
    if "Ritmo dos atendimentos" in c["selected"]: evolution(c,"Ritmo dos atendimentos")
    left,right=st.columns(2)
    with left:
        if "Distribuição por responsável" in c["selected"]: ranking(c,"Técnico","Tarefas por responsável",{"Total de tarefas","Técnicos envolvidos"})
    with right:
        if "Distribuição por equipamento" in c["selected"]: ranking(c,"Rótulo da máquina","Tarefas por equipamento",{"Total de tarefas","Máquinas atendidas"})
    if "Concentração de tarefas por equipamento" in c["selected"]:
        concentration(c,"Rótulo da máquina","Concentração de tarefas por equipamento",
                      {"Total de tarefas","Máquinas atendidas"},None,
                      ["Tarefa","Técnico"])
    if "Concentração de tarefas por responsável" in c["selected"]:
        concentration(c,"Técnico","Concentração de tarefas por responsável",
                      {"Total de tarefas","Técnicos envolvidos"},None,
                      ["Rótulo da máquina","Tarefa"])
    finish(c)


def render_corretivas():
    c=context("corretivas","Corretivas","Quais falhas ocorreram e como foram tratadas? Apenas tarefas corretivas entram nesta página.",True)
    if c is None: return
    configuration(c,["Corretivas","Máquinas atendidas","Técnicos envolvidos","Problema mais frequente","Peça mais trocada","Corretivas em garantia","Corretivas fora da garantia"],
                  ["Falhas relatadas","Peças utilizadas","Serviços corretivos","Equipamentos envolvidos","Concentração de falhas por equipamento","Concentração de falhas por problema","Concentração de peças por equipamento","Evolução das corretivas"])
    left,right=st.columns(2)
    with left:
        if "Falhas relatadas" in c["selected"]: ranking(c,"Problema","Falhas relatadas",{"Corretivas","Problema mais frequente"})
    with right:
        if "Peças utilizadas" in c["selected"]: ranking(c,"Peça","Peças utilizadas",{"Corretivas","Peça mais trocada"})
    if "Serviços corretivos" in c["selected"]: ranking(c,"Tarefa","Serviços corretivos",{"Corretivas"})
    if "Equipamentos envolvidos" in c["selected"]: ranking(c,"Rótulo da máquina","Equipamentos envolvidos em corretivas",{"Corretivas","Máquinas atendidas"})
    if "Concentração de falhas por equipamento" in c["selected"]:
        concentration(c,"Rótulo da máquina","Concentração de falhas por equipamento",
                      {"Corretivas","Máquinas atendidas"},"Corretiva",
                      ["Problema","Peça","Tarefa"])
    if "Concentração de falhas por problema" in c["selected"]:
        concentration(c,"Problema","Concentração de falhas por problema",
                      {"Corretivas","Problema mais frequente"},"Corretiva",
                      ["Rótulo da máquina","Peça","Tarefa"])
    if "Concentração de peças por equipamento" in c["selected"]:
        concentration(c,"Peça","Concentração de peças por equipamento",
                      {"Corretivas","Peça mais trocada"},"Corretiva",
                      ["Rótulo da máquina","Problema","Tarefa"])
    if "Evolução das corretivas" in c["selected"]: evolution(c,"Evolução das corretivas")
    missing=c["df"]["Problema"].fillna("").astype(str).str.strip().isin(["","Não informado","Nao informado"])
    if missing.any(): st.warning(f"{int(missing.sum())} corretiva(s) sem problema válido preenchido. Não entram no ranking de falhas.")
    finish(c)


def render_clientes_regioes():
    c=context("clientes_regioes","Clientes e regiões","Onde os atendimentos se concentram? Cliente, localização e composição das manutenções.")
    if c is None: return
    available_columns=[col for col in ["Cliente","Estado","Região","Cidade"] if c["df"][col].fillna("").astype(str).str.strip().ne("").any()]
    if not available_columns:
        st.info("A fonte não possui cliente ou localização preenchidos neste recorte. Não serão criadas categorias artificiais.")
    with st.expander("Refinar cliente e localização nesta página",expanded=False):
        for col in available_columns:
            options=sorted(c["df"][col].dropna().loc[lambda s:s.astype(str).str.strip().ne("")].unique())
            chosen=widget("multiselect",col+" nesta página",c["key"]+"local_"+col,options=options,default=[])
            if chosen: c["df"]=c["df"].loc[c["df"][col].isin(chosen)]
    if c["df"].empty:
        st.info("Nenhum atendimento corresponde ao refinamento local.")
        return
    dims=[col for col in available_columns if c["df"][col].fillna("").astype(str).str.strip().ne("").any()]
    options=["Distribuição por "+col.lower() for col in dims]
    options+=["Concentração por "+col.lower() for col in dims]
    options+=["Composição local","Participação no universo"]
    configuration(c,["Total de tarefas","Máquinas atendidas","Preventivas","Corretivas","% Corretivas"],options)
    for i in range(0,len(dims),2):
        cols=st.columns(2)
        for slot,col in zip(cols,dims[i:i+2]):
            with slot:
                if "Distribuição por "+col.lower() in c["selected"]: ranking(c,col,"Atendimentos por "+col.lower(),{"Total de tarefas","Máquinas atendidas"})
    for col in dims:
        if "Concentração por "+col.lower() in c["selected"]:
            concentration(c,col,"Concentração por "+col.lower(),
                          {"Total de tarefas","Máquinas atendidas"},None,
                          ["Rótulo da máquina","Tarefa"])
    if "Composição local" in c["selected"]: composition(c,"Composição das manutenções no recorte local")
    if "Participação no universo" in c["selected"]: participation(c)
    finish(c)


def render_maquinas():
    c=context("maquinas","Máquinas","Qual equipamento exige atenção? Explore uma máquina ou compare duas sob os mesmos filtros de contexto.")
    if c is None: return
    base=comparison_base(c["raw"],c["spec"])
    if base.empty:
        st.info("Nenhuma máquina com tarefas neste contexto.")
        return
    st.caption("Seleções abaixo substituem apenas o filtro de máquina da lateral nesta página. Período, tipo, técnico, cliente e localização continuam aplicados.")
    labels=dict(zip(c["raw"]["Máquina"],c["raw"]["Seleção da máquina"]))
    codes=sorted(base["Máquina"].unique())
    mode=widget("radio","Modo de análise",c["key"]+"mode",options=["Uma máquina","Comparar A × B"],horizontal=True)
    choices=[None]+codes
    label_func=lambda code: "Selecione uma máquina" if code is None else labels.get(code,code)
    code_a=widget("selectbox","Máquina A" if mode=="Comparar A × B" else "Equipamento",c["key"]+"machine_a",options=choices,format_func=label_func)
    if code_a is None:
        st.info("Escolha o equipamento para iniciar a análise.")
        return
    a=base.loc[base["Máquina"].eq(code_a)].copy()
    if mode=="Uma máquina":
        c["df"]=a
        st.subheader(labels[code_a])
        configuration(c,["Total de tarefas","Preventivas","Corretivas","% Corretivas","Problema mais frequente","Peça mais trocada"],
                      ["Histórico do equipamento","Composição do equipamento","Problemas do equipamento","Peças do equipamento","Serviços no equipamento"])
        if "Histórico do equipamento" in c["selected"]: evolution(c,"Histórico do equipamento")
        if "Composição do equipamento" in c["selected"]: composition(c,"Composição do equipamento")
        left,right=st.columns(2)
        with left:
            if "Problemas do equipamento" in c["selected"]: ranking(c,"Problema","Problemas do equipamento",{"Corretivas","Problema mais frequente"})
        with right:
            if "Peças do equipamento" in c["selected"]: ranking(c,"Peça","Peças do equipamento",{"Corretivas","Peça mais trocada"})
        if "Serviços no equipamento" in c["selected"]: ranking(c,"Tarefa","Serviços no equipamento",{"Total de tarefas"})
    else:
        code_b=widget("selectbox","Máquina B",c["key"]+"machine_b",options=[None]+[v for v in codes if v!=code_a],format_func=label_func)
        if code_b is None:
            st.info("Escolha uma segunda máquina diferente da primeira.")
            return
        a,b=split_machines(base,code_a,code_b)
        c["df"]=base.loc[base["Máquina"].isin([code_a,code_b])].copy()
        la,lb=labels[code_a],labels[code_b]
        configuration(c,["Total de tarefas","Preventivas","Corretivas","% Corretivas","Máquinas atendidas","Problema mais frequente","Peça mais trocada"],
                      ["Volume A × B","Evolução A × B","Participação A × B","Problemas A × B","Peças A × B"])
        if c["kpis"]:
            st.subheader("Indicadores individuais — mesmos filtros de contexto")
            left,right=st.columns(2)
            for slot,data,label in [(left,a,la),(right,b,lb)]:
                with slot:
                    st.markdown("#### "+label)
                    stats=calculate_kpis(data)
                    for name in c["kpis"]: st.metric(name,stats[name])
        associated={"Total de tarefas","Preventivas","Corretivas","% Corretivas","Máquinas atendidas"}
        if "Volume A × B" in c["selected"]: registry(c,"Volume A × B",comparison_bars(a,b,la,lb),associated)
        if "Evolução A × B" in c["selected"]:
            gran=widget("selectbox","Agrupamento da comparação",c["key"]+"compare_gran",options=["Diária","Semanal","Mensal"])
            registry(c,"Evolução A × B",comparison_evolution(a,b,la,lb,c["spec"]["period"],gran),associated)
        if "Participação A × B" in c["selected"]: registry(c,"Participação A × B",comparison_share(a,b,la,lb),associated)
        for name,column in [("Problemas A × B","Problema"),("Peças A × B","Peça")]:
            if name in c["selected"]:
                key=chart_key(c,name)
                with st.expander("Top N — "+name):
                    own=widget("checkbox","Usar Top N individual",key+"own",value=False)
                    n=widget("number_input","Top N individual",key+"n",min_value=1,max_value=100,value=10) if own else c["top"]
                registry(c,name,comparison_occurrences(a,b,column,la,lb,n),{"Corretivas","Problema mais frequente" if column=="Problema" else "Peça mais trocada"})
    finish(c)
