@echo off
echo ========================================
echo  DeepCore Agent - Build
echo ========================================
cd /d "%~dp0"
if exist deepcore_shared rmdir /s /q deepcore_shared
xcopy /E /I /Q ..\deepcore_shared deepcore_shared
pip install -r requirements.txt pyinstaller -q
pyinstaller --name DeepCoreAgent ^
  --windowed --onedir --noconfirm ^
  --add-data "deepcore_shared;deepcore_shared" ^
  --hidden-import=anthropic ^
  --hidden-import=chromadb ^
  main.py
powershell -Command "Compress-Archive -Force -Path dist\DeepCoreAgent -DestinationPath DeepCoreAgent-Windows.zip"
echo Listo: DeepCoreAgent-Windows.zip
pause
