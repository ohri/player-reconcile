@echo off
REM Dry Run - Preview Changes Without Generating SQL

echo ============================================
echo NFL Player Database Reconciliation - DRY RUN
echo ============================================
echo.
echo This will show you what would change without generating SQL.
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

REM Ask if user wants full reconcile or weekly
echo What type of dry run?
echo 1. Weekly (team changes only)
echo 2. Full (team AND position changes)
echo.
set /p CHOICE="Enter choice (1 or 2): "

if "%CHOICE%"=="2" (
    echo.
    echo Running DRY RUN with full reconciliation...
    python player_reconcile.py --full-reconcile --dry-run
) else (
    echo.
    echo Running DRY RUN with weekly reconciliation...
    python player_reconcile.py --dry-run
)

echo.
echo ============================================
echo Dry run complete - no files were generated.
echo Review the output above to see what would change.
echo ============================================
pause
