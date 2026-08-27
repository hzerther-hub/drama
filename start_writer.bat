@echo off
rem Local AI Writer launcher: force Python 3.14 (Tk 9, colored toolbar icons)
rem conda py312 (Tk 8.6) renders emoji icons in black on Windows.
"C:\Users\user\py314\python.exe" "%~dp0main.py" %*
