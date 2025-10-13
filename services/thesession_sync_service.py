"""
ThesessionSyncService for syncing tune collections from thesession.org.

This service handles fetching tunebook data from thesession.org API,
creating missing tune records, and bulk importing tunes into personal collections.
"""

import requests
import time
from typing import Dict, List, Optional, Tuple, Any, Callable
from database import get_db_connection, save_to_history


class ThesessionSyncService:
    """
    Service for synchronizing tune collections from thesession.org.
    
    Handles API integration with thesession.org, fetching tunebook data,
    creating missing tune records, and bulk importing into person_tune table.
    """
    
    TUNEBOOK_API_URL = "https://thesession.org/members/{user_id}/tunebook?format=json"
    TUNE_DETAILS_API_URL = "https://thesession.org/tunes/{tune_id}?format=json"
    REQUEST_TIMEOUT = 10  # seconds
    MAX_RETRIES = 3  # Maximum number of retry attempts
    RETRY_DELAY = 2  # Seconds to wait between retries
    RETRY_BACKOFF = 2  # Multiplier for exponential backoff
    
    def __init__(self):
        """Initialize the sync service."""
        pass
    
    def _retry_request(
        self,
        request_func: Callable,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None
    ) -> Tuple[bool, str, Any]:
        """
        Retry a request function with exponential backoff.
        
        Args:
            request_func: Function that returns (success, message, data) tuple
            max_retries: Maximum number of retry attempts (uses class default if None)
            retry_delay: Initial delay between retries in seconds (uses class default if None)
            
        Returns:
            Tuple of (success, message, data) from the request function
        """
        if max_retries is None:
            max_retries = self.MAX_RETRIES
        if retry_delay is None:
            retry_delay = self.RETRY_DELAY
        
        last_error = None
        current_delay = retry_delay
        
        for attempt in range(max_retries):
            success, message, data = request_func()
            
            # If successful or non-retryable error, return immediately
            if success:
                return success, message, data
            
            # Check if error is retryable (timeout or connection errors)
            is_retryable = any(keyword in message.lower() for keyword in [
                'timed out', 'timeout', 'connect', 'connection', 'unavailable'
            ])
            
            if not is_retryable:
                # Non-retryable error (e.g., 404, invalid data)
                return success, message, data
            
            last_error = message
            
            # If not the last attempt, wait before retrying
            if attempt < max_retries - 1:
                time.sleep(current_delay)
                current_delay *= self.RETRY_BACKOFF
        
        # All retries exhausted
        return False, f"{last_error} (after {max_retries} attempts)", None
    
    def fetch_tunebook(self, thesession_user_id: int, retry: bool = True) -> Tuple[bool, str, Optional[List[Dict[str, Any]]]]:
        """
        Fetch tunebook data from thesession.org for a given user.
        Handles pagination to fetch all tunes across multiple pages.

        Args:
            thesession_user_id: The thesession.org user ID
            retry: Whether to retry on transient failures

        Returns:
            Tuple of (success, message, tunebook_data)
            where tunebook_data is a list of tune dictionaries
        """
        def _fetch():
            try:
                all_tunes = []
                page = 1
                total_pages = 1

                # Fetch all pages
                while page <= total_pages:
                    url = f"{self.TUNEBOOK_API_URL.format(user_id=thesession_user_id)}&page={page}"
                    response = requests.get(url, timeout=self.REQUEST_TIMEOUT)

                    if response.status_code == 404:
                        return False, f"User #{thesession_user_id} not found on thesession.org", None
                    elif response.status_code != 200:
                        return False, f"Failed to fetch tunebook (status: {response.status_code})", None

                    data = response.json()

                    # The tunebook API returns a dict with 'tunes' key containing list of tunes
                    if 'tunes' not in data:
                        return False, "Invalid tunebook data received from thesession.org", None

                    tunes = data['tunes']

                    if not isinstance(tunes, list):
                        return False, "Invalid tunebook format received from thesession.org", None

                    all_tunes.extend(tunes)

                    # Update total_pages from API response
                    if page == 1:
                        total_pages = data.get('pages', 1)

                    page += 1

                return True, f"Successfully fetched {len(all_tunes)} tunes from {total_pages} page(s)", all_tunes

            except requests.exceptions.Timeout:
                return False, "Request to thesession.org timed out", None
            except requests.exceptions.ConnectionError:
                return False, "Could not connect to thesession.org", None
            except requests.exceptions.RequestException as e:
                return False, f"Error fetching tunebook: {str(e)}", None
            except Exception as e:
                return False, f"Unexpected error: {str(e)}", None

        if retry:
            return self._retry_request(_fetch)
        else:
            return _fetch()
    
    def fetch_tune_metadata(self, tune_id: int, retry: bool = True) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Fetch complete tune metadata from thesession.org.
        
        Args:
            tune_id: The thesession.org tune ID
            retry: Whether to retry on transient failures
            
        Returns:
            Tuple of (success, message, tune_metadata)
        """
        def _fetch():
            try:
                url = self.TUNE_DETAILS_API_URL.format(tune_id=tune_id)
                response = requests.get(url, timeout=self.REQUEST_TIMEOUT)
                
                if response.status_code == 404:
                    return False, f"Tune #{tune_id} not found on thesession.org", None
                elif response.status_code != 200:
                    return False, f"Failed to fetch tune data (status: {response.status_code})", None
                
                data = response.json()
                
                # Validate required fields
                if 'name' not in data or 'type' not in data:
                    return False, "Invalid tune data received from thesession.org", None
                
                # Extract and normalize metadata
                metadata = {
                    'tune_id': tune_id,
                    'name': data['name'],
                    'tune_type': data['type'].title(),  # Convert to title case
                    'tunebook_count': data.get('tunebooks', 0)
                }
                
                return True, "Successfully fetched tune metadata", metadata
                
            except requests.exceptions.Timeout:
                return False, "Request to thesession.org timed out", None
            except requests.exceptions.ConnectionError:
                return False, "Could not connect to thesession.org", None
            except requests.exceptions.RequestException as e:
                return False, f"Error fetching tune metadata: {str(e)}", None
            except Exception as e:
                return False, f"Unexpected error: {str(e)}", None
        
        if retry:
            return self._retry_request(_fetch)
        else:
            return _fetch()
    
    def ensure_tune_exists(self, tune_id: int, changed_by: str = 'system', retry: bool = True, tune_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Ensure a tune exists in the tune table, fetching from thesession.org if needed.

        Args:
            tune_id: The tune ID to check/create
            changed_by: User who triggered the operation
            retry: Whether to retry on transient failures
            tune_data: Optional dict with 'name' and 'type' to avoid API call

        Returns:
            Tuple of (success, message)
        """
        conn = get_db_connection()
        cur = conn.cursor()

        try:
            # Check if tune already exists
            cur.execute("SELECT tune_id FROM tune WHERE tune_id = %s", (tune_id,))
            exists = cur.fetchone()

            if exists:
                return True, f"Tune #{tune_id} already exists"

            # Use provided tune_data if available, otherwise fetch from API
            if tune_data and 'name' in tune_data and 'type' in tune_data:
                metadata = {
                    'tune_id': tune_id,
                    'name': tune_data['name'],
                    'tune_type': tune_data['type'].title(),
                    'tunebook_count': 0  # Will be updated later if needed
                }
            else:
                # Fetch tune metadata from thesession.org (with retry if enabled)
                success, message, metadata = self.fetch_tune_metadata(tune_id, retry=retry)

                if not success:
                    return False, f"Could not fetch tune #{tune_id}: {message}"

            # Insert tune into database
            cur.execute("""
                INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached, tunebook_count_cached_date)
                VALUES (%s, %s, %s, %s, CURRENT_DATE)
            """, (
                metadata['tune_id'],
                metadata['name'],
                metadata['tune_type'],
                metadata['tunebook_count']
            ))

            # Save to history
            save_to_history(cur, 'tune', 'INSERT', tune_id, changed_by)

            conn.commit()

            return True, f"Created tune #{tune_id}: {metadata['name']}"

        except Exception as e:
            conn.rollback()
            return False, f"Error ensuring tune exists: {str(e)}"
        finally:
            cur.close()
            conn.close()
    
    def sync_tunebook_to_person(
        self,
        person_id: int,
        thesession_user_id: int,
        learn_status: str = 'want to learn',
        changed_by: str = 'system',
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Sync a user's tunebook from thesession.org to their person_tune collection.
        
        Args:
            person_id: The person's ID in our system
            thesession_user_id: The thesession.org user ID
            learn_status: Default learning status for imported tunes
            changed_by: User who triggered the sync
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Tuple of (success, message, results_dict)
        """
        # Fetch tunebook from thesession.org (with retry)
        success, message, tunebook = self.fetch_tunebook(thesession_user_id, retry=True)
        
        if not success:
            return False, message, {
                'tunes_fetched': 0,
                'tunes_created': 0,
                'person_tunes_added': 0,
                'person_tunes_skipped': 0,
                'errors': [message],
                'status': 'failed',
                'progress_percent': 0
            }
        
        results = {
            'tunes_fetched': len(tunebook),
            'tunes_created': 0,
            'person_tunes_added': 0,
            'person_tunes_skipped': 0,
            'errors': [],
            'status': 'in_progress',
            'progress_percent': 0
        }
        
        total_tunes = len(tunebook)
        
        # Report initial progress
        if progress_callback:
            progress_callback({
                **results,
                'status': 'fetching_metadata',
                'progress_percent': 10
            })
        
        # First pass: ensure all tunes exist in tune table (BATCH OPERATION)
        import sys
        print(f"Starting tune creation check for {total_tunes} tunes...", file=sys.stderr)

        conn = get_db_connection()
        try:
            cur = conn.cursor()

            # Get all tune IDs from tunebook
            tune_ids_to_check = [t.get('id') for t in tunebook if t.get('id')]

            # Batch check which tunes already exist
            cur.execute("""
                SELECT tune_id FROM tune WHERE tune_id = ANY(%s)
            """, (tune_ids_to_check,))

            existing_tune_ids = set(row[0] for row in cur.fetchall())
            print(f"Found {len(existing_tune_ids)} existing tunes, need to create {len(tune_ids_to_check) - len(existing_tune_ids)}", file=sys.stderr)

            # Prepare batch insert for new tunes
            tunes_to_create = []
            for tune_entry in tunebook:
                tune_id = tune_entry.get('id')
                if tune_id and tune_id not in existing_tune_ids:
                    tunes_to_create.append((
                        tune_id,
                        tune_entry.get('name'),
                        tune_entry.get('type', '').title(),
                        0  # tunebook_count_cached
                    ))

            # Batch insert new tunes
            if tunes_to_create:
                print(f"Inserting {len(tunes_to_create)} new tunes in batch...", file=sys.stderr)
                from psycopg2.extras import execute_values
                cur.execute("BEGIN")
                execute_values(cur, """
                    INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached, tunebook_count_cached_date)
                    VALUES %s
                    ON CONFLICT (tune_id) DO NOTHING
                """, tunes_to_create, template="(%s, %s, %s, %s, CURRENT_DATE)")
                conn.commit()
                results['tunes_created'] = len(tunes_to_create)
                print(f"Successfully created {len(tunes_to_create)} tunes", file=sys.stderr)

            # Report progress
            if progress_callback:
                progress_callback({
                    **results,
                    'status': 'adding_to_collection',
                    'progress_percent': 50
                })

        except Exception as e:
            conn.rollback()
            print(f"ERROR in batch tune creation: {str(e)}", file=sys.stderr)
            import traceback
            print(traceback.format_exc(), file=sys.stderr)
            results['errors'].append(f"Error creating tunes: {str(e)}")
        finally:
            cur.close()
            conn.close()
        
        # Report progress before database operations
        if progress_callback:
            progress_callback({
                **results,
                'status': 'adding_to_collection',
                'progress_percent': 60
            })
        
        # Second pass: create person_tune records in a single transaction
        conn = get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute("BEGIN")

            # Get all tune_ids that need to be processed (excluding errors)
            error_tune_ids = set()
            for error in results['errors']:
                # Extract tune ID from error messages like "Tune #123: ..."
                if error.startswith("Tune #"):
                    try:
                        tune_id = int(error.split("#")[1].split(":")[0])
                        error_tune_ids.add(tune_id)
                    except:
                        pass

            valid_tune_ids = [t.get('id') for t in tunebook if t.get('id') and t.get('id') not in error_tune_ids]

            if valid_tune_ids:
                # Batch check for existing person_tunes
                cur.execute("""
                    SELECT tune_id FROM person_tune
                    WHERE person_id = %s AND tune_id = ANY(%s)
                """, (person_id, valid_tune_ids))

                existing_tune_ids = set(row[0] for row in cur.fetchall())
                results['person_tunes_skipped'] = len(existing_tune_ids)

                # Filter out existing tunes
                tunes_to_add = [(person_id, tid, learn_status) for tid in valid_tune_ids if tid not in existing_tune_ids]

                if tunes_to_add:
                    # Batch insert new person_tunes
                    from psycopg2.extras import execute_values
                    execute_values(cur, """
                        INSERT INTO person_tune (
                            person_id, tune_id, learn_status,
                            created_date, last_modified_date
                        )
                        VALUES %s
                    """, tunes_to_add, template="(%s, %s, %s, (NOW() AT TIME ZONE 'UTC'), (NOW() AT TIME ZONE 'UTC'))")

                    results['person_tunes_added'] = len(tunes_to_add)

                # Report progress
                if progress_callback:
                    progress_callback({
                        **results,
                        'status': 'adding_to_collection',
                        'progress_percent': 95
                    })

            conn.commit()
            
            # Build summary message
            summary_parts = []
            if results['person_tunes_added'] > 0:
                summary_parts.append(f"added {results['person_tunes_added']} tunes")
            if results['person_tunes_skipped'] > 0:
                summary_parts.append(f"skipped {results['person_tunes_skipped']} existing")
            if results['tunes_created'] > 0:
                summary_parts.append(f"created {results['tunes_created']} new tune records")
            if results['errors']:
                summary_parts.append(f"{len(results['errors'])} errors")
            
            if not summary_parts:
                summary = "No changes made"
            else:
                summary = "Sync complete: " + ", ".join(summary_parts)
            
            success = len(results['errors']) == 0 or results['person_tunes_added'] > 0
            results['status'] = 'completed' if success else 'completed_with_errors'
            results['progress_percent'] = 100
            
            # Final progress report
            if progress_callback:
                progress_callback(results)
            
            return success, summary, results
            
        except Exception as e:
            conn.rollback()
            results['errors'].append(f"Database error: {str(e)}")
            results['status'] = 'failed'
            results['progress_percent'] = 0
            
            if progress_callback:
                progress_callback(results)
            
            return False, f"Sync failed: {str(e)}", results
        finally:
            cur.close()
            conn.close()
    
    def get_sync_preview(
        self,
        person_id: int,
        thesession_user_id: int
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Preview what would be synced without actually syncing.
        
        Args:
            person_id: The person's ID in our system
            thesession_user_id: The thesession.org user ID
            
        Returns:
            Tuple of (success, message, preview_dict)
        """
        # Fetch tunebook from thesession.org
        success, message, tunebook = self.fetch_tunebook(thesession_user_id)
        
        if not success:
            return False, message, {
                'total_tunes': 0,
                'new_tunes': 0,
                'existing_tunes': 0,
                'missing_from_db': 0
            }
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            preview = {
                'total_tunes': len(tunebook),
                'new_tunes': 0,
                'existing_tunes': 0,
                'missing_from_db': 0
            }
            
            for tune_entry in tunebook:
                tune_id = tune_entry.get('id')
                
                if not tune_id:
                    continue
                
                # Check if person_tune exists
                cur.execute("""
                    SELECT person_tune_id FROM person_tune
                    WHERE person_id = %s AND tune_id = %s
                """, (person_id, tune_id))
                
                person_tune_exists = cur.fetchone()
                
                if person_tune_exists:
                    preview['existing_tunes'] += 1
                else:
                    # Check if tune exists in tune table
                    cur.execute("SELECT tune_id FROM tune WHERE tune_id = %s", (tune_id,))
                    tune_exists = cur.fetchone()
                    
                    if not tune_exists:
                        preview['missing_from_db'] += 1
                    
                    preview['new_tunes'] += 1
            
            message = f"Preview: {preview['new_tunes']} new tunes, {preview['existing_tunes']} already in collection"
            if preview['missing_from_db'] > 0:
                message += f", {preview['missing_from_db']} will be fetched from thesession.org"
            
            return True, message, preview
            
        except Exception as e:
            return False, f"Error generating preview: {str(e)}", {}
        finally:
            cur.close()
            conn.close()
