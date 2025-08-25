#!/usr/bin/env python3
"""
Database Restore Script for ceol.io

This script restores data from a backup file created by backup_database.py

Usage:
    python restore_database.py backup_2024-01-15_14-30-00.sql
    python restore_database.py backup_2024-01-15_14-30-00.sql.gz

Environment variables needed:
    PGHOST, PGDATABASE, PGUSER, PGPASSWORD, PGPORT

WARNING: This will add data to the target database. 
Make sure the database schema exists and matches the backup.
"""

import os
import sys
import gzip
import psycopg2
from dotenv import load_dotenv

# Load environment variables from parent directory
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
load_dotenv(os.path.join(project_root, '.env'))

def get_db_connection():
    """Create database connection using environment variables"""
    try:
        conn = psycopg2.connect(
            host=os.environ.get('PGHOST'),
            database=os.environ.get('PGDATABASE'),
            user=os.environ.get('PGUSER'),
            password=os.environ.get('PGPASSWORD'),
            port=int(os.environ.get('PGPORT', 5432))
        )
        return conn
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        sys.exit(1)

def restore_from_file(backup_file):
    """Restore data from backup file"""
    # If file doesn't exist, try looking in data/backup directory
    if not os.path.exists(backup_file):
        backup_dir_path = os.path.join(project_root, 'data', 'backup', backup_file)
        if os.path.exists(backup_dir_path):
            backup_file = backup_dir_path
        else:
            print(f"Error: Backup file not found: {backup_file}")
            print(f"Also tried: {backup_dir_path}")
            sys.exit(1)
    
    print(f"Restoring from: {backup_file}")
    
    # Connect to database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Open file (handle both compressed and uncompressed)
        if backup_file.endswith('.gz'):
            file_handle = gzip.open(backup_file, 'rt', encoding='utf-8')
        else:
            file_handle = open(backup_file, 'r', encoding='utf-8')
        
        # Read and execute SQL
        sql_content = file_handle.read()
        file_handle.close()
        
        print("Executing SQL statements...")
        cursor.execute(sql_content)
        conn.commit()
        
        print("Restore completed successfully!")
        
    except Exception as e:
        print(f"Error during restore: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()

def main():
    """Main function"""
    if len(sys.argv) != 2:
        print("Usage: python restore_database.py <backup_file>")
        print("Example: python restore_database.py backup_2024-01-15_14-30-00.sql")
        sys.exit(1)
    
    backup_file = sys.argv[1]
    
    print("ceol.io Database Restore Script")
    print("=" * 40)
    
    # Check environment variables
    required_vars = ['PGHOST', 'PGDATABASE', 'PGUSER', 'PGPASSWORD']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)
    
    print(f"Target Database: {os.environ.get('PGDATABASE')}")
    print(f"Host: {os.environ.get('PGHOST')}")
    print(f"Backup File: {backup_file}")
    print()
    
    print("WARNING: This will add data to the target database.")
    print("Make sure the database schema exists and is empty if you want a clean restore.")
    print()
    
    response = input("Proceed with restore? (y/N): ")
    if response.lower() != 'y':
        print("Restore cancelled")
        sys.exit(0)
    
    restore_from_file(backup_file)

if __name__ == "__main__":
    main()