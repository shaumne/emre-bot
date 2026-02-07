@echo off
REM Market Maker Bot Başlatma Scripti (Windows)

echo ==========================================
echo POLYMARKET MARKET MAKER BOT
echo ==========================================
echo.

REM Venv kontrol
if exist venv\Scripts\activate.bat (
    echo [OK] Virtual environment bulundu
    call venv\Scripts\activate.bat
) else (
    echo [!] Virtual environment bulunamadi
    echo     Devam ediliyor...
)

echo.
echo [START] Market Maker Bot baslatiliyor...
echo.

python market_maker_bot.py

echo.
echo [STOP] Bot durduruldu
pause

