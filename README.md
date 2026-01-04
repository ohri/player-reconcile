# NFL Player Database Reconciliation

Efficient Python script to reconcile your Oracle player database with NFLVerse player data.

## Features

- **Efficient Processing**: Handles thousands of players using pandas for fast in-memory operations
- **Flexible Reconciliation**:
  - Weekly: Updates current team (REALTEAMID)
  - Annual: Updates positions (POSITIONID) with `--full-reconcile` flag
  - Automatic: Adds new players to database
- **Safe SQL Generation**: Creates reviewable SQL scripts instead of direct database modifications
- **Comprehensive Logging**:
  - Detailed change logs
  - Summary statistics
  - Error/warning reports
- **Dry Run Mode**: Preview changes without generating SQL
- **Configurable**: External YAML config for team/position mappings

## Prerequisites

1. **Python 3.8+**
2. **Oracle Database Access**
   - python-oracledb works in "thin" mode without Oracle Instant Client
   - Optional: Oracle Instant Client for "thick" mode (advanced features)
3. **Network Access**:
   - VPN connection to database server (if remote)
   - Internet access to fetch NFLVerse data

## Installation

### 1. Clone or Download This Repository

```bash
cd C:\Users\raman\dev\player-reconcile
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note**: This project uses `python-oracledb`, the modern replacement for `cx_Oracle`. It works without Oracle Instant Client in most cases.

### 4. Configure Environment Variables

Copy the example environment file and fill in your database credentials:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:
```bash
ORACLE_USER=your_username
ORACLE_PASSWORD=your_password
ORACLE_HOST=192.168.1.100
ORACLE_PORT=1521
ORACLE_SERVICE=your_service_name
```

**Load environment variables before running:**

Windows (PowerShell):
```powershell
Get-Content .env | ForEach-Object {
    $name, $value = $_.split('=')
    Set-Item -Path "env:$name" -Value $value
}
```

Windows (Command Prompt):
```cmd
for /F "tokens=*" %i in (.env) do set %i
```

Linux/Mac:
```bash
export $(cat .env | xargs)
```

### 5. Review and Customize config.yaml

The `config.yaml` file contains:
- Team abbreviation to database OID mappings
- Position code to database OID mappings
- Status handling rules
- Output settings

**Important**: Verify the team and position OIDs match your database!

To check your database values:
```sql
-- Check team mappings
SELECT OID, TEAMABBREVIATION, TEAMNAME FROM NETFL.TBLREALTEAMS ORDER BY OID;

-- Check position mappings
SELECT OID, POSITION FROM NETFL.TBLPOSITIONS ORDER BY OID;
```

Update `config.yaml` if your OIDs differ.

## Usage

### Basic Usage

#### Weekly Team Reconciliation
Run several times a week during the season to update player teams:

```bash
python player_reconcile.py
```

This will:
1. Fetch fresh players.csv from NFLVerse
2. Connect to your Oracle database
3. Identify team changes
4. Generate SQL script: `player_reconcile_YYYYMMDD_HHMMSS.sql`
5. Create log file: `player_reconcile_YYYYMMDD_HHMMSS.log`

#### Full Reconciliation (Pre-Season)
Run once before the season to update both teams AND positions:

```bash
python player_reconcile.py --full-reconcile
```

#### Dry Run (Preview Changes)
See what would change without generating SQL:

```bash
python player_reconcile.py --dry-run
```

Or combine with full reconcile:
```bash
python player_reconcile.py --full-reconcile --dry-run
```

### Advanced Options

```bash
python player_reconcile.py --help
```

Options:
- `--config PATH`: Use custom config file (default: config.yaml)
- `--full-reconcile`: Include position updates
- `--dry-run`: Preview changes only

## Workflow

### Typical Weekly Run

1. **Connect to VPN** (if database is remote)

2. **Set environment variables**:
   ```powershell
   Get-Content .env | ForEach-Object { $name, $value = $_.split('='); Set-Item -Path "env:$name" -Value $value }
   ```

3. **Run reconciliation**:
   ```bash
   python player_reconcile.py
   ```

4. **Review output**:
   - Check console for summary statistics
   - Review log file for detailed changes
   - Check errors_YYYYMMDD_HHMMSS.log if present

5. **Review SQL script**:
   ```bash
   # Open and review the generated SQL file
   notepad player_reconcile_YYYYMMDD_HHMMSS.sql
   ```

6. **Execute SQL**:
   - Connect to Oracle with SQL Developer, SQL*Plus, or your preferred tool
   - Execute the reviewed SQL script
   - Commit changes

### Typical Annual Run (Pre-Season)

Same as weekly, but use `--full-reconcile` flag:

```bash
python player_reconcile.py --full-reconcile
```

This will update both teams and positions.

## Output Files

### Generated Files

1. **SQL Script**: `player_reconcile_YYYYMMDD_HHMMSS.sql`
   - Contains UPDATE statements for changed players
   - Contains INSERT statements for new players
   - COMMIT statement is commented out for safety

2. **Log File**: `player_reconcile_YYYYMMDD_HHMMSS.log`
   - Detailed execution log
   - Shows each step of the process
   - Lists all changes found

3. **Error Log**: `errors_YYYYMMDD_HHMMSS.log` (if errors/warnings occur)
   - Unknown team abbreviations
   - Unknown position codes
   - Missing required fields
   - Other issues

### Example SQL Output

```sql
-- Player Reconciliation SQL Script
-- Generated: 2024-12-30 10:15:23
-- Mode: TEAM ONLY
-- Updates: 47
-- Inserts: 12

