import pandas as pd
import plotly.graph_objects as go
from filters import apply_filters
from charts import integer_axis, style, category_counts

COLORS = ["#245A81", "#D58246"]


def comparison_base(raw, spec):
    return apply_filters(raw, spec, ignore=("Máquina",))


def split_machines(base, code_a, code_b):
    if code_a == code_b:
        raise ValueError("Escolha duas máquinas diferentes.")
    return base.loc[base["Máquina"].eq(code_a)].copy(), base.loc[base["Máquina"].eq(code_b)].copy()


def comparison_evolution(a, b, label_a, label_b, period, granularity="Mensal"):
    freq = {"Diária":"D", "Semanal":"W-SUN", "Mensal":"M"}[granularity]
    periods = pd.period_range(period[0], period[1], freq=freq)
    fig = go.Figure()
    maximum = 0
    for data, label, color in zip([a,b], [label_a,label_b], COLORS):
        counts = data.groupby(data["Data da tarefa"].dt.to_period(freq)).size().reindex(periods, fill_value=0)
        maximum = max(maximum, int(counts.max()) if len(counts) else 0)
        fig.add_scatter(x=periods.start_time, y=counts.values, name=label,
                        mode="lines+markers", line=dict(color=color, width=3))
    fig.update_layout(yaxis=integer_axis(maximum))
    fig.update_traces(hovertemplate="%{x|%d/%m/%Y}<br>%{y:.0f} tarefas<extra>%{fullData.name}</extra>")
    return style(fig, "Evolução comparativa", 420)


def comparison_bars(a, b, label_a, label_b):
    categories = ["Total de tarefas", "Preventivas", "Corretivas"]
    fig = go.Figure()
    maximum = 0
    for data, label, color in zip([a,b], [label_a,label_b], COLORS):
        counts = [len(data), int(data["Tipo"].eq("Preventiva").sum()), int(data["Tipo"].eq("Corretiva").sum())]
        maximum = max(maximum, *counts)
        fig.add_bar(x=categories, y=counts, name=label, marker_color=color, text=counts, textposition="auto")
    fig.update_layout(barmode="group", yaxis=integer_axis(maximum))
    return style(fig, "Volume de manutenção — A × B")


def comparison_share(a, b, label_a, label_b):
    fig = go.Figure(go.Pie(labels=[label_a,label_b], values=[len(a),len(b)], hole=.65,
                           sort=False, marker=dict(colors=COLORS), textinfo="percent+label"))
    fig.add_annotation(text=f"{len(a)+len(b)}<br>tarefas A + B", showarrow=False)
    return style(fig, "Participação entre as duas máquinas")


def comparison_occurrences(a, b, column, label_a, label_b, top_n):
    ca, cb = category_counts(a,column), category_counts(b,column)
    joined = pd.concat([ca.rename("A"), cb.rename("B")],axis=1).fillna(0).astype(int)
    if joined.empty:
        return None
    categories = joined.sum(axis=1).sort_values(ascending=False).head(top_n).index
    fig = go.Figure()
    for key,label,color in zip(["A","B"],[label_a,label_b],COLORS):
        fig.add_bar(y=categories, x=joined.loc[categories,key], name=label, orientation="h",marker_color=color)
    fig.update_layout(barmode="group")
    fig.update_yaxes(autorange="reversed",automargin=True)
    fig.update_xaxes(tickformat="d", rangemode="tozero")
    return style(fig, f"{column} — comparação por ocorrência", max(360, 38*len(categories)+130))
