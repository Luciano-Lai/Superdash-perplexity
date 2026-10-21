import math
from html import escape
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from kpis import occurrence_frame

BLUE = "#245A81"
COLORS = {"Preventiva": "#31889A", "Corretiva": "#D58246"}
ABC_COLORS = {"A": "#245A81", "B": "#D58246", "C": "#9AA7B4"}


def style(fig, title, height=400):
    fig.update_layout(template="plotly_white", title=dict(text=title, font=dict(size=17)),
        height=int(height), paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Arial", color="#172B4D", size=12),
        margin=dict(l=70, r=70, t=100, b=80),
        legend=dict(orientation="h", y=-0.18), separators=",.")
    return fig


def integer_axis(maximum):
    if maximum is None or pd.isna(maximum):
        maximum = 1
    maximum = max(1, math.ceil(float(maximum)))
    step = max(1, math.ceil(maximum / 6))
    return dict(range=[0, math.ceil(maximum / step) * step], tick0=0,
                dtick=step, tickformat="d", zeroline=False)


def dynamic_height(quantity, minimum=360, per_item=34, extra=150):
    return max(minimum, int(quantity) * per_item + extra)


def abbreviated_label(value, limit=32):
    text = " ".join(str(value).split()) or "Sem descrição"
    return escape(text if len(text) <= limit else text[:limit - 1] + "…")


def configure_category_axis(fig, labels):
    count = len(labels)
    positions = list(range(count))
    fig.update_xaxes(type="linear", tickmode="array", tickvals=positions,
        ticktext=[abbreviated_label(label) for label in labels],
        tickangle=-45 if count <= 10 else -60, showticklabels=True,
        ticklabeloverflow="allow", automargin=True, title=None,
        range=[-0.9, max(0, count - 1) + 0.9], fixedrange=False,
        showgrid=False, zeroline=False, layer="below traces")
    if count > 20:
        fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.08))
    return fig


def revise_bar_labels(fig):
    maximums = {}
    for trace in fig.data:
        if trace.type != "bar":
            continue
        horizontal = trace.orientation == "h"
        values = trace.x if horizontal else trace.y
        if values is None:
            continue
        texts, numbers = [], []
        for value in values:
            try:
                number = float(value)
                if not math.isfinite(number):
                    texts.append("")
                    continue
                numbers.append(number)
                text = (f"{int(number):,}".replace(",", ".") if number.is_integer()
                    else f"{number:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."))
                texts.append(text)
            except (TypeError, ValueError):
                texts.append("")
        trace.update(text=texts, texttemplate="%{text}", textposition="outside",
                     textangle=0, textfont=dict(size=12), cliponaxis=False,
                     constraintext="none")
        if not horizontal and numbers:
            axis = trace.yaxis or "y"
            maximums[axis] = max(maximums.get(axis, 0), max(numbers))
    for reference, maximum in maximums.items():
        key = "yaxis" if reference == "y" else "yaxis" + reference[1:]
        axis = getattr(fig.layout, key)
        upper = max(1, maximum * 1.22)
        if axis.range is not None:
            try:
                upper = max(upper, float(axis.range[1]))
            except (TypeError, ValueError, IndexError):
                pass
        axis.update(range=[0, upper], automargin=True, layer="below traces")
    if maximums:
        fig.update_layout(uniformtext=dict(minsize=11, mode="show"))
    return fig


def category_counts(df, column):
    if column not in df.columns:
        return pd.Series(dtype="int64")
    data = occurrence_frame(df, column) if column in {"Problema", "Peça"} else df
    values = data[column].fillna("").astype(str).str.strip()
    counts = values.loc[values.ne("")].value_counts()
    if counts.empty:
        return pd.Series(dtype="int64")
    table = counts.rename_axis("Categoria").reset_index(name="Quantidade")
    table = table.sort_values(["Quantidade", "Categoria"], ascending=[False, True], kind="stable")
    return table.set_index("Categoria")["Quantidade"]


