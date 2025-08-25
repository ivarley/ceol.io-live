#!/usr/bin/env python3
"""
Database Backup Script for ceol.io Production Database

This script creates a complete backup of all tables and data in the production database.
It generates SQL INSERT statements that can be used to restore the data.

Usage:
    python backup_database.py

Environment variables needed (same as your Flask app):
    PGHOST, PGDATABASE, PGUSER, PGPASSWORD, PGPORT

Output:
    - backup_YYYY-MM-DD_HH-MM-SS.sql file with all data
    - Compressed backup_YYYY-MM-DD_HH-MM-SS.sql.gz file
"""

import os
import psycopg2
import psycopg2.extras
from datetime import datetime
import gzip
import sys
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

def get_all_tables(cursor):
    """Get list of all user tables in the database, ordered for proper restore"""
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY 
            -- Base tables first, then history tables
            CASE WHEN table_name LIKE '%_history' THEN 2 ELSE 1 END,
            table_name;
    """)
    return [row[0] for row in cursor.fetchall()]

def get_table_schema(cursor, table_name):
    """Get column information for a table"""
    cursor.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = %s
        ORDER BY ordinal_position;
    """, (table_name,))
    return cursor.fetchall()

def escape_sql_value(value):
    """Escape SQL values for INSERT statements"""
    if value is None:
        return 'NULL'
    elif isinstance(value, str):
        # Escape single quotes by doubling them
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    elif hasattr(value, 'isoformat'):  # datetime, date
        return f"'{value.isoformat()}'"
    else:
        # For other types, convert to string and escape
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"

def backup_table_data(cursor, table_name, file_handle):
    """Backup all data from a table"""
    print(f"Backing up table: {table_name}")
    
    # Get table schema
    schema = get_table_schema(cursor, table_name)
    columns = [col[0] for col in schema]
    
    # Get row count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
    row_count = cursor.fetchone()[0]
    
    if row_count == 0:
        file_handle.write(f"\n-- Table {table_name} is empty\n")
        return
    
    print(f"  Found {row_count} rows")
    
    # Write table header
    file_handle.write(f"\n-- Backup of table: {table_name}\n")
    file_handle.write(f"-- Rows: {row_count}\n")
    file_handle.write(f"-- Generated: {datetime.now().isoformat()}\n\n")
    
    # Get all data
    column_list = ', '.join(columns)
    cursor.execute(f"SELECT {column_list} FROM {table_name} ORDER BY 1;")
    
    # Write INSERT statements in batches
    batch_size = 100
    rows_processed = 0
    
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
            
        # Create multi-row INSERT statement
        file_handle.write(f"INSERT INTO {table_name} ({column_list}) VALUES\n")
        
        for i, row in enumerate(rows):
            values = [escape_sql_value(val) for val in row]
            values_str = '(' + ', '.join(values) + ')'
            
            if i == len(rows) - 1:  # Last row in batch
                file_handle.write(f"  {values_str};\n")
            else:
                file_handle.write(f"  {values_str},\n")
        
        rows_processed += len(rows)
        file_handle.write(f"\n")
        
        if rows_processed % 1000 == 0:
            print(f"  Processed {rows_processed}/{row_count} rows")
    
    print(f"  Completed: {rows_processed} rows")

def create_backup():
    """Create a complete database backup"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Create backup directory path relative to project root
    backup_dir = os.path.join(project_root, 'data', 'backup')
    os.makedirs(backup_dir, exist_ok=True)
    
    backup_filename = os.path.join(backup_dir, f"backup_{timestamp}.sql")
    compressed_filename = os.path.join(backup_dir, f"backup_{timestamp}.sql.gz")
    
    print(f"Creating database backup: {backup_filename}")
    print("=" * 50)
    
    # Connect to database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get all tables
        tables = get_all_tables(cursor)
        base_tables = [t for t in tables if not t.endswith('_history')]
        history_tables = [t for t in tables if t.endswith('_history')]
        
        print(f"Found {len(tables)} tables:")
        print(f"  Base tables ({len(base_tables)}): {', '.join(base_tables)}")
        print(f"  History/audit tables ({len(history_tables)}): {', '.join(history_tables)}")
        print()
        
        # Create backup file
        with open(backup_filename, 'w', encoding='utf-8') as f:
            # Write header
            f.write("-- ceol.io Database Backup\n")
            f.write(f"-- Generated: {datetime.now().isoformat()}\n")
            f.write(f"-- Database: {os.environ.get('PGDATABASE')}\n")
            f.write(f"-- Host: {os.environ.get('PGHOST')}\n")
            f.write("-- \n")
            f.write("-- This file contains INSERT statements to restore all data.\n")
            f.write("-- Run this against an empty database with the same schema.\n")
            f.write("-- \n")
            f.write(f"-- Tables included:\n")
            f.write(f"--   Base tables ({len(base_tables)}): {', '.join(base_tables)}\n")
            f.write(f"--   History/audit tables ({len(history_tables)}): {', '.join(history_tables)}\n")
            f.write("-- \n")
            f.write("-- NOTE: History tables contain audit trails for undo/diff functionality.\n")
            f.write("--       All base tables have created_date and last_modified_date columns.\n")
            f.write("-- \n\n")
            
            f.write("-- Disable triggers and constraints during restore for speed\n")
            f.write("SET session_replication_role = replica;\n\n")
            
            # Backup each table
            for table in tables:
                backup_table_data(cursor, table, f)
            
            f.write("\n-- Re-enable triggers and constraints\n")
            f.write("SET session_replication_role = DEFAULT;\n")
            f.write("\n-- Backup completed successfully\n")
        
        print(f"\nBackup completed: {backup_filename}")
        
        # Create compressed version
        print(f"Creating compressed backup: {compressed_filename}")
        with open(backup_filename, 'rb') as f_in:
            with gzip.open(compressed_filename, 'wb') as f_out:
                f_out.writelines(f_in)
        
        # Get file sizes
        original_size = os.path.getsize(backup_filename) / (1024 * 1024)  # MB
        compressed_size = os.path.getsize(compressed_filename) / (1024 * 1024)  # MB
        
        print(f"\nBackup files created:")
        print(f"  {backup_filename} ({original_size:.1f} MB)")
        print(f"  {compressed_filename} ({compressed_size:.1f} MB)")
        print(f"  Compression ratio: {(compressed_size/original_size)*100:.1f}%")
        
    except Exception as e:
        print(f"Error during backup: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()

def main():
    """Main function"""
    print("ceol.io Database Backup Script")
    print("=" * 40)
    
    # Check environment variables
    required_vars = ['PGHOST', 'PGDATABASE', 'PGUSER', 'PGPASSWORD']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these variables or update your .env file")
        sys.exit(1)
    
    print(f"Database: {os.environ.get('PGDATABASE')}")
    print(f"Host: {os.environ.get('PGHOST')}")
    print(f"User: {os.environ.get('PGUSER')}")
    print()
    
    # Confirm before proceeding (skip if not interactive or --yes flag)
    if '--yes' in sys.argv or not sys.stdin.isatty():
        print("Proceeding with backup (non-interactive mode)")
    else:
        response = input("Proceed with backup? (y/N): ")
        if response.lower() != 'y':
            print("Backup cancelled")
            sys.exit(0)
    
    create_backup()
    print("\nBackup completed successfully!")

if __name__ == "__main__":
    main()