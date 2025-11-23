#!/usr/bin/env python3
"""
Script to cache missing settings in the system.

This script:
1. Collects all setting IDs from:
   - person_tune.setting_id
   - session_tune.setting_id
   - session_instance_tune.setting_override
   - Default (first) settings for tunes that don't have any cached settings yet
2. Filters out settings that are already cached (have ABC and both images)
3. Processes only missing settings in batches
4. Creates tune_setting records and generates images (same as "Fetch" button)
"""

import os
import sys
import time
import requests
import psycopg2
from collections import defaultdict
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path so we can import from the main app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_connection, extract_abc_incipit


def render_abc_to_png(abc_notation, is_incipit=False):
    """
    Call the ABC renderer microservice to convert ABC notation to PNG image.
    Returns the PNG image as bytes, or None if rendering fails.

    Args:
        abc_notation: ABC notation string to render
        is_incipit: If True, uses minimal padding for compact rendering (default: False)
    """
    try:
        abc_renderer_url = os.getenv('ABC_RENDERER_URL')
        if not abc_renderer_url:
            print("Warning: ABC_RENDERER_URL not configured")
            return None

        response = requests.post(
            f'{abc_renderer_url}/api/render',
            json={'abc': abc_notation, 'isIncipit': is_incipit},
            timeout=15
        )

        if response.status_code == 200:
            if response.headers.get('content-type') == 'image/png':
                return response.content
            else:
                print(f"Unexpected content type: {response.headers.get('content-type')}")
                return None
        else:
            print(f"ABC renderer returned status {response.status_code}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error calling ABC renderer: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error in render_abc_to_png: {e}")
        return None


def collect_setting_ids():
    """
    Collect all setting IDs that need to be cached.
    Returns a dict mapping (tune_id, setting_id) to count of occurrences.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    settings_needed = defaultdict(int)  # (tune_id, setting_id) -> count

    print("Collecting setting IDs from person_tune...")
    cur.execute("""
        SELECT DISTINCT tune_id, setting_id
        FROM person_tune
        WHERE setting_id IS NOT NULL
    """)
    for row in cur.fetchall():
        settings_needed[(row[0], row[1])] += 1
    print(f"  Found {len(settings_needed)} unique tune/setting combinations from person_tune")

    print("Collecting setting IDs from session_tune...")
    cur.execute("""
        SELECT DISTINCT tune_id, setting_id
        FROM session_tune
        WHERE setting_id IS NOT NULL
    """)
    for row in cur.fetchall():
        settings_needed[(row[0], row[1])] += 1
    print(f"  Total unique combinations so far: {len(settings_needed)}")

    print("Collecting setting IDs from session_instance_tune...")
    cur.execute("""
        SELECT DISTINCT tune_id, setting_override
        FROM session_instance_tune
        WHERE setting_override IS NOT NULL
    """)
    for row in cur.fetchall():
        settings_needed[(row[0], row[1])] += 1
    print(f"  Total unique combinations so far: {len(settings_needed)}")

    cur.close()
    conn.close()

    return settings_needed


def get_all_tune_ids():
    """Get all tune IDs in the system."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT tune_id FROM tune ORDER BY tune_id")
    tune_ids = [row[0] for row in cur.fetchall()]

    cur.close()
    conn.close()

    return tune_ids


