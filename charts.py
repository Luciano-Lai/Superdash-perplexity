import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from kpis import occurrence_frame


BLUE = "#245A81"
COLORS = {
    "Preventiva": "#31889A",
    "Corretiva": "#D58246",
}
ABC_COLORS = {
    "A": "#245A81",
    "B": "#D58246",
    "C": "#9AA7B4",
}


def style(fig, title, height=400):
    fig.update_layout(
        template="plotly_white",
        title=dict(text=title, font=dict(size=17)),
        height=int(height),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Arial", color="#172B4D", size=12),
        margin=dict(l=30, r=55, t=85, b=65),
        legend=dict(orientation="h", y=-0.18),
        separators=",.",
    )
    return fig


def integer_axis(maximum):
    if maximum is None or pd.isna(maximum):
        maximum = 1
    maximum = max(1, int(maximum))
    step = max(1, math.ceil(maximum / 6))
    ceiling = math.ceil(maximum / step) * step
    return dict(
        range=[0, ceiling],
        tick0=0,
        dtick=step,
        tickformat="d",
        zeroline=False,
    )


def dynamic_height(quantity, minimum=360, per_item=34, extra=150):
    return max(minimum, int(quantity) * per_item + extra)


def category_counts(df, column):
    if column not in df.columns:
        return pd.Series(dtype="int64")

    data = occurrence_frame(df, column) if column in {"Problema", "Peça"} else df
    values = data[column].fillna("").astype(str).str.strip()
    counts = values.loc[values.ne("")].value_counts()

    if counts.empty:
        return pd.Series(dtype="int64")

    table = counts.rename_axis("Categoria").reset_index(name="Quantidade")
    table = table.sort_values(
        ["Quantidade", "Categoria"],
        ascending=[False, True],
        kind="stable",
    )
    return table.set_index("Categoria")["Quantidade"]


def render_evolution_chart(
    df,
    granularity="Diária",
    chart_type="Barras",
    period=None,
):
    data = df.loc[df["Data da tarefa"].notna()].copy()
    freq = {"Diária": "D", "Semanal": "W-SUN", "Mensal": "M"}[granularity]

    if period is not None and len(period) == 2:
        start, end = map(pd.Timestamp, period)
    elif not data.empty:
        start = data["Data da tarefa"].min()
        end = data["Data da tarefa"].max()
    else:
        return None

    periods = pd.period_range(start, end, freq=freq)
    dates = data["Data da tarefa"].dt.to_period(freq)

    if data.empty:
        table = pd.DataFrame(index=periods)
    else:
        table = pd.crosstab(dates, data["Tipo"]).reindex(periods, fill_value=0)

    totals = table.sum(axis=1).astype(int)
    x = periods.start_time
    maximum = int(totals.max()) if len(totals) else 0
    fig = go.Figure()

    if chart_type == "Barras + linha acumulada":
        accumulated = totals.cumsum()
        fig.add_bar(
            x=x,
            y=totals,
            name="Tarefas no período",
            marker_color=BLUE,
        )
        fig.add_scatter(
            x=x,
            y=accumulated,
            name="Acumulado",
            mode="lines+markers",
            yaxis="y2",
            line=dict(color=COLORS["Corretiva"], width=3),
        )
        fig.update_layout(
            yaxis=dict(
                title="Tarefas no período",
                **integer_axis(maximum),
            ),
            yaxis2=dict(
                title="Acumulado de tarefas",
                overlaying="y",
                side="right",
                showgrid=False,
                **integer_axis(
                    accumulated.max() if len(accumulated) else 0
                ),
            ),
        )
    else:
        for kind in table.columns:
            if chart_type == "Linha":
                fig.add_scatter(
                    x=x,
                    y=table[kind],
                    name=str(kind),
                    mode="lines+markers",
                    line=dict(color=COLORS.get(kind, BLUE)),
                )
            else:
                fig.add_bar(
                    x=x,
                    y=table[kind],
                    name=str(kind),
                    marker_color=COLORS.get(kind, BLUE),
                )

        fig.update_layout(
            barmode="group",
            yaxis=dict(title="Tarefas", **integer_axis(maximum)),
        )

    fig.update_traces(
        hovertemplate=(
            "%{x|%d/%m/%Y}<br>%{y:.0f} tarefas"
            "<extra>%{fullData.name}</extra>"
        )
    )
    fig.update_xaxes(title=None, tickformat="%d/%m/%Y")
    return style(fig, "Evolução das manutenções", 460)


