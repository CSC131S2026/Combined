# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ConflictChecker.

Build from project root:
    pyinstaller ConflictChecker.spec --clean --noconfirm

Outputs land in ``dist/``:
    macOS:   dist/ConflictChecker.app
    Windows: dist/ConflictChecker.exe

One spec, two platforms. We branch on ``sys.platform`` so macOS produces a
one-folder .app bundle (via COLLECT + BUNDLE) and Windows produces a single
windowed .exe (onefile).
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# ``SPEC`` is injected by PyInstaller and points at this file.
PROJECT_ROOT = os.path.abspath(os.path.dirname(SPEC))  # noqa: F821
ENTRY = os.path.join(PROJECT_ROOT, "Frontend", "main.py")
MAC_ICON = os.path.join(PROJECT_ROOT, "assets", "app_icon.icns")
WIN_ICON = os.path.join(PROJECT_ROOT, "assets", "app_icon.ico")
BUILD_ICON = None
if sys.platform == "darwin":
    BUILD_ICON = MAC_ICON
elif sys.platform.startswith("win"):
    BUILD_ICON = WIN_ICON
if BUILD_ICON and not os.path.exists(BUILD_ICON):
    print(f"[spec] WARNING: app icon missing, using default: {BUILD_ICON}")
    BUILD_ICON = None

# ---------------------------------------------------------------------------
# Data files (bundled at ``Backend/...`` so ``resource_path("Backend")`` works
# under PyInstaller's frozen ``sys._MEIPASS`` layout).
# ---------------------------------------------------------------------------
data_candidates = [
    ("assets/app_logo.png", "assets"),
    ("assets/app_icon.ico", "assets"),
    ("Backend/conflict_checker.sqlite3", "Backend"),
]
datas = []
for src, dest in data_candidates:
    full = os.path.join(PROJECT_ROOT, src)
    if os.path.exists(full):
        datas.append((full, dest))
    else:
        print(f"[spec] WARNING: optional data file missing, skipping: {full}")

for path in sorted((Path(PROJECT_ROOT) / "Backend").glob("conflict_flags*.csv")):
    datas.append((str(path), "Backend"))
for path in sorted((Path(PROJECT_ROOT) / "Backend").glob("conflict_flags*.json")):
    datas.append((str(path), "Backend"))

# Bundle non-Python data files from the Backend source tree (e.g. xlsx,
# json fixtures) so the Pipeline tab can read them at runtime. Python
# sources are compiled into the pyz via hiddenimports + pathex, so we
# deliberately skip ``.py``/``.pyc``/``.pyo`` and ``__pycache__`` here to
# avoid duplicating modules.
_BACKEND_SRC = os.path.join(PROJECT_ROOT, "Backend", "src")
_BACKEND_OUTPUT_DATA = os.path.join(_BACKEND_SRC, "web_scrapers", "output_data")
if os.path.isdir(_BACKEND_SRC):
    for root, dirs, files in os.walk(_BACKEND_SRC):
        # Prune __pycache__ directories in-place so os.walk skips them.
        root_abs = os.path.abspath(root)
        if os.path.commonpath([root_abs, _BACKEND_OUTPUT_DATA]) == _BACKEND_OUTPUT_DATA:
            dirs[:] = []
            continue
        dirs[:] = [
            d for d in dirs
            if d != "__pycache__"
            and os.path.abspath(os.path.join(root, d)) != _BACKEND_OUTPUT_DATA
        ]
        rel_root = os.path.relpath(root, PROJECT_ROOT)
        for fname in files:
            if fname.endswith((".py", ".pyc", ".pyo")) or fname.startswith("."):
                continue
            full = os.path.join(root, fname)
            datas.append((full, rel_root))

# ---------------------------------------------------------------------------
# collect_all() for packages that ship lazy submodules, data, or native libs.
# tkinter is handled automatically by PyInstaller; do not collect it.
# ---------------------------------------------------------------------------
hiddenimports = []
binaries = []
for pkg in (
    "customtkinter",
    "langchain",
    "langchain_ollama",
    "matplotlib",
    "tiktoken",
    "pymupdf",  # importable as ``fitz`` -- see hiddenimports below
    "openai",
    "rich",
    "pydantic",
):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:  # pragma: no cover - build-time diagnostic
        print(f"[spec] collect_all({pkg!r}) skipped: {exc}")

# ---------------------------------------------------------------------------
# Hidden imports: lazy-loaded modules that static analysis misses.
# ---------------------------------------------------------------------------
hiddenimports += [
    # Backend pipeline modules — imported lazily by the Pipeline tab.
    "src",
    "src.llmFlagging",
    "src.llmFlagging.higherSpec_openai",
    "src.llmFlagging.form700_paths",
    "src.web_scrapers",
    "src.web_scrapers.county_registry",
    "src.web_scrapers.preprocess",
    "src.web_scrapers.scraper_sacramento_county",
    "src.web_scrapers.scraper_sonoma_county",
    "src.web_scrapers.useful_functions",
    # pymupdf's public import name
    "fitz",
    # openpyxl write-only optimization path
    "openpyxl.cell._writer",
    # silences a common setuptools warning under PyInstaller
    "pkg_resources.py2_warn",
    # reportlab encoders / built-in font width tables (loaded by name)
    "reportlab.pdfbase._fontdata_enc_winansi",
    "reportlab.pdfbase._fontdata_enc_macroman",
    "reportlab.pdfbase._fontdata_widths_helvetica",
    "reportlab.pdfbase._fontdata_widths_helveticabold",
    "reportlab.pdfbase._fontdata_widths_helveticaoblique",
    "reportlab.pdfbase._fontdata_widths_helveticaboldoblique",
    "reportlab.pdfbase._fontdata_widths_courier",
    "reportlab.pdfbase._fontdata_widths_courierbold",
    "reportlab.pdfbase._fontdata_widths_courieroblique",
    "reportlab.pdfbase._fontdata_widths_courierboldoblique",
    "reportlab.pdfbase._fontdata_widths_timesroman",
    "reportlab.pdfbase._fontdata_widths_timesbold",
    "reportlab.pdfbase._fontdata_widths_timesitalic",
    "reportlab.pdfbase._fontdata_widths_timesbolditalic",
    "reportlab.pdfbase._fontdata_widths_symbol",
    "reportlab.pdfbase._fontdata_widths_zapfdingbats",
]

# ---------------------------------------------------------------------------
# Things we explicitly do NOT ship.
# ---------------------------------------------------------------------------
excludes = [
    "tests",
    "pytest",
    "pytest_asyncio",
    "IPython",
    "jupyter",
    "notebook",
    # matplotlib sometimes drags these in; we use Tk.
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [ENTRY],
    pathex=[
        PROJECT_ROOT,
        os.path.join(PROJECT_ROOT, "Frontend"),
        os.path.join(PROJECT_ROOT, "Backend"),
    ],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

is_mac = sys.platform == "darwin"

if is_mac:
    # macOS: one-folder build, then wrap in a .app bundle.
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="ConflictChecker",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name="ConflictChecker",
    )
    app = BUNDLE(
        coll,
        name="ConflictChecker.app",
        icon=BUILD_ICON,
        bundle_identifier="com.sacramento.conflictchecker",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "0.1.0",
            "LSMinimumSystemVersion": "11.0",
        },
    )
else:
    # Windows (and Linux fallback): single-file windowed executable.
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="ConflictChecker",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=BUILD_ICON,
    )