def render_evolution_chart(df, granularity="Diária", chart_type="Barras", period=None):
    data = df.loc[df["Data da tarefa"].notna()].copy()
    frequency = {"Diária": "D", "Semanal": "W-SUN", "Mensal": "M"}[granularity]
    if period is not None and len(period) == 2:
        start, end = map(pd.Timestamp, period)
    elif not data.empty:
        start, end = data["Data da tarefa"].min(), data["Data da tarefa"].max()
    else:
        return None
    periods = pd.period_range(start, end, freq=frequency)
    if data.empty:
        table = pd.DataFrame(index=periods)
    else:
        dates = data["Data da tarefa"].dt.to_period(frequency)
        table = pd.crosstab(dates, data["Tipo"]).reindex(periods, fill_value=0)
    totals = table.sum(axis=1).astype(int)
    maximum = int(totals.max()) if len(totals) else 0
    fig = go.Figure()
    if chart_type == "Barras + linha acumulada":
        accumulated = totals.cumsum()
        fig.add_bar(x=periods.start_time, y=totals, name="Tarefas no período", marker_color=BLUE)
        fig.add_scatter(x=periods.start_time, y=accumulated, name="Acumulado de tarefas",
                       mode="lines+markers", yaxis="y2", line=dict(color=COLORS["Corretiva"], width=3))
        fig.update_layout(yaxis=dict(title="Tarefas no período", **integer_axis(maximum)),
            yaxis2=dict(title="Acumulado de tarefas", overlaying="y", side="right", showgrid=False,
                        **integer_axis(accumulated.max() if len(accumulated) else 0)))
    else:
        for kind in table.columns:
            if chart_type == "Linha":
                fig.add_scatter(x=periods.start_time, y=table[kind], name=str(kind),
                    mode="lines+markers", line=dict(color=COLORS.get(kind, BLUE)))
            else:
                fig.add_bar(x=periods.start_time, y=table[kind], name=str(kind), marker_color=COLORS.get(kind, BLUE))
        fig.update_layout(barmode="group", yaxis=dict(title="Tarefas", **integer_axis(maximum)))
    fig.update_traces(hovertemplate="%{x|%d/%m/%Y}<br>%{y:.0f} tarefas<extra>%{fullData.name}</extra>")
    fig.update_xaxes(title=None, tickformat="%d/%m/%Y", automargin=True)
    return revise_bar_labels(style(fig, "Evolução das manutenções", 520))


def render_horizontal_ranking(df, column, title, top_n=10):
    # Nome preservado para compatibilidade: a orientação é vertical.
    counts = category_counts(df, column).head(max(1, int(top_n)))
    if counts.empty:
        return None
    labels, values = counts.index.astype(str).tolist(), counts.astype(int).tolist()
    unit = "ocorrências" if column in {"Problema", "Peça"} else "tarefas"
    fig = go.Figure(go.Bar(x=list(range(len(labels))), y=values, customdata=labels,
        marker_color=BLUE, text=values, textposition="outside", cliponaxis=False,
        hovertemplate="%{customdata}<br>%{y:.0f} " + unit + "<extra></extra>"))
    height = 580 if len(labels) <= 10 else (720 if len(labels) <= 20 else 820)
    style(fig, title, height)
    configure_category_axis(fig, labels)
    fig.update_yaxes(title=unit.capitalize(), **integer_axis(max(values) * 1.22))
    fig.update_layout(showlegend=False, bargap=0.22,
        margin=dict(l=110, r=90, t=100, b=210 if len(labels) <= 20 else 240))
    return revise_bar_labels(fig)


def abc_table(counts, a_limit=0.80, b_limit=0.95):
    columns = ["Categoria", "Quantidade", "Participação", "Acumulado", "Acumulado %", "Classe"]
    if not 0 < float(a_limit) < float(b_limit) <= 1:
        raise ValueError("Os limites precisam respeitar: 0 < A < B <= 100%.")
    values = pd.to_numeric(counts, errors="coerce").dropna()
    values = values.loc[values.gt(0)]
    if values.empty:
        return pd.DataFrame(columns=columns)
    table = pd.DataFrame({"Categoria": values.index.astype(str), "Quantidade": values.astype(int).values})
    table = table.sort_values(["Quantidade", "Categoria"], ascending=[False, True], kind="stable").reset_index(drop=True)
    total = int(table["Quantidade"].sum())
    if total <= 0:
        return pd.DataFrame(columns=columns)
    table["Participação"] = table["Quantidade"] / total * 100
    table["Acumulado"] = table["Quantidade"].cumsum()
    table["Acumulado %"] = table["Acumulado"] / total * 100
    classes, before = [], 0
    for quantity in table["Quantidade"].drop_duplicates():
        size = int(table["Quantidade"].eq(quantity).sum())
        letter = "A" if before < total * a_limit - 1e-9 else ("B" if before < total * b_limit - 1e-9 else "C")
        classes.extend([letter] * size)
        before += int(quantity) * size
    table["Classe"] = classes
    return table[columns]