def fetch_default_settings_for_tunes(tune_ids):
    """
    Fetch the first (default) setting for tunes that don't have any cached settings yet.
    Returns a dict mapping (tune_id, setting_id) to True for settings found.
    """
    # First, check which tunes already have cached settings
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT tune_id
        FROM tune_setting
        WHERE tune_id = ANY(%s)
          AND abc IS NOT NULL
          AND image IS NOT NULL
          AND incipit_image IS NOT NULL
    """, (tune_ids,))

    tunes_with_cache = set(row[0] for row in cur.fetchall())
    cur.close()
    conn.close()

    # Filter to only tunes without any cached settings
    tunes_needing_defaults = [tid for tid in tune_ids if tid not in tunes_with_cache]

    print(f"\nChecking default settings for tunes without cache...")
    print(f"  Total tunes in system: {len(tune_ids)}")
    print(f"  Tunes with cached settings: {len(tunes_with_cache)}")
    print(f"  Tunes needing default settings: {len(tunes_needing_defaults)}")

    if not tunes_needing_defaults:
        print("  All tunes already have cached settings!")
        return {}

    default_settings = {}

    print(f"\nFetching default settings for {len(tunes_needing_defaults)} tunes from thesession.org...")

    for i, tune_id in enumerate(tunes_needing_defaults, 1):
        if i % 10 == 0:
            print(f"  Progress: {i}/{len(tunes_needing_defaults)} tunes checked")

        try:
            # Fetch data from thesession.org API
            api_url = f"https://thesession.org/tunes/{tune_id}?format=json"
            response = requests.get(api_url, timeout=10)

            if response.status_code != 200:
                print(f"  Warning: Failed to fetch tune {tune_id} (status: {response.status_code})")
                continue

            data = response.json()

            # Check if settings exist in the response
            if "settings" not in data or not data["settings"]:
                print(f"  Warning: No settings found for tune {tune_id}")
                continue

            # Get the first setting (default)
            first_setting = data["settings"][0]
            setting_id = first_setting["id"]

            default_settings[(tune_id, setting_id)] = True

            # Be nice to thesession.org API - rate limit
            time.sleep(0.1)

        except Exception as e:
            print(f"  Error fetching tune {tune_id}: {e}")
            continue

    print(f"  Found default settings for {len(default_settings)} tunes")

    return default_settings


def fetch_abc_from_thesession(tune_id, setting_id):
    """
    Fetch ABC notation for a specific setting from thesession.org API.
    Returns (key, abc, incipit_abc) tuple.
    Raises exception if fetching fails.
    """
    # Fetch data from thesession.org API
    api_url = f"https://thesession.org/tunes/{tune_id}?format=json"
    response = requests.get(api_url, timeout=10)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch from API (status: {response.status_code})")

    data = response.json()

    # Check if settings exist in the response
    if "settings" not in data or not data["settings"]:
        raise Exception("No settings found for this tune")

    settings = data["settings"]

    # Find the specific setting
    setting_to_cache = next((s for s in settings if s["id"] == setting_id), None)
    if not setting_to_cache:
        raise Exception(f"Setting {setting_id} not found for tune {tune_id}")

    # Extract the data we need
    key = setting_to_cache.get("key", "")
    abc = setting_to_cache.get("abc", "")
    tune_type = data.get("type", "").title()  # Convert to title case (jig -> Jig)

    # Replace "!" with newline for proper staff line breaks
    abc = abc.replace("!", "\n")

    # Extract incipit from ABC notation
    incipit_abc = extract_abc_incipit(abc, tune_type)

    return key, abc, incipit_abc


def cache_setting(tune_id, setting_id):
    """
    Cache a specific setting for a tune.
    Minimizes thesession.org API calls by only fetching if ABC is missing.
    Returns (success, message).
    """
    try:
        # First check if this setting already exists in the database
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT setting_id, key, abc, incipit_abc, image, incipit_image
            FROM tune_setting
            WHERE setting_id = %s
        """, (setting_id,))
        existing_setting = cur.fetchone()

        # Check what we have cached
        if existing_setting:
            has_abc = existing_setting[2] is not None and existing_setting[2] != ""
            has_image = existing_setting[4] is not None
            has_incipit_image = existing_setting[5] is not None

            # If we have both images, we're done
            if has_image and has_incipit_image:
                cur.close()
                conn.close()
                return True, "already cached"

            # If we have ABC but missing images, just render images (no API call needed)
            if has_abc:
                key = existing_setting[1]
                abc = existing_setting[2]
                incipit_abc = existing_setting[3]
                action = "images rendered"
            else:
                # ABC is missing, need to fetch from thesession.org
                key, abc, incipit_abc = fetch_abc_from_thesession(tune_id, setting_id)

                # Update the ABC in the database
                cur.execute("""
                    UPDATE tune_setting
                    SET key = %s, abc = %s, incipit_abc = %s, cache_updated_date = (NOW() AT TIME ZONE 'UTC'),
                        last_modified_date = (NOW() AT TIME ZONE 'UTC')
                    WHERE setting_id = %s
                """, (key, abc, incipit_abc, setting_id))
                conn.commit()
                action = "ABC updated"
        else:
            # Setting doesn't exist at all, fetch from thesession.org
            key, abc, incipit_abc = fetch_abc_from_thesession(tune_id, setting_id)

            # Insert new setting
            cur.execute("""
                INSERT INTO tune_setting (setting_id, tune_id, key, abc, incipit_abc, cache_updated_date)
                VALUES (%s, %s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'))
            """, (setting_id, tune_id, key, abc, incipit_abc))
            conn.commit()
            action = "cached"

        # Generate PNG images for both full ABC and incipit
        full_image = None
        incipit_image = None

        # Construct full ABC notation with headers for rendering
        abc_with_headers = abc
        if not abc.startswith('X:'):
            abc_with_headers = f"X:1\nM:4/4\nL:1/8\nK:{key if key else 'D'}\n{abc}"

        # Render full ABC image
        full_image = render_abc_to_png(abc_with_headers)

        # Render incipit image
        if incipit_abc:
            incipit_with_headers = incipit_abc
            if not incipit_abc.startswith('X:'):
                incipit_with_headers = f"X:1\nM:4/4\nL:1/8\nK:{key if key else 'D'}\n{incipit_abc}"
            incipit_image = render_abc_to_png(incipit_with_headers, is_incipit=True)

        # Update database with images if they were generated
        if full_image or incipit_image:
            cur.execute("""
                UPDATE tune_setting
                SET image = %s, incipit_image = %s, last_modified_date = (NOW() AT TIME ZONE 'UTC')
                WHERE setting_id = %s
            """, (
                psycopg2.Binary(full_image) if full_image else None,
                psycopg2.Binary(incipit_image) if incipit_image else None,
                setting_id
            ))
            conn.commit()

        cur.close()
        conn.close()

        return True, action

    except requests.exceptions.RequestException as e:
        return False, f"Error connecting to thesession.org: {str(e)}"
    except Exception as e:
        return False, f"Error caching setting: {str(e)}"


