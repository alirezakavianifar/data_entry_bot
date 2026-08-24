# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path
import playwright
import customtkinter

block_cipher = None

SPEC_ROOT = Path(SPECPATH).resolve()

# 1. Playwright Driver data folder
playwright_dir = Path(playwright.__file__).parent
playwright_driver_dir = playwright_dir / "driver"

# 2. CustomTkinter assets
customtkinter_dir = Path(customtkinter.__file__).parent
customtkinter_assets_dir = customtkinter_dir / "assets"

datas = [
    (str(playwright_driver_dir), "playwright/driver"),
    (str(customtkinter_assets_dir), "customtkinter/assets"),
]

# Include default promo links configuration if present
promo_config_path = SPEC_ROOT / "config"
if promo_config_path.exists():
    datas.append((str(promo_config_path), "config"))

hiddenimports = [
    # Core Libraries
    "playwright",
    "playwright.sync_api",
    "playwright._impl",
    "customtkinter",
    "tkinter",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "openpyxl",
    "openpyxl.styles",
    "openpyxl.worksheet",
    "pandas",
    "pydantic",
    "pydantic_core",
    "dotenv",
    "loguru",
    "gspread",
    "google.auth",
    "google.auth.transport.requests",
    "google.oauth2.service_account",
    "sqlite3",
    "queue",
    "threading",
    "subprocess",
    "webbrowser",
    "ctypes",
    # Internal Modules
    "config",
    "config.settings",
    "core",
    "core.browser",
    "core.engine",
    "core.logger",
    "core.password_gen",
    "core.state",
    "data",
    "data.base_provider",
    "data.excel_provider",
    "data.factory",
    "data.google_sheets",
    "data.models",
    "gui",
    "gui.main_gui",
    "sites",
    "sites.base",
    "sites.fairplaybet",
    "sites.betfred",
    "sites.quinnbet",
    "sites.bresbet",
    "sites.planetsportbet",
    "sites.starsports",
    "sites.betgoodwin",
    "sites.betstgeorge",
    "sites.affiliate_redirects",
]

a = Analysis(
    ["gui_app.py"],
    pathex=[str(SPEC_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "scipy", "notebook", "torch", "tensorboard", "paddleocr"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Single Executable (onefile) configuration
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="DataEntryBot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
