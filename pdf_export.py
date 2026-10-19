import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

def generate_pdf_report(kpi_dict, selected_kpis, chart_figs=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>Relatório de Acompanhamento de Refrigeração</b>", styles["Title"]))
    story.append(Spacer(1, 12))

    if selected_kpis:
        story.append(Paragraph("<b>Indicadores Chave (KPIs)</b>", styles["Heading2"]))
        kpi_data = [["KPI", "Valor"]]
        for k in selected_kpis:
            kpi_data.append([k, str(kpi_dict.get(k, "—"))])
        
        t = Table(kpi_data, colWidths=[250, 150])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0052CC')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 1, colors.grey),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 18))

    doc.build(story)
    buffer.seek(0)
    return buffer
