from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO
from datetime import datetime

DARK   = colors.HexColor('#1a1a2e')
ACCENT = colors.HexColor('#e94560')
RED    = colors.HexColor('#FFCCCC')
YELLOW = colors.HexColor('#FFF3CD')


def _fmt_date(value, fmt='%d/%m/%Y'):
    if value is None:
        return 'N/A'
    try:
        if hasattr(value, 'strftime'):
            return value.strftime(fmt)
        return str(value)[:10]
    except Exception:
        return str(value)


def _fmt_money(value):
    try:
        return f'${float(value):,.0f}'
    except (TypeError, ValueError):
        return 'N/A'


def generate_receipt_pdf(payment):
    buf  = BytesIO()
    doc  = SimpleDocTemplate(buf, pagesize=letter)
    styles   = getSampleStyleSheet()
    elements = []
    elements.append(Paragraph('Body-Fit', ParagraphStyle('title', fontSize=20, textColor=DARK, spaceAfter=4)))
    elements.append(Paragraph('RECIBO DE PAGO', styles['Title']))
    elements.append(Spacer(1, 12))
    data = [
        ['Cliente:',      payment.client.full_name    if payment.client     else 'N/A'],
        ['Membresía:',    payment.membership.name     if payment.membership else 'N/A'],
        ['Monto:',        _fmt_money(payment.amount)],
        ['Fecha de pago:',_fmt_date(payment.payment_date)],
        ['Vencimiento:',  _fmt_date(payment.end_date)],
        ['Método:',       payment.payment_method or 'N/A'],
    ]
    table = Table(data, colWidths=[150, 300])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)
    doc.build(elements)
    buf.seek(0)
    return buf


def generate_report_pdf(tipo, data, start=None, end=None, today=None):
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.5*inch, rightMargin=0.5*inch,
        topMargin=0.5*inch,  bottomMargin=0.5*inch,
    )
    styles   = getSampleStyleSheet()
    elements = []

    # ── Encabezado ───────────────────────────────────────────────
    titulo_map = {
        'clientes':   'Clientes Activos',
        'pagos':      'Ingresos / Pagos',
        'ventas':     'Ventas de Productos',
        'vencidos':   'Membresías Vencidas',
        'por_vencer': 'Membresías por Vencer (≤3 días)',
    }
    titulo = titulo_map.get(tipo, tipo.capitalize())
    elements.append(Paragraph('Body-Fit', ParagraphStyle('brand', fontSize=18, textColor=DARK, spaceAfter=2)))
    now_str = datetime.now().strftime('%d/%m/%Y %H:%M')
    elements.append(Paragraph(f'Reporte: {titulo} — {now_str}', styles['Normal']))

    if start and end:
        elements.append(Paragraph(
            f'Período: {_fmt_date(start)} al {_fmt_date(end)}',
            styles['Normal']
        ))

    elements.append(Spacer(1, 14))

    # ── Tabla según tipo ─────────────────────────────────────────
    row_colors = []  # para colorear filas de vencidos

    if tipo == 'clientes':
        table_data = [['Nombre', 'Documento', 'Email', 'Teléfono', 'Inscripción']]
        for c in data:
            table_data.append([
                c.full_name      or '',
                c.document_number or '',
                c.email          or '',
                c.phone          or '',
                _fmt_date(c.enrollment_date),
            ])
        col_widths = [170, 90, 130, 85, 70]

    elif tipo == 'pagos':
        table_data = [['Cliente', 'Plan', 'Monto', 'Fecha Pago', 'Método']]
        total = 0
        for p in data:
            table_data.append([
                p.client.full_name    if p.client     else 'N/A',
                p.membership.name     if p.membership else 'N/A',
                _fmt_money(p.amount),
                _fmt_date(p.payment_date),
                p.payment_method      or '',
            ])
            total += p.amount or 0
        table_data.append(['', '', _fmt_money(total), 'TOTAL', ''])
        col_widths = [160, 110, 75, 80, 75]

    elif tipo == 'ventas':
        table_data = [['Cliente', 'Total', 'Método', 'Fecha']]
        for s in data:
            table_data.append([
                s.client.full_name if s.client else 'General',
                _fmt_money(s.total),
                s.payment_method or '',
                _fmt_date(s.sale_date, '%d/%m/%Y %H:%M'),
            ])
        col_widths = [200, 80, 90, 130]

    elif tipo in ('vencidos', 'por_vencer'):
        table_data = [['Cliente', 'Teléfono', 'Email', 'Plan', 'Venció / Vence', 'Días']]
        ref = today or datetime.now().date()
        for p in data:
            dias = (p.end_date - ref).days
            table_data.append([
                p.client.full_name if p.client else 'N/A',
                p.client.phone     if p.client else '',
                p.client.email     if p.client else '',
                p.membership.name  if p.membership else 'N/A',
                _fmt_date(p.end_date),
                str(dias),
            ])
            row_colors.append(RED if dias < 0 else YELLOW)
        col_widths = [130, 75, 120, 90, 75, 40]

    else:
        table_data = [['Sin datos']]
        col_widths = [500]

    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    # Estilo base
    style_cmds = [
        ('BACKGROUND',  (0, 0),  (-1, 0),  DARK),
        ('TEXTCOLOR',   (0, 0),  (-1, 0),  colors.white),
        ('FONTNAME',    (0, 0),  (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0),  (-1, -1), 8),
        ('GRID',        (0, 0),  (-1, -1), 0.3, colors.lightgrey),
        ('PADDING',     (0, 0),  (-1, -1), 5),
        ('ALIGN',       (0, 0),  (-1, -1), 'LEFT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
    ]

    # Colorear filas individuales para vencidos
    for i, fill in enumerate(row_colors, start=1):
        style_cmds.append(('BACKGROUND', (0, i), (-1, i), fill))

    table.setStyle(TableStyle(style_cmds))
    elements.append(table)
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f'Total de registros: {len(data)}', styles['Normal']))

    doc.build(elements)
    buf.seek(0)
    return buf


