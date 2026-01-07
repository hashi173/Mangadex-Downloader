import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
from PIL import Image, ImageTk

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.mangadex_api import MangaDexAPI
from downloader.turbo_downloader import TurboDownloader


class ModernButton(tk.Canvas):
    """Modern button with rounded corners"""

    def __init__(self, parent, text, command, bg='#3B82F6', width=140, height=40):
        super().__init__(parent, width=width, height=height, bg=parent['bg'],
                         highlightthickness=0, cursor='hand2')

        self.bg = bg
        self.hover_bg = self.lighten_color(bg, 1.15)
        self.command = command
        self.text = text
        self.enabled = True
        self.width = width
        self.height = height

        # Draw rounded button
        self.create_rounded_rect(0, 0, width, height, radius=10, fill=bg, outline='', tags='main')
        self.text_id = self.create_text(width // 2, height // 2, text=text,
                                        fill='white', font=('Segoe UI', 10, 'bold'), tags='text')

        self.bind('<Enter>', self.on_enter)
        self.bind('<Leave>', self.on_leave)
        self.bind('<Button-1>', self.on_click)

    def create_rounded_rect(self, x1, y1, x2, y2, radius=25, **kwargs):
        points = [x1 + radius, y1,
                  x2 - radius, y1,
                  x2, y1,
                  x2, y1 + radius,
                  x2, y2 - radius,
                  x2, y2,
                  x2 - radius, y2,
                  x1 + radius, y2,
                  x1, y2,
                  x1, y2 - radius,
                  x1, y1 + radius,
                  x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)

    def lighten_color(self, hex_color, factor):
        """FIXED: Remove ALL spaces from hex color"""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
        r = min(255, int(r * factor))
        g = min(255, int(g * factor))
        b = min(255, int(b * factor))
        return '#{:02x}{:02x}{:02x}'.format(r, g, b)

    def on_enter(self, e):
        if self.enabled:
            self.itemconfig('main', fill=self.hover_bg)

    def on_leave(self, e):
        if self.enabled:
            self.itemconfig('main', fill=self.bg)

    def on_click(self, e):
        if self.enabled and self.command:
            self.command()

    def set_state(self, state):
        self.enabled = (state == 'normal')
        if self.enabled:
            self.itemconfig('main', fill=self.bg)
            self.itemconfig('text', fill='white')
        else:
            self.itemconfig('main', fill='#CBD5E1')
            self.itemconfig('text', fill='#94A3B8')