def render_horizontal_ranking(df, column, title, top_n=10):
    # Nome preservado para compatibilidade com o restante do projeto.
    counts = category_counts(df, column).head(max(1, int(top_n)))
    if counts.empty:
        return None

    unit = "ocorrências" if column in {"Problema", "Peça"} else "tarefas"
    vertical = len(counts) > 20
    fig = go.Figure()

    if vertical:
        fig.add_bar(
            x=counts.index,
            y=counts.values,
            text=counts.values,
            textposition="outside",
            cliponaxis=False,
            marker_color=BLUE,
            hovertemplate=(
                "%{x}<br>%{y:.0f} " + unit + "<extra></extra>"
            ),
        )
        fig.update_xaxes(
            type="category",
            categoryorder="array",
            categoryarray=counts.index.tolist(),
            tickangle=-60,
            automargin=True,
            title=None,
        )
        fig.update_yaxes(
            title=unit.capitalize(),
            **integer_axis(counts.max() * 1.15),
        )
        height = 680 if len(counts) <= 40 else 820
        fig = style(fig, title, height)
        fig.update_layout(margin=dict(l=50, r=50, t=85, b=190))
    else:
        fig.add_bar(
            x=counts.values,
            y=counts.index,
            orientation="h",
            text=counts.values,
            textposition="outside",
            cliponaxis=False,
            marker_color=BLUE,
            hovertemplate=(
                "%{y}<br>%{x:.0f} " + unit + "<extra></extra>"
            ),
        )
        fig.update_yaxes(
            type="category",
            categoryorder="array",
            categoryarray=counts.index.tolist(),
            autorange="reversed",
            automargin=True,
        )
        fig.update_xaxes(
            visible=False,
            range=[0, max(1, int(counts.max())) * 1.2],
        )
        fig = style(
            fig,
            title,
            dynamic_height(len(counts), 420, 34, 140),
        )

    return fig


def abc_table(counts, a_limit=0.80, b_limit=0.95):
    columns = [
        "Categoria",
        "Quantidade",
        "Participação",
        "Acumulado",
        "Acumulado %",
        "Classe",
    ]

    if not 0 < float(a_limit) < float(b_limit) <= 1:
        raise ValueError(
            "Os limites precisam respeitar: 0 < A < B <= 100%."
        )

    values = pd.to_numeric(counts, errors="coerce").dropna()
    values = values.loc[values.gt(0)]

    if values.empty:
        return pd.DataFrame(columns=columns)

    table = pd.DataFrame({
        "Categoria": values.index.astype(str),
        "Quantidade": values.astype(int).values,
    })
    table = table.sort_values(
        ["Quantidade", "Categoria"],
        ascending=[False, True],
        kind="stable",
    ).reset_index(drop=True)

    total = int(table["Quantidade"].sum())
    if total <= 0:
        return pd.DataFrame(columns=columns)

    table["Participação"] = table["Quantidade"] / total * 100
    table["Acumulado"] = table["Quantidade"].cumsum()
    table["Acumulado %"] = table["Acumulado"] / total * 100

    # Cada bloco empatado recebe a mesma classe.
    # A classe é definida pelo acumulado antes do bloco.
    classes = []
    accumulated_before = 0

    for quantity in table["Quantidade"].drop_duplicates():
        block_size = int(table["Quantidade"].eq(quantity).sum())

        if accumulated_before < total * a_limit - 1e-9:
            letter = "A"
        elif accumulated_before < total * b_limit - 1e-9:
            letter = "B"
        else:
            letter = "C"

        classes.extend([letter] * block_size)
        accumulated_before += int(quantity) * block_size

    table["Classe"] = classes
    return table[columns]


