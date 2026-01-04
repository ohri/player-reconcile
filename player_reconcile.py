#!/usr/bin/env python3
"""
NFL Player Database Reconciliation Script

Reconciles player database with NFLVerse players.csv data:
- Weekly: Updates current team (REALTEAMID)
- Annual: Updates position (POSITIONID) with --full-reconcile flag
- Adds new players as needed

Generates SQL script for review before execution.
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Set

import pandas as pd
import requests
import yaml
import oracledb


class PlayerReconciler:
    """Handles reconciliation between NFLVerse data and Oracle database."""

    def __init__(self, config_path: str, dry_run: bool = False, full_reconcile: bool = False):
        """Initialize reconciler with configuration.

        Args:
            config_path: Path to YAML configuration file
            dry_run: If True, show changes without generating SQL
            full_reconcile: If True, include position reconciliation
        """
        self.dry_run = dry_run
        self.full_reconcile = full_reconcile
        self.config = self._load_config(config_path)
        self.timestamp = datetime.now().strftime(self.config['output']['timestamp_format'])

        # Setup logging
        self._setup_logging()

        # Statistics tracking
        self.stats = {
            'team_updates': 0,
            'position_updates': 0,
            'new_players': 0,
            'errors': 0,
            'warnings': 0,
            'unchanged': 0
        }

        # Error tracking
        self.errors = []
        self.warnings = []

    def _load_config(self, config_path: str) -> dict:
        """Load YAML configuration file."""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def _setup_logging(self):
        """Configure logging to console and file."""
        log_filename = f"{self.config['output']['log_file_prefix']}_{self.timestamp}.log"

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("="*80)
        self.logger.info(f"Player Reconciliation Started - {datetime.now()}")
        self.logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'SQL GENERATION'}")
        self.logger.info(f"Full Reconcile: {'YES' if self.full_reconcile else 'NO (team only)'}")
        self.logger.info("="*80)

    def get_db_connection(self):
        """Create Oracle database connection using environment variables."""
        required_vars = ['ORACLE_USER', 'ORACLE_PASSWORD', 'ORACLE_HOST', 'ORACLE_SERVICE']
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing_vars)}\n"
                "Please set: ORACLE_USER, ORACLE_PASSWORD, ORACLE_HOST, ORACLE_SERVICE"
            )

        user = os.getenv('ORACLE_USER')
        password = os.getenv('ORACLE_PASSWORD')
        host = os.getenv('ORACLE_HOST')
        port = os.getenv('ORACLE_PORT', '1521')
        service = os.getenv('ORACLE_SERVICE')

        dsn = oracledb.makedsn(host, port, service_name=service)

        self.logger.info(f"Connecting to Oracle: {user}@{host}:{port}/{service}")
        return oracledb.connect(user, password, dsn)

    def fetch_nflverse_data(self) -> pd.DataFrame:
        """Fetch fresh players.csv from NFLVerse."""
        url = self.config['nflverse']['url']
        self.logger.info(f"Fetching NFLVerse data from: {url}")

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Parse CSV from response content
            from io import StringIO
            df = pd.read_csv(StringIO(response.text), low_memory=False)

            self.logger.info(f"Fetched {len(df)} players from NFLVerse")
            return df
        except Exception as e:
            self.logger.error(f"Failed to fetch NFLVerse data: {e}")
            raise

    def fetch_database_players(self, conn) -> pd.DataFrame:
        """Fetch current player data from Oracle database."""
        query = f"""
        SELECT
            p.OID,
            p.GSIS,
            p.FIRSTNAME,
            p.LASTNAME,
            p.REALTEAMID,
            p.POSITIONID,
            p.TEAMID,
            p.ISONINJUREDRESERVE,
            rt.TEAMABBREVIATION as CURRENT_TEAM,
            pos.POSITION as CURRENT_POSITION
        FROM {self.config['database']['schema']}.TBLPLAYERS p
        LEFT JOIN {self.config['database']['schema']}.TBLREALTEAMS rt ON p.REALTEAMID = rt.OID
        LEFT JOIN {self.config['database']['schema']}.TBLPOSITIONS pos ON p.POSITIONID = pos.OID
        WHERE p.GSIS IS NOT NULL
        """

        self.logger.info("Fetching current player data from database...")
        df = pd.read_sql(query, conn)
        self.logger.info(f"Fetched {len(df)} players from database")
        return df

    def get_team_mapping(self) -> Dict[str, int]:
        """Get team abbreviation to OID mapping from config."""
        return self.config['teams']

    def get_position_mapping(self) -> Dict[str, int]:
        """Get position code to OID mapping from config."""
        return self.config['positions']

    def reconcile_players(self, nfl_df: pd.DataFrame, db_df: pd.DataFrame) -> Tuple[List[dict], List[dict]]:
        """Compare NFLVerse data with database and identify changes.

        Returns:
            Tuple of (updates, inserts) - lists of change dictionaries
        """
        updates = []
        inserts = []

        team_map = self.get_team_mapping()
        pos_map = self.get_position_mapping()

        # Create lookup for existing players
        db_lookup = db_df.set_index('GSIS').to_dict('index')

        self.logger.info("Starting reconciliation...")

        for _, nfl_player in nfl_df.iterrows():
            gsis_id = nfl_player.get('gsis_id')

            # Skip if no GSIS ID
            if pd.isna(gsis_id) or str(gsis_id).strip() == '':
                continue

            gsis_id = str(gsis_id).strip()

            # Check if player exists in database
            if gsis_id in db_lookup:
                # Existing player - check for updates
                update = self._check_player_updates(nfl_player, db_lookup[gsis_id], team_map, pos_map)
                if update:
                    updates.append(update)
                else:
                    self.stats['unchanged'] += 1
            else:
                # New player - prepare insert
                insert = self._prepare_player_insert(nfl_player, team_map, pos_map)
                if insert:
                    inserts.append(insert)

        self.logger.info(f"Reconciliation complete: {len(updates)} updates, {len(inserts)} inserts")
        return updates, inserts

    def _check_player_updates(self, nfl_player: pd.Series, db_player: dict,
                              team_map: Dict[str, int], pos_map: Dict[str, int]) -> dict:
        """Check if player needs updates.

        Returns:
            Dictionary with update information, or None if no changes needed
        """
        changes = {}
        gsis_id = str(nfl_player.get('gsis_id')).strip()
        db_oid = db_player['OID']

        # Check team update (always done)
        nfl_team = str(nfl_player.get('latest_team', '')).strip().upper()
        if nfl_team and nfl_team in team_map:
            new_team_id = team_map[nfl_team]
            old_team_id = db_player['REALTEAMID']

            if new_team_id != old_team_id:
                changes['realteamid'] = {
                    'old': old_team_id,
                    'new': new_team_id,
                    'old_abbrev': db_player.get('CURRENT_TEAM', ''),
                    'new_abbrev': nfl_team
                }
                self.stats['team_updates'] += 1
        elif nfl_team and nfl_team not in team_map:
            self.warnings.append(f"Unknown team '{nfl_team}' for player {gsis_id} - {nfl_player.get('display_name')}")
            self.stats['warnings'] += 1

        # Check position update (only if full reconcile)
        if self.full_reconcile:
            nfl_pos = str(nfl_player.get('position', '')).strip().upper()
            if nfl_pos and nfl_pos in pos_map:
                new_pos_id = pos_map[nfl_pos]
                old_pos_id = db_player['POSITIONID']

                if new_pos_id != old_pos_id:
                    changes['positionid'] = {
                        'old': old_pos_id,
                        'new': new_pos_id,
                        'old_abbrev': db_player.get('CURRENT_POSITION', ''),
                        'new_abbrev': nfl_pos
                    }
                    self.stats['position_updates'] += 1
            elif nfl_pos and nfl_pos not in pos_map:
                self.warnings.append(f"Unknown position '{nfl_pos}' for player {gsis_id} - {nfl_player.get('display_name')}")
                self.stats['warnings'] += 1

        if changes:
            return {
                'oid': db_oid,
                'gsis': gsis_id,
                'name': nfl_player.get('display_name', f"{nfl_player.get('first_name')} {nfl_player.get('last_name')}"),
                'changes': changes
            }

        return None

    def _prepare_player_insert(self, nfl_player: pd.Series,
                               team_map: Dict[str, int], pos_map: Dict[str, int]) -> dict:
        """Prepare INSERT data for new player.

        Returns:
            Dictionary with insert information, or None if required fields missing
        """
        gsis_id = str(nfl_player.get('gsis_id', '')).strip()
        first_name = str(nfl_player.get('first_name', '')).strip()
        last_name = str(nfl_player.get('last_name', '')).strip()
        nfl_team = str(nfl_player.get('latest_team', '')).strip().upper()
        nfl_pos = str(nfl_player.get('position', '')).strip().upper()

        # Validate required fields
        required = self.config['reconciliation']['required_fields_for_insert']
        missing = []

        if not gsis_id:
            missing.append('gsis_id')
        if not first_name:
            missing.append('first_name')
        if not last_name:
            missing.append('last_name')
        if not nfl_team:
            missing.append('latest_team')
        if not nfl_pos:
            missing.append('position')

        if missing:
            self.errors.append(f"Cannot insert player - missing fields {missing}: {nfl_player.get('display_name')}")
            self.stats['errors'] += 1
            return None

        # Map team and position
        team_id = team_map.get(nfl_team)
        pos_id = pos_map.get(nfl_pos)

        if not team_id:
            self.errors.append(f"Cannot insert player - unknown team '{nfl_team}': {gsis_id}")
            self.stats['errors'] += 1
            return None

        if not pos_id:
            self.errors.append(f"Cannot insert player - unknown position '{nfl_pos}': {gsis_id}")
            self.stats['errors'] += 1
            return None

        self.stats['new_players'] += 1

        return {
            'gsis': gsis_id,
            'firstname': first_name,
            'lastname': last_name,
            'realteamid': team_id,
            'positionid': pos_id,
            'jersey_number': nfl_player.get('jersey_number'),
            'display_name': nfl_player.get('display_name', f"{first_name} {last_name}")
        }

    def generate_sql_script(self, updates: List[dict], inserts: List[dict]) -> str:
        """Generate SQL script with UPDATE and INSERT statements.

        Returns:
            Filename of generated SQL script
        """
        sql_filename = f"{self.config['output']['sql_file_prefix']}_{self.timestamp}.sql"

        self.logger.info(f"Generating SQL script: {sql_filename}")

        with open(sql_filename, 'w') as f:
            # Header
            f.write("-- Player Reconciliation SQL Script\n")
            f.write(f"-- Generated: {datetime.now()}\n")
            f.write(f"-- Mode: {'FULL RECONCILE' if self.full_reconcile else 'TEAM ONLY'}\n")
            f.write(f"-- Updates: {len(updates)}\n")
            f.write(f"-- Inserts: {len(inserts)}\n")
            f.write("--\n")
            f.write("-- REVIEW THIS SCRIPT BEFORE EXECUTING\n")
            f.write("--\n\n")

            schema = self.config['database']['schema']

            # Generate UPDATE statements
            if updates:
                f.write("-- ============================================\n")
                f.write("-- PLAYER UPDATES\n")
                f.write("-- ============================================\n\n")

                for update in updates:
                    f.write(f"-- {update['name']} (GSIS: {update['gsis']})\n")

                    set_clauses = []
                    comments = []

                    if 'realteamid' in update['changes']:
                        change = update['changes']['realteamid']
                        set_clauses.append(f"REALTEAMID = {change['new']}")
                        comments.append(f"Team: {change['old_abbrev']} -> {change['new_abbrev']}")

                    if 'positionid' in update['changes']:
                        change = update['changes']['positionid']
                        set_clauses.append(f"POSITIONID = {change['new']}")
                        comments.append(f"Position: {change['old_abbrev']} -> {change['new_abbrev']}")

                    f.write(f"-- Changes: {', '.join(comments)}\n")
                    f.write(f"UPDATE {schema}.TBLPLAYERS\n")
                    f.write(f"SET {', '.join(set_clauses)}\n")
                    f.write(f"WHERE OID = {update['oid']};\n\n")

            # Generate INSERT statements
            if inserts:
                f.write("\n-- ============================================\n")
                f.write("-- NEW PLAYERS\n")
                f.write("-- ============================================\n\n")

                for insert in inserts:
                    f.write(f"-- {insert['display_name']} (GSIS: {insert['gsis']})\n")

                    # Build INSERT statement
                    columns = ['FIRSTNAME', 'LASTNAME', 'GSIS', 'REALTEAMID', 'POSITIONID', 'ISONINJUREDRESERVE']
                    values = [
                        f"'{self._escape_sql(insert['firstname'])}'",
                        f"'{self._escape_sql(insert['lastname'])}'",
                        f"'{insert['gsis']}'",
                        str(insert['realteamid']),
                        str(insert['positionid']),
                        '0'  # Default: not on IR
                    ]

                    # Add jersey number if available
                    if insert.get('jersey_number') and not pd.isna(insert['jersey_number']):
                        columns.append('JERSEYNUMBER')
                        values.append(str(int(insert['jersey_number'])))

                    f.write(f"INSERT INTO {schema}.TBLPLAYERS ({', '.join(columns)})\n")
                    f.write(f"VALUES ({', '.join(values)});\n\n")

            # Footer
            f.write("\n-- ============================================\n")
            f.write("-- COMMIT\n")
            f.write("-- ============================================\n")
            f.write("-- COMMIT;\n")
            f.write("-- Uncomment above line after reviewing changes\n")

        return sql_filename

    def _escape_sql(self, value: str) -> str:
        """Escape single quotes in SQL string values."""
        if pd.isna(value):
            return ''
        return str(value).replace("'", "''")

    def write_error_log(self):
        """Write errors and warnings to separate file."""
        if not self.errors and not self.warnings:
            return

        error_filename = f"errors_{self.timestamp}.log"

        with open(error_filename, 'w') as f:
            f.write("Player Reconciliation - Errors and Warnings\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write("="*80 + "\n\n")

            if self.errors:
                f.write("ERRORS:\n")
                f.write("-"*80 + "\n")
                for error in self.errors:
                    f.write(f"  - {error}\n")
                f.write("\n")

            if self.warnings:
                f.write("WARNINGS:\n")
                f.write("-"*80 + "\n")
                for warning in self.warnings:
                    f.write(f"  - {warning}\n")

        self.logger.info(f"Errors and warnings written to: {error_filename}")

    def print_summary(self):
        """Print summary statistics."""
        self.logger.info("\n" + "="*80)
        self.logger.info("RECONCILIATION SUMMARY")
        self.logger.info("="*80)
        self.logger.info(f"Team Updates:      {self.stats['team_updates']}")
        if self.full_reconcile:
            self.logger.info(f"Position Updates:  {self.stats['position_updates']}")
        self.logger.info(f"New Players:       {self.stats['new_players']}")
        self.logger.info(f"Unchanged:         {self.stats['unchanged']}")
        self.logger.info(f"Warnings:          {self.stats['warnings']}")
        self.logger.info(f"Errors:            {self.stats['errors']}")
        self.logger.info("="*80)

    def run(self):
        """Main execution flow."""
        try:
            # Fetch NFLVerse data
            nfl_df = self.fetch_nflverse_data()

            # Connect to database and fetch current data
            conn = self.get_db_connection()
            db_df = self.fetch_database_players(conn)
            conn.close()

            # Reconcile
            updates, inserts = self.reconcile_players(nfl_df, db_df)

            # Print summary
            self.print_summary()

            # Write error log if needed
            if self.errors or self.warnings:
                self.write_error_log()

            # Generate SQL script (unless dry run)
            if not self.dry_run:
                if updates or inserts:
                    sql_file = self.generate_sql_script(updates, inserts)
                    self.logger.info(f"\nSQL script generated: {sql_file}")
                    self.logger.info("Review the script and execute it in your Oracle environment.")
                else:
                    self.logger.info("\nNo changes detected - no SQL script generated.")
            else:
                self.logger.info("\nDRY RUN - No SQL script generated.")

            return 0

        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=True)
            return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Reconcile NFL player database with NFLVerse data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Weekly team reconciliation
  python player_reconcile.py

  # Full reconciliation (teams + positions)
  python player_reconcile.py --full-reconcile

  # Dry run to see what would change
  python player_reconcile.py --dry-run

  # Full reconcile with dry run
  python player_reconcile.py --full-reconcile --dry-run
        """
    )

    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )

    parser.add_argument(
        '--full-reconcile',
        action='store_true',
        help='Include position reconciliation (default: team only)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show changes without generating SQL script'
    )

    args = parser.parse_args()

    # Verify config file exists
    if not Path(args.config).exists():
        print(f"Error: Configuration file not found: {args.config}")
        return 1

    # Run reconciliation
    reconciler = PlayerReconciler(
        config_path=args.config,
        dry_run=args.dry_run,
        full_reconcile=args.full_reconcile
    )

    return reconciler.run()


if __name__ == '__main__':
    sys.exit(main())
