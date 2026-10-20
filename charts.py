import math
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from kpis import occurrence_frame

BLUE = "#245A81"
COLORS = {"Preventiva": "#31889A", "Corretiva": "#D58246"}
ABC_COLORS = {"A": "#245A81", "B": "#D58246", "C": "#9AA7B4"}


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


def dynamic_height(quantity, minimum=360, per_item=34, extra=150):
    return max(minimum, int(quantity) * per_item + extra)


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


def abc_table(counts, a_limit=0.80, b_limit=0.95):
    counts = counts.sort_values(ascending=False)
    total = int(counts.sum())
    if total == 0 or counts.empty:
        return pd.DataFrame(columns=["Categoria", "Quantidade", "Participação",
                                     "Acumulado", "Acumulado %", "Classe"])
    a_limit = min(max(float(a_limit), 0.01), 1.0)
    b_limit = min(max(float(b_limit), a_limit + 0.01), 1.0)
    quantities = counts.astype(int)
    cumulative = quantities.cumsum()
    cumulative_pct = cumulative / total * 100
    classes = pd.Series("C", index=quantities.index)

    a_boundary = None
    for position, value in enumerate(cumulative_pct.values):
        if value >= a_limit * 100:
            a_boundary = position
            break
    if a_boundary is not None:
        while a_boundary + 1 < len(quantities) and quantities.iloc[a_boundary + 1] == quantities.iloc[a_boundary]:
            a_boundary += 1
        classes.iloc[:a_boundary + 1] = "A"

    b_start = 0 if a_boundary is None else a_boundary + 1
    b_boundary = None
    for position in range(b_start, len(cumulative_pct)):
        if cumulative_pct.iloc[position] >= b_limit * 100:
            b_boundary = position
            break
    if b_boundary is not None:
        while b_boundary + 1 < len(quantities) and quantities.iloc[b_boundary + 1] == quantities.iloc[b_boundary]:
            b_boundary += 1
        classes.iloc[b_start:b_boundary + 1] = "B"

    result = pd.DataFrame({
        "Categoria": quantities.index,
        "Quantidade": quantities.values,
        "Participação": quantities.values / total * 100,
        "Acumulado": cumulative.values,
        "Acumulado %": cumulative_pct.values,
        "Classe": classes.values,
    })
    return result


def render_pareto_chart(counts, title, top_n=None, highlight=None,
                        a_limit=0.80, b_limit=0.95, unit="ocorrências"):
    abc = abc_table(counts, a_limit, b_limit)
    if abc.empty:
        return None
    display = abc if not top_n else abc.head(int(top_n))
    labels = display["Categoria"].tolist()[::-1]
    quantities = display["Quantidade"].tolist()[::-1]
    cumulative = display["Acumulado %"].tolist()[::-1]
    classes = display["Classe"].tolist()[::-1]
    shares = display["Participação"].tolist()[::-1]
    highlight = set(highlight or [])
    colors = [ABC_COLORS.get(item, BLUE) for item in classes]
    outline = ["#172B4D" if label in highlight else "rgba(0,0,0,0)" for label in labels]
    width = [3 if label in highlight else 0 for label in labels]

    fig = go.Figure()
    fig.add_bar(y=labels, x=quantities, orientation="h", marker_color=colors,
                marker_line_color=outline, marker_line_width=width,
                text=[f"{value:,}".replace(",", ".") for value in quantities],
                textposition="outside", cliponaxis=False,
                customdata=list(zip(shares, cumulative, classes)),
                hovertemplate=("%{y}<br>%{x:.0f} " + unit +
                               "<br>Participação: %{customdata[0]:.1f}%" +
                               "<br>Acumulado: %{customdata[1]:.1f}%" +
                               "<br>Classe: %{customdata[2]}<extra></extra>"))
    fig.add_scatter(y=labels, x=cumulative, mode="lines+markers", name="Acumulado %",
                    xaxis="x2", line=dict(color="#172B4D", width=3),
                    marker=dict(size=6),
                    hovertemplate="%{y}<br>Acumulado: %{x:.1f}%<extra></extra>")
    fig.update_layout(xaxis=dict(title=unit.capitalize(), **integer_axis(max(quantities))),
                      xaxis2=dict(overlaying="x", side="top", range=[0, 100],
                                  ticksuffix="%", showgrid=False, zeroline=False),
                      yaxis=dict(automargin=True, autorange="reversed"),
                      showlegend=False,
                      shapes=[dict(type="line", x0=a_limit * 100, x1=a_limit * 100, y0=0, y1=1,
                                   xref="x2", yref="paper", line=dict(color="#31889A", dash="dash")),
                              dict(type="line", x0=b_limit * 100, x1=b_limit * 100, y0=0, y1=1,
                                   xref="x2", yref="paper", line=dict(color="#D58246", dash="dash"))])
    fig.update_xaxes(tickformat="d", rangemode="tozero")
    total = int(abc["Quantidade"].sum())
    shown = int(display["Quantidade"].sum())
    subtitle = title
    if top_n and len(abc) > int(top_n):
        subtitle += f" — Top {int(top_n)} de {len(abc)} categorias"
    fig = style(fig, subtitle, dynamic_height(len(display)))
    fig.add_annotation(text=(f"Base: {total:,} {unit}".replace(",", ".") +
                             (f"<br>Exibindo {shown:,} ({shown / total * 100:.1f}%)".replace(",", ".")
                              if shown < total else "")),
                       xref="paper", yref="paper", x=1, y=-0.12,
                       showarrow=False, font=dict(size=11), align="right")
    return fig


def render_abc_donut(abc, title, unit="ocorrências"):
    if abc.empty:
        return None
    classes = (abc.groupby("Classe", as_index=False)
                  .agg(Quantidade=("Quantidade", "sum"), Itens=("Categoria", "nunique")))
    classes = classes.loc[classes["Quantidade"].gt(0)].set_index("Classe")
    classes = classes.reindex(["A", "B", "C"]).dropna(how="all")
    if classes.empty:
        return None
    labels = [f"Classe {index}" for index in classes.index]
    values = classes["Quantidade"].astype(int).tolist()
    colors = [ABC_COLORS.get(index, BLUE) for index in classes.index]
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=.65, sort=False,
                           marker=dict(colors=colors), textinfo="percent",
                           hovertemplate=("%{label}<br>%{value:.0f} " + unit +
                                          "<br>%{percent}<extra></extra>")))
    total = int(classes["Quantidade"].sum())
    items = int(classes["Itens"].sum())
    fig.add_annotation(text=f"{total:,}<br>{unit}<br>{items} categorias".replace(",", "."),
                       showarrow=False)
    return style(fig, title, 460)


def render_horizontal_ranking(df, column, title, top_n=10):
    counts = category_counts(df, column).head(top_n)
    fig = go.Figure(go.Bar(x=counts.values, y=counts.index, orientation="h", text=counts.values,
                           textposition="outside", cliponaxis=False, marker_color=BLUE,
                           hovertemplate="%{y}<br>%{x:.0f} ocorrências<extra></extra>"))
    fig.update_yaxes(autorange="reversed", automargin=True)
    fig.update_xaxes(visible=False, range=[0, max(1, counts.max() if len(counts) else 1) * 1.2])
    return style(fig, title, dynamic_height(len(counts), 340, 34, 110))


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