def render_pareto_chart(
    counts,
    title,
    top_n=None,
    highlight=None,
    a_limit=0.80,
    b_limit=0.95,
    unit="ocorrências",
):
    abc = abc_table(counts, a_limit, b_limit)
    if abc.empty:
        return None

    display = (
        abc.copy()
        if top_n is None
        else abc.head(max(1, int(top_n))).copy()
    )

    labels = display["Categoria"].tolist()
    quantities = display["Quantidade"].tolist()
    cumulative = display["Acumulado %"].tolist()
    highlight = set(highlight) if highlight is not None else set()

    colors = [ABC_COLORS[c] for c in display["Classe"]]
    outlines = [
        "#172B4D" if label in highlight else "rgba(0,0,0,0)"
        for label in labels
    ]
    widths = [3 if label in highlight else 0 for label in labels]
    customdata = display[
        ["Participação", "Acumulado %", "Classe", "Acumulado"]
    ].values.tolist()

    vertical = len(display) > 20
    fig = go.Figure()

    if vertical:
        fig.add_bar(
            x=labels,
            y=quantities,
            marker=dict(
                color=colors,
                line=dict(color=outlines, width=widths),
            ),
            text=quantities,
            textposition="outside",
            cliponaxis=False,
            customdata=customdata,
            hovertemplate=(
                "%{x}<br>%{y:.0f} " + unit +
                "<br>Participação: %{customdata[0]:.1f}%"
                "<br>Acumulado: %{customdata[3]:.0f}"
                "<br>Acumulado: %{customdata[1]:.1f}%"
                "<br>Classe: %{customdata[2]}<extra></extra>"
            ),
        )
        fig.add_scatter(
            x=labels,
            y=cumulative,
            yaxis="y2",
            mode="lines+markers",
            name="Acumulado %",
            line=dict(color="#172B4D", width=3),
            hovertemplate=(
                "%{x}<br>Acumulado: %{y:.1f}%<extra></extra>"
            ),
        )
        fig.update_layout(
            xaxis=dict(
                type="category",
                categoryorder="array",
                categoryarray=labels,
                tickangle=-60,
                automargin=True,
            ),
            yaxis=dict(
                title=unit.capitalize(),
                **integer_axis(max(quantities) * 1.15),
            ),
            yaxis2=dict(
                title="Acumulado %",
                overlaying="y",
                side="right",
                range=[0, 100],
                ticksuffix="%",
                showgrid=False,
            ),
            shapes=[
                dict(
                    type="line",
                    x0=0,
                    x1=1,
                    y0=limit * 100,
                    y1=limit * 100,
                    xref="paper",
                    yref="y2",
                    line=dict(color=color, dash="dash"),
                )
                for limit, color in [
                    (a_limit, "#31889A"),
                    (b_limit, "#D58246"),
                ]
            ],
        )
        height = 720 if len(display) <= 40 else 850
    else:
        fig.add_bar(
            y=labels,
            x=quantities,
            orientation="h",
            marker=dict(
                color=colors,
                line=dict(color=outlines, width=widths),
            ),
            text=quantities,
            textposition="outside",
            cliponaxis=False,
            customdata=customdata,
            hovertemplate=(
                "%{y}<br>%{x:.0f} " + unit +
                "<br>Participação: %{customdata[0]:.1f}%"
                "<br>Acumulado: %{customdata[3]:.0f}"
                "<br>Acumulado: %{customdata[1]:.1f}%"
                "<br>Classe: %{customdata[2]}<extra></extra>"
            ),
        )
        fig.add_scatter(
            y=labels,
            x=cumulative,
            xaxis="x2",
            mode="lines+markers",
            name="Acumulado %",
            line=dict(color="#172B4D", width=3),
            hovertemplate=(
                "%{y}<br>Acumulado: %{x:.1f}%<extra></extra>"
            ),
        )
        fig.update_layout(
            xaxis=dict(
                title=unit.capitalize(),
                **integer_axis(max(quantities) * 1.15),
            ),
            xaxis2=dict(
                title="Acumulado %",
                overlaying="x",
                side="top",
                range=[0, 100],
                ticksuffix="%",
                showgrid=False,
            ),
            yaxis=dict(
                type="category",
                categoryorder="array",
                categoryarray=labels,
                autorange="reversed",
                automargin=True,
            ),
            shapes=[
                dict(
                    type="line",
                    x0=limit * 100,
                    x1=limit * 100,
                    y0=0,
                    y1=1,
                    xref="x2",
                    yref="paper",
                    line=dict(color=color, dash="dash"),
                )
                for limit, color in [
                    (a_limit, "#31889A"),
                    (b_limit, "#D58246"),
                ]
            ],
        )
        height = dynamic_height(len(display), 480, 34, 180)

    shown_title = title
    if len(display) < len(abc):
        shown_title += f" — Top {len(display)} de {len(abc)}"

    fig = style(fig, shown_title, height)
    fig.update_layout(showlegend=False)

    if vertical:
        fig.update_layout(
            margin=dict(l=55, r=80, t=90, b=200)
        )
    else:
        fig.update_layout(
            margin=dict(l=30, r=65, t=110, b=70)
        )

    return fig


