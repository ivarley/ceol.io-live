#!/usr/bin/env python3
"""
Script to refresh tunebook counts for tunes with null cache refresh dates.

This script queries the database for tunes that have never had their tunebook count
refreshed (where tunebook_count_cached_date is NULL) and updates them one by one
using the thesession.org API, with a 1-second delay between requests to avoid
rate limiting.
"""

import os
import sys
import time
import requests
import psycopg2
from dotenv import load_dotenv
from database import get_db_connection

# Load environment variables from .env file
load_dotenv()


def refresh_single_tune_count(tune_id):
    """
    Refresh the tunebook count for a single tune using thesession.org API.
    Returns tuple: (success, message, old_count, new_count)
    """
    try:
        # Fetch data from thesession.org API
        api_url = f"https://thesession.org/tunes/{tune_id}?format=json"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code != 200:
            return False, f'Failed to fetch data from thesession.org (status: {response.status_code})', None, None
        
        data = response.json()
        
        # Check if tunebooks property exists in the response
        if 'tunebooks' not in data:
            return False, 'No tunebooks data found in API response', None, None
        
        new_tunebook_count = data['tunebooks']
        
        # Update the database
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get current cached count
        cur.execute('SELECT tunebook_count_cached FROM tune WHERE tune_id = %s', (tune_id,))
        result = cur.fetchone()
        
        if not result:
            cur.close()
            conn.close()
            return False, 'Tune not found in database', None, None
        
        current_count = result[0] if result[0] is not None else 0
        
        # Update both count and cached date
        cur.execute(
            'UPDATE tune SET tunebook_count_cached = %s, tunebook_count_cached_date = CURRENT_DATE WHERE tune_id = %s',
            (new_tunebook_count, tune_id)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        return True, f'Updated tunebook count from {current_count} to {new_tunebook_count}', current_count, new_tunebook_count
        
    except requests.exceptions.RequestException as e:
        return False, f'Error connecting to thesession.org: {str(e)}', None, None
    except Exception as e:
        return False, f'Error updating tunebook count: {str(e)}', None, None


def get_tunes_needing_refresh():
    """Get all tunes that have never had their tunebook count refreshed."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('''
            SELECT tune_id, name 
            FROM tune 
            WHERE tunebook_count_cached_date IS NULL 
            ORDER BY tune_id
        ''')
        
        tunes = cur.fetchall()
        cur.close()
        conn.close()
        
        return tunes
        
    except Exception as e:
        print(f"Error fetching tunes from database: {str(e)}")
        return []


def main():
    """Main function to refresh tunebook counts for all tunes with null refresh dates."""
    
    # Check for help flag
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        print(__doc__)
        print("\nUsage: python3 refresh_tunebook_counts.py [--test] [--yes]")
        print("\nOptions:")
        print("  --test    Process only the first 5 tunes (for testing)")
        print("  --yes     Skip confirmation prompt and proceed automatically")
        print("\nThe script automatically loads environment variables from .env file.")
        print("\nRequired environment variables:")
        print("  PGHOST - PostgreSQL host")
        print("  PGDATABASE - Database name")
        print("  PGUSER - Database user")
        print("  PGPASSWORD - Database password")
        print("  PGPORT - Database port (optional, defaults to 5432)")
        print("\nThe script will:")
        print("  1. Find all tunes with null tunebook_count_cached_date")
        print("  2. Refresh their counts from thesession.org API")
        print("  3. Wait 1 second between each request to avoid rate limiting")
        sys.exit(0)
    
    print("Starting tunebook count refresh for tunes with null cache dates...")
    
    # Check environment variables
    required_vars = ['PGHOST', 'PGDATABASE', 'PGUSER', 'PGPASSWORD']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print("Error: Missing required environment variables:")
        for var in missing_vars:
            print(f"  {var}")
        print("\nPlease ensure these variables are set in your .env file.")
        print("Run 'python3 refresh_tunebook_counts.py --help' for more information.")
        sys.exit(1)
    
    print("Environment variables loaded successfully.")
    print("Connecting to database to find tunes needing refresh...")
    
    # Get tunes that need refreshing
    tunes = get_tunes_needing_refresh()
    
    if not tunes:
        print("No tunes found that need refreshing.")
        return
    
    print(f"Found {len(tunes)} tunes that need tunebook count refresh.")
    
    # Check for flags
    test_mode = '--test' in sys.argv
    skip_confirm = '--yes' in sys.argv
    
    if test_mode:
        tunes = tunes[:5]  # Process only first 5 tunes in test mode
        print(f"TEST MODE: Processing only first {len(tunes)} tunes.")
    else:
        # Ask for confirmation for large batches (unless --yes flag is used)
        if len(tunes) > 10 and not skip_confirm:
            estimated_time = len(tunes) // 60  # rough estimate in minutes
            response = input(f"This will process {len(tunes)} tunes (estimated {estimated_time}+ minutes). Continue? (y/N): ")
            if response.lower() not in ['y', 'yes']:
                print("Cancelled by user.")
                return
    
    success_count = 0
    error_count = 0
    
    for i, (tune_id, tune_name) in enumerate(tunes, 1):
        print(f"[{i}/{len(tunes)}] Processing tune {tune_id}: {tune_name}")
        
        success, message, old_count, new_count = refresh_single_tune_count(tune_id)
        
        if success:
            print(f"  ✓ {message}")
            success_count += 1
        else:
            print(f"  ✗ {message}")
            error_count += 1
        
        # Wait 1 second between requests to avoid rate limiting
        if i < len(tunes):  # Don't wait after the last tune
            print("  Waiting 1 second...")
            time.sleep(1)
    
    print(f"\nRefresh complete!")
    print(f"Successfully updated: {success_count}")
    print(f"Errors: {error_count}")
    print(f"Total processed: {len(tunes)}")


if __name__ == "__main__":
    main()