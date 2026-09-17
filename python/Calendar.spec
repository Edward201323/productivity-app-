# Build with: .app-venv/bin/pyinstaller --noconfirm Calendar.spec
from pathlib import Path

root = Path(SPECPATH)
a = Analysis([str(root / 'calendar_app.py')], pathex=[str(root)], binaries=[], datas=[],
             hiddenimports=['AppKit', 'Foundation', 'UserNotifications'],
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Calendar',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, argv_emulation=False, target_arch=None, codesign_identity=None,
          entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Calendar')
app = BUNDLE(coll, name='Calendar.app', icon=None,
             bundle_identifier='com.twenty.python', info_plist={
                 'CFBundleName': 'Calendar',
                 'CFBundleDisplayName': 'Calendar',
                 'CFBundleShortVersionString': '1.0',
                 'CFBundleVersion': '2',
                 'LSMinimumSystemVersion': '14.0',
                 'LSApplicationCategoryType': 'public.app-category.productivity',
                 'NSHighResolutionCapable': True,
             })
