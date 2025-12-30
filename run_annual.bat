@echo off
REM Annual/Pre-Season Player Reconciliation Script
REM Updates BOTH current team AND position assignments

echo ================================================
echo NFL Player Database Reconciliation - FULL ANNUAL
echo ================================================
echo.
echo WARNING: This will reconcile BOTH teams AND positions!
echo This should typically be run once before the season starts.
echo.
set /p CONFIRM="Continue with full reconciliation? (y/n): "
if /i not "%CONFIRM%"=="y" (
    echo Cancelled.
    pause
    exit /b 0
)

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

REM Run the reconciliation script with full reconcile flag
echo Running FULL reconciliation teams AND positions...
echo.
python player_reconcile.py --full-reconcile

echo.
echo ============================================
echo Full reconciliation complete!
echo.
echo Next steps:
echo 1. CAREFULLY review the generated SQL script
echo 2. Check the log file for details
echo 3. Verify both team AND position changes are correct
echo 4. Execute the SQL script in your Oracle environment
echo 5. Commit the changes
echo ============================================
pause
