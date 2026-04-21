"""
Conflict of Interest Checker
Polished dark-theme Tkinter UI with live bar graph,
filterable treeview, and CSV/PDF export.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import csv
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

PALETTE = {
    'bg':         '#1a1f35',
    'header_bg':  '#11152a',
    'panel':      '#222840',
    'fg':         '#e8eaf6',
    'muted':      '#7a85a0',
    'accent':     '#4a9cdd',
    'btn':        '#2e3a56',
    'btn_hover':  '#3a4f77',
    'entry_bg':   '#2a3047',
    'border':     '#3a4460',
    'high':       '#e05252',
    'medium':     '#e8a838',
    'low':        '#5aabcc',
    'alt_row':    '#222840',
}


class AutocompleteDropdown(ttk.Frame):
    def __init__(self, master, values, width=30):
        super().__init__(master)
        self.values   = values[:]
        self.filtered = values[:]

        self.entry  = ttk.Entry(self, width=width)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.button = ttk.Button(self, text="▼", width=2, command=self.toggle_popup)
        self.button.pack(side=tk.RIGHT)

        self.dropdown_frame = tk.Frame(
            self.winfo_toplevel(), bd=1, relief="solid",
            bg=PALETTE['entry_bg'], highlightbackground=PALETTE['border']
        )
        self.scrollbar = tk.Scrollbar(self.dropdown_frame, orient="vertical",
                                      bg=PALETTE['panel'], troughcolor=PALETTE['bg'])
        self.listbox = tk.Listbox(
            self.dropdown_frame, height=6,
            yscrollcommand=self.scrollbar.set,
            bg=PALETTE['entry_bg'], fg=PALETTE['fg'],
            selectbackground=PALETTE['accent'], selectforeground='#ffffff',
            borderwidth=0, highlightthickness=0, font=("Segoe UI", 9)
        )
        self.scrollbar.config(command=self.listbox.yview)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.dropdown_visible = False

        self.entry.bind("<KeyRelease>", self.on_keyrelease)
        self.entry.bind("<Down>",    self.on_down)
        self.entry.bind("<Up>",      self.on_up)
        self.entry.bind("<Return>",  self.on_return)
        self.entry.bind("<Escape>",  lambda e: self.hide_popup())
        self.listbox.bind("<ButtonRelease-1>", self.on_click)

    def toggle_popup(self):
        self.hide_popup() if self.dropdown_visible else self.show_popup(self.values)

    def show_popup(self, items):
        self.filtered = items[:]
        self.listbox.delete(0, tk.END)
        for item in items:
            self.listbox.insert(tk.END, item)
        toplevel = self.winfo_toplevel()
        ex  = self.entry.winfo_rootx()
        ey  = self.entry.winfo_rooty() + self.entry.winfo_height()
        rel_x = ex - toplevel.winfo_rootx()
        rel_y = ey - toplevel.winfo_rooty()
        width = self.entry.winfo_width() + self.button.winfo_width()
        self.dropdown_frame.place(x=rel_x, y=rel_y, width=width)
        self.dropdown_visible = True

    def hide_popup(self):
        self.dropdown_frame.place_forget()
        self.dropdown_visible = False

    def on_keyrelease(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape"):
            return
        typed   = self.entry.get().lower()
        matches = [v for v in self.values if typed in v.lower()]
        self.show_popup(matches) if matches else self.hide_popup()

    def on_down(self, event):
        if self.dropdown_visible and self.listbox.size() > 0:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(0)
            return "break"

    def on_up(self, event):
        return "break"

    def on_return(self, event):
        if self.dropdown_visible:
            cur = self.listbox.curselection()
            if cur:
                self.set_value(self.listbox.get(cur))
                return "break"

    def on_click(self, event):
        cur = self.listbox.curselection()
        if cur:
            self.set_value(self.listbox.get(cur))

    def set_value(self, value):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, value)
        self.hide_popup()
        self.event_generate("<<DropdownSelected>>")

    def get(self):
        return self.entry.get()

    def set_values(self, new_values):
        self.values   = new_values[:]
        self.filtered = new_values[:]


# ─────────────────────────────────────────────────────────────────────────────

class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Conflict of Interest Checker")
        self.geometry("1200x740")
        self.minsize(900, 600)
        self._apply_theme()

        self.all_results       = []
        self.officials_list    = ["Anyone"]
        self.confidence_levels = ["All", "High", "Medium", "Low"]
        self._reasoning_map    = {}
        self._graph_data       = {}

        self._build_ui()
        self._redraw_graph()

    # ── Theme ──────────────────────────────────────────────────────────────

    def _apply_theme(self):
        self.configure(bg=PALETTE['bg'])
        s = ttk.Style(self)
        s.theme_use('clam')

        s.configure('TFrame',      background=PALETTE['bg'])
        s.configure('TLabelframe', background=PALETTE['bg'],
                    bordercolor=PALETTE['border'], relief='ridge', borderwidth=2)
        s.configure('TLabelframe.Label', background=PALETTE['bg'],
                    foreground=PALETTE['accent'], font=('Segoe UI', 10, 'bold'))
        s.configure('TLabel', background=PALETTE['bg'], foreground=PALETTE['fg'],
                    font=('Segoe UI', 9))
        s.configure('TEntry',
                    fieldbackground=PALETTE['entry_bg'], foreground=PALETTE['fg'],
                    bordercolor=PALETTE['border'], insertcolor=PALETTE['fg'],
                    selectbackground=PALETTE['accent'], selectforeground='#ffffff')
        s.map('TEntry', fieldbackground=[('readonly', PALETTE['entry_bg'])])

        for name in ('TButton', 'Find.TButton', 'Dl.TButton', 'New.TButton'):
            s.configure(name, background=PALETTE['btn'], foreground=PALETTE['fg'],
                        relief='flat', borderwidth=0, padding=(10, 5),
                        font=('Segoe UI', 9, 'bold'))
            s.map(name,
                  background=[('active', PALETTE['btn_hover']), ('pressed', PALETTE['accent'])],
                  foreground=[('active', PALETTE['fg'])])

        s.configure('Treeview',
                    background=PALETTE['bg'], foreground=PALETTE['fg'],
                    fieldbackground=PALETTE['bg'], borderwidth=0,
                    font=('Segoe UI', 9), rowheight=26)
        s.configure('Treeview.Heading',
                    background=PALETTE['panel'], foreground=PALETTE['accent'],
                    relief='flat', font=('Segoe UI', 9, 'bold'))
        s.map('Treeview',
              background=[('selected', PALETTE['accent'])],
              foreground=[('selected', '#ffffff')])
        s.map('Treeview.Heading', background=[('active', PALETTE['border'])])

        for orient in ('Vertical', 'Horizontal'):
            s.configure(f'{orient}.TScrollbar',
                        background=PALETTE['panel'], troughcolor=PALETTE['bg'],
                        borderwidth=0, arrowcolor=PALETTE['muted'])

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ────────────────────────────────────────
        hdr = tk.Frame(self, bg=PALETTE['header_bg'], height=54)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        tk.Label(hdr, text="CONFLICT  CHECKER",
                 bg=PALETTE['header_bg'], fg=PALETTE['accent'],
                 font=('Segoe UI', 13, 'bold')).pack(side=tk.LEFT, padx=24)
        tk.Label(hdr, text="Sacramento County Board of Supervisors · Form 700 Analysis",
                 bg=PALETTE['header_bg'], fg=PALETTE['muted'],
                 font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=0)

        self.hdr_stats = tk.Label(hdr, text="No data loaded — use Import JSON",
                                   bg=PALETTE['header_bg'], fg=PALETTE['muted'],
                                   font=('Segoe UI', 9))
        self.hdr_stats.pack(side=tk.RIGHT, padx=24)

        # accent underline
        tk.Frame(self, bg=PALETTE['accent'], height=2).pack(fill=tk.X)

        # ── Body ──────────────────────────────────────────
        body = tk.Frame(self, bg=PALETTE['bg'])
        body.pack(fill=tk.BOTH, expand=True)

        # ── Sidebar ───────────────────────────────────────
        sidebar = tk.Frame(body, bg=PALETTE['panel'], width=220)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        tk.Frame(body, bg=PALETTE['border'], width=1).pack(side=tk.LEFT, fill=tk.Y)

        pad = tk.Frame(sidebar, bg=PALETTE['panel'])
        pad.pack(fill=tk.BOTH, expand=True, padx=18, pady=24)

        def section_label(text):
            tk.Label(pad, text=text, bg=PALETTE['panel'], fg=PALETTE['muted'],
                     font=('Segoe UI', 7, 'bold')).pack(anchor='w')

        section_label("OFFICIAL")
        self.juris = AutocompleteDropdown(pad, self.officials_list, width=22)
        self.juris.pack(fill=tk.X, pady=(4, 16))

        section_label("CONFIDENCE")
        self.names = AutocompleteDropdown(pad, self.confidence_levels, width=22)
        self.names.pack(fill=tk.X, pady=(4, 22))

        self._btn(pad, "Find Conflicts",  "Find.TButton",  self.find_conflicts).pack(fill=tk.X, pady=(0, 6))
        self._btn(pad, "Import JSON",     "Find.TButton",  self.import_json).pack(fill=tk.X)

        tk.Frame(pad, bg=PALETTE['border'], height=1).pack(fill=tk.X, pady=20)

        self.report_label = tk.Label(pad, text="", bg=PALETTE['panel'],
                                      fg=PALETTE['accent'], font=('Segoe UI', 9))
        self.report_label.pack(anchor='w', pady=(0, 10))

        self.download_btn = self._btn(pad, "Download Report", "Dl.TButton", self.open_download_page)
        # hidden until results exist

        # ── Right panel ───────────────────────────────────
        right = tk.Frame(body, bg=PALETTE['bg'])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Graph card
        graph_card = tk.Frame(right, bg=PALETTE['panel'],
                               highlightthickness=1,
                               highlightbackground=PALETTE['border'])
        graph_card.pack(fill=tk.X, padx=18, pady=(18, 0))

        graph_top = tk.Frame(graph_card, bg=PALETTE['panel'])
        graph_top.pack(fill=tk.X, padx=14, pady=(10, 4))
        self.graph_title = tk.Label(graph_top, text="OVERVIEW",
                                     bg=PALETTE['panel'], fg=PALETTE['muted'],
                                     font=('Segoe UI', 7, 'bold'))
        self.graph_title.pack(side=tk.LEFT)
        self.graph_sub = tk.Label(graph_top, text="",
                                   bg=PALETTE['panel'], fg=PALETTE['muted'],
                                   font=('Segoe UI', 7))
        self.graph_sub.pack(side=tk.RIGHT)

        self.canvas = tk.Canvas(graph_card, bg=PALETTE['panel'], height=155,
                                 highlightthickness=0)
        self.canvas.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.canvas.bind("<Configure>", lambda e: self._redraw_graph())

        # Treeview card
        tree_card = tk.Frame(right, bg=PALETTE['bg'])
        tree_card.pack(fill=tk.BOTH, expand=True, padx=18, pady=(12, 0))
        tree_card.rowconfigure(0, weight=1)
        tree_card.columnconfigure(0, weight=1)

        cols = ("Confidence", "Official", "Entity", "Keywords", "Source", "Page")
        self.tree = ttk.Treeview(tree_card, columns=cols, show="headings", selectmode="browse")
        for col in cols:
            self.tree.heading(col, text=col)
        self.tree.column("Confidence", width=95,  minwidth=70,  anchor="center")
        self.tree.column("Official",   width=135, minwidth=100)
        self.tree.column("Entity",     width=160, minwidth=100)
        self.tree.column("Keywords",   width=120, minwidth=80)
        self.tree.column("Source",     width=230, minwidth=120)
        self.tree.column("Page",       width=52,  minwidth=40,  anchor="center")

        vsb = ttk.Scrollbar(tree_card, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_card, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.tree.tag_configure('high',   foreground=PALETTE['high'])
        self.tree.tag_configure('medium', foreground=PALETTE['medium'])
        self.tree.tag_configure('low',    foreground=PALETTE['low'])
        self.tree.tag_configure('alt',    background=PALETTE['alt_row'])
        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)

        # Detail strip
        detail_card = tk.Frame(right, bg=PALETTE['panel'],
                                highlightthickness=1,
                                highlightbackground=PALETTE['border'])
        detail_card.pack(fill=tk.X, padx=18, pady=(10, 16))

        tk.Label(detail_card, text="REASONING", bg=PALETTE['panel'],
                 fg=PALETTE['muted'], font=('Segoe UI', 7, 'bold')).pack(
            anchor='w', padx=12, pady=(8, 0))

        self.detail = tk.Text(
            detail_card, height=3, wrap=tk.WORD, state=tk.DISABLED,
            bg=PALETTE['panel'], fg=PALETTE['fg'], relief="flat",
            font=("Segoe UI", 9), padx=12, pady=6,
            insertbackground=PALETTE['fg'], borderwidth=0, highlightthickness=0,
        )
        self.detail.pack(fill=tk.X, pady=(2, 8))

    def _btn(self, parent, text, style, cmd):
        """Create a styled button with hover bindings."""
        b = ttk.Button(parent, text=text, style=style, command=cmd)
        b.bind("<Enter>", lambda e: ttk.Style().configure(style, background=PALETTE['btn_hover']))
        b.bind("<Leave>", lambda e: ttk.Style().configure(style, background=PALETTE['btn']))
        return b

    # ── Graph ──────────────────────────────────────────────────────────────

    def _init_graph(self):
        """Show overall conflict distribution after a file is loaded."""
        counts = {}
        for r in self.all_results:
            for o in r['form700']['officials']:
                counts[o] = counts.get(o, 0) + 1
        self._graph_data = {'type': 'officials', 'data': counts}
        self.graph_title.config(text="CONFLICTS BY OFFICIAL")
        self.graph_sub.config(text=f"all {len(self.all_results)} records")
        self.after(50, self._redraw_graph)

    def _update_graph(self, results):
        official = self.juris.get().strip()
        if official.lower() in ('anyone', ''):
            # Show per-official totals from full dataset, ignoring confidence filter
            counts = {}
            for r in self.all_results:
                for o in r['form700']['officials']:
                    counts[o] = counts.get(o, 0) + 1
            self._graph_data = {'type': 'officials', 'data': counts}
            self.graph_title.config(text="CONFLICTS BY OFFICIAL")
        else:
            # Show full confidence breakdown for this official, ignoring confidence filter
            counts = {'High': 0, 'Medium': 0, 'Low': 0}
            for r in self.all_results:
                if official in r['form700']['officials']:
                    c = r['conflict']['confidence'].capitalize()
                    if c in counts:
                        counts[c] += 1
            self._graph_data = {'type': 'confidence', 'data': counts}
            self.graph_title.config(text=f"CONFIDENCE BREAKDOWN  ·  {official.upper()}")
        self.graph_sub.config(text=f"{len(results)} result{'s' if len(results) != 1 else ''} shown")
        self._redraw_graph()

    def _redraw_graph(self):
        cv = self.canvas
        cv.delete('all')
        W = cv.winfo_width()
        H = cv.winfo_height()
        if W < 20:
            return

        data  = self._graph_data.get('data', {})
        gtype = self._graph_data.get('type', 'officials')

        if not data:
            cv.create_text(W // 2, H // 2,
                           text="Run a search to populate the graph",
                           fill=PALETTE['muted'], font=('Segoe UI', 10), anchor='center')
            return

        PAD_L, PAD_R, PAD_T, PAD_B = 44, 16, 14, 34
        labels = list(data.keys())
        values = list(data.values())
        max_v  = max(values) if values else 1
        n      = len(labels)
        cw     = W - PAD_L - PAD_R
        ch     = H - PAD_T - PAD_B

        conf_colors = {
            'High':   PALETTE['high'],
            'Medium': PALETTE['medium'],
            'Low':    PALETTE['low'],
        }

        # Y grid
        steps = min(max_v, 4)
        for i in range(steps + 1):
            y     = PAD_T + ch - (i / steps) * ch
            label = str(int(max_v * i / steps))
            cv.create_line(PAD_L, y, W - PAD_R, y,
                           fill='#2e3a56', width=1, dash=(2, 4))
            cv.create_text(PAD_L - 6, y, text=label,
                           fill=PALETTE['muted'], font=('Segoe UI', 7), anchor='e')

        # X axis
        cv.create_line(PAD_L, PAD_T + ch, W - PAD_R, PAD_T + ch,
                       fill=PALETTE['border'], width=1)

        # Bars
        slot_w = cw / n
        bar_w  = slot_w * 0.55

        for i, (lbl, val) in enumerate(zip(labels, values)):
            xc     = PAD_L + (i + 0.5) * slot_w
            bh     = (val / max_v) * ch if max_v else 0
            x0, x1 = xc - bar_w / 2, xc + bar_w / 2
            y0, y1 = PAD_T + ch - bh, PAD_T + ch

            color = conf_colors.get(lbl, PALETTE['accent']) if gtype == 'confidence' else PALETTE['accent']
            light = self._lighten(color, 50)

            # subtle drop shadow
            cv.create_rectangle(x0 + 2, y0 + 3, x1 + 2, y1,
                                 fill='#0d1020', outline='')
            # bar body
            cv.create_rectangle(x0, y0, x1, y1, fill=color, outline='')
            # top highlight strip
            cv.create_rectangle(x0, y0, x1, y0 + 3, fill=light, outline='')

            # value label
            if bh > 14:
                cv.create_text(xc, y0 - 5, text=str(val),
                               fill=PALETTE['fg'], font=('Segoe UI', 8, 'bold'), anchor='s')

            # x label
            short = (lbl[:13] + '…') if len(lbl) > 14 else lbl
            cv.create_text(xc, PAD_T + ch + 8, text=short,
                           fill=PALETTE['muted'], font=('Segoe UI', 7), anchor='n')

    @staticmethod
    def _lighten(hex_color, amount=40):
        h = hex_color.lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return '#{:02x}{:02x}{:02x}'.format(
            min(255, r + amount), min(255, g + amount), min(255, b + amount))

    # ── Event handlers ─────────────────────────────────────────────────────

    def find_conflicts(self):
        official   = self.juris.get().strip()
        confidence = self.names.get().strip().lower()

        if not official:
            messagebox.showwarning("Missing Input", "Please select an official.")
            return

        filtered = [
            r for r in self.all_results
            if (official.lower() == 'anyone' or official in r['form700']['officials'])
            and (confidence in ('', 'all') or r['conflict']['confidence'] == confidence)
        ]

        for row in self.tree.get_children():
            self.tree.delete(row)
        self.detail.configure(state=tk.NORMAL)
        self.detail.delete("1.0", tk.END)
        self.detail.configure(state=tk.DISABLED)

        for i, r in enumerate(filtered):
            conf     = r['conflict']['confidence']
            officers = ", ".join(r['form700']['officials'])
            entities = ", ".join(r['form700']['entities'])
            keywords = ", ".join(r['keywords_matched'])
            source   = r['source']['file'].replace('.txt', '').replace('.pdf', '')[-40:]
            page     = r['source']['page']
            tags     = (conf, 'alt') if i % 2 else (conf,)
            self.tree.insert('', tk.END, iid=str(i),
                             values=(conf.capitalize(), officers, entities,
                                     keywords, source, page),
                             tags=tags)

        self._reasoning_map = {
            str(i): r['conflict']['reasoning'] for i, r in enumerate(filtered)
        }

        count = len(filtered)
        self.report_label.config(text=f"{count} conflict{'s' if count != 1 else ''} found")
        if count > 0:
            self.download_btn.pack(fill=tk.X)
        else:
            self.download_btn.pack_forget()

        self._update_graph(filtered)
        self.hdr_stats.config(text=f"{len(self.all_results)} records · {count} shown")

    def _on_row_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        reasoning = self._reasoning_map.get(sel[0], "")
        self.detail.configure(state=tk.NORMAL)
        self.detail.delete("1.0", tk.END)
        self.detail.insert(tk.END, reasoning)
        self.detail.configure(state=tk.DISABLED)

    def reset_app(self, win):
        win.destroy()
        self.juris.entry.delete(0, tk.END)
        self.names.entry.delete(0, tk.END)
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.detail.configure(state=tk.NORMAL)
        self.detail.delete("1.0", tk.END)
        self.detail.configure(state=tk.DISABLED)
        self.report_label.config(text="")
        self.download_btn.pack_forget()
        self._reasoning_map = {}
        self._init_graph()
        self.hdr_stats.config(text=f"{len(self.all_results)} records loaded")

    def import_json(self):
        path = filedialog.askopenfilename(
            title="Select conflict JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                self.all_results = data
            elif isinstance(data, dict) and 'results' in data:
                self.all_results = data['results']
            else:
                messagebox.showerror("Invalid File",
                                     "JSON must be a flat array or an object with a 'results' key.")
                return

            seen = set()
            self.officials_list = ["Anyone"]
            for r in self.all_results:
                for o in r['form700']['officials']:
                    if o not in seen:
                        seen.add(o)
                        self.officials_list.append(o)

            self.juris.set_values(self.officials_list)
            self.juris.entry.delete(0, tk.END)
            self.names.entry.delete(0, tk.END)
            for row in self.tree.get_children():
                self.tree.delete(row)
            self.detail.configure(state=tk.NORMAL)
            self.detail.delete("1.0", tk.END)
            self.detail.configure(state=tk.DISABLED)
            self.report_label.config(text=f"Loaded {len(self.all_results)} records")
            self.download_btn.pack_forget()
            self._reasoning_map = {}
            self._init_graph()
            self.hdr_stats.config(text=f"{len(self.all_results)} records loaded")
        except Exception as exc:
            messagebox.showerror("Load Error", str(exc))

    # ── Export ─────────────────────────────────────────────────────────────

    def _current_rows(self):
        rows = []
        for iid in self.tree.get_children():
            vals = self.tree.item(iid, 'values')
            rows.append({
                'Confidence': vals[0], 'Official': vals[1], 'Entity':    vals[2],
                'Keywords':   vals[3], 'Source':   vals[4], 'Page':      vals[5],
                'Reasoning':  self._reasoning_map.get(iid, ''),
            })
        return rows

    def _export_csv(self, win):
        path = filedialog.asksaveasfilename(
            parent=win, title="Save CSV", defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not path:
            return
        fields = ['Confidence', 'Official', 'Entity', 'Keywords', 'Source', 'Page', 'Reasoning']
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(self._current_rows())
            messagebox.showinfo("Saved", f"CSV saved to:\n{path}", parent=win)
            win.destroy()
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc), parent=win)

    def _export_pdf(self, win):
        path = filedialog.asksaveasfilename(
            parent=win, title="Save PDF", defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if not path:
            return
        rows = self._current_rows()
        try:
            doc    = SimpleDocTemplate(path, pagesize=letter,
                                       leftMargin=0.5*inch, rightMargin=0.5*inch,
                                       topMargin=0.6*inch, bottomMargin=0.6*inch)
            styles = getSampleStyleSheet()
            title_style  = ParagraphStyle('t', parent=styles['Heading1'], fontSize=14,
                                          textColor=colors.HexColor('#1a1f35'), spaceAfter=6)
            cell_style   = ParagraphStyle('c', parent=styles['Normal'], fontSize=7.5, leading=10)
            reason_style = ParagraphStyle('r', parent=styles['Normal'], fontSize=7, leading=9,
                                          textColor=colors.HexColor('#444444'))

            conf_colors_pdf = {
                'High':   colors.HexColor(PALETTE['high']),
                'Medium': colors.HexColor(PALETTE['medium']),
                'Low':    colors.HexColor(PALETTE['low']),
            }

            story = [
                Paragraph("Conflict of Interest Report", title_style),
                Paragraph(f"{len(rows)} result(s) exported", styles['Normal']),
                Spacer(1, 0.2*inch),
            ]

            header = ['Confidence', 'Official', 'Entity', 'Keywords', 'Source', 'Pg', 'Reasoning']
            table_data = [header] + [
                [Paragraph(r['Confidence'], cell_style),
                 Paragraph(r['Official'],   cell_style),
                 Paragraph(r['Entity'],     cell_style),
                 Paragraph(r['Keywords'],   cell_style),
                 Paragraph(r['Source'],     cell_style),
                 Paragraph(str(r['Page']),  cell_style),
                 Paragraph(r['Reasoning'],  reason_style)]
                for r in rows
            ]

            col_widths = [0.7*inch, 1.0*inch, 1.1*inch, 1.0*inch, 1.5*inch, 0.3*inch, 2.0*inch]
            tbl = Table(table_data, colWidths=col_widths, repeatRows=1)

            style_cmds = [
                ('BACKGROUND',    (0, 0), (-1, 0), colors.HexColor('#1a1f35')),
                ('TEXTCOLOR',     (0, 0), (-1, 0), colors.HexColor(PALETTE['accent'])),
                ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE',      (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('ROWBACKGROUNDS',(0, 1), (-1,-1), [colors.HexColor('#f7f7f7'), colors.white]),
                ('GRID',          (0, 0), (-1,-1), 0.25, colors.HexColor('#cccccc')),
                ('VALIGN',        (0, 0), (-1,-1), 'TOP'),
                ('LEFTPADDING',   (0, 0), (-1,-1), 4),
                ('RIGHTPADDING',  (0, 0), (-1,-1), 4),
                ('TOPPADDING',    (0, 1), (-1,-1), 4),
                ('BOTTOMPADDING', (0, 1), (-1,-1), 4),
            ]
            for i, r in enumerate(rows, start=1):
                c = conf_colors_pdf.get(r['Confidence'], colors.black)
                style_cmds += [('TEXTCOLOR', (0,i), (0,i), c),
                                ('FONTNAME',  (0,i), (0,i), 'Helvetica-Bold')]
            tbl.setStyle(TableStyle(style_cmds))
            story.append(tbl)
            doc.build(story)
            messagebox.showinfo("Saved", f"PDF saved to:\n{path}", parent=win)
            win.destroy()
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc), parent=win)

    def open_download_page(self):
        win = tk.Toplevel(self)
        win.title("Download Report")
        win.geometry("340x210")
        win.resizable(False, False)
        win.configure(bg=PALETTE['bg'])

        tk.Label(win, text="Export current results as:",
                 bg=PALETTE['bg'], fg=PALETTE['fg'],
                 font=('Segoe UI', 10)).pack(pady=(22, 14))

        self._btn(win, "Download CSV", "Find.TButton",
                  lambda: self._export_csv(win)).pack(fill=tk.X, padx=40, pady=4)
        self._btn(win, "Download PDF", "Dl.TButton",
                  lambda: self._export_pdf(win)).pack(fill=tk.X, padx=40, pady=4)
        self._btn(win, "New Search",   "New.TButton",
                  lambda: self.reset_app(win)).pack(fill=tk.X, padx=40, pady=(10, 4))


if __name__ == "__main__":
    app = App()
    app.mainloop()