class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("MangaDex Downloader Pro")

        # Window setup
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        window_width = min(1600, int(screen_width * 0.85))
        window_height = min(900, int(screen_height * 0.90))

        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.minsize(1500, 850)

        # Modern color palette
        self.colors = {
            'bg': '#0F172A',
            'bg_light': '#1E293B',
            'sidebar':  '#FFFFFF',
            'panel': '#FFFFFF',
            'accent': '#3B82F6',
            'accent2': '#8B5CF6',
            'success': '#10B981',
            'warning': '#F59E0B',
            'error': '#EF4444',
            'text': '#1F2937',
            'text_secondary': '#6B7280',
        }

        self.root.configure(bg=self.colors['bg'])

        # API and Downloader
        self.api = MangaDexAPI()
        self.downloader = TurboDownloader(max_workers=10)  # TURBO MODE

        # Data
        self.selected_manga = None
        self.chapters = []
        self.output_dir = os.path.join(os.getcwd(), "downloads")
        self.cover_photo = None
        self.is_downloading = False

        self.setup_ui()

    def setup_ui(self):
        """Setup compact UI - fit in one screen"""

        # Gradient top bar
        top_bar = tk.Canvas(self.root, height=3, bg=self.colors['bg'], highlightthickness=0)
        top_bar.pack(fill=tk.X)
        top_bar.create_rectangle(0, 0, 2000, 3, fill=self. colors['accent'], outline='')

        # Main container
        main_bg = tk.Frame(self.root, bg=self.colors['bg'])
        main_bg.pack(fill=tk.BOTH, expand=True)

        # Compact header
        header = tk.Canvas(main_bg, height=60, bg=self.colors['bg'], highlightthickness=0)
        header.pack(fill=tk.X, padx=15, pady=(10, 0))
        header.create_rectangle(0, 0, 2000, 60, fill=self.colors['bg_light'], outline='')
        header.create_text(20, 30, text="📚 MangaDex Downloader Pro",
                           font=('Segoe UI', 18, 'bold'), anchor='w', fill='white')

        self.header_status = header.create_text(1450, 30, text="● Ready",
                                                font=('Segoe UI', 10), anchor='e', fill='#10B981')

        # Content
        content = tk.Frame(main_bg, bg=self.colors['bg'])
        content.pack(fill=tk. BOTH, expand=True, padx=15, pady=10)

        # Sidebar
        self.sidebar = tk.Frame(content, bg='white', width=340)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.sidebar.pack_propagate(False)

        # Main area
        main_area = tk.Frame(content, bg=self.colors['bg'])
        main_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.setup_sidebar()
        self.setup_main_area(main_area)

    def setup_sidebar(self):
        """Compact sidebar"""
        inner = tk.Frame(self.sidebar, bg='white')
        inner.pack(fill=tk. BOTH, expand=True, padx=15, pady=15)

        # Cover
        cover_frame = tk.Frame(inner, bg='#F1F5F9')
        cover_frame.pack(pady=(0, 10))

        self.cover_label = tk.Label(cover_frame,
                                    text="📚\n\nNo Cover",
                                    font=('Segoe UI', 10),
                                    bg='#F8FAFC',
                                    fg=self.colors['text_secondary'],
                                    width=20,
                                    height=14)
        self.cover_label.pack(padx=2, pady=2)

        # Divider
        tk.Frame(inner, bg='#E5E7EB', height=1).pack(fill=tk.X, pady=10)

        # Info
        self.manga_title_label = tk.Label(inner,
                                          text="No Manga Selected",
                                          font=('Segoe UI', 11, 'bold'),
                                          bg='white',
                                          fg=self.colors['text'],
                                          wraplength=300,
                                          justify=tk. LEFT,
                                          anchor=tk.W)
        self.manga_title_label.pack(fill=tk.X, pady=(0, 8))

        self.manga_info_label = tk.Label(inner,
                                         text="Paste URL to start",
                                         font=('Segoe UI', 8),
                                         bg='white',
                                         fg=self.colors['text_secondary'],
                                         wraplength=300,
                                         justify=tk.LEFT,
                                         anchor=tk.W)
        self.manga_info_label.pack(fill=tk.X)

        # Languages info
        self.languages_frame = tk.Frame(inner, bg='#F0F4FF')
        languages_inner = tk.Frame(self.languages_frame, bg='#F0F4FF')
        languages_inner.pack(padx=10, pady=8)

        tk.Label(languages_inner, text="🌍 Available Languages",
                 font=('Segoe UI', 9, 'bold'),
                 bg='#F0F4FF', fg=self.colors['text']).pack(anchor=tk.W)

        self.languages_label = tk.Label(languages_inner,
                                        text="Click 🔍 Detect to find languages",
                                        font=('Segoe UI', 8),
                                        bg='#F0F4FF',
                                        fg=self. colors['text_secondary'],
                                        justify=tk.LEFT,
                                        anchor=tk.W)
        self.languages_label.pack(anchor=tk.W, pady=(4, 0))

        # Hide by default
        self.languages_frame.pack_forget()

        # Status
        status_card = tk.Frame(inner, bg='#F8FAFC')
        status_card.pack(side=tk. BOTTOM, fill=tk.X, pady=(10, 0))

        status_inner = tk.Frame(status_card, bg='#F8FAFC')
        status_inner.pack(padx=10, pady=10)

        tk.Label(status_inner, text="● Status", font=('Segoe UI', 9, 'bold'),
                 bg='#F8FAFC', fg=self.colors['text']).pack(anchor=tk.W)

        self.status_label = tk.Label(status_inner, text="Ready",
                                     font=('Segoe UI', 8),
                                     bg='#F8FAFC',
                                     fg=self.colors['success'])
        self.status_label. pack(anchor=tk.W, pady=(3, 0))

    def setup_main_area(self, parent):
        """Setup main content - NO SCROLL"""

        # URL Section
        url_card = tk.Frame(parent, bg='white')
        url_card.pack(fill=tk.X, pady=(0, 10))

        url_inner = tk.Frame(url_card, bg='white')
        url_inner.pack(fill=tk.X, padx=15, pady=12)

        tk.Label(url_inner, text="🔗 Load Manga", font=('Segoe UI', 12, 'bold'),
                 bg='white', fg=self. colors['text']).pack(anchor=tk.W, pady=(0, 8))

        input_row = tk.Frame(url_inner, bg='white')
        input_row.pack(fill=tk.X)

        input_cont = tk.Frame(input_row, bg='#F8FAFC')
        input_cont.pack(side=tk.LEFT, fill=tk. X, expand=True, padx=(0, 8))

        self.url_entry = tk.Entry(input_cont, font=('Segoe UI', 10),
                                  bg='#F8FAFC', fg=self.colors['text'],
                                  relief=tk.FLAT, bd=0,
                                  insertbackground=self.colors['accent'])
        self.url_entry. pack(fill=tk.X, padx=10, pady=8)
        self.url_entry.insert(0, "https://mangadex.org/title/...")
        self.url_entry.bind('<FocusIn>', lambda e: self.url_entry.delete(0, tk.END)
        if '.. .' in self.url_entry. get() else None)

        # Language selector - DYNAMIC
        lang_cont = tk.Frame(input_row, bg='#F8FAFC')
        lang_cont.pack(side=tk.LEFT, padx=(0, 8))

        lang_inner = tk.Frame(lang_cont, bg='#F8FAFC')
        lang_inner.pack(padx=8, pady=6)

        tk.Label(lang_inner, text="🌍 Language", font=('Segoe UI', 8, 'bold'),
                 bg='#F8FAFC', fg=self.colors['text_secondary']).pack()

        self.language_var = tk.StringVar(value='en')
        self.language_combo = ttk.Combobox(lang_inner,
                                           textvariable=self.language_var,
                                           values=['en - 🇬🇧 English'],
                                           state='readonly',
                                           width=18,
                                           font=('Segoe UI', 8))
        self.language_combo. pack(pady=(4, 0))

        # Auto-detect button
        detect_btn = tk.Label(lang_inner, text="🔍 Detect",
                              font=('Segoe UI', 7, 'bold'),
                              bg='#E0E7FF', fg=self. colors['accent'],
                              padx=8, pady=2, cursor='hand2')
        detect_btn.pack(pady=(4, 0))
        detect_btn.bind('<Button-1>', lambda e: self.detect_languages())

        # Load button
        self.load_btn = ModernButton(input_row, "Load", self.load_manga,
                                     bg=self.colors['accent'], width=100, height=40)
        self.load_btn.pack(side=tk.LEFT)

        # ADD:  Reload button (reload chapters with new language)
        self.reload_btn = ModernButton(input_row, "🔄", self.reload_chapters,
                                       bg='#64748B', width=40, height=40)
        self.reload_btn.pack(side=tk.LEFT, padx=(4, 0))
        self.reload_btn.set_state('disabled')

        # Chapters Section
        ch_card = tk.Frame(parent, bg='white')
        ch_card.pack(fill=tk. BOTH, expand=True, pady=(0, 10))

        ch_inner = tk.Frame(ch_card, bg='white')
        ch_inner.pack(fill=tk.BOTH, expand=True, padx=15, pady=12)

        ch_header = tk.Frame(ch_inner, bg='white')
        ch_header.pack(fill=tk.X, pady=(0, 8))

        tk.Label(ch_header, text="📑 Chapters", font=('Segoe UI', 12, 'bold'),
                 bg='white', fg=self.colors['text']).pack(side=tk.LEFT)

        btn_group = tk.Frame(ch_header, bg='white')
        btn_group.pack(side=tk.LEFT, padx=(10, 0))

        sel_all = tk.Label(btn_group, text="✓ All", font=('Segoe UI', 8, 'bold'),
                           bg=self.colors['success'], fg='white',
                           padx=10, pady=4, cursor='hand2')
        sel_all.pack(side=tk.LEFT, padx=(0, 4))
        sel_all.bind('<Button-1>', lambda e: self. select_all_chapters())

        clr_all = tk.Label(btn_group, text="✗ Clear", font=('Segoe UI', 8, 'bold'),
                           bg='#94A3B8', fg='white',
                           padx=10, pady=4, cursor='hand2')
        clr_all.pack(side=tk.LEFT)
        clr_all.bind('<Button-1>', lambda e:  self.deselect_all_chapters())

        self.chapter_count_label = tk.Label(ch_header, text="0/0",
                                            font=('Segoe UI', 9, 'bold'),
                                            bg='#F8FAFC', fg=self.colors['text'],
                                            padx=12, pady=4)
        self.chapter_count_label.pack(side=tk.RIGHT)

        # Tree
        tree_cont = tk.Frame(ch_inner, bg='#F8FAFC')
        tree_cont.pack(fill=tk.BOTH, expand=True)

        tree_scroll = ttk.Scrollbar(tree_cont)
        tree_scroll.pack(side=tk. RIGHT, fill=tk.Y)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Modern.Treeview",
                        background='white', foreground=self.colors['text'],
                        fieldbackground='white', font=('Segoe UI', 9),
                        rowheight=28, borderwidth=0)
        style.configure("Modern.Treeview.Heading",
                        background='#F8FAFC', foreground=self.colors['text'],
                        font=('Segoe UI', 9, 'bold'), borderwidth=0)
        style.map('Modern.Treeview',
                  background=[('selected', self.colors['accent'])],
                  foreground=[('selected', 'white')])

        self.chapters_tree = ttk.Treeview(tree_cont,
                                          columns=('Chapter', 'Title', 'Pages'),
                                          show='tree headings',
                                          yscrollcommand=tree_scroll.set,
                                          style="Modern.Treeview",
                                          height=7)
        self.chapters_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1, pady=1)
        tree_scroll.config(command=self. chapters_tree.yview)

        self.chapters_tree.heading('#0', text='✓')
        self.chapters_tree. heading('Chapter', text='Ch')
        self.chapters_tree.heading('Title', text='Title')
        self.chapters_tree.heading('Pages', text='Pg')

        self.chapters_tree.column('#0', width=40, anchor=tk.CENTER)
        self.chapters_tree.column('Chapter', width=60)
        self.chapters_tree. column('Title', width=600)
        self.chapters_tree.column('Pages', width=50, anchor=tk.CENTER)

        self.chapters_tree.bind('<Button-1>', self.toggle_chapter)

        # Download Section
        dl_card = tk.Frame(parent, bg='white')
        dl_card.pack(fill=tk.X)

        dl_inner = tk. Frame(dl_card, bg='white')
        dl_inner.pack(fill=tk.X, padx=15, pady=12)

        tk.Label(dl_inner, text="⚡ Download", font=('Segoe UI', 12, 'bold'),
                 bg='white', fg=self.colors['text']).pack(anchor=tk.W, pady=(0, 8))

        # Save location
        dir_row = tk.Frame(dl_inner, bg='white')
        dir_row.pack(fill=tk.X, pady=(0, 8))

        tk.Label(dir_row, text="💾", font=('Segoe UI', 12), bg='white').pack(side=tk.LEFT, padx=(0, 6))

        dir_cont = tk.Frame(dir_row, bg='#F8FAFC')
        dir_cont.pack(side=tk. LEFT, fill=tk.X, expand=True, padx=(0, 8))

        self.output_entry = tk.Entry(dir_cont, font=('Segoe UI', 9),
                                     bg='#F8FAFC', fg=self.colors['text'],
                                     relief=tk.FLAT, bd=0)
        self.output_entry. insert(0, self.output_dir)
        self.output_entry.pack(fill=tk.X, padx=8, pady=6)

        ModernButton(dir_row, "Browse", self.browse_output_dir,
                     bg='#64748B', width=80, height=32).pack(side=tk.LEFT)

        # Export options
        export_row = tk.Frame(dl_inner, bg='white')
        export_row.pack(fill=tk.X, pady=(0, 8))

        # Per Chapter
        per_col = tk.Frame(export_row, bg='#F8FAFC')
        per_col.pack(side=tk.LEFT, fill=tk. X, expand=True, padx=(0, 6))

        per_inner = tk.Frame(per_col, bg='#F8FAFC')
        per_inner.pack(padx=10, pady=8)

        tk.Label(per_inner, text="Per Chapter", font=('Segoe UI', 8, 'bold'),
                 bg='#F8FAFC', fg=self.colors['text_secondary']).pack(anchor=tk.W)

        self.cbz_per_chapter_var = tk.BooleanVar(value=False)
        tk.Checkbutton(per_inner, text="📚 CBZ", variable=self.cbz_per_chapter_var,
                       bg='#F8FAFC', font=('Segoe UI', 8),
                       cursor='hand2', anchor='w').pack(fill=tk.X)

        self.pdf_per_chapter_var = tk.BooleanVar(value=False)
        tk.Checkbutton(per_inner, text="📄 PDF", variable=self.pdf_per_chapter_var,
                       bg='#F8FAFC', font=('Segoe UI', 8),
                       cursor='hand2', anchor='w').pack(fill=tk.X)

        # All Chapters
        all_col = tk.Frame(export_row, bg='#F8FAFC')
        all_col.pack(side=tk.LEFT, fill=tk.X, expand=True)

        all_inner = tk. Frame(all_col, bg='#F8FAFC')
        all_inner.pack(padx=10, pady=8)

        tk.Label(all_inner, text="All (Merged)", font=('Segoe UI', 8, 'bold'),
                 bg='#F8FAFC', fg=self. colors['text_secondary']).pack(anchor=tk.W)

        self.cbz_all_var = tk.BooleanVar(value=False)
        tk.Checkbutton(all_inner, text="📚 CBZ", variable=self.cbz_all_var,
                       bg='#F8FAFC', font=('Segoe UI', 8),
                       cursor='hand2', anchor='w').pack(fill=tk.X)

        self.pdf_all_var = tk.BooleanVar(value=False)
        tk.Checkbutton(all_inner, text="📄 PDF", variable=self.pdf_all_var,
                       bg='#F8FAFC', font=('Segoe UI', 8),
                       cursor='hand2', anchor='w').pack(fill=tk.X)

        # Progress
        prog_cont = tk.Frame(dl_inner, bg='#F8FAFC')
        prog_cont.pack(fill=tk. X, pady=(0, 8))

        prog_inner = tk.Frame(prog_cont, bg='#F8FAFC')
        prog_inner.pack(fill=tk.X, padx=12, pady=10)

        # Chapter progress
        left_prog = tk.Frame(prog_inner, bg='#F8FAFC')
        left_prog.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        tk.Label(left_prog, text="📖 Chapter", font=('Segoe UI', 8, 'bold'),
                 bg='#F8FAFC', fg=self.colors['text']).pack(anchor=tk.W)

        self.chapter_progress_label = tk.Label(left_prog, text="Waiting...",
                                               font=('Segoe UI', 7),
                                               bg='#F8FAFC',
                                               fg=self. colors['text_secondary'])
        self.chapter_progress_label. pack(anchor=tk.W, pady=(2, 3))

        self.chapter_progress = ttk.Progressbar(left_prog, mode='determinate')
        self.chapter_progress. pack(fill=tk.X)

        # Page progress
        right_prog = tk.Frame(prog_inner, bg='#F8FAFC')
        right_prog.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(right_prog, text="📄 Page", font=('Segoe UI', 8, 'bold'),
                 bg='#F8FAFC', fg=self.colors['text']).pack(anchor=tk.W)

        self.page_progress_label = tk.Label(right_prog, text="--/--",
                                            font=('Segoe UI', 7),
                                            bg='#F8FAFC',
                                            fg=self. colors['text_secondary'])
        self.page_progress_label. pack(anchor=tk.W, pady=(2, 3))

        self.page_progress = ttk.Progressbar(right_prog, mode='determinate')
        self.page_progress.pack(fill=tk.X)

        # Buttons
        btn_row = tk.Frame(dl_inner, bg='white')
        btn_row.pack()

        self.download_btn = ModernButton(btn_row, "⬇ Download", self.download_selected,
                                         bg=self.colors['accent'], width=140, height=38)
        self.download_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.download_btn.set_state('disabled')

        self.pause_btn = ModernButton(btn_row, "⏸ Pause", self.pause_download,
                                      bg=self.colors['warning'], width=90, height=38)
        self.pause_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.pause_btn.set_state('disabled')

        self.stop_btn = ModernButton(btn_row, "⏹ Stop", self.stop_download,
                                     bg=self. colors['error'], width=90, height=38)
        self.stop_btn.pack(side=tk.LEFT)
        self.stop_btn. set_state('disabled')

    def detect_languages(self):
        """Auto-detect available languages"""
        url = self.url_entry.get().strip()
        if not url or '.. .' in url:
            messagebox.showwarning("No URL", "Please paste manga URL first!")
            return

        manga_id = self.api.extract_manga_id(url)
        if not manga_id:
            messagebox.showerror("Invalid URL", "Cannot extract manga ID")
            return

        self.language_combo.config(state='disabled')
        self.status_label.config(text="Detecting languages.. .", fg=self.colors['accent'])

        def detect_thread():
            try:
                available_langs = self.api.get_available_languages(manga_id)

                if not available_langs:
                    available_langs = {'en':  0, 'ja': 0, 'es': 0}

                lang_values = []
                for lang_code, count in available_langs.items():
                    lang_name = self.api.get_language_name(lang_code)
                    lang_values.append(f"{lang_code} - {lang_name} ({count} ch)")

                def update_ui():
                    self.language_combo.config(state='readonly')
                    self.language_combo['values'] = lang_values

                    if lang_values:
                        self. language_combo.current(0)
                        first_lang_code = list(available_langs. keys())[0]
                        self.language_var.set(first_lang_code)

                    self.status_label.config(
                        text=f"Found {len(available_langs)} languages",
                        fg=self. colors['success'])

                    top_langs = list(available_langs.items())[:5]
                    lang_text = "\n".join([
                        f"• {self.api.get_language_name(code)}: {count} ch"
                        for code, count in top_langs
                    ])

                    self.languages_label.config(text=lang_text)
                    self.languages_frame.pack(fill=tk.X, pady=(10, 0))

                self.root.after(0, update_ui)

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "Error", f"Failed to detect languages:\n{str(e)}"))
                self.root.after(0, lambda: self.status_label.config(
                    text="Detection failed", fg=self.colors['error']))
            finally:
                self.root. after(0, lambda: self. language_combo.config(state='readonly'))

        threading.Thread(target=detect_thread, daemon=True).start()

    def load_manga(self):
        """Load manga from URL"""
        url = self.url_entry.get().strip()
        if not url or '.. .' in url:
            messagebox.showwarning("Invalid URL", "Please enter valid URL")
            return

        manga_id = self.api.extract_manga_id(url)
        if not manga_id:
            messagebox.showerror("Invalid URL", "Cannot extract manga ID")
            return

        self.load_btn.set_state('disabled')
        self.status_label.config(text="Loading...")

        def load_thread():
            try:
                manga_info = self.api.get_manga_info(manga_id)
                if not manga_info or 'data' not in manga_info:
                    raise Exception("Failed")

                self.selected_manga = manga_info['data']

                manga_title = self.selected_manga['attributes']['title']
                display_title = manga_title.get('en', list(manga_title.values())[0]
                if manga_title else 'Unknown')

                description = self.selected_manga['attributes'].get('description', {})
                display_desc = description.get('en', list(description.values())[0]
                if description else 'No description')
                if len(display_desc) > 200:
                    display_desc = display_desc[:200] + "..."

                status = self.selected_manga['attributes'].get('status', 'Unknown').title()
                year = self.selected_manga['attributes'].get('year', 'Unknown')

                self.root.after(0, lambda: self.manga_title_label.config(text=display_title))
                self.root.after(0, lambda: self.manga_info_label.config(
                    text=f"📅 {status} • {year}\n\n{display_desc}"))

                # Auto-detect languages if not done yet
                if self.language_combo['values'] == ('en - 🇬🇧 English',):
                    self.root.after(0, lambda: self.detect_languages())

                # Cover
                cover_art = None
                for rel in self.selected_manga.get('relationships', []):
                    if rel['type'] == 'cover_art':
                        cover_art = rel['attributes']['fileName']
                        break

                if cover_art:
                    cover_image = self.api.get_cover_image(manga_id, cover_art, quality='512')
                    if cover_image:
                        cover_image = cover_image.resize((230, 330), Image.Resampling.LANCZOS)
                        self.cover_photo = ImageTk.PhotoImage(cover_image)
                        self.root.after(0, lambda: self.cover_label.config(
                            image=self.cover_photo, text='', bg='white', width=230, height=330))

                # FIXED: Extract language code properly from combo value
                language_value = self.language_var.get()

                # Parse language code from "en - 🇬🇧 English (15 ch)" format
                if ' - ' in language_value:
                    language_code = language_value.split(' - ')[0].strip()
                else:
                    language_code = language_value.strip()

                print(f"📚 Loading chapters for language: {language_code}")

                chapters = self.api.get_manga_chapters(manga_id, language=language_code)

                if not chapters:
                    self.root.after(0, lambda: messagebox.showinfo(
                        "No Chapters",
                        f"No chapters found for language: {language_code}\n\n"
                        "Try selecting a different language. "))

                self.root.after(0, lambda: self.display_chapters(chapters))
                self.root.after(0, lambda: self.status_label.config(text="Ready"))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed:\n{str(e)}"))
                self.root.after(0, lambda: self.status_label.config(text="Failed"))

            finally:
                self.root.after(0, lambda: self.load_btn.set_state('normal'))

        threading.Thread(target=load_thread, daemon=True).start()

    def display_chapters(self, chapters):
        for item in self.chapters_tree.get_children():
            self.chapters_tree.delete(item)

        self.chapters = chapters

        if not chapters:
            messagebox.showinfo("No Chapters", "No chapters found")
            return

        for chapter in chapters:
            attrs = chapter['attributes']
            ch_num = attrs. get('chapter', 'N/A')
            title = attrs.get('title', 'No Title')
            pages = attrs.get('pages', '? ')

            self.chapters_tree.insert('', tk.END,
                                      values=(ch_num, title, pages),
                                      tags=('unchecked',))

        self.download_btn.set_state('normal')
        self.update_chapter_count()
        self.download_btn.set_state('normal')
        self.reload_btn.set_state('normal')  # Enable reload button
        self.update_chapter_count()

    def toggle_chapter(self, event):
        region = self.chapters_tree.identify('region', event.x, event. y)
        if region == 'tree':
            item = self.chapters_tree.identify_row(event.y)
            if item:
                tags = self.chapters_tree.item(item, 'tags')
                if 'checked' in tags:
                    self.chapters_tree.item(item, tags=('unchecked',), text='☐')
                else:
                    self.chapters_tree.item(item, tags=('checked',), text='☑')
                self.update_chapter_count()

    def select_all_chapters(self):
        for item in self.chapters_tree. get_children():
            self.chapters_tree.item(item, tags=('checked',), text='☑')
        self.update_chapter_count()

    def deselect_all_chapters(self):
        for item in self. chapters_tree.get_children():
            self.chapters_tree. item(item, tags=('unchecked',), text='☐')
        self.update_chapter_count()

    def update_chapter_count(self):
        selected = sum(1 for item in self. chapters_tree.get_children()
                       if 'checked' in self.chapters_tree.item(item, 'tags'))
        total = len(self.chapters_tree.get_children())
        self.chapter_count_label.config(text=f"{selected}/{total}")

    def browse_output_dir(self):
        directory = filedialog.askdirectory(initialdir=self.output_dir)
        if directory:
            self.output_dir = directory
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, directory)

    def download_selected(self):
        selected_items = []
        for item in self.chapters_tree.get_children():
            if 'checked' in self.chapters_tree.item(item, 'tags'):
                selected_items.append(item)

        if not selected_items:
            messagebox.showwarning("No Selection", "Select chapters")
            return

        self.is_downloading = True
        self. download_btn.set_state('disabled')
        self.pause_btn.set_state('normal')
        self.stop_btn.set_state('normal')
        self.load_btn.set_state('disabled')

        self.downloader. reset()

        manga_title = self.selected_manga['attributes']['title']
        display_title = manga_title.get('en', list(manga_title.values())[0]
                                       if manga_title else 'Unknown')

        # Get cover URL
        cover_url = None
        manga_id = self.api.extract_manga_id(self.url_entry.get().strip())
        if manga_id:
            for rel in self.selected_manga. get('relationships', []):
                if rel['type'] == 'cover_art':
                    cover_filename = rel['attributes']['fileName']
                    cover_url = f"https://uploads.mangadex.org/covers/{manga_id}/{cover_filename}"
                    break

        self.status_label.config(text="Downloading...")

        def download_thread():
            chapters_data = []

            for i, item in enumerate(selected_items, 1):
                if self.downloader.is_stopped:
                    break

                index = self.chapters_tree.index(item)
                chapter = self.chapters[index]
                chapter_id = chapter['id']
                chapter_num = chapter['attributes']. get('chapter', 'N/A')

                self.root.after(0, lambda n=chapter_num, i=i, t=len(selected_items):
                self.chapter_progress_label.config(text=f"Crawl Ch. {n} ({i}/{t})"))

                page_urls = self.api.get_chapter_pages(chapter_id)

                if page_urls:
                    chapters_data.append({
                        'chapter_info': chapter,
                        'page_urls': page_urls
                    })

            if not chapters_data or self.downloader.is_stopped:
                self.root.after(0, lambda: self.status_label.config(text="Stopped"))
                self.root.after(0, self.reset_download_buttons)
                return

            total_chapters = len(chapters_data)

            def progress_callback(ch_idx, total_ch, folder, status, *args):
                if self.downloader.is_stopped:
                    return

                if status == "chapter_start":
                    self.root. after(0, lambda: self. chapter_progress_label.config(
                        text=f"Ch.{ch_idx}/{total_ch}"))
                    self.root.after(0, lambda: self.status_label. config(text=f"DL {ch_idx}/{total_ch}"))

                elif status == "page_progress":
                    pg_num, total_pg, pg_name, pg_status = args[: 4]

                    ch_percent = (ch_idx / total_ch) * 100
                    pg_percent = (pg_num / total_pg) * 100 if pg_num > 0 else 0

                    self.root.after(0, lambda: self.chapter_progress. config(value=ch_percent))
                    self.root.after(0, lambda: self.page_progress. config(value=pg_percent))

                    if pg_num == 0:
                        self.root.after(0, lambda: self.page_progress_label.config(text="Cover"))
                    else:
                        self.root.after(0, lambda: self.page_progress_label.config(text=f"{pg_num}/{total_pg}"))

                    # Show speed
                    avg_speed = self.downloader. get_average_speed()
                    if avg_speed > 0:
                        self. root.after(0, lambda: self.status_label.config(
                            text=f"DL {ch_idx}/{total_ch} ⚡{avg_speed:.1f}MB/s"))

                elif status == "creating_cbz":
                    self.root.after(0, lambda: self.page_progress_label.config(text="CBZ... "))

                elif status == "creating_pdf":
                    self.root. after(0, lambda: self. page_progress_label.config(text="PDF..."))

                elif status == "merging_cbz":
                    self.root.after(0, lambda: self.chapter_progress_label.config(text="Merge CBZ..."))

                elif status == "merging_pdf":
                    self.root.after(0, lambda: self.chapter_progress_label.config(text="Merge PDF..."))

                elif status == "chapter_complete":
                    ch_percent = (ch_idx / total_ch) * 100
                    self.root.after(0, lambda: self.chapter_progress. config(value=ch_percent))
                    self.root.after(0, lambda: self.page_progress. config(value=0))

                elif status == "retrying":
                    self.root.after(0, lambda: self.status_label.config(text="Retrying failed files..."))
                    self.root.after(0, lambda: self.page_progress_label.config(text="Retrying..."))

                elif status.startswith("retry_attempt_"):
                    # Extract retry attempt number from status like "retry_attempt_1"
                    attempt = status.split("_")[-1]
                    self.root.after(0, lambda a=attempt: self.status_label.config(text=f"Retry #{a}..."))
                    if len(args) >= 1:
                        # Show progress if available
                        pg_num = ch_idx
                        total_pg = total_ch
                        self.root.after(0, lambda: self.page_progress_label.config(text=f"Retry {pg_num}/{total_pg}"))

            output_dir = self.output_entry.get().strip()
            cbz_per = self.cbz_per_chapter_var.get()
            pdf_per = self.pdf_per_chapter_var.get()
            cbz_all = self.cbz_all_var.get()
            pdf_all = self.pdf_all_var.get()

            success = self.downloader.download_manga(display_title, chapters_data,
                                                     output_dir, progress_callback,
                                                     create_cbz_per_chapter=cbz_per,
                                                     create_pdf_per_chapter=pdf_per,
                                                     create_cbz_all=cbz_all,
                                                     create_pdf_all=pdf_all,
                                                     cover_url=cover_url)

            if self.downloader.is_stopped:
                self.root.after(0, lambda: self.status_label.config(text="Stopped"))
                self.root.after(0, lambda: messagebox.showinfo("Stopped", "Download stopped"))
            elif success:
                download_path = os.path.join(output_dir,
                                             self.downloader.sanitize_filename(display_title))
                self.root.after(0, lambda: self.status_label.config(text="Complete! "))
                self.root.after(0, lambda: messagebox. showinfo("Success",
                                                               f"Complete!\n\n{download_path}"))
            else:
                self.root.after(0, lambda: self.status_label.config(text="Failed"))
                self.root.after(0, lambda: messagebox. showerror("Error", "Failed"))

            self.root.after(0, self.reset_download_buttons)

        threading.Thread(target=download_thread, daemon=True).start()

    def pause_download(self):
        if self.downloader.is_paused:
            self.downloader.resume()
            self.pause_btn. itemconfig('text', text='⏸ Pause')
            self.status_label.config(text="Downloading...")
        else:
            self.downloader.pause()
            self.pause_btn.itemconfig('text', text='▶ Resume')
            self.status_label. config(text="Paused")

    def stop_download(self):
        if messagebox.askyesno("Stop", "Stop download?"):
            self.downloader.stop()
            self.status_label.config(text="Stopping...")

    def reload_chapters(self):
        """Reload chapters with currently selected language"""
        if not self.selected_manga:
            messagebox.showwarning("No Manga", "Please load a manga first")
            return

        manga_id = self.api.extract_manga_id(self.url_entry.get().strip())
        if not manga_id:
            return

        self.reload_btn.set_state('disabled')
        self.status_label.config(text="Reloading...")

        def reload_thread():
            try:
                # Extract language code
                language_value = self.language_var.get()
                if ' - ' in language_value:
                    language_code = language_value.split(' - ')[0].strip()
                else:
                    language_code = language_value.strip()

                print(f"🔄 Reloading chapters for language: {language_code}")

                chapters = self.api.get_manga_chapters(manga_id, language=language_code)

                if not chapters:
                    self.root.after(0, lambda: messagebox.showinfo(
                        "No Chapters",
                        f"No chapters found for {language_code}"))

                self.root.after(0, lambda: self.display_chapters(chapters))
                self.root.after(0, lambda: self.status_label.config(text="Reloaded"))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed:\n{str(e)}"))
            finally:
                self.root.after(0, lambda: self.reload_btn.set_state('normal'))

        threading.Thread(target=reload_thread, daemon=True).start()

    def reset_download_buttons(self):
        self.is_downloading = False
        self. download_btn.set_state('normal')
        self.pause_btn.set_state('disabled')
        self.stop_btn. set_state('disabled')
        self.load_btn.set_state('normal')
        self.pause_btn.itemconfig('text', text='⏸ Pause')
        self.chapter_progress. config(value=0)
        self.page_progress.config(value=0)