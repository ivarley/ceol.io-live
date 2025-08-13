# Database Backup and Restore

This directory contains scripts to backup and restore the ceol.io production database.

## Backup Script

### Usage
```bash
# From project root:
python scripts/backup_database.py

# Or from scripts directory:
cd scripts
python backup_database.py
```

### What it does
- Connects to your production database using the same environment variables as your Flask app
- Exports all data from all tables as SQL INSERT statements
- Creates two files in `/data/backup/`:
  - `backup_YYYY-MM-DD_HH-MM-SS.sql` - Full SQL backup
  - `backup_YYYY-MM-DD_HH-MM-SS.sql.gz` - Compressed version (much smaller)

### Environment Variables Required
The script uses the same environment variables as your Flask app:
- `PGHOST` - Database host
- `PGDATABASE` - Database name  
- `PGUSER` - Database user
- `PGPASSWORD` - Database password
- `PGPORT` - Database port (optional, defaults to 5432)

### Features
- **Safe**: Only reads data, never modifies the database
- **Complete**: Backs up all tables and all data
- **Efficient**: Uses batched INSERT statements for better performance
- **Compressed**: Creates both regular and gzipped versions
- **Informative**: Shows progress and file sizes

## Restore Script

### Usage
```bash
# From project root:
python scripts/restore_database.py backup_2024-01-15_14-30-00.sql
# or
python scripts/restore_database.py backup_2024-01-15_14-30-00.sql.gz

# From scripts directory (will auto-find files in ../data/backup/):
cd scripts
python restore_database.py backup_2024-01-15_14-30-00.sql.gz
```

### What it does
- Connects to a target database
- Executes all the SQL INSERT statements from the backup file
- Restores all your data

### Important Notes
- **Schema Required**: The target database must already have the correct schema (tables, columns, etc.)
- **Additive**: This adds data to existing tables - it doesn't clear them first
- **For Clean Restore**: Make sure target database tables are empty if you want a clean restore

## Recommended Backup Strategy

1. **Regular Backups**: Run the backup script regularly (daily/weekly)
2. **Store Safely**: Keep backup files in a secure location separate from your production server
3. **Test Restores**: Periodically test the restore process on a test database
4. **Keep Multiple**: Don't delete old backups immediately - keep several recent ones

## Example Workflow

```bash
# Create a backup
python backup_database.py

# This creates files like:
# backup_2024-01-15_14-30-00.sql (15.2 MB)
# backup_2024-01-15_14-30-00.sql.gz (2.1 MB)

# To restore later (on a database with existing schema):
python restore_database.py backup_2024-01-15_14-30-00.sql.gz
```

## Emergency Recovery Process

If you lose all production data:

1. **Set up fresh database** with the same schema (run your schema creation scripts)
2. **Run restore script** with your most recent backup:
   ```bash
   python restore_database.py backup_YYYY-MM-DD_HH-MM-SS.sql.gz
   ```
3. **Verify data** by checking your application

## Security Notes

- Backup files contain all your data in plain text - store them securely
- The compressed (.gz) files are much smaller and easier to transfer/store
- Never commit backup files to version control
- Consider encrypting backup files if storing in cloud storage