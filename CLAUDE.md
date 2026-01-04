# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an NFL player database reconciliation tool that syncs an Oracle database with NFLVerse player data. The script fetches fresh player data from NFLVerse, compares it with the database, and generates SQL scripts for updates rather than modifying the database directly.

**Key workflow:**
1. Fetch fresh `players.csv` from NFLVerse GitHub releases
2. Query Oracle database for current player data (single query, all players with GSIS IDs)
3. Reconcile in-memory using pandas DataFrames
4. Generate SQL script with UPDATE statements (team/position changes) and INSERT statements (new players)
5. User reviews and executes SQL script manually

## Architecture

### Core Components

**PlayerReconciler class** (`player_reconcile.py`):
- Single entry point that orchestrates entire reconciliation flow
- Uses pandas for efficient in-memory comparison of thousands of players
- Optimized for VPN/remote database access (minimal database roundtrips)
- Generates timestamped output files: SQL scripts, logs, error reports

**Configuration system** (`config.yaml`):
- Maps NFLVerse team abbreviations (e.g., "KC", "SF") to Oracle TBLREALTEAMS.OID integers
- Maps NFLVerse position codes (e.g., "QB", "WR") to Oracle TBLPOSITIONS.OID integers
- **CRITICAL**: These mappings must match the actual OID values in the database tables

**Database schema** (Oracle):
- `TBLPLAYERS`: Main player table with GSIS (NFLVerse ID), REALTEAMID (current NFL team), POSITIONID, FIRSTNAME, LASTNAME
- `TBLREALTEAMS`: NFL teams with OID and TEAMABBREVIATION
- `TBLPOSITIONS`: Positions with OID and POSITION code
- **Important**: TBLPLAYERS has triggers that automatically log changes to TBLPLAYERHISTORY

### Reconciliation Modes

**Weekly mode (default)**: Only reconciles REALTEAMID (current team)
- Run several times per week during NFL season
- Does NOT update positions (they rarely change mid-season)
- Command: `python player_reconcile.py`

**Annual/Full mode**: Reconciles both REALTEAMID and POSITIONID
- Run once before season starts
- Includes position changes (rookie position assignments, conversions, etc.)
- Command: `python player_reconcile.py --full-reconcile`

**Dry run mode**: Shows what would change without generating SQL
- Command: `python player_reconcile.py --dry-run`

### Data Matching

**Primary key**: GSIS ID from NFLVerse matches TBLPLAYERS.GSIS column
- All reconciliation is GSIS-based (not name-based)
- Players without GSIS IDs are skipped
- New players from NFLVerse with GSIS IDs will be inserted

**Status handling**:
- Practice squad (DEV), IR (RES), and cut (CUT) players keep their team assignment
- Script does NOT automatically update ISONINJUREDRESERVE flag
- This behavior is configurable in `config.yaml` under `status_rules:`

## Development Commands

### Setup
```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure database credentials
cp .env.example .env
# Edit .env with actual Oracle connection details

# Load environment variables (required before running)
# Windows PowerShell:
Get-Content .env | ForEach-Object { $name, $value = $_.split('='); Set-Item -Path "env:$name" -Value $value }
# Linux/Mac:
export $(cat .env | xargs)
```

### Running Reconciliation

```bash
# Test what would change (recommended first run)
python player_reconcile.py --dry-run

# Weekly reconciliation (team updates only)
python player_reconcile.py

# Full reconciliation (teams + positions)
python player_reconcile.py --full-reconcile

# Use custom config
python player_reconcile.py --config custom_config.yaml
```

**Windows batch scripts** (convenience wrappers that handle env loading):
- `run_weekly.bat` - Weekly team reconciliation
- `run_annual.bat` - Full reconciliation with confirmation prompt
- `run_dryrun.bat` - Interactive dry run mode selector

### Output Files

Generated files use timestamp format `YYYYMMDD_HHMMSS`:
- `player_reconcile_{timestamp}.sql` - SQL script to review and execute
- `player_reconcile_{timestamp}.log` - Detailed execution log
- `errors_{timestamp}.log` - Warnings/errors (only if issues occurred)

## Critical Implementation Details

### Oracle Connection
- Uses environment variables (ORACLE_USER, ORACLE_PASSWORD, ORACLE_HOST, ORACLE_PORT, ORACLE_SERVICE)
- Connection is opened once, query executed, then closed immediately
- Uses `python-oracledb` library (modern replacement for cx_Oracle)
- Works in "thin" mode without requiring Oracle Instant Client

### Team/Position Mapping Maintenance
When adding new teams or positions:
1. Insert new record in Oracle (TBLREALTEAMS or TBLPOSITIONS)
2. Note the auto-generated OID from the sequence trigger
3. Update `config.yaml` with the new mapping
4. If NFLVerse uses abbreviation not in config, script will log warning in errors file

### SQL Script Safety
- All generated SQL uses parameterized OID values (not string concatenation for names)
- Single quotes in player names are escaped (`O'Brien` → `O''Brien`)
- COMMIT statement is commented out by default
- INSERT statements for new players include only required fields + jersey number (if available)

### Database Triggers
When SQL script is executed, these triggers fire automatically:
- `TR_TBLPLAYERS_B_INS`: Auto-generates OID from sequence for new players
- `tr_tblplayer_a_upd`: Logs changes to TBLPLAYERHISTORY with narrative
- `tr_tblplayer_b_upd`: Clears STARTER field when player goes on IR or is cut

## Troubleshooting

**"Missing required environment variables"**: Environment variables not loaded. Run the appropriate command for your OS to load .env file.

**"Unknown team 'XXX' for player..."**: NFLVerse has a team abbreviation not in config.yaml. Add mapping under `teams:` section after verifying OID in TBLREALTEAMS.

**"Cannot insert player - unknown position 'XXX'"**: NFLVerse has a position code not in config.yaml. Add mapping under `positions:` section after verifying OID in TBLPOSITIONS.

**Database connection errors**: python-oracledb runs in "thin" mode by default (no Oracle Instant Client required). Check that environment variables are correctly set and database is accessible.

## NFLVerse Data Source

- URL: https://github.com/nflverse/nflverse-data/releases/download/players/players.csv
- Always fetches fresh data (no caching)
- Key fields: `gsis_id`, `display_name`, `first_name`, `last_name`, `latest_team`, `position`, `status`, `jersey_number`
- Sample CSV included in repo as `players.csv` but script always fetches live data
