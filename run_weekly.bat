@echo off
REM Weekly Player Reconciliation Script
REM Updates current team assignments only

echo ============================================
echo NFL Player Database Reconciliation - WEEKLY
echo ============================================
echo.

REM Load environment variables from .env file
if not exist .env (
    echo ERROR: .env file not found!
    echo Please copy .env.example to .env and fill in your database credentials.
    pause
    exit /b 1
)

echo Loading database credentials from .env...
for /F "tokens=*" %%i in (.env) do set %%i

REM Verify required variables are set
if "%ORACLE_USER%"=="" (
    echo ERROR: ORACLE_USER not set in .env
    pause
    exit /b 1
)

echo Credentials loaded successfully.
echo.

REM Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Run the reconciliation script
echo Running weekly reconciliation team updates only...
echo.
python player_reconcile.py

echo.
echo ============================================
echo Reconciliation complete!
echo.
echo Next steps:
echo 1. Review the generated SQL script
echo 2. Check the log file for details
echo 3. Execute the SQL script in your Oracle environment
echo 4. Commit the changes
echo ============================================
pause
