@echo off
rem Before building a new release: change VERSION in version.py and add a line to CHANGELOG.md
cd /d "%~dp0"
pip install pymupdf==1.25.5 pyside6 pyinstaller
python build.py
pause
