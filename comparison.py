import pandas as pd
import plotly.graph_objects as go

from filters import apply_filters
from charts import (
    integer_axis,
    style,
    category_counts,
    configure_category_axis,
    revise_bar_labels,
)


COLORS = [
    "#245A81",
    "#D58246",
]


def comparison_base(raw, spec):
    return apply_filters(
        raw,
        spec,
        ignore=("Máquina",),
    )


def split_machines(base, code_a, code_b):
    if code_a == code_b:
        raise ValueError(
            "Escolha duas máquinas diferentes."
        )

    a = base.loc[
        base["Máquina"].eq(code_a)
    ].copy()

    b = base.loc[
        base["Máquina"].eq(code_b)
    ].copy()

    return a, b


def comparison_evolution(
    a,
    b,
    label_a,
    label_b,
    period,
    granularity="Mensal",
):
    """
    Evolução comparativa com barras verticais agrupadas.

    Cada período apresenta duas barras:
    máquina A em azul e máquina B em laranja.
    """
    frequency = {
        "Diária": "D",
        "Semanal": "W-SUN",
        "Mensal": "M",
    }[granularity]

    start = pd.Timestamp(period[0])
    end = pd.Timestamp(period[1])

    periods = pd.period_range(
        start,
        end,
        freq=frequency,
    )

    if len(periods) == 0:
        return None

    positions = list(range(len(periods)))

    axis_labels = []
    hover_periods = []

    for current in periods:
        period_start = max(
            current.start_time.normalize(),
            start.normalize(),
        )
        period_end = min(
            current.end_time.normalize(),
            end.normalize(),
        )

        if granularity == "Mensal":
            axis_labels.append(
                current.start_time.strftime("%m/%Y")
            )
        else:
            axis_labels.append(
                period_start.strftime("%d/%m/%Y")
            )

        if granularity == "Diária":
            hover_periods.append(
                period_start.strftime("%d/%m/%Y")
            )
        else:
            hover_periods.append(
                f"{period_start:%d/%m/%Y}"
                f" a {period_end:%d/%m/%Y}"
            )

    fig = go.Figure()
    maximum = 0

    for data, label, color in zip(
        [a, b],
        [label_a, label_b],
        COLORS,
    ):
        valid = data.loc[
            data["Data da tarefa"].notna()
        ].copy()

        valid = valid.loc[
            valid["Data da tarefa"].ge(start)
            & valid["Data da tarefa"].lt(
                end + pd.Timedelta(days=1)
            )
        ]

        counts = (
            valid.groupby(
                valid["Data da tarefa"].dt.to_period(
                    frequency
                )
            )
            .size()
            .reindex(periods, fill_value=0)
            .astype(int)
        )

        maximum = max(
            maximum,
            int(counts.max()) if len(counts) else 0,
        )

        fig.add_bar(
            x=positions,
            y=counts.values,
            name=str(label),
            marker_color=color,
            offsetgroup=str(label),
            text=counts.values,
            textposition="outside",
            cliponaxis=False,
            customdata=hover_periods,
            hovertemplate=(
                "Período: %{customdata}<br>"
                "Tarefas: %{y:.0f}"
                "<extra>%{fullData.name}</extra>"
            ),
        )

    height = 580 if len(periods) <= 12 else 680

    if len(periods) > 30:
        height = 780

    fig = style(
        fig,
        f"Evolução comparativa — {granularity.lower()}",
        height,
    )

    configure_category_axis(
        fig,
        axis_labels,
    )

    fig.update_layout(
        barmode="group",
        bargap=0.25,
        bargroupgap=0.08,
        hovermode="x",
        margin=dict(
            l=100,
            r=90,
            t=140,
            b=180 if len(periods) <= 20 else 230,
        ),
        legend=dict(
            orientation="h",
            x=0,
            xanchor="left",
            y=1.12,
            yanchor="bottom",
        ),
        yaxis=dict(
            title="Quantidade de tarefas",
            **integer_axis(maximum * 1.22),
        ),
    )

    fig.update_xaxes(
        title="Período",
    )

    return revise_bar_labels(fig)


