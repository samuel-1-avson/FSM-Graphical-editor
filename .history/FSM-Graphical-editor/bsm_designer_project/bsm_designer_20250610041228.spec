# bsm_designer.spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(['bsm_designer_project/main.py'],
             pathex=['.'], # Look for imports in the project root
             binaries=[],
             datas=[
                 ('bsm_designer_project/docs', 'bsm_designer_project/docs'),
                 ('bsm_designer_project/examples', 'bsm_designer_project/examples'),
                 ('bsm_designer_project/dependencies/icons', 'bsm_designer_project/dependencies/icons')
             ],
             hiddenimports=['pygraphviz'], # Help PyInstaller find tricky imports
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='BSM_Designer',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False, # Set to False for a GUI application
          icon='bsm_designer_project/dependencies/icons/app_icon.ico' # CREATE THIS ICON
          )