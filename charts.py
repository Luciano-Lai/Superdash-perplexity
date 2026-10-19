import math
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from kpis import occurrence_frame

BLUE = "#245A81"
COLORS = {"Preventiva": "#31889A", "Corretiva": "#D58246"}


def style(fig, title, height=400):
    fig.update_layout(template="plotly_white", title=dict(text=title, font=dict(size=17)),
                      height=height, paper_bgcolor="white", plot_bgcolor="white",
                      font=dict(family="Arial", color="#172B4D", size=12),
                      margin=dict(l=20, r=45, t=70, b=45),
                      legend=dict(orientation="h", y=-0.22), separators=",.")
    return fig


def integer_axis(maximum):
    maximum = max(1, int(maximum))
    step = max(1, math.ceil(maximum / 6))
    ceiling = math.ceil(maximum / step) * step
    return dict(range=[0, ceiling], tick0=0, dtick=step, tickformat="d", zeroline=False)


def render_evolution_chart(df, granularity="Diária", chart_type="Barras", period=None):
    data = df.loc[df["Data da tarefa"].notna()].copy()
    freq = {"Diária": "D", "Semanal": "W-SUN", "Mensal": "M"}[granularity]
    dates = data["Data da tarefa"].dt.to_period(freq)
    start = pd.Timestamp(period[0]) if period else data["Data da tarefa"].min()
    end = pd.Timestamp(period[1]) if period else data["Data da tarefa"].max()
    periods = pd.period_range(start, end, freq=freq)
    table = pd.crosstab(dates, data["Tipo"]).reindex(periods, fill_value=0)
    totals = table.sum(axis=1)
    x = periods.start_time
    fig = go.Figure()
    if chart_type == "Barras + linha acumulada":
        accumulated = totals.cumsum()
        fig.add_bar(x=x, y=totals, name="Tarefas no período", marker_color=BLUE)
        fig.add_scatter(x=x, y=accumulated, name="Acumulado", mode="lines+markers",
                        yaxis="y2", line=dict(color="#D58246", width=3))
        fig.update_layout(yaxis=dict(title="Tarefas no período", **integer_axis(totals.max())),
                          yaxis2=dict(title="Acumulado de tarefas", overlaying="y", side="right",
                                      showgrid=False, **integer_axis(accumulated.max())))
    else:
        for kind in table.columns:
            if chart_type == "Linha":
                fig.add_scatter(x=x, y=table[kind], name=kind, mode="lines+markers", line=dict(color=COLORS.get(kind, BLUE)))
            else:
                fig.add_bar(x=x, y=table[kind], name=kind, marker_color=COLORS.get(kind, BLUE))
        fig.update_layout(barmode="group", yaxis=dict(title="Tarefas", **integer_axis(table.max().max())))
    fig.update_traces(hovertemplate="%{x|%d/%m/%Y}<br>%{y:.0f} tarefas<extra>%{fullData.name}</extra>")
    fig.update_xaxes(title=None, tickformat="%d/%m/%Y")
    return style(fig, "Evolução das manutenções", 420)


def category_counts(df, column):
    if column in {"Problema", "Peça"}:
        df = occurrence_frame(df, column)
    values = df[column].fillna("").astype(str).str.strip()
    return values.loc[values.ne("")].value_counts()


def render_horizontal_ranking(df, column, title, top_n=10):
    counts = category_counts(df, column).head(top_n)
    fig = go.Figure(go.Bar(x=counts.values, y=counts.index, orientation="h", text=counts.values,
                           textposition="outside", cliponaxis=False, marker_color=BLUE,
                           hovertemplate="%{y}<br>%{x:.0f} ocorrências<extra></extra>"))
    fig.update_yaxes(autorange="reversed", automargin=True)
    fig.update_xaxes(visible=False, range=[0, max(1, counts.max() if len(counts) else 1) * 1.2])
    return style(fig, title, max(340, len(counts) * 34 + 110))


def render_donut_chart(df, column, title, top_n=10, show_others=True):
    counts = category_counts(df, column)
    top = counts.head(top_n).copy()
    if show_others and len(counts) > top_n:
        top.loc["Outras"] = counts.iloc[top_n:].sum()
    palette = px.colors.qualitative.Safe
    colors = ["#CBD5E1" if label == "Outras" else palette[i % len(palette)] for i, label in enumerate(top.index)]
    fig = go.Figure(go.Pie(labels=top.index, values=top.values, hole=.65, sort=False,
                           marker=dict(colors=colors), textinfo="percent",
                           hovertemplate="%{label}<br>%{value:.0f} ocorrências<br>%{percent}<extra></extra>"))
    fig.add_annotation(text=f"{int(top.sum())}<br>ocorrências", showarrow=False)
    return style(fig, title)


def render_cut_donut(universe, cut):
    total, selected = len(universe), len(cut)
    if selected > total or not set(cut.index).issubset(set(universe.index)):
        raise ValueError("O recorte precisa estar contido no universo.")
    fig = go.Figure(go.Pie(labels=["Recorte selecionado", "Restante do universo"],
                           values=[selected, total-selected], hole=.68, sort=False,
                           marker=dict(colors=[BLUE, "#DCE4EC"]), textinfo="label+percent"))
    pct = selected / total * 100 if total else 0
    fig.add_annotation(text=f"{pct:.1f}%<br>{selected} de {total} tarefas".replace(".", ","), showarrow=False)
    return style(fig, "Participação do recorte no universo")