def render_pareto_chart(counts, title, top_n=None, highlight=None,
                        a_limit=0.80, b_limit=0.95, unit="ocorrências"):
    abc = abc_table(counts, a_limit, b_limit)
    if abc.empty:
        return None
    display = abc.copy() if top_n is None else abc.head(max(1, int(top_n))).copy()
    labels = display["Categoria"].tolist()
    positions = list(range(len(display)))
    quantities = display["Quantidade"].tolist()
    cumulative = display["Acumulado %"].tolist()
    highlighted = set(highlight) if highlight is not None else set()
    customdata = display[["Categoria", "Participação", "Acumulado", "Acumulado %", "Classe"]].values.tolist()
    fig = go.Figure()
    fig.add_bar(x=positions, y=quantities, name="Quantidade", customdata=customdata,
        marker=dict(color=[ABC_COLORS[c] for c in display["Classe"]],
            line=dict(color=["#172B4D" if label in highlighted else "rgba(0,0,0,0)" for label in labels],
                      width=[3 if label in highlighted else 0 for label in labels])),
        text=quantities, textposition="outside", cliponaxis=False,
        hovertemplate=("%{customdata[0]}<br>%{y:.0f} " + unit +
            "<br>Participação: %{customdata[1]:.2f}%<br>Quantidade acumulada: %{customdata[2]:.0f}"
            "<br>Percentual acumulado: %{customdata[3]:.2f}%<br>Classe: %{customdata[4]}<extra></extra>"))
    fig.add_scatter(x=positions, y=cumulative, yaxis="y2", name="Acumulado %",
        mode="lines+markers" if len(display) <= 25 else "lines",
        line=dict(color="#172B4D", width=3), marker=dict(size=5), customdata=customdata,
        hovertemplate="%{customdata[0]}<br>Acumulado: %{y:.2f}%<br>%{customdata[2]:.0f} " + unit + "<extra></extra>")
    shown_title = title + (f" — Top {len(display)} de {len(abc)}" if len(display) < len(abc) else "")
    style(fig, shown_title, 660 if len(display) <= 10 else (740 if len(display) <= 20 else 850))
    configure_category_axis(fig, labels)
    fig.update_layout(showlegend=False, bargap=0.18, hovermode="x",
        margin=dict(l=110, r=100, t=105, b=220 if len(display) <= 20 else 250),
        yaxis=dict(title=f"Quantidade de {unit}", **integer_axis(max(quantities) * 1.22)),
        yaxis2=dict(title="Percentual acumulado", overlaying="y", side="right", range=[0, 100],
                    tick0=0, dtick=20, ticksuffix="%", showgrid=False, zeroline=False, fixedrange=True))
    for limit, color in [(a_limit, "#31889A"), (b_limit, "#D58246")]:
        fig.add_shape(type="line", x0=0, x1=1, y0=limit * 100, y1=limit * 100,
            xref="paper", yref="y2", line=dict(color=color, width=1, dash="dash"))
        fig.add_annotation(x=1, y=limit * 100, xref="paper", yref="y2",
            text=f"{limit * 100:.0f}%", xanchor="left", xshift=5, showarrow=False,
            font=dict(size=11, color=color))
    fig.add_annotation(x=positions[-1], y=cumulative[-1], xref="x", yref="y2",
        text=f"{cumulative[-1]:.2f}%".replace(".", ","), showarrow=True, arrowhead=0,
        ax=-25, ay=30 if cumulative[-1] >= 90 else -30, bgcolor="white",
        bordercolor="#DCE4EC", borderpad=4, font=dict(size=12, color="#172B4D"))
    return revise_bar_labels(fig)


