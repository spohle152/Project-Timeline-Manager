from datetime import datetime, timedelta, date
import io
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
from PIL import Image

FIGURE_BG = '#f5f7fb'
SURFACE = '#ffffff'
TEXT_PRIMARY = '#172033'
TEXT_MUTED = '#667085'
GRID_COLOR = '#dfe5ee'
ACCENT = '#5b6cf9'


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


def text_color_for_rgb(rgb):
    """Choose readable text for a solid status-colored task bar."""
    luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    return TEXT_PRIMARY if luminance > 0.68 else '#ffffff'


def _letterbox_to_size(path, target_width, target_height):
    """Pad/center the saved chart onto an exact target_width x target_height
    canvas without distorting it, so any requested resolution or aspect
    ratio (e.g. 16:9, 4:3) can be produced regardless of the chart's own
    natural shape."""
    with Image.open(path) as img:
        img = img.convert('RGBA')
        scale = min(target_width / img.width, target_height / img.height)
        new_size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
        resized = img.resize(new_size, Image.LANCZOS)
        bg_rgb = tuple(round(c * 255) for c in hex_to_rgb(FIGURE_BG))
        canvas = Image.new('RGBA', (target_width, target_height), bg_rgb + (255,))
        offset = ((target_width - new_size[0]) // 2, (target_height - new_size[1]) // 2)
        canvas.paste(resized, offset, resized)
        canvas.convert('RGB').save(path, 'PNG')


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


def export_timeline(tasks, attribute_type_id, attr_type_name, range_start, range_end, output_path,
                     dpi=150, target_width=None, target_height=None):
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
    # Lane spacing stays stable, while the final bar height is calculated
    # after the chart's total height is known. This prevents a one-row chart
    # from stretching a task bar to fill most of the plot.
    MAX_BAR_H = 0.13
    LANE_H = 0.24
    ROW_PAD = 0.025
    LEFT_MARGIN = 2.2

    # Compute y positions
    y_positions = []
    y = 0
    for _, _, _, num_lanes in row_data:
        row_height = num_lanes * LANE_H + ROW_PAD
        y_positions.append((y, row_height, num_lanes))
        y += row_height

    total_height = y
    BAR_H = min(MAX_BAR_H, total_height * 0.14)
    fig_height = max(1.9, total_height * 0.50 + 1.35)
    total_days = (end_date - start_date).days

    fig_width = max(14, total_days * 0.15 + LEFT_MARGIN + 1)
    fig_width = min(fig_width, 40)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    fig.patch.set_facecolor(FIGURE_BG)
    ax.set_facecolor(SURFACE)

    # Date axis setup
    date_nums_start = mdates.date2num(datetime.combine(start_date, datetime.min.time()))
    date_nums_end = mdates.date2num(datetime.combine(end_date, datetime.min.time()))
    ax.set_xlim(date_nums_start, date_nums_end)
    ax.set_ylim(-ROW_PAD / 2, total_height)
    ax.invert_yaxis()

    # Date header formatting
    day_span = (end_date - start_date).days
    if day_span <= 30:
        date_format = '%b %d'
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, day_span // 10)))
    elif day_span <= 180:
        date_format = '%b %d'
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
    elif day_span <= 730:
        date_format = '%b %Y'
        ax.xaxis.set_major_locator(mdates.MonthLocator())
    else:
        date_format = '%Y'
        ax.xaxis.set_major_locator(mdates.YearLocator())

    date_formatter = mdates.DateFormatter(date_format)

    def format_date_tick(value, position=None):
        # The range-start date already appears in the subtitle. Hiding a tick
        # at that exact position prevents it colliding with the first interval.
        if mdates.num2date(value).date() == start_date:
            return ''
        return date_formatter(value, position)

    ax.xaxis.set_major_formatter(FuncFormatter(format_date_tick))
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position('top')
    plt.setp(ax.get_xticklabels(), rotation=0, ha='center', va='bottom')
    ax.tick_params(
        axis='x', which='major', top=True, bottom=False,
        labeltop=True, labelbottom=False, pad=7, labelsize=8,
        length=0, colors=TEXT_MUTED
    )
    ax.yaxis.set_visible(False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    # A light date grid keeps the schedule readable without dominating it.
    ax.xaxis.grid(True, color=GRID_COLOR, linewidth=0.7, linestyle='-')
    ax.set_axisbelow(True)

    # Draw today line if in range
    today = date.today()
    if start_date <= today <= end_date:
        today_num = mdates.date2num(datetime.combine(today, datetime.min.time()))
        ax.axvline(today_num, color=ACCENT, linewidth=1.5, linestyle='-',
                   alpha=0.85, zorder=6)
        ax.text(today_num, -ROW_PAD / 2, ' TODAY ', ha='center', va='bottom',
                fontsize=6.5, fontweight='bold', color='#ffffff', zorder=7,
                bbox=dict(boxstyle='round,pad=0.28,rounding_size=0.5',
                          facecolor=ACCENT, edgecolor='none'))

    legend_entries = {}

    for ri, (attr_name, task_list, lane_assigns, num_lanes) in enumerate(row_data):
        y0, row_height, _ = y_positions[ri]

        # Very subtle row tinting helps track long schedules across the page.
        bg_color = SURFACE if ri % 2 == 0 else '#f8faff'
        ax.barh(y0 + row_height / 2, date_nums_end - date_nums_start,
                left=date_nums_start, height=row_height,
                color=bg_color, edgecolor='none', zorder=0)

        # Row label on left
        ax.text(date_nums_start - (date_nums_end - date_nums_start) * 0.01,
                y0 + row_height / 2,
                attr_name, va='center', ha='right',
                fontsize=9, fontweight='semibold', color=TEXT_PRIMARY,
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

            # Rounded, solid bars give the timeline a cleaner card-like look.
            bar = mpatches.FancyBboxPatch(
                (s_num, bar_y - BAR_H / 2), width, BAR_H,
                boxstyle=f'round,pad=0,rounding_size={BAR_H * 0.50}',
                facecolor=rgb, edgecolor='none', linewidth=0,
                zorder=3, clip_on=True,
            )
            ax.add_patch(bar)

            # Task label - estimate how many characters actually fit inside
            # this bar's rendered width (a fraction of the axes, scaled by
            # how many of the chart's total days the bar covers).
            label = task['name']
            bar_center = s_num + width / 2
            text_color = text_color_for_rgb(rgb)
            avg_char_pts = 7.5 * 0.62
            axes_width_in = max(fig_width - LEFT_MARGIN, 1)
            bar_frac = width / total_days if total_days else 1
            max_chars = int(bar_frac * axes_width_in * 72 / avg_char_pts)
            if max_chars < 4:
                label = ''
            elif len(label) > max_chars:
                label = label[:max_chars - 1] + '…'

            if label:
                ax.text(bar_center, bar_y, label,
                        va='center', ha='center', fontsize=7.5,
                        color=text_color, fontweight='bold', zorder=5,
                        clip_on=True)

            sname = task.get('status_name') or 'Unknown'
            if sname not in legend_entries:
                legend_entries[sname] = mpatches.Patch(
                    facecolor=rgb, edgecolor='none', label=sname
                )

        # Row separator
        ax.axhline(y0 + row_height, color='#edf0f5', linewidth=0.7, zorder=1)

    # Title
    title = f'{attr_type_name} Timeline'
    subtitle = f'Through {end_date.strftime("%b %d, %Y")}'
    ax.set_title(title, fontsize=15, fontweight='bold', color=TEXT_PRIMARY,
                 pad=40, loc='left')
    ax.text(0, 1.30, subtitle, transform=ax.transAxes, fontsize=8.5,
            color=TEXT_MUTED, ha='left', va='bottom', clip_on=False)

    # Legend
    if legend_entries:
        legend = ax.legend(
            handles=list(legend_entries.values()),
            loc='upper right', fontsize=8, frameon=False,
            title='STATUS', title_fontsize=7.5,
            handlelength=1.1, handleheight=1.1,
            borderaxespad=0.2, labelspacing=0.55
        )
        legend.get_title().set_color(TEXT_MUTED)
        legend.get_title().set_fontweight('bold')
        for text in legend.get_texts():
            text.set_color(TEXT_PRIMARY)

    plt.tight_layout(pad=0.8)

    if target_width and target_height:
        # bbox_inches='tight' crops to the actual rendered content, so the
        # final pixel size can't be predicted from figsize * dpi alone.
        # Render once at a reference DPI to measure the real tight-bbox
        # size, then compute the DPI that scales the chart to fit the
        # requested resolution without distorting it.
        ref_dpi = 100
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=ref_dpi, bbox_inches='tight',
                    facecolor=fig.get_facecolor())
        buf.seek(0)
        with Image.open(buf) as probe:
            probe_w, probe_h = probe.size
        scale = min(target_width / probe_w, target_height / probe_h)
        dpi = max(10, ref_dpi * scale)

    fig.savefig(output_path, dpi=dpi, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close(fig)

    if target_width and target_height:
        _letterbox_to_size(output_path, target_width, target_height)