def process_settings_in_batches(settings_dict, batch_size=10, delay_between_batches=2.0, limit=None):
    """
    Process settings in batches with rate limiting.
    Only processes settings that are missing or don't have both images.
    Already fully cached settings are filtered out and skipped.

    Args:
        settings_dict: Dict mapping (tune_id, setting_id) to count
        batch_size: Number of settings to process per batch
        delay_between_batches: Seconds to wait between batches
        limit: Maximum number of missing settings to process (None = all missing)
    """
    settings_list = list(settings_dict.keys())

    # Filter to only settings that need caching (don't exist or missing images)
    print("\nChecking which settings need caching...")
    conn = get_db_connection()
    cur = conn.cursor()

    # Get all setting_ids to check (bulk query is much faster than individual queries)
    setting_ids = [setting_id for tune_id, setting_id in settings_list]

    # Bulk query: get all existing settings with their image status
    cur.execute("""
        SELECT setting_id,
               (image IS NOT NULL) as has_image,
               (incipit_image IS NOT NULL) as has_incipit_image
        FROM tune_setting
        WHERE setting_id = ANY(%s)
    """, (setting_ids,))

    # Build a dict of which settings exist and have images
    cached_status = {}
    for row in cur.fetchall():
        setting_id = row[0]
        has_both_images = row[1] and row[2]
        cached_status[setting_id] = has_both_images

    cur.close()
    conn.close()

    # Categorize settings
    needs_caching = []
    already_cached = []

    for tune_id, setting_id in settings_list:
        if cached_status.get(setting_id, False):
            # Already fully cached (exists and has both images)
            already_cached.append((tune_id, setting_id))
        else:
            # Doesn't exist or missing images
            needs_caching.append((tune_id, setting_id))

    # Only process settings that need caching (skip already cached)
    settings_list = needs_caching

    print(f"  {len(needs_caching)} settings need caching")
    print(f"  {len(already_cached)} settings already cached (will be skipped)")

    # Apply limit if specified
    if limit is not None and limit < len(settings_list):
        settings_list = settings_list[:limit]
        print(f"NOTE: Processing limited to first {limit} settings that need caching")

    total = len(settings_list)

    print(f"\nProcessing {total} settings in batches of {batch_size}...")
    print(f"Delay between batches: {delay_between_batches} seconds")

    stats = {
        'cached': 0,
        'abc_updated': 0,
        'images_rendered': 0,
        'already_cached': 0,
        'failed': 0,
        'errors': []
    }

    start_time = time.time()

    for i in range(0, total, batch_size):
        batch = settings_list[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size

        print(f"\nBatch {batch_num}/{total_batches} (settings {i+1}-{min(i+batch_size, total)} of {total})")

        for tune_id, setting_id in batch:
            success, message = cache_setting(tune_id, setting_id)

            if success:
                if message == "already cached":
                    stats['already_cached'] += 1
                    print(f"  ✓ Tune {tune_id}, Setting {setting_id}: already cached")
                elif message == "cached":
                    stats['cached'] += 1
                    print(f"  ✓ Tune {tune_id}, Setting {setting_id}: cached (fetched from thesession.org)")
                elif message == "ABC updated":
                    stats['abc_updated'] += 1
                    print(f"  ✓ Tune {tune_id}, Setting {setting_id}: ABC updated (fetched from thesession.org)")
                elif message == "images rendered":
                    stats['images_rendered'] += 1
                    print(f"  ✓ Tune {tune_id}, Setting {setting_id}: images rendered (ABC already cached)")
            else:
                stats['failed'] += 1
                error_msg = f"Tune {tune_id}, Setting {setting_id}: {message}"
                stats['errors'].append(error_msg)
                print(f"  ✗ {error_msg}")

        # Show batch summary
        processed = min(i + batch_size, total)
        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        remaining = total - processed
        eta = remaining / rate if rate > 0 else 0

        print(f"  Batch complete. Progress: {processed}/{total} ({100*processed/total:.1f}%)")
        print(f"  Stats: {stats['cached']} cached, {stats['abc_updated']} ABC updated, {stats['images_rendered']} images rendered, {stats['already_cached']} already cached, {stats['failed']} failed")
        print(f"  Rate: {rate:.1f} settings/sec, ETA: {eta/60:.1f} minutes")

        # Wait before next batch (except for last batch)
        if i + batch_size < total:
            time.sleep(delay_between_batches)

    elapsed = time.time() - start_time

    # Calculate thesession.org API calls
    api_calls = stats['cached'] + stats['abc_updated']

    print(f"\n" + "="*80)
    print(f"SUMMARY")
    print(f"="*80)
    print(f"Total settings processed: {total}")
    print(f"  Newly cached: {stats['cached']} (fetched ABC from thesession.org)")
    print(f"  ABC updated: {stats['abc_updated']} (fetched ABC from thesession.org)")
    print(f"  Images rendered: {stats['images_rendered']} (used cached ABC)")
    print(f"  Already cached: {stats['already_cached']}")
    print(f"  Failed: {stats['failed']}")
    print(f"\nthesession.org API calls: {api_calls}")
    print(f"Total time: {elapsed/60:.1f} minutes")
    print(f"Average rate: {total/elapsed:.1f} settings/sec")

    if stats['errors']:
        print(f"\nErrors ({len(stats['errors'])}):")
        for error in stats['errors'][:20]:  # Show first 20 errors
            print(f"  - {error}")
        if len(stats['errors']) > 20:
            print(f"  ... and {len(stats['errors']) - 20} more errors")

    return stats


def main():
    """Main entry point for the script."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Cache missing settings in the system (skips already cached settings)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Cache all missing settings with default batch size (10)
  python scripts/cache_missing_settings.py

  # Test with just 5 missing settings
  python scripts/cache_missing_settings.py --limit 5

  # Use larger batches and faster processing
  python scripts/cache_missing_settings.py --batch-size 50 --delay 1.0

  # Only collect and show what would be cached (dry run)
  python scripts/cache_missing_settings.py --dry-run

  # Skip fetching default settings for tunes (only cache explicitly referenced settings)
  python scripts/cache_missing_settings.py --skip-defaults
        """
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Number of settings to process per batch (default: 10)'
    )

    parser.add_argument(
        '--delay',
        type=float,
        default=2.0,
        help='Delay in seconds between batches (default: 2.0)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Only collect and show what would be cached, without actually caching'
    )

    parser.add_argument(
        '--skip-defaults',
        action='store_true',
        help='Skip fetching default settings for tunes without any cached settings'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Maximum number of missing settings to process (default: all missing)'
    )

    args = parser.parse_args()

    print("="*80)
    print("MISSING SETTINGS CACHE SCRIPT")
    print("="*80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Batch size: {args.batch_size}")
    print(f"Delay between batches: {args.delay} seconds")
    if args.limit:
        print(f"Limit: {args.limit} settings")
    if args.dry_run:
        print("MODE: DRY RUN (no actual caching)")
    if args.skip_defaults:
        print("SKIP: Default settings for all tunes")
    print("")

    # Step 1: Collect setting IDs from database
    print("STEP 1: Collecting setting IDs from database tables")
    print("-" * 80)
    settings_needed = collect_setting_ids()

    # Step 2: Fetch default settings for tunes without any cached settings (unless skipped or limited)
    # When --limit is specified, skip defaults to avoid hammering thesession.org API
    if args.limit:
        print("\nSTEP 2: SKIPPED (--limit specified, not fetching defaults to avoid API spam)")
        print("         Use without --limit or add --skip-defaults to control this explicitly")
    elif not args.skip_defaults:
        print("\nSTEP 2: Fetching default settings for tunes without cache")
        print("-" * 80)
        tune_ids = get_all_tune_ids()
        default_settings = fetch_default_settings_for_tunes(tune_ids)

        # Merge with settings_needed
        for key in default_settings:
            if key not in settings_needed:
                settings_needed[key] = 1

        print(f"\nTotal unique settings after adding defaults: {len(settings_needed)}")
    else:
        print("\nSTEP 2: SKIPPED (--skip-defaults flag)")

    # Step 3: Process settings
    if args.dry_run:
        print("\nDRY RUN - Checking which settings need caching...")
        print("-" * 80)

        # Check which settings are already cached
        conn = get_db_connection()
        cur = conn.cursor()

        settings_list = list(settings_needed.keys())
        setting_ids = [setting_id for tune_id, setting_id in settings_list]

        cur.execute("""
            SELECT setting_id,
                   (image IS NOT NULL) as has_image,
                   (incipit_image IS NOT NULL) as has_incipit_image
            FROM tune_setting
            WHERE setting_id = ANY(%s)
        """, (setting_ids,))

        cached_status = {}
        for row in cur.fetchall():
            setting_id = row[0]
            has_both_images = row[1] and row[2]
            cached_status[setting_id] = has_both_images

        cur.close()
        conn.close()

        # Filter to only missing settings
        settings_to_show = [(t, s) for t, s in sorted(settings_needed.keys())
                           if not cached_status.get(s, False)]

        total_needed = len(settings_needed)
        total_missing = len(settings_to_show)
        total_cached = total_needed - total_missing

        print(f"  Found {total_needed} total settings")
        print(f"  {total_missing} need caching")
        print(f"  {total_cached} already cached (would be skipped)")
        print(f"\nWould process the following missing settings:")

        display_settings = settings_to_show
        if args.limit:
            display_settings = settings_to_show[:args.limit]

        for i, (tune_id, setting_id) in enumerate(display_settings, 1):
            count = settings_needed[(tune_id, setting_id)]
            print(f"  {i}. Tune {tune_id}, Setting {setting_id} (used {count} times)")

        if args.limit and args.limit < len(settings_to_show):
            print(f"\n... showing {args.limit} of {len(settings_to_show)} missing settings (--limit {args.limit})")
        else:
            print(f"\nTotal: {len(settings_to_show)} missing settings would be processed")
    else:
        print("\nSTEP 3: Processing settings")
        print("-" * 80)
        process_settings_in_batches(
            settings_needed,
            batch_size=args.batch_size,
            delay_between_batches=args.delay,
            limit=args.limit
        )

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
