from datetime import datetime, date
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.colors import HexColor, white, black


def hex_to_color(hex_str):
    hex_str = hex_str.lstrip('#')
    r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
    return colors.Color(r / 255, g / 255, b / 255)


def lighten(hex_str, factor=0.85):
    hex_str = hex_str.lstrip('#')
    r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return colors.Color(r / 255, g / 255, b / 255)


def duration_label(start_str, end_str):
    if not start_str or not end_str:
        return ''
    try:
        start = datetime.strptime(start_str, '%Y-%m-%d').date()
        end = datetime.strptime(end_str, '%Y-%m-%d').date()
        delta = (end - start).days + 1
        if delta == 1:
            return '1 day'
        if delta < 7:
            return f'{delta} days'
        weeks = delta // 7
        rem = delta % 7
        parts = [f'{weeks} week{"s" if weeks > 1 else ""}']
        if rem:
            parts.append(f'{rem} day{"s" if rem > 1 else ""}')
        return ', '.join(parts)
    except ValueError:
        return ''


def group_attributes(attributes):
    grouped = {}
    for a in attributes:
        t = a.get('type_name', 'Uncategorized')
        grouped.setdefault(t, []).append(a['name'])
    return grouped


def export_pdf(tasks, output_path, project_name='Project'):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(letter),
        rightMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', parent=styles['Title'],
        fontSize=20, spaceAfter=12, textColor=colors.HexColor('#1a1a2e')
    )
    subtitle_style = ParagraphStyle(
        'Subtitle', parent=styles['Normal'],
        fontSize=9, textColor=colors.HexColor('#666666'), spaceAfter=20
    )
    status_header_style = ParagraphStyle(
        'StatusHeader', parent=styles['Heading2'],
        fontSize=13, spaceBefore=14, spaceAfter=6, textColor=white
    )
    task_name_style = ParagraphStyle(
        'TaskName', parent=styles['Normal'],
        fontSize=11, fontName='Helvetica-Bold', textColor=colors.HexColor('#1a1a2e')
    )
    body_style = ParagraphStyle(
        'Body', parent=styles['Normal'],
        fontSize=9, textColor=colors.HexColor('#333333'), leading=13
    )
    label_style = ParagraphStyle(
        'Label', parent=styles['Normal'],
        fontSize=8, textColor=colors.HexColor('#888888'), fontName='Helvetica-Bold'
    )

    story = []
    story.append(Paragraph(f'{project_name} — Task Report', title_style))
    story.append(Paragraph(
        f'Generated {datetime.now().strftime("%B %d, %Y at %I:%M %p")}',
        subtitle_style
    ))
    story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#cccccc')))
    story.append(Spacer(1, 16))

    # Group tasks by status (already sorted by priority from db query)
    by_status = {}
    status_meta = {}
    for task in tasks:
        sname = task.get('status_name') or 'No Status'
        scolor = task.get('status_color') or '#888888'
        if sname not in by_status:
            by_status[sname] = []
            status_meta[sname] = scolor
        by_status[sname].append(task)

    page_width = landscape(letter)[0] - 1.2 * inch

    for status_name, task_list in by_status.items():
        status_color_hex = status_meta[status_name]
        status_color = hex_to_color(status_color_hex)
        light_color = lighten(status_color_hex, 0.88)

        # Status header banner
        header_data = [[Paragraph(f'  {status_name}', status_header_style)]]
        header_table = Table(header_data, colWidths=[page_width])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), status_color),
            ('ROUNDEDCORNERS', [4]),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 6))

        for task in task_list:
            start = task.get('start_date', '')
            end = task.get('end_date', '')
            duration = duration_label(start, end)
            date_range = ''
            if start and end:
                date_range = f'{start} → {end}'
                if duration:
                    date_range += f'  ({duration})'
            elif start:
                date_range = f'Starts {start}'
            elif end:
                date_range = f'Ends {end}'

            grouped_attrs = group_attributes(task.get('attributes', []))
            attr_lines = []
            for type_name, attr_names in grouped_attrs.items():
                attr_lines.append(
                    Paragraph(f'<b>{type_name}:</b> {", ".join(attr_names)}', body_style)
                )

            left_col_items = [Paragraph(task['name'], task_name_style)]
            if task.get('description'):
                left_col_items.append(Spacer(1, 3))
                left_col_items.append(Paragraph(task['description'], body_style))
            if attr_lines:
                left_col_items.append(Spacer(1, 5))
                left_col_items += attr_lines
            subtasks = task.get('subtasks', [])
            if subtasks:
                left_col_items.append(Spacer(1, 5))
                for st in subtasks:
                    mark = '[x]' if st.get('is_done') else '[ ]'
                    left_col_items.append(Paragraph(f'{mark} {st["name"]}', body_style))

            right_col_items = []
            if date_range:
                right_col_items.append(Paragraph('DATE RANGE', label_style))
                right_col_items.append(Paragraph(date_range, body_style))

            row_data = [[left_col_items, right_col_items]]
            col_widths = [page_width * 0.65, page_width * 0.35]
            task_table = Table(row_data, colWidths=col_widths)
            task_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), light_color),
                ('LEFTPADDING', (0, 0), (0, -1), 14),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LINEAFTER', (-1, 0), (-1, -1), 0, colors.white),
                ('LINEBEFORE', (0, 0), (0, -1), 4, status_color),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(task_table)
            story.append(Spacer(1, 4))

        story.append(Spacer(1, 16))

    doc.build(story)
