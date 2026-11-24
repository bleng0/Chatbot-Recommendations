"""Plotly views for the Cost tab's modeled API and self-hosted comparison."""
import plotly.graph_objects as go
import streamlit as st

from pome.app.render import TOKENS
from pome.app.scenario import SELFHOST
from pome.app.views import USD_INR, ApiCostComparison, api_cost_comparisons, inr
from pome.evidence.schema import EvidenceValue

T = TOKENS["light"]
MODEBAR = {"displayModeBar": False}


def _style(figure: go.Figure, *, height: int, volume: int, x_max: float) -> None:
    figure.update_layout(
        height=height, margin={"l": 10, "r": 20, "t": 32, "b": 42},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Fira Sans, sans-serif", "color": T["text"], "size": 13},
        hoverlabel={"bgcolor": T["panel"], "bordercolor": T["accent"]},
    )
    figure.update_xaxes(title="Tickets per month", range=[0, x_max],
                        gridcolor=T["line"], linecolor=T["grey"], zeroline=False,
                        tickfont={"color": T["muted"]})
    figure.add_vline(
        x=volume, line={"color": T["muted"], "dash": "dot", "width": 1.5},
        annotation_text=f"Selected volume ({volume:,})",
        annotation_position="top right" if volume < x_max / 2 else "top left",
        annotation_yanchor="bottom", annotation_yshift=4, annotation_font_color=T["muted"],
    )


def _breakeven_chart(rows: list[ApiCostComparison], *, volume: int) -> go.Figure | None:
    thresholds = [(row.config_id, row.breakeven) for row in rows if row.breakeven is not None]
    if not thresholds:
        return None
    names, tickets = zip(*thresholds)
    figure = go.Figure(go.Bar(
        x=tickets, y=names, orientation="h",
        marker={"color": T["teal"], "cornerradius": 4},
        text=[f"{count:,}" for count in tickets], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>Break-even around %{x:,.0f} tickets/month<extra></extra>",
    ))
    _style(figure, height=82 + 29 * len(thresholds), volume=volume,
           x_max=max(volume, *tickets) * 1.05)
    figure.update_layout(bargap=0.35, margin_r=12 + 7 * len(f"{max(tickets):,}"))
    figure.update_yaxes(autorange="reversed", automargin=True,
                        tickfont={"family": "Fira Code, monospace", "color": T["muted"], "size": 11})
    return figure


def _monthly_cost_chart(
    row: ApiCostComparison, *, selfhost_monthly: float, volume: int,
) -> go.Figure:
    crossing = selfhost_monthly / row.usd_per_ticket if row.breakeven is not None else None
    x_max = max(volume, crossing or 0) * 1.1
    points = {x_max * i / 60 for i in range(61)} | {volume}
    if crossing is not None:
        points.add(crossing)
    tickets = sorted(points)
    api_usd = [x * row.usd_per_ticket for x in tickets]
    rate = float(USD_INR.value)
    fixed_inr = selfhost_monthly * rate
    figure = go.Figure([
        go.Scatter(
            x=tickets, y=[cost * rate for cost in api_usd], name="API", mode="lines",
            line={"color": T["accent"], "width": 2.5},
            customdata=[inr(cost) for cost in api_usd],
            hovertemplate="API · %{x:,.0f} tickets/month<br>%{customdata}/month<extra></extra>",
        ),
        go.Scatter(
            x=tickets, y=[fixed_inr] * len(tickets), name="Self-hosted", mode="lines",
            line={"color": T["coraltext"], "width": 2.5, "dash": "dash"},
            hovertemplate=("Self-hosted · %{x:,.0f} tickets/month"
                           f"<br>{inr(selfhost_monthly)}/month<extra></extra>"),
        ),
    ])
    if crossing is not None:
        figure.add_scatter(
            x=[crossing], y=[fixed_inr], name="Break-even", mode="markers",
            marker={"color": T["text"], "size": 10, "line": {"color": T["panel"], "width": 1}},
            hovertemplate=("Break-even around %{x:,.0f} tickets/month"
                           f"<br>{inr(selfhost_monthly)}/month<extra></extra>"),
        )
    _style(figure, height=375, volume=volume, x_max=x_max)
    figure.update_layout(legend={"orientation": "h", "y": -0.25}, hovermode="closest")
    figure.update_yaxes(title="INR per month", tickprefix="₹", rangemode="tozero",
                        automargin=True, gridcolor=T["line"], zeroline=False)
    return figure


def show_api_comparison(costs: dict[str, EvidenceValue], *, volume: int) -> None:
    st.subheader("API versus self-hosted costs")
    baseline = costs.get(SELFHOST)
    if baseline is None:
        st.write("No modeled self-hosted cost is available for this scenario.")
        return
    selfhost_monthly = float(baseline.value)
    rows = api_cost_comparisons(costs, volume=volume, selfhost_monthly=selfhost_monthly)
    if not rows:
        st.write("No API configurations have a modeled cost per ticket.")
        return

    st.caption(f"MODELED · Self-hosted baseline `{SELFHOST}` costs "
               f"{inr(selfhost_monthly)} per month with the selected GPU and ops settings.")
    st.markdown("#### Break-even by API")
    breakeven_chart = _breakeven_chart(rows, volume=volume)
    if breakeven_chart is not None:
        st.caption("Above each break-even volume, self-hosting has the lower modeled cost.")
        st.plotly_chart(breakeven_chart, width="stretch", config=MODEBAR, key="api-breakeven-chart")
    else:
        st.caption("The available APIs have zero modeled cost per ticket and no break-even volume.")

    st.markdown("#### Monthly cost by ticket volume")
    by_id = {row.config_id: row for row in rows}
    selected = st.selectbox("API configuration", list(by_id), key="cost-comparison-api")
    row = by_id[selected]
    if row.breakeven is None and breakeven_chart is not None:
        st.caption("This API has zero modeled cost per ticket and no break-even volume.")
    st.plotly_chart(_monthly_cost_chart(row, selfhost_monthly=selfhost_monthly, volume=volume),
                    width="stretch", config=MODEBAR, key="api-monthly-cost-chart")

    with st.expander("API versus self-hosted details"):
        st.dataframe([{
            "API configuration": row.config_id,
            "API cost per ticket": inr(row.usd_per_ticket, 4),
            "Self-hosted cost per month": inr(selfhost_monthly),
            "Approx. break-even tickets per month": (
                f"{row.breakeven:,}" if row.breakeven is not None else "No break-even"
            ),
        } for row in rows], hide_index=True, width="stretch")
