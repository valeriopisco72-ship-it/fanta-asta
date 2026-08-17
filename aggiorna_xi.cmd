@echo off
REM Aggiorna titolari.csv dalle probabili formazioni. Registrato in Utilita' di
REM pianificazione come "fanta-asta aggiorna XI". Per toglierlo:
REM   schtasks /Delete /TN "fanta-asta aggiorna XI" /F
cd /d "%~dp0"
echo. >> aggiornamenti.log
echo [%date% %time%] >> aggiornamenti.log
python formazioni.py >> aggiornamenti.log 2>&1