def render_abc_donut(abc, title, unit="ocorrências"):
    if abc.empty:
        return None
    summary = (abc.groupby("Classe").agg(Quantidade=("Quantidade", "sum"), Itens=("Categoria", "nunique"))
               .reindex(["A", "B", "C"]).dropna())
    summary = summary.loc[summary["Quantidade"].gt(0)]
    if summary.empty:
        return None
    fig = go.Figure(go.Pie(labels=[f"Classe {c}" for c in summary.index], values=summary["Quantidade"].tolist(),
        hole=0.62, sort=False, marker=dict(colors=[ABC_COLORS[c] for c in summary.index], line=dict(color="white", width=1)),
        textinfo="label+percent", textposition="inside", texttemplate="%{label}<br>%{percent:.2%}",
        hovertemplate="%{label}<br>%{value:.0f} " + unit + "<br>%{percent:.2%}<extra></extra>"))
    style(fig, title, 520)
    fig.update_layout(legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.05))
    fig.add_annotation(text=f"{int(summary['Quantidade'].sum()):,}".replace(",", ".") + f"<br>{unit}",
                       x=0.5, y=0.5, showarrow=False, font=dict(size=17))
    return fig


def render_donut_chart(df, column, title, top_n=10, show_others=True):
    counts = category_counts(df, column)
    if counts.empty:
        return None
    n = max(1, int(top_n))
    top = counts.head(n).copy()
    has_others = show_others and len(counts) > n
    others_label = "Outras"
    if has_others:
        while others_label in counts.index:
            others_label += " — agrupadas"
        top.loc[others_label] = counts.iloc[n:].sum()
    quantity = len(top)
    unit = "ocorrências" if column in {"Problema", "Peça"} else "tarefas"
    palette = px.colors.qualitative.Safe
    percentages = top / top.sum() * 100
    colors = ["#CBD5E1" if has_others and label == others_label else palette[i % len(palette)]
              for i, label in enumerate(top.index)]
    texts = [f"{p:.2f}%".replace(".", ",") if p >= 3 else "" for p in percentages]
    fig = go.Figure(go.Pie(labels=top.index, values=top.values, hole=0.62, sort=False,
        marker=dict(colors=colors, line=dict(color="white", width=1)), text=texts, textinfo="text",
        textposition="inside", insidetextorientation="horizontal", textfont=dict(size=14), automargin=True,
        hovertemplate="%{label}<br>%{value:.0f} " + unit + "<br>%{percent:.2%}<extra></extra>"))
    style(fig, title, 520 if quantity <= 10 else min(1400, 700 + (quantity - 10) * 22))
    fig.update_layout(margin=dict(l=35, r=35, t=90, b=60),
        legend=dict(orientation="h", x=0, xanchor="left", y=-0.06, yanchor="top", font=dict(size=12)),
        uniformtext=dict(minsize=11, mode="hide"))
    fig.add_annotation(text=f"{int(top.sum()):,}".replace(",", ".") + f"<br>{unit}",
        x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False, font=dict(size=17))
    return fig


def _validate_cut(universe, cut):
    if len(cut) > len(universe) or not set(cut.index).issubset(set(universe.index)):
        raise ValueError("O recorte precisa estar contido no universo.")


def render_cut_donut(universe, cut):
    _validate_cut(universe, cut)
    total, selected = len(universe), len(cut)
    if total == 0:
        return None
    fig = go.Figure(go.Pie(labels=["Recorte selecionado", "Restante do universo"], values=[selected, total-selected],
        hole=0.65, sort=False, marker=dict(colors=[BLUE, "#DCE4EC"]), textinfo="percent", textposition="inside",
        texttemplate="%{percent:.2%}", hovertemplate="%{label}<br>%{value:.0f} tarefas<br>%{percent:.2%}<extra></extra>"))
    style(fig, "Participação do recorte no universo", 520)
    fig.update_layout(legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.05))
    fig.add_annotation(text=f"{selected/total*100:.2f}%".replace(".", ",") + f"<br>{selected} de {total}<br>tarefas",
                       x=0.5, y=0.5, showarrow=False, font=dict(size=16))
    return fig


def render_cut_bars(universe, cut):
    _validate_cut(universe, cut)
    total, selected = len(universe), len(cut)
    if total == 0:
        return None
    fig = go.Figure(go.Bar(x=["Recorte selecionado", "Restante do universo"], y=[selected, total-selected],
        marker_color=[BLUE, "#DCE4EC"], text=[selected, total-selected], textposition="outside", cliponaxis=False,
        hovertemplate="%{x}<br>%{y:.0f} tarefas<extra></extra>"))
    fig.update_yaxes(title="Tarefas", **integer_axis(max(selected, total-selected) * 1.22))
    return revise_bar_labels(style(fig, "Volume do recorte no universo", 500))