-- ============================================
-- PLAYER UPDATES
-- ============================================

-- Patrick Mahomes (GSIS: 00-0033873)
-- Changes: Team: KC -> MIA
UPDATE NETFL.TBLPLAYERS
SET REALTEAMID = 20
WHERE OID = 12345;

-- ...more updates...

-- ============================================
-- NEW PLAYERS
-- ============================================

-- John Doe (GSIS: 00-0039999)
INSERT INTO NETFL.TBLPLAYERS (FIRSTNAME, LASTNAME, GSIS, REALTEAMID, POSITIONID, ISONINJUREDRESERVE, JERSEYNUMBER)
VALUES ('John', 'Doe', '00-0039999', 9, 1, 0, 15);

-- ...more inserts...

-- ============================================
-- COMMIT
-- ============================================
-- COMMIT;
-- Uncomment above line after reviewing changes
```

## Troubleshooting

### Connection Errors

**Error**: `Missing required environment variables`
- Make sure you've loaded the .env file
- Verify all required variables are set: `echo %ORACLE_USER%` (Windows) or `echo $ORACLE_USER` (Linux/Mac)

**Error**: Database connection errors
- python-oracledb uses "thin" mode by default (no client library needed)
- If you need thick mode features, install Oracle Instant Client
- Check ORACLE_HOST, ORACLE_PORT, and ORACLE_SERVICE are correct

**Error**: `ORA-12170: TNS:Connect timeout occurred`
- Verify VPN connection is active
- Check ORACLE_HOST and ORACLE_PORT are correct
- Test connection with SQL*Plus or SQL Developer

### Data Issues

**Warning**: `Unknown team 'XXX' for player...`
- NFLVerse has a team abbreviation not in your config.yaml
- Add mapping to `config.yaml` under `teams:` section
- Verify team exists in TBLREALTEAMS

**Warning**: `Unknown position 'XXX' for player...`
- NFLVerse has a position code not in your config.yaml
- Add mapping to `config.yaml` under `positions:` section
- Verify position exists in TBLPOSITIONS

**Error**: `Cannot insert player - missing fields`
- NFLVerse data is incomplete for some players
- These players will be skipped
- Review errors_YYYYMMDD_HHMMSS.log for details

## Configuration Details

### Team Mappings

The `teams:` section in config.yaml maps NFLVerse team abbreviations to your database OIDs:

```yaml
teams:
  ARI: 1    # Arizona Cardinals
  ATL: 2    # Atlanta Falcons
  # ...
  FA: 33    # Free Agent
```

### Position Mappings

The `positions:` section maps NFLVerse position codes to your database OIDs:

```yaml
positions:
  QB: 1     # Quarterback
  RB: 2     # Running Back
  # ...
```

### Status Handling

Practice squad, IR, and waived players:
- Script keeps their latest_team from NFLVerse
- Does NOT automatically set ISONINJUREDRESERVE flag
- You can customize this in config.yaml under `status_rules:`

## Database Triggers

**Important**: The database has triggers on TBLPLAYERS:
- `tr_tblplayer_a_upd`: Logs changes to TBLPLAYERHISTORY
- `tr_tblplayer_b_upd`: Clears STARTER field when player goes on IR or cut

These triggers will fire when you execute the generated SQL script.

## Security Notes

- Never commit `.env` file to version control
- Add `.env` to `.gitignore`
- Use read-only database credentials if possible
- Always review SQL scripts before executing
- Keep backups before running updates

## Performance

- Typical runtime: 10-30 seconds for ~5000 players
- Uses pandas for efficient in-memory processing
- Single database query to fetch all players
- Batch SQL generation

## Future Migration

When moving to same network as database server:
- Update ORACLE_HOST to local server address
- May get better performance
- No VPN connection needed
- Script works exactly the same

## Support

For issues:
1. Check the log files
2. Review error messages
3. Verify database connectivity
4. Check config.yaml mappings
5. Ensure NFLVerse URL is accessible

## License

Internal use only.
