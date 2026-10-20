import io
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether


def _figure_image(fig, target_width=1100):
    height = int(fig.layout.height or 650)
    image = fig.to_image(format="png", width=target_width, height=height, scale=1)
    return image, target_width, height


def generate_pdf_report(kpi_dict, selected_kpis, chart_figs=None, charts_per_page=1):
    if not 1 <= charts_per_page <= 4:
        raise ValueError("Escolha de 1 a 4 gráficos por página.")
    chart_figs = chart_figs or {}
    if not selected_kpis and not chart_figs:
        raise ValueError("Selecione ao menos um indicador ou gráfico.")
    buffer = io.BytesIO()
    page = landscape(A4)
    width, height = page[0]-60, page[1]-60
    doc = SimpleDocTemplate(buffer, pagesize=page, leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    story = []
    if selected_kpis:
        cards = []
        for name in selected_kpis:
            cards.append(Paragraph(escape(name) + "<br/><b>" + escape(str(kpi_dict.get(name, "—"))) + "</b>", styles["Normal"]))
        for start in range(0, len(cards), 4):
            row = cards[start:start+4]
            row += [""] * (4-len(row))
            table = Table([row], colWidths=[width/4]*4)
            table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#F0F4F8")),
                                       ("VALIGN", (0,0), (-1,-1), "TOP"),
                                       ("BOX", (0,0), (-1,-1), .5, colors.HexColor("#DCE4EC")),
                                       ("LEFTPADDING", (0,0), (-1,-1), 10),
                                       ("TOPPADDING", (0,0), (-1,-1), 12),
                                       ("BOTTOMPADDING", (0,0), (-1,-1), 12)]))
            story.extend([table, Spacer(1,12)])
        if chart_figs:
            story.append(PageBreak())
    entries = list(chart_figs.items())
    columns = 1 if charts_per_page == 1 else 2
    rows = 1 if charts_per_page <= 2 else 2
    cell_w, cell_h = width/columns, (height-12)/rows
    for start in range(0, len(entries), charts_per_page):
        chunk = entries[start:start+charts_per_page]
        cells = []
        for name, fig in chunk:
            image_bytes, source_width, source_height = _figure_image(fig)
            proportional_height = (cell_w-14)*source_height/source_width
            image = Image(io.BytesIO(image_bytes), width=cell_w-14, height=proportional_height)
            image._restrictSize(cell_w-14, cell_h-35)
            cells.append(KeepTogether([Paragraph(escape(name), styles["Normal"]), image]))
        cells += [""] * ((rows*columns)-len(cells))
        grid = [cells[i:i+columns] for i in range(0, len(cells), columns)]
        table = Table(grid, colWidths=[cell_w]*columns)
        table.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
        story.append(table)
        if start+charts_per_page < len(entries):
            story.append(PageBreak())
    doc.build(story)
    return buffer.getvalue()