def comparison_bars(
    a,
    b,
    label_a,
    label_b,
):
    categories = [
        "Total de tarefas",
        "Preventivas",
        "Corretivas",
    ]

    fig = go.Figure()
    maximum = 0

    for data, label, color in zip(
        [a, b],
        [label_a, label_b],
        COLORS,
    ):
        counts = [
            len(data),
            int(
                data["Tipo"].eq("Preventiva").sum()
            ),
            int(
                data["Tipo"].eq("Corretiva").sum()
            ),
        ]

        maximum = max(
            maximum,
            max(counts),
        )

        fig.add_bar(
            x=categories,
            y=counts,
            name=str(label),
            marker_color=color,
            text=counts,
            textposition="outside",
            cliponaxis=False,
            hovertemplate=(
                "%{x}<br>"
                "%{y:.0f} tarefas"
                "<extra>%{fullData.name}</extra>"
            ),
        )

    fig.update_layout(
        barmode="group",
        bargap=0.25,
        yaxis=dict(
            title="Tarefas",
            **integer_axis(maximum * 1.22),
        ),
    )

    fig = style(
        fig,
        "Volume de manutenção — A × B",
        540,
    )

    return revise_bar_labels(fig)


def comparison_share(
    a,
    b,
    label_a,
    label_b,
):
    total = len(a) + len(b)

    if total == 0:
        return None

    fig = go.Figure(
        go.Pie(
            labels=[
                str(label_a),
                str(label_b),
            ],
            values=[
                len(a),
                len(b),
            ],
            hole=0.65,
            sort=False,
            marker=dict(
                colors=COLORS,
                line=dict(
                    color="white",
                    width=1,
                ),
            ),
            textinfo="percent",
            textposition="inside",
            texttemplate="%{percent:.2%}",
            hovertemplate=(
                "%{label}<br>"
                "%{value:.0f} tarefas"
                "<br>%{percent:.2%}"
                "<extra></extra>"
            ),
        )
    )

    fig = style(
        fig,
        "Participação entre as duas máquinas",
        520,
    )

    fig.update_layout(
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=-0.06,
        )
    )

    fig.add_annotation(
        text=f"{total}<br>tarefas A + B",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=17),
    )

    return fig


def comparison_occurrences(
    a,
    b,
    column,
    label_a,
    label_b,
    top_n,
):
    ca = category_counts(
        a,
        column,
    )
    cb = category_counts(
        b,
        column,
    )

    joined = (
        pd.concat(
            [
                ca.rename("A"),
                cb.rename("B"),
            ],
            axis=1,
        )
        .fillna(0)
        .astype(int)
    )

    if joined.empty:
        return None

    joined["Total"] = (
        joined["A"] + joined["B"]
    )
    joined["Categoria"] = (
        joined.index.astype(str)
    )

    ordered = joined.sort_values(
        ["Total", "Categoria"],
        ascending=[False, True],
        kind="stable",
    ).head(
        max(1, int(top_n))
    )

    labels = ordered["Categoria"].tolist()
    positions = list(range(len(labels)))

    fig = go.Figure()

    for key, label, color in zip(
        ["A", "B"],
        [label_a, label_b],
        COLORS,
    ):
        values = ordered[key].tolist()

        fig.add_bar(
            x=positions,
            y=values,
            name=str(label),
            marker_color=color,
            customdata=labels,
            text=values,
            textposition="outside",
            cliponaxis=False,
            hovertemplate=(
                "%{customdata}<br>"
                "%{y:.0f} ocorrências"
                "<extra>%{fullData.name}</extra>"
            ),
        )

    maximum = int(
        ordered[["A", "B"]].max().max()
    )

    height = 620 if len(labels) <= 10 else 740

    if len(labels) > 20:
        height = 850

    fig = style(
        fig,
        f"{column} — comparação por ocorrência",
        height,
    )

    configure_category_axis(
        fig,
        labels,
    )

    fig.update_layout(
        barmode="group",
        bargap=0.25,
        bargroupgap=0.08,
        margin=dict(
            l=110,
            r=90,
            t=130,
            b=220 if len(labels) <= 20 else 250,
        ),
        legend=dict(
            orientation="h",
            x=0,
            y=1.13,
            xanchor="left",
            yanchor="bottom",
        ),
        yaxis=dict(
            title="Ocorrências",
            **integer_axis(maximum * 1.22),
        ),
    )

    return revise_bar_labels(fig)
