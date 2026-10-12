import os
import sys
import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
import database

# Résolution dynamique du répertoire de travail (Script vs Executable PyInstaller)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DOSSIER_FACTURES = os.path.join(BASE_DIR, "Factures")

def dessiner_pied_de_page(canvas, doc):
    """Dessine le pied de page en bas absolu de la feuille PDF."""
    canvas.saveState()
    p_info = database.get_parametres()
    
    footer_text = p_info.get("pied_page", "").strip()
    if not footer_text:
        footer_text = "Merci pour votre confiance !\nBuilding Pro Services Guinea - S.A.R.L - BTP, Alu-Vitrerie & Négoce Matériaux"

    footer_text_html = footer_text.replace("\n", "<br/>")
    styles = getSampleStyleSheet()
    
    footer_style = ParagraphStyle(
        'FooterBottom',
        parent=styles['Normal'],
        fontSize=8,
        leading=11,
        alignment=1,  # Centré
        textColor=colors.HexColor('#64748B')
    )
    
    p = Paragraph(footer_text_html, footer_style)
    w, h = p.wrap(doc.width, doc.bottomMargin)
    
    # Positionnement à 20 points du bas de la page A4
    p.drawOn(canvas, doc.leftMargin, 20)
    canvas.restoreState()

def creer_facture(numero_facture, nom_client, articles, total_general, acompte, reste_a_payer):
    # Création du dossier 'Factures' s'il n'existe pas
    if not os.path.exists(DOSSIER_FACTURES):
        os.makedirs(DOSSIER_FACTURES, exist_ok=True)

    nom_fichier = os.path.join(DOSSIER_FACTURES, f"Facture_{numero_facture}.pdf")

    # bottomMargin=60 réserve l'espace en bas pour le pied de page fixe
    doc = SimpleDocTemplate(
        nom_fichier,
        pagesize=A4,
        rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=60
    )
    
    story = []
    styles = getSampleStyleSheet()
    p_info = database.get_parametres()

    sub_style = ParagraphStyle(
        'CompanySub',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#4A5568')
    )
    inv_title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading2'],
        fontSize=14,
        leading=16,
        alignment=2,
        textColor=colors.HexColor('#1B365D'),
        fontName='Helvetica-Bold'
    )

    logo_path = p_info.get("logo", "")
    logo_img = None
    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image(logo_path, width=70, height=70)
        except Exception:
            logo_img = None

    company_text = f"<b>{p_info['nom']}</b><br/>"
    if p_info['slogan']:
        company_text += f"<i>{p_info['slogan']}</i><br/>"
    company_text += f"Tél : {p_info['tel']} | Email : {p_info['email']}<br/>Adresse : {p_info['adresse']}"
    
    company_p = Paragraph(company_text, sub_style)
    date_str = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
    inv_text = f"<b>FACTURE</b><br/>N° : {numero_facture}<br/>Date : {date_str}"
    inv_p = Paragraph(inv_text, inv_title_style)

    if logo_img:
        header_table = Table([[logo_img, company_p, inv_p]], colWidths=[80, 280, 175])
    else:
        header_table = Table([[company_p, inv_p]], colWidths=[360, 195])

    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 15))

    client_style = ParagraphStyle('ClientStyle', parent=styles['Normal'], fontSize=10, leading=13)
    client_p = Paragraph(f"<b>Client :</b> {nom_client}", client_style)
    
    client_table = Table([[client_p]], colWidths=[535])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F9')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(client_table)
    story.append(Spacer(1, 15))

    header_table_style = ParagraphStyle('TH', parent=styles['Normal'], fontName='Helvetica-Bold', textColor=colors.white, fontSize=9)
    cell_style = ParagraphStyle('TD', parent=styles['Normal'], fontSize=9, leading=11)
    cell_right = ParagraphStyle('TDR', parent=styles['Normal'], fontSize=9, leading=11, alignment=2)
    cell_center = ParagraphStyle('TDC', parent=styles['Normal'], fontSize=9, leading=11, alignment=1)

    table_data = [[
        Paragraph("<b>Désignation</b>", header_table_style),
        Paragraph("<b>Qté / Surface</b>", header_table_style),
        Paragraph("<b>Prix Unitaire (GNF)</b>", header_table_style),
        Paragraph("<b>Total (GNF)</b>", header_table_style)
    ]]

    for art in articles:
        table_data.append([
            Paragraph(str(art['designation']), cell_style),
            Paragraph(str(art['quantite']), cell_center),
            Paragraph(f"{art['pu']:,.0f}".replace(",", " "), cell_right),
            Paragraph(f"{art['total']:,.0f}".replace(",", " "), cell_right)
        ])

    art_table = Table(table_data, colWidths=[245, 70, 110, 110])
    art_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B365D')),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    story.append(art_table)
    story.append(Spacer(1, 15))

    summary_style = ParagraphStyle('SumStyle', parent=styles['Normal'], fontSize=10, leading=14, fontName='Helvetica-Bold')
    
    summary_data = [
        [Paragraph("Total Général :", summary_style), Paragraph(f"{total_general:,.0f} GNF".replace(",", " "), summary_style)],
        [Paragraph("Acompte versé :", summary_style), Paragraph(f"{acompte:,.0f} GNF".replace(",", " "), summary_style)],
        [Paragraph("Reste à payer :", summary_style), Paragraph(f"{reste_a_payer:,.0f} GNF".replace(",", " "), summary_style)]
    ]
    
    sum_table = Table(summary_data, colWidths=[120, 130])
    sum_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#FEF2F2')),
        ('TEXTCOLOR', (0, 2), (-1, 2), colors.HexColor('#991B1B')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))

    wrapper_table = Table([["", sum_table]], colWidths=[285, 250])
    wrapper_table.setStyle(TableStyle([('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
    story.append(wrapper_table)

    # Dessine le pied de page en bas absolu
    doc.build(story, onFirstPage=dessiner_pied_de_page, onLaterPages=dessiner_pied_de_page)
    return nom_fichier