def render_abc_donut(abc, title, unit="ocorrências"):
    if abc.empty:
        return None

    summary = (
        abc.groupby("Classe")
        .agg(
            Quantidade=("Quantidade", "sum"),
            Itens=("Categoria", "nunique"),
        )
        .reindex(["A", "B", "C"])
        .dropna()
    )
    summary = summary.loc[summary["Quantidade"].gt(0)]

    if summary.empty:
        return None

    fig = go.Figure(
        go.Pie(
            labels=[f"Classe {c}" for c in summary.index],
            values=summary["Quantidade"].tolist(),
            hole=0.62,
            sort=False,
            marker=dict(
                colors=[ABC_COLORS[c] for c in summary.index],
                line=dict(color="white", width=1),
            ),
            textinfo="label+percent",
            textposition="inside",
            hovertemplate=(
                "%{label}<br>%{value:.0f} " + unit +
                "<br>%{percent}<extra></extra>"
            ),
        )
    )
    fig = style(fig, title, 520)
    fig.update_layout(
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=-0.05,
        )
    )
    fig.add_annotation(
        text=(
            f"{int(summary['Quantidade'].sum()):,}".replace(",", ".")
            + f"<br>{unit}"
        ),
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=17),
    )
    return fig


def render_donut_chart(
    df,
    column,
    title,
    top_n=10,
    show_others=True,
):
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

    colors = [
        "#CBD5E1"
        if has_others and label == others_label
        else palette[i % len(palette)]
        for i, label in enumerate(top.index)
    ]

    percentage_labels = [
        f"{value:.1f}%".replace(".", ",") if value >= 3 else ""
        for value in percentages
    ]

    fig = go.Figure(
        go.Pie(
            labels=top.index,
            values=top.values,
            hole=0.62,
            sort=False,
            marker=dict(
                colors=colors,
                line=dict(color="white", width=1),
            ),
            text=percentage_labels,
            textinfo="text",
            textposition="inside",
            insidetextorientation="horizontal",
            textfont=dict(size=14),
            automargin=True,
            hovertemplate=(
                "%{label}<br>%{value:.0f} " + unit +
                "<br>%{percent}<extra></extra>"
            ),
        )
    )

    height = (
        520 if quantity <= 10
        else min(1400, 700 + (quantity - 10) * 22)
    )

    # Aplicar estilo antes das configurações específicas da rosca.
    fig = style(fig, title, height)
    fig.update_layout(
        margin=dict(l=35, r=35, t=90, b=60),
        legend=dict(
            orientation="h",
            x=0,
            xanchor="left",
            y=-0.06,
            yanchor="top",
            font=dict(size=12),
        ),
        uniformtext=dict(minsize=11, mode="hide"),
    )
    fig.add_annotation(
        text=(
            f"{int(top.sum()):,}".replace(",", ".")
            + f"<br>{unit}"
        ),
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=17),
    )
    return fig


def _validate_cut(universe, cut):
    if (
        len(cut) > len(universe)
        or not set(cut.index).issubset(set(universe.index))
    ):
        raise ValueError(
            "O recorte precisa estar contido no universo."
        )


def render_cut_donut(universe, cut):
    _validate_cut(universe, cut)
    total, selected = len(universe), len(cut)

    if total == 0:
        return None

    fig = go.Figure(
        go.Pie(
            labels=["Recorte selecionado", "Restante do universo"],
            values=[selected, total - selected],
            hole=0.65,
            sort=False,
            marker=dict(colors=[BLUE, "#DCE4EC"]),
            textinfo="percent",
            textposition="inside",
            hovertemplate=(
                "%{label}<br>%{value:.0f} tarefas"
                "<br>%{percent}<extra></extra>"
            ),
        )
    )
    fig = style(fig, "Participação do recorte no universo", 520)
    fig.update_layout(
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=-0.05,
        )
    )
    pct = selected / total * 100
    fig.add_annotation(
        text=(
            f"{pct:.1f}%".replace(".", ",")
            + f"<br>{selected} de {total}<br>tarefas"
        ),
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=16),
    )
    return fig


def render_cut_bars(universe, cut):
    _validate_cut(universe, cut)
    total, selected = len(universe), len(cut)

    if total == 0:
        return None

    fig = go.Figure(
        go.Bar(
            x=["Recorte selecionado", "Restante do universo"],
            y=[selected, total - selected],
            marker_color=[BLUE, "#DCE4EC"],
            text=[selected, total - selected],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{x}<br>%{y:.0f} tarefas<extra></extra>",
        )
    )
    fig.update_yaxes(
        title="Tarefas",
        **integer_axis(max(selected, total - selected) * 1.15),
    )
    return style(fig, "Volume do recorte no universo", 460)
