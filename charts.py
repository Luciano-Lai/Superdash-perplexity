import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

COLOR_PREVENTIVA = "#2E86AB"
COLOR_CORRETIVA = "#E76F51"
COLOR_TOTAL = "#1F4E79"
COLOR_NEUTRO = "#9CA3AF"
COLOR_DESTAQUE = "#1F4E79"

BASE_LAYOUT = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {
        "family": "Arial, sans-serif",
        "size": 12,
        "color": "#374151",
    },
    "margin": {"l": 20, "r": 20, "t": 30, "b": 40},
    "showlegend": False,
}


def _clean_layout(fig, height=380):
    fig.update_layout(**BASE_LAYOUT)
    fig.update_layout(height=height)

    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor="#E5E7EB",
        tickfont={"size": 11, "color": "#6B7280"},
    )

    fig.update_yaxes(
        showgrid=True,
        gridcolor="#F3F4F6",
        zeroline=False,
        tickfont={"size": 11, "color": "#6B7280"},
    )

    return fig


def render_evolution_chart(df, granularity="Diária", chart_type="Barras"):
    df_evo = df.copy()

    if granularity == "Semanal":
        df_evo["Período"] = df_evo["Data da tarefa"].dt.to_period("W").dt.start_time
    elif granularity == "Mensal":
        df_evo["Período"] = df_evo["Data da tarefa"].dt.to_period("M").dt.start_time
    else:
        df_evo["Período"] = df_evo["Data da tarefa"].dt.date

    grouped = (
        df_evo
        .groupby(["Período", "Tipo"], dropna=False)
        .size()
        .reset_index(name="Quantidade")
    )

    color_map = {
        "Preventiva": COLOR_PREVENTIVA,
        "Corretiva": COLOR_CORRETIVA,
    }

    if chart_type == "Linha":
        fig = px.line(
            grouped,
            x="Período",
            y="Quantidade",
            color="Tipo",
            color_discrete_map=color_map,
            markers=True,
        )

        fig.update_traces(
            line={"width": 3},
            marker={"size": 7},
        )

    elif chart_type == "Barras + linha acumulada":
        totals = (
            df_evo
            .groupby("Período")
            .size()
            .reset_index(name="Total")
            .sort_values("Período")
        )
        totals["Acumulado"] = totals["Total"].cumsum()

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=totals["Período"],
                y=totals["Total"],
                name="Tarefas no período",
                marker_color=COLOR_TOTAL,
                hovertemplate="%{x}<br>Tarefas: %{y}<extra></extra>",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=totals["Período"],
                y=totals["Acumulado"],
                name="Acumulado",
                mode="lines+markers",
                line={"color": COLOR_CORRETIVA, "width": 3},
                marker={"size": 7},
                yaxis="y2",
                hovertemplate="%{x}<br>Acumulado: %{y}<extra></extra>",
            )
        )

        fig.update_layout(
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "left",
                "x": 0,
                "font": {"size": 11},
            },
            yaxis={"title": "Tarefas no período"},
            yaxis2={
                "title": "Acumulado",
                "overlaying": "y",
                "side": "right",
                "showgrid": False,
            },
        )

    else:
        fig = px.bar(
            grouped,
            x="Período",
            y="Quantidade",
            color="Tipo",
            barmode="group",
            color_discrete_map=color_map,
        )

        fig.update_traces(
            marker_line_width=0,
            hovertemplate="%{x}<br>%{legendgroup}: %{y}<extra></extra>",
        )

    fig.update_layout(
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 11},
        }
    )

    return _clean_layout(fig, height=400)


def render_horizontal_ranking(df, column, title, top_n=10):
    counts = (
        df[column]
        .value_counts()
        .head(top_n)
        .reset_index()
    )
    counts.columns = [column, "Total"]

    max_value = counts["Total"].max()
    colors = [
        COLOR_DESTAQUE if value == max_value else "#7FA8C9"
        for value in counts["Total"]
    ]

    fig = go.Figure(
        go.Bar(
            x=counts["Total"],
            y=counts[column],
            orientation="h",
            marker_color=colors,
            text=counts["Total"],
            textposition="outside",
            textfont={"size": 12, "color": "#374151"},
            hovertemplate="%{y}<br>Total: %{x}<extra></extra>",
        )
    )

    fig.update_layout(
        title={
            "text": title,
            "x": 0,
            "xanchor": "left",
            "font": {"size": 15, "color": "#1F2937"},
        },
        xaxis={"visible": False},
        yaxis={
            "autorange": "reversed",
            "tickfont": {"size": 11, "color": "#374151"},
        },
        margin={"l": 10, "r": 50, "t": 45, "b": 20},
    )

    return _clean_layout(fig, height=max(320, 38 * len(counts) + 90))


def render_donut_chart(df, column, title, top_n=10, show_others=True):
    counts = df[column].value_counts()

    if len(counts) > top_n and show_others:
        top = counts.head(top_n)
        others = pd.Series({"Outras": counts.iloc[top_n:].sum()})
        counts = pd.concat([top, others])
    else:
        counts = counts.head(top_n)

    total = counts.sum()

    colors = [
        COLOR_NEUTRO if name == "Outras" else None
        for name in counts.index
    ]

    fig = go.Figure(
        go.Pie(
            labels=counts.index,
            values=counts.values,
            hole=0.62,
            marker={
                "colors": colors,
                "line": {"color": "#FFFFFF", "width": 2},
            },
            textinfo="percent",
            textposition="outside",
            textfont={"size": 11, "color": "#374151"},
            hovertemplate="%{label}<br>%{value} tarefas<br>%{percent}<extra></extra>",
            sort=False,
        )
    )

    fig.add_annotation(
        text=f"<b>{total}</b><br><span style='font-size:11px;color:#6B7280'>tarefas</span>",
        showarrow=False,
        font={"size": 20, "color": "#1F2937"},
    )

    fig.update_layout(
        title={
            "text": title,
            "x": 0,
            "xanchor": "left",
            "font": {"size": 15, "color": "#1F2937"},
        },
        legend={
            "orientation": "v",
            "yanchor": "middle",
            "y": 0.5,
            "xanchor": "left",
            "x": 1.02,
            "font": {"size": 11},
        },
        margin={"l": 20, "r": 120, "t": 45, "b": 20},
    )

    return _clean_layout(fig, height=380)
