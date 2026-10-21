import pandas as pd
import plotly.graph_objects as go
from filters import apply_filters
from charts import integer_axis, style, category_counts, configure_category_axis, revise_bar_labels

COLORS = ["#245A81", "#D58246"]


def comparison_base(raw, spec):
    return apply_filters(raw, spec, ignore=("Máquina",))


def split_machines(base, code_a, code_b):
    if code_a == code_b:
        raise ValueError("Escolha duas máquinas diferentes.")
    return base.loc[base["Máquina"].eq(code_a)].copy(), base.loc[base["Máquina"].eq(code_b)].copy()


def comparison_evolution(a, b, label_a, label_b, period, granularity="Mensal"):
    frequency = {"Diária": "D", "Semanal": "W-SUN", "Mensal": "M"}[granularity]
    periods = pd.period_range(period[0], period[1], freq=frequency)
    fig, maximum = go.Figure(), 0
    for data, label, color in zip([a, b], [label_a, label_b], COLORS):
        valid = data.loc[data["Data da tarefa"].notna()]
        counts = valid.groupby(valid["Data da tarefa"].dt.to_period(frequency)).size().reindex(periods, fill_value=0)
        maximum = max(maximum, int(counts.max()) if len(counts) else 0)
        fig.add_scatter(x=periods.start_time, y=counts.values, name=str(label), mode="lines+markers",
                       line=dict(color=color, width=3))
    fig.update_layout(yaxis=dict(title="Tarefas", **integer_axis(maximum)))
    fig.update_traces(hovertemplate="%{x|%d/%m/%Y}<br>%{y:.0f} tarefas<extra>%{fullData.name}</extra>")
    fig.update_xaxes(tickformat="%d/%m/%Y", title=None)
    return style(fig, "Evolução comparativa", 500)


def comparison_bars(a, b, label_a, label_b):
    categories = ["Total de tarefas", "Preventivas", "Corretivas"]
    fig, maximum = go.Figure(), 0
    for data, label, color in zip([a, b], [label_a, label_b], COLORS):
        counts = [len(data), int(data["Tipo"].eq("Preventiva").sum()), int(data["Tipo"].eq("Corretiva").sum())]
        maximum = max(maximum, max(counts))
        fig.add_bar(x=categories, y=counts, name=str(label), marker_color=color,
                    text=counts, textposition="outside", cliponaxis=False,
                    hovertemplate="%{x}<br>%{y:.0f} tarefas<extra>%{fullData.name}</extra>")
    fig.update_layout(barmode="group", bargap=0.25,
                      yaxis=dict(title="Tarefas", **integer_axis(maximum * 1.22)))
    return revise_bar_labels(style(fig, "Volume de manutenção — A × B", 540))


def comparison_share(a, b, label_a, label_b):
    total = len(a) + len(b)
    if total == 0:
        return None
    fig = go.Figure(go.Pie(labels=[str(label_a), str(label_b)], values=[len(a), len(b)],
        hole=0.65, sort=False, marker=dict(colors=COLORS, line=dict(color="white", width=1)),
        textinfo="percent", textposition="inside", texttemplate="%{percent:.2%}",
        hovertemplate="%{label}<br>%{value:.0f} tarefas<br>%{percent:.2%}<extra></extra>"))
    style(fig, "Participação entre as duas máquinas", 520)
    fig.update_layout(legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.06))
    fig.add_annotation(text=f"{total}<br>tarefas A + B", x=0.5, y=0.5, showarrow=False, font=dict(size=17))
    return fig


def comparison_occurrences(a, b, column, label_a, label_b, top_n):
    ca, cb = category_counts(a, column), category_counts(b, column)
    joined = pd.concat([ca.rename("A"), cb.rename("B")], axis=1).fillna(0).astype(int)
    if joined.empty:
        return None
    joined["Total"] = joined["A"] + joined["B"]
    joined["Categoria"] = joined.index.astype(str)
    ordered = joined.sort_values(["Total", "Categoria"], ascending=[False, True], kind="stable").head(max(1, int(top_n)))
    labels = ordered["Categoria"].tolist()
    fig = go.Figure()
    for key, label, color in zip(["A", "B"], [label_a, label_b], COLORS):
        values = ordered[key].tolist()
        fig.add_bar(x=list(range(len(labels))), y=values, name=str(label), marker_color=color,
            customdata=labels, text=values, textposition="outside", cliponaxis=False,
            hovertemplate="%{customdata}<br>%{y:.0f} ocorrências<extra>%{fullData.name}</extra>")
    maximum = int(ordered[["A", "B"]].max().max())
    style(fig, f"{column} — comparação por ocorrência", 620 if len(labels) <= 10 else (740 if len(labels) <= 20 else 850))
    configure_category_axis(fig, labels)
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08,
        margin=dict(l=110, r=90, t=130, b=220 if len(labels) <= 20 else 250),
        legend=dict(orientation="h", x=0, y=1.13, xanchor="left", yanchor="bottom"),
        yaxis=dict(title="Ocorrências", **integer_axis(maximum * 1.22)))
    return revise_bar_labels(fig)
