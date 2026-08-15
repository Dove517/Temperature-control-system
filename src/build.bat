@echo off
pyinstaller -F -w -n "Temperature control system" --icon=logo.ico Tcs.py
pause