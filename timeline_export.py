from datetime import datetime, timedelta, date
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates


def parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError:
        return None


def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4))


def lighten_rgb(rgb, factor=0.4):
    return tuple(c + (1 - c) * factor for c in rgb)


def natural_sort_key(value):
    """Sort text alphabetically while treating embedded digits numerically."""
    return [int(part) if part.isdigit() else part.casefold()
            for part in re.split(r'(\d+)', value or '')]


def assign_lanes(task_list):
    lanes = []
    task_lanes = []
    for task in task_list:
        start = parse_date(task.get('start_date'))
        end = parse_date(task.get('end_date'))
        placed = False
        for li, lane_end in enumerate(lanes):
            if start is None or lane_end is None or start > lane_end:
                lanes[li] = end
                task_lanes.append(li)
                placed = True
                break
        if not placed:
            lanes.append(end)
            task_lanes.append(len(lanes) - 1)
    return task_lanes, len(lanes)


def export_timeline(tasks, attribute_type_id, attr_type_name, range_start, range_end, output_path):
    start_date = parse_date(range_start)
    end_date = parse_date(range_end)
    if not start_date or not end_date or start_date >= end_date:
        raise ValueError('Invalid date range')

    # Collect attributes of the chosen type
    attr_map = {}  # attr_id -> attr_name
    for task in tasks:
        for a in task.get('attributes', []):
            if str(a.get('type_id')) == str(attribute_type_id):
                attr_map[a['id']] = a['name']

    if not attr_map:
        raise ValueError('No attributes found for the selected type')

    # Build rows: {attr_name: [task, ...]}
    rows = {name: [] for name in attr_map.values()}
    for task in tasks:
        s = parse_date(task.get('start_date'))
        e = parse_date(task.get('end_date'))
        if not s or not e:
            continue
        if e < start_date or s > end_date:
            continue
        s = max(s, start_date)
        e = min(e, end_date)
        for a in task.get('attributes', []):
            if str(a.get('type_id')) == str(attribute_type_id):
                aname = a['name']
                if aname in rows:
                    rows[aname].append({**task, '_clip_start': s, '_clip_end': e})

    # Remove empty rows
    rows = {k: v for k, v in rows.items() if v}
    if not rows:
        raise ValueError('No tasks fall within the selected date range for this attribute type')

    # Compute lane layout per row
    row_data = []  # list of (attr_name, task_list, lane_assignments, num_lanes)
    for attr_name in sorted(rows, key=natural_sort_key):
        task_list = rows[attr_name]
        sorted_tasks = sorted(task_list, key=lambda t: t['_clip_start'])
        lane_assigns, num_lanes = assign_lanes(sorted_tasks)
        row_data.append((attr_name, sorted_tasks, lane_assigns, num_lanes))

    # Keep each task close to its row boundaries so the chart reads as a
    # compact grid instead of a collection of floating bars.
    BAR_H = 0.29
    LANE_H = 0.34
    ROW_PAD = 0.06
    LEFT_MARGIN = 2.2

    # Compute y positions
    y_positions = []
    y = 0
    for _, _, _, num_lanes in row_data:
        row_height = num_lanes * LANE_H + ROW_PAD
        y_positions.append((y, row_height, num_lanes))
        y += row_height

    total_height = y
    fig_height = max(1.9, total_height * 0.50 + 1.35)
    total_days = (end_date - start_date).days

    fig_width = max(14, total_days * 0.15 + LEFT_MARGIN + 1)
    fig_width = min(fig_width, 40)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    fig.patch.set_facecolor('#f8f9fa')
    ax.set_facecolor('#f8f9fa')

    # Date axis setup
    date_nums_start = mdates.date2num(datetime.combine(start_date, datetime.min.time()))
    date_nums_end = mdates.date2num(datetime.combine(end_date, datetime.min.time()))
    ax.set_xlim(date_nums_start, date_nums_end)
    ax.set_ylim(-ROW_PAD / 2, total_height)
    ax.invert_yaxis()

    # Date header formatting
    day_span = (end_date - start_date).days
    if day_span <= 30:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, day_span // 10)))
    elif day_span <= 180:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
    elif day_span <= 730:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        ax.xaxis.set_major_locator(mdates.YearLocator())

    ax.xaxis.tick_top()
    ax.xaxis.set_label_position('top')
    plt.setp(ax.get_xticklabels(), rotation=0, ha='center', va='bottom')
    ax.tick_params(
        axis='x', which='major', top=True, bottom=False,
        labeltop=True, labelbottom=False, pad=7, labelsize=8,
        length=0, colors='#4b5563'
    )
    ax.yaxis.set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_color('#b8c0cc')
    ax.spines['top'].set_linewidth(0.9)
    ax.spines['bottom'].set_color('#b8c0cc')

    # Solid grid lines visually connect each date header to the task rows.
    ax.xaxis.grid(True, color='#d9dee7', linewidth=0.7, linestyle='-')
    ax.set_axisbelow(True)

    # Draw today line if in range
    today = date.today()
    if start_date <= today <= end_date:
        today_num = mdates.date2num(datetime.combine(today, datetime.min.time()))
        ax.axvline(today_num, color='#e74c3c', linewidth=1.5, linestyle='-', alpha=0.7, zorder=5)

    legend_entries = {}

    for ri, (attr_name, task_list, lane_assigns, num_lanes) in enumerate(row_data):
        y0, row_height, _ = y_positions[ri]

        # Row background alternating
        bg_color = '#ffffff' if ri % 2 == 0 else '#f0f2f5'
        ax.barh(y0 + row_height / 2, date_nums_end - date_nums_start,
                left=date_nums_start, height=row_height,
                color=bg_color, alpha=0.6, zorder=0)

        # Row label on left
        ax.text(date_nums_start - (date_nums_end - date_nums_start) * 0.01,
                y0 + row_height / 2,
                attr_name, va='center', ha='right',
                fontsize=9, fontweight='bold', color='#333333',
                clip_on=False)

        # Draw task bars
        for ti, (task, lane) in enumerate(zip(task_list, lane_assigns)):
            bar_y = y0 + lane * LANE_H + LANE_H / 2

            s_dt = datetime.combine(task['_clip_start'], datetime.min.time())
            e_dt = datetime.combine(task['_clip_end'], datetime.min.time())
            s_num = mdates.date2num(s_dt)
            e_num = mdates.date2num(e_dt)
            width = max(e_num - s_num, 0.3)

            status_color = task.get('status_color') or '#7f8c8d'
            rgb = hex_to_rgb(status_color)
            light_rgb = lighten_rgb(rgb, 0.55)

            # Bar
            ax.barh(bar_y, width, left=s_num, height=BAR_H,
                    color=light_rgb, edgecolor=rgb, linewidth=1.2,
                    zorder=3, align='center')

            # Task label
            label = task['name']
            bar_center = s_num + width / 2
            text_color = '#1a1a2e'
            char_width_est = width / (fig_width / fig.get_dpi() * 72 / 7)
            if len(label) > int(char_width_est * 0.8) and int(char_width_est * 0.8) > 3:
                label = label[:int(char_width_est * 0.8) - 2] + '…'

            ax.text(bar_center, bar_y, label,
                    va='center', ha='center', fontsize=7.5,
                    color=text_color, fontweight='semibold', zorder=5,
                    clip_on=True)

            sname = task.get('status_name') or 'Unknown'
            if sname not in legend_entries:
                legend_entries[sname] = mpatches.Patch(
                    facecolor=light_rgb, edgecolor=rgb, linewidth=1.2, label=sname
                )

        # Row separator
        ax.axhline(y0 + row_height, color='#cccccc', linewidth=0.7, zorder=1)

    # Title
    title = f'{attr_type_name} Timeline  ·  {start_date.strftime("%b %d, %Y")} – {end_date.strftime("%b %d, %Y")}'
    ax.set_title(title, fontsize=13, fontweight='bold', color='#1a1a2e',
                 pad=36, loc='left')

    # Legend
    if legend_entries:
        legend = ax.legend(
            handles=list(legend_entries.values()),
            loc='upper right', fontsize=8,
            framealpha=0.9, edgecolor='#cccccc',
            title='Status', title_fontsize=8
        )

    plt.tight_layout(pad=0.8)
    fig.savefig(output_path, dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close(fig)