def generate_cierre_caja_pdf(fecha, payments, expenses, sales, opening_cash,
                              cash_breakdown, usuario_cierre):
    """
    PDF de cierre de caja del día.
    Incluye: resumen financiero, detalle de cada pago (con quién lo registró),
    ventas de inventario, egresos y balance final.
    """
    from reportlab.platypus import HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    import pytz
    BOGOTA = pytz.timezone('America/Bogota')

    GREEN  = colors.HexColor('#16a34a')
    RED2   = colors.HexColor('#dc2626')
    GRAY   = colors.HexColor('#f3f4f6')
    GRAY2  = colors.HexColor('#e5e7eb')
    GOLD   = colors.HexColor('#b45309')

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.5*inch, rightMargin=0.5*inch,
        topMargin=0.5*inch,  bottomMargin=0.5*inch,
    )
    styles  = getSampleStyleSheet()
    elems   = []

    centro  = ParagraphStyle('centro',  alignment=TA_CENTER, fontSize=10)
    derecha = ParagraphStyle('derecha', alignment=TA_RIGHT,  fontSize=9)
    titulo  = ParagraphStyle('titulo',  alignment=TA_CENTER, fontSize=22,
                              textColor=colors.white, fontName='Helvetica-Bold')
    sub     = ParagraphStyle('sub',     alignment=TA_CENTER, fontSize=11,
                              textColor=colors.HexColor('#d1d5db'))
    seccion = ParagraphStyle('seccion', fontSize=11, fontName='Helvetica-Bold',
                              textColor=DARK, spaceBefore=14, spaceAfter=4)

    # ── Encabezado oscuro ────────────────────────────────────────────
    fecha_str   = fecha.strftime('%d de %B de %Y').capitalize() if hasattr(fecha,'strftime') else str(fecha)
    generado_en = datetime.now(BOGOTA).strftime('%d/%m/%Y %H:%M:%S')

    header_data = [[
        Paragraph('<b>💪 BODY-FIT GYM</b>', titulo),
    ]]
    header_sub  = [[
        Paragraph(f'CIERRE DE CAJA — {fecha_str}', sub),
    ]]
    h1 = Table(header_data, colWidths=[7.5*inch])
    h1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), DARK),
        ('PADDING',    (0,0), (-1,-1), 10),
    ]))
    h2 = Table(header_sub, colWidths=[7.5*inch])
    h2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#111827')),
        ('PADDING',    (0,0), (-1,-1), 6),
    ]))
    elems += [h1, h2, Spacer(1, 10)]

    # ── Meta: generado por / hora ────────────────────────────────────
    meta = Table([[
        Paragraph(f'<font size="8" color="#6b7280">Generado: {generado_en}</font>', styles['Normal']),
        Paragraph(f'<font size="8" color="#6b7280">Responsable: <b>{usuario_cierre}</b></font>', derecha),
    ]], colWidths=[3.75*inch, 3.75*inch])
    meta.setStyle(TableStyle([('PADDING', (0,0), (-1,-1), 2)]))
    elems += [meta, Spacer(1, 12)]

    # ── Calcular totales ─────────────────────────────────────────────
    total_membresías = sum(p.amount for p in payments)
    total_ventas     = sum(s.total  for s in sales)
    total_egresos    = sum(e.amount for e in expenses)
    total_ingresos   = total_membresías + total_ventas
    balance_neto     = total_ingresos - total_egresos

    # ── Tarjetas de resumen (tabla 4 columnas) ───────────────────────
    elems.append(Paragraph('RESUMEN DEL DÍA', seccion))

    def card(label, value, color):
        t = Table([
            [Paragraph(f'<font size="8" color="#6b7280">{label}</font>', styles['Normal'])],
            [Paragraph(f'<b><font size="14" color="{color}">{_fmt_money(value)}</font></b>', styles['Normal'])],
        ], colWidths=[1.8*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), GRAY),
            ('BOX',        (0,0), (-1,-1), 0.5, colors.HexColor('#d1d5db')),
            ('PADDING',    (0,0), (-1,-1), 8),
            ('ROUNDEDCORNERS', [4]),
        ]))
        return t

    summary = Table([[
        card('Membresías',    total_membresías, '#1d4ed8'),
        card('Inventario',    total_ventas,     '#0891b2'),
        card('Egresos',       total_egresos,    '#dc2626'),
        card('Balance Neto',  balance_neto,     '#16a34a' if balance_neto >= 0 else '#dc2626'),
    ]], colWidths=[1.85*inch]*4, hAlign='CENTER')
    summary.setStyle(TableStyle([('PADDING', (0,0), (-1,-1), 4)]))
    elems += [summary, Spacer(1, 8)]

    # Caja base
    if opening_cash is not None:
        elems.append(Paragraph(
            f'<font size="9" color="#6b7280">Caja base al abrir: <b>{_fmt_money(opening_cash)}</b> &nbsp;|&nbsp; '
            f'Efectivo disponible estimado: <b>{_fmt_money((opening_cash or 0) + (cash_breakdown.get("efectivo", 0)))}</b></font>',
            styles['Normal']
        ))
        elems.append(Spacer(1, 8))

    # ── Desglose por método de pago ──────────────────────────────────
    if cash_breakdown:
        elems.append(Paragraph('INGRESOS POR MÉTODO DE PAGO', seccion))
        bd_data = [['Método', 'Total']]
        ICONOS = {
            'efectivo':      '💵 Efectivo',
            'nequi':         '📱 Nequi',
            'transferencia': '🏦 Transferencia',
            'tarjeta':       '💳 Tarjeta',
            'datafono':      '📟 Datáfono',
        }
        for method, total in sorted(cash_breakdown.items()):
            label = ICONOS.get(method, method.capitalize())
            bd_data.append([label, _fmt_money(total)])
        bd_data.append(['TOTAL MEMBRESÍAS', _fmt_money(total_membresías)])

        bd_table = Table(bd_data, colWidths=[4*inch, 3.5*inch])
        bd_table.setStyle(TableStyle([
            ('BACKGROUND',     (0,0),  (-1,0),  DARK),
            ('TEXTCOLOR',      (0,0),  (-1,0),  colors.white),
            ('FONTNAME',       (0,0),  (-1,0),  'Helvetica-Bold'),
            ('BACKGROUND',     (0,-1), (-1,-1), colors.HexColor('#dcfce7')),
            ('FONTNAME',       (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('TEXTCOLOR',      (0,-1), (-1,-1), GREEN),
            ('GRID',           (0,0),  (-1,-1), 0.3, colors.lightgrey),
            ('FONTSIZE',       (0,0),  (-1,-1), 9),
            ('PADDING',        (0,0),  (-1,-1), 6),
            ('ROWBACKGROUNDS', (0,1),  (-1,-2), [colors.white, GRAY]),
        ]))
        elems += [bd_table, Spacer(1, 10)]

    # ── Detalle de pagos ─────────────────────────────────────────────
    elems.append(Paragraph(f'DETALLE DE PAGOS ({len(payments)} registros)', seccion))

    if payments:
        pay_data = [['#', 'Cliente', 'Plan', 'Monto', 'Método', 'Turno', 'Registrado por']]
        for i, p in enumerate(payments, 1):
            # Buscar quién lo registró en audit_logs
            registrado_por = '—'
            try:
                from database.models.audit import AuditLog
                from database.models.user import User
                log = (AuditLog.query
                       .filter_by(table_name='payments', record_id=p.id, action='CREATE')
                       .first())
                if log and log.user:
                    registrado_por = log.user.username
            except Exception:
                pass

            pay_data.append([
                str(i),
                (p.client.full_name if p.client else 'N/A')[:25],
                (p.membership.name  if p.membership else 'N/A')[:18],
                _fmt_money(p.amount),
                (p.payment_method or '')[:12],
                p.shift or '—',
                registrado_por[:15],
            ])
        pay_data.append(['', '', 'TOTAL', _fmt_money(total_membresías), '', '', ''])

        pay_table = Table(pay_data, colWidths=[0.3*inch, 1.8*inch, 1.4*inch,
                                                0.75*inch, 1*inch, 0.7*inch, 1.05*inch],
                          repeatRows=1)
        pay_table.setStyle(TableStyle([
            ('BACKGROUND',     (0,0),  (-1,0),  DARK),
            ('TEXTCOLOR',      (0,0),  (-1,0),  colors.white),
            ('FONTNAME',       (0,0),  (-1,0),  'Helvetica-Bold'),
            ('BACKGROUND',     (0,-1), (-1,-1), colors.HexColor('#dcfce7')),
            ('FONTNAME',       (2,-1), (3,-1),  'Helvetica-Bold'),
            ('TEXTCOLOR',      (2,-1), (3,-1),  GREEN),
            ('GRID',           (0,0),  (-1,-1), 0.3, colors.lightgrey),
            ('FONTSIZE',       (0,0),  (-1,-1), 7.5),
            ('PADDING',        (0,0),  (-1,-1), 5),
            ('ROWBACKGROUNDS', (0,1),  (-1,-2), [colors.white, GRAY]),
        ]))
        elems += [pay_table, Spacer(1, 10)]
    else:
        elems.append(Paragraph('<i>Sin pagos de membresía registrados hoy.</i>', styles['Normal']))
        elems.append(Spacer(1, 8))

    # ── Ventas de inventario ─────────────────────────────────────────
    if sales:
        elems.append(Paragraph(f'VENTAS DE INVENTARIO ({len(sales)} registros)', seccion))
        s_data = [['Cliente', 'Total', 'Método', 'Hora']]
        for s in sales:
            s_data.append([
                (s.client.full_name if s.client else 'General')[:25],
                _fmt_money(s.total),
                s.payment_method or '—',
                s.sale_date.strftime('%H:%M') if hasattr(s.sale_date, 'strftime') else '—',
            ])
        s_data.append(['TOTAL', _fmt_money(total_ventas), '', ''])
        s_table = Table(s_data, colWidths=[2.5*inch, 1.2*inch, 2*inch, 1.8*inch], repeatRows=1)
        s_table.setStyle(TableStyle([
            ('BACKGROUND',     (0,0),  (-1,0),  DARK),
            ('TEXTCOLOR',      (0,0),  (-1,0),  colors.white),
            ('FONTNAME',       (0,0),  (-1,0),  'Helvetica-Bold'),
            ('BACKGROUND',     (0,-1), (-1,-1), colors.HexColor('#dcfce7')),
            ('FONTNAME',       (0,-1), (1,-1),  'Helvetica-Bold'),
            ('TEXTCOLOR',      (0,-1), (1,-1),  GREEN),
            ('GRID',           (0,0),  (-1,-1), 0.3, colors.lightgrey),
            ('FONTSIZE',       (0,0),  (-1,-1), 8),
            ('PADDING',        (0,0),  (-1,-1), 5),
            ('ROWBACKGROUNDS', (0,1),  (-1,-2), [colors.white, GRAY]),
        ]))
        elems += [s_table, Spacer(1, 10)]

    # ── Egresos ──────────────────────────────────────────────────────
    if expenses:
        elems.append(Paragraph(f'EGRESOS DEL DÍA ({len(expenses)} registros)', seccion))
        e_data = [['Descripción', 'Categoría', 'Monto', 'Registrado por']]
        for e in expenses:
            registrado_por = '—'
            try:
                if e.user:
                    registrado_por = e.user.username
            except Exception:
                pass
            e_data.append([
                (e.description or '')[:35],
                (e.category or '—').capitalize(),
                _fmt_money(e.amount),
                registrado_por[:15],
            ])
        e_data.append(['TOTAL EGRESOS', '', _fmt_money(total_egresos), ''])
        e_table = Table(e_data, colWidths=[2.8*inch, 1.5*inch, 1.2*inch, 2*inch], repeatRows=1)
        e_table.setStyle(TableStyle([
            ('BACKGROUND',     (0,0),  (-1,0),  colors.HexColor('#7f1d1d')),
            ('TEXTCOLOR',      (0,0),  (-1,0),  colors.white),
            ('FONTNAME',       (0,0),  (-1,0),  'Helvetica-Bold'),
            ('BACKGROUND',     (0,-1), (-1,-1), colors.HexColor('#fee2e2')),
            ('FONTNAME',       (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('TEXTCOLOR',      (0,-1), (2,-1),  RED2),
            ('GRID',           (0,0),  (-1,-1), 0.3, colors.lightgrey),
            ('FONTSIZE',       (0,0),  (-1,-1), 8),
            ('PADDING',        (0,0),  (-1,-1), 5),
            ('ROWBACKGROUNDS', (0,1),  (-1,-2), [colors.white, colors.HexColor('#fff1f2')]),
        ]))
        elems += [e_table, Spacer(1, 10)]

    # ── Balance final ────────────────────────────────────────────────
    elems.append(HRFlowable(width='100%', thickness=1.5, color=DARK))
    elems.append(Spacer(1, 6))

    color_balance = '#16a34a' if balance_neto >= 0 else '#dc2626'
    balance_data = [
        ['Total ingresos (membresías + inventario)',
         Paragraph(f'<b><font color="#1d4ed8">{_fmt_money(total_ingresos)}</font></b>', styles['Normal'])],
        ['Total egresos',
         Paragraph(f'<b><font color="#dc2626">- {_fmt_money(total_egresos)}</font></b>', styles['Normal'])],
        ['BALANCE NETO DEL DÍA',
         Paragraph(f'<b><font size="13" color="{color_balance}">{_fmt_money(balance_neto)}</font></b>', styles['Normal'])],
    ]
    bal_table = Table(balance_data, colWidths=[5*inch, 2.5*inch])
    bal_table.setStyle(TableStyle([
        ('FONTSIZE',   (0,0),  (-1,-1), 9),
        ('PADDING',    (0,0),  (-1,-1), 7),
        ('BACKGROUND', (0,-1), (-1,-1), GRAY2),
        ('FONTNAME',   (0,-1), (0,-1),  'Helvetica-Bold'),
        ('LINEABOVE',  (0,-1), (-1,-1), 1, DARK),
        ('GRID',       (0,0),  (-1,-1), 0.3, colors.lightgrey),
    ]))
    elems += [bal_table, Spacer(1, 14)]

    # ── Pie ──────────────────────────────────────────────────────────
    elems.append(Paragraph(
        f'<font size="7.5" color="#9ca3af">Body-Fit Gym — Documento generado automáticamente el {generado_en} '
        f'por {usuario_cierre}. Este reporte es confidencial.</font>',
        centro
    ))

    doc.build(elems)
    buf.seek(0)
    return buf
