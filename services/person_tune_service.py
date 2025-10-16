"""
PersonTune service layer for managing personal tune collections.

This service provides business logic for PersonTune operations, including
CRUD operations, learning status management, and heard count tracking.
It acts as an abstraction layer over the PersonTune model.
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from models.person_tune import PersonTune
from database import get_db_connection


# Sentinel value to distinguish between "not provided" and "explicitly set to None"
class _Unset:
    def __repr__(self):
        return "<UNSET>"

UNSET = _Unset()


class PersonTuneService:
    """
    Service class for managing PersonTune operations.
    
    Provides business logic layer for personal tune collection management,
    including CRUD operations, status transitions, and heard count tracking.
    """
    
    def create_person_tune(
        self,
        person_id: int,
        tune_id: int,
        learn_status: str = PersonTune.DEFAULT_LEARN_STATUS,
        notes: Optional[str] = None,
        changed_by: str = 'system'
    ) -> Tuple[bool, str, Optional[PersonTune]]:
        """
        Create a new PersonTune record.
        
        Args:
            person_id: ID of the person
            tune_id: ID of the tune
            learn_status: Initial learning status (defaults to 'want to learn')
            notes: Optional notes
            changed_by: User who created the record
            
        Returns:
            Tuple of (success, message, person_tune_instance)
        """
        try:
            # Check if person_tune already exists
            existing = PersonTune.get_by_person_and_tune(person_id, tune_id)
            if existing:
                return False, f"PersonTune already exists for person {person_id} and tune {tune_id}", None
            
            # Create new PersonTune
            person_tune = PersonTune(
                person_id=person_id,
                tune_id=tune_id,
                learn_status=learn_status,
                notes=notes
            )
            
            # Save to database
            saved_person_tune = person_tune.save(changed_by=changed_by)
            
            return True, "PersonTune created successfully", saved_person_tune
            
        except ValueError as e:
            return False, f"Validation error: {str(e)}", None
        except Exception as e:
            return False, f"Error creating PersonTune: {str(e)}", None
    
    def get_person_tune_by_id(self, person_tune_id: int) -> Optional[PersonTune]:
        """
        Retrieve a PersonTune by its ID.
        
        Args:
            person_tune_id: The person_tune_id to look up
            
        Returns:
            PersonTune instance or None if not found
        """
        try:
            return PersonTune.get_by_id(person_tune_id)
        except Exception:
            return None
    
    def get_person_tune_by_person_and_tune(
        self, 
        person_id: int, 
        tune_id: int
    ) -> Optional[PersonTune]:
        """
        Retrieve a PersonTune by person_id and tune_id.
        
        Args:
            person_id: The person's ID
            tune_id: The tune's ID
            
        Returns:
            PersonTune instance or None if not found
        """
        try:
            return PersonTune.get_by_person_and_tune(person_id, tune_id)
        except Exception:
            return None
    
    def get_person_tunes(
        self,
        person_id: int,
        learn_status_filter: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[PersonTune]:
        """
        Retrieve all PersonTunes for a specific person.
        
        Args:
            person_id: The person's ID
            learn_status_filter: Optional filter by learn_status
            limit: Optional limit on number of results
            offset: Offset for pagination
            
        Returns:
            List of PersonTune instances
        """
        try:
            return PersonTune.get_for_person(
                person_id=person_id,
                learn_status_filter=learn_status_filter,
                limit=limit,
                offset=offset
            )
        except Exception:
            return []
    
    def update_learn_status(
        self,
        person_tune_id: int,
        new_status: str,
        changed_by: str = 'system'
    ) -> Tuple[bool, str, Optional[PersonTune]]:
        """
        Update the learning status of a PersonTune.
        
        Args:
            person_tune_id: ID of the PersonTune to update
            new_status: New learning status
            changed_by: User who made the change
            
        Returns:
            Tuple of (success, message, updated_person_tune)
        """
        try:
            person_tune = PersonTune.get_by_id(person_tune_id)
            if not person_tune:
                return False, f"PersonTune with ID {person_tune_id} not found", None
            
            # Attempt to set the new status
            status_changed = person_tune.set_learn_status(new_status, changed_by=changed_by)
            
            if not status_changed:
                return False, f"Status was already '{new_status}'", person_tune
            
            return True, f"Status updated to '{new_status}' successfully", person_tune
            
        except ValueError as e:
            return False, f"Validation error: {str(e)}", None
        except Exception as e:
            return False, f"Error updating status: {str(e)}", None
    
    def increment_heard_count(
        self,
        person_tune_id: int,
        changed_by: str = 'system'
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Increment the heard_count for a PersonTune.
        
        Args:
            person_tune_id: ID of the PersonTune to update
            changed_by: User who made the change
            
        Returns:
            Tuple of (success, message, new_heard_count)
        """
        try:
            person_tune = PersonTune.get_by_id(person_tune_id)
            if not person_tune:
                return False, f"PersonTune with ID {person_tune_id} not found", None
            
            # Increment the heard count
            new_count = person_tune.increment_heard_count(changed_by=changed_by)
            
            return True, f"Heard count incremented to {new_count}", new_count
            
        except ValueError as e:
            return False, f"Validation error: {str(e)}", None
        except Exception as e:
            return False, f"Error incrementing heard count: {str(e)}", None
    
    def update_person_tune(
        self,
        person_tune_id: int,
        learn_status=UNSET,
        notes=UNSET,
        setting_id=UNSET,
        name_alias=UNSET,
        heard_count=UNSET,
        changed_by: str = 'system'
    ) -> Tuple[bool, str, Optional[PersonTune]]:
        """
        Update multiple fields of a PersonTune.

        Args:
            person_tune_id: ID of the PersonTune to update
            learn_status: New learning status, or UNSET to skip (can be None to clear)
            notes: New notes, or UNSET to skip (can be None to clear)
            setting_id: New thesession.org setting ID, or UNSET to skip (can be None to clear)
            name_alias: New custom name/alias, or UNSET to skip (can be None to clear)
            heard_count: New heard count, or UNSET to skip (must be >= 0 if provided)
            changed_by: User who made the change

        Returns:
            Tuple of (success, message, updated_person_tune)
        """
        try:
            person_tune = PersonTune.get_by_id(person_tune_id)
            if not person_tune:
                return False, f"PersonTune with ID {person_tune_id} not found", None

            changes_made = []

            # Update learn_status if provided
            if learn_status is not UNSET and learn_status != person_tune.learn_status:
                status_changed = person_tune.set_learn_status(learn_status, changed_by=changed_by)
                if status_changed:
                    changes_made.append(f"status to '{learn_status}'")

            # Update notes if provided
            if notes is not UNSET and notes != person_tune.notes:
                person_tune.notes = notes
                changes_made.append("notes")

            # Update setting_id if provided (can be None to clear it)
            if setting_id is not UNSET and setting_id != person_tune.setting_id:
                person_tune.setting_id = setting_id
                changes_made.append("setting_id")

            # Update name_alias if provided (can be None to clear it)
            if name_alias is not UNSET and name_alias != person_tune.name_alias:
                person_tune.name_alias = name_alias
                changes_made.append("name_alias")

            # Update heard_count if provided (must be >= 0)
            if heard_count is not UNSET:
                if heard_count < 0:
                    return False, "heard_count cannot be negative", None
                if heard_count != person_tune.heard_count:
                    person_tune.heard_count = heard_count
                    changes_made.append("heard_count")

            # Save changes if any were made
            if changes_made:
                person_tune.save(changed_by=changed_by)
                message = f"Updated {', '.join(changes_made)} successfully"
            else:
                message = "No changes were made"

            return True, message, person_tune

        except ValueError as e:
            return False, f"Validation error: {str(e)}", None
        except Exception as e:
            return False, f"Error updating PersonTune: {str(e)}", None
    
    def delete_person_tune(
        self,
        person_tune_id: int,
        changed_by: str = 'system'
    ) -> Tuple[bool, str]:
        """
        Delete a PersonTune record.
        
        Args:
            person_tune_id: ID of the PersonTune to delete
            changed_by: User who deleted the record
            
        Returns:
            Tuple of (success, message)
        """
        try:
            person_tune = PersonTune.get_by_id(person_tune_id)
            if not person_tune:
                return False, f"PersonTune with ID {person_tune_id} not found"
            
            deleted = person_tune.delete(changed_by=changed_by)
            
            if deleted:
                return True, "PersonTune deleted successfully"
            else:
                return False, "Failed to delete PersonTune"
                
        except Exception as e:
            return False, f"Error deleting PersonTune: {str(e)}"
    
    def bulk_create_person_tunes(
        self,
        person_id: int,
        tune_ids: List[int],
        learn_status: str = PersonTune.DEFAULT_LEARN_STATUS,
        changed_by: str = 'system'
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Create multiple PersonTune records for a person.
        
        Args:
            person_id: ID of the person
            tune_ids: List of tune IDs to add
            learn_status: Learning status for all tunes
            changed_by: User who created the records
            
        Returns:
            Tuple of (success, message, results_dict)
        """
        results = {
            'created': [],
            'skipped': [],
            'errors': [],
            'total_processed': len(tune_ids)
        }
        
        for tune_id in tune_ids:
            success, message, person_tune = self.create_person_tune(
                person_id=person_id,
                tune_id=tune_id,
                learn_status=learn_status,
                changed_by=changed_by
            )
            
            if success:
                results['created'].append({
                    'tune_id': tune_id,
                    'person_tune_id': person_tune.person_tune_id
                })
            elif "already exists" in message:
                results['skipped'].append({
                    'tune_id': tune_id,
                    'reason': message
                })
            else:
                results['errors'].append({
                    'tune_id': tune_id,
                    'error': message
                })
        
        created_count = len(results['created'])
        skipped_count = len(results['skipped'])
        error_count = len(results['errors'])
        
        if error_count == 0:
            if created_count > 0:
                message = f"Successfully created {created_count} PersonTunes"
                if skipped_count > 0:
                    message += f", skipped {skipped_count} existing"
                success = True
            else:
                message = f"All {skipped_count} PersonTunes already existed"
                success = True
        else:
            message = f"Created {created_count}, skipped {skipped_count}, failed {error_count}"
            success = False
        
        return success, message, results
    
    def get_learning_status_summary(self, person_id: int) -> Dict[str, int]:
        """
        Get a summary of learning statuses for a person's tune collection.
        
        Args:
            person_id: ID of the person
            
        Returns:
            Dictionary with counts for each learning status
        """
        try:
            all_tunes = self.get_person_tunes(person_id)
            
            summary = {
                'want to learn': 0,
                'learning': 0,
                'learned': 0,
                'total': len(all_tunes)
            }
            
            for tune in all_tunes:
                if tune.learn_status in summary:
                    summary[tune.learn_status] += 1
            
            return summary
            
        except Exception:
            return {
                'want to learn': 0,
                'learning': 0,
                'learned': 0,
                'total': 0
            }
    
    def get_heard_count_statistics(self, person_id: int) -> Dict[str, Any]:
        """
        Get statistics about heard counts for a person's tune collection.
        
        Args:
            person_id: ID of the person
            
        Returns:
            Dictionary with heard count statistics
        """
        try:
            want_to_learn_tunes = self.get_person_tunes(
                person_id, 
                learn_status_filter='want to learn'
            )
            
            heard_counts = [tune.heard_count for tune in want_to_learn_tunes]
            
            if not heard_counts:
                return {
                    'total_tunes': 0,
                    'total_heard_count': 0,
                    'average_heard_count': 0.0,
                    'max_heard_count': 0,
                    'tunes_never_heard': 0,
                    'tunes_heard_multiple_times': 0
                }
            
            total_heard = sum(heard_counts)
            never_heard = sum(1 for count in heard_counts if count == 0)
            heard_multiple = sum(1 for count in heard_counts if count > 1)
            
            return {
                'total_tunes': len(heard_counts),
                'total_heard_count': total_heard,
                'average_heard_count': total_heard / len(heard_counts),
                'max_heard_count': max(heard_counts),
                'tunes_never_heard': never_heard,
                'tunes_heard_multiple_times': heard_multiple
            }
            
        except Exception:
            return {
                'total_tunes': 0,
                'total_heard_count': 0,
                'average_heard_count': 0.0,
                'max_heard_count': 0,
                'tunes_never_heard': 0,
                'tunes_heard_multiple_times': 0
            }

    def get_person_tunes_with_details(
        self,
        person_id: int,
        learn_status_filter: Optional[str] = None,
        tune_type_filter: Optional[str] = None,
        search_query: Optional[str] = None,
        page: int = 1,
        per_page: int = 2000,
        sort_by: str = 'alpha-asc'
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get person tunes with joined tune details - optimized for display.

        This method uses raw SQL with JOIN for performance optimization on read-heavy
        operations. Returns tune data formatted for API responses.

        Args:
            person_id: The person's ID
            learn_status_filter: Optional filter by learn_status
            tune_type_filter: Optional filter by tune type
            search_query: Optional search string for tune name
            page: Page number (1-indexed)
            per_page: Items per page (max 2000)
            sort_by: Sort order - one of: alpha-asc, alpha-desc, popularity-desc, popularity-asc, heard-desc, heard-asc

        Returns:
            Tuple of (list of tune dictionaries, total_count)
        """
        conn = get_db_connection()
        try:
            cur = conn.cursor()

            # Base query - use name_alias if it exists, otherwise fall back to tune name
            query = """
                SELECT
                    pt.person_tune_id, pt.person_id, pt.tune_id, pt.learn_status,
                    pt.heard_count, pt.learned_date, pt.notes,
                    pt.setting_id, pt.name_alias,
                    pt.created_date, pt.last_modified_date,
                    COALESCE(pt.name_alias, t.name) AS tune_name, t.tune_type, t.tunebook_count_cached
                FROM person_tune pt
                LEFT JOIN tune t ON pt.tune_id = t.tune_id
                WHERE pt.person_id = %s
            """
            params = [person_id]

            # Apply filters
            if learn_status_filter:
                query += " AND pt.learn_status = %s"
                params.append(learn_status_filter)

            if tune_type_filter:
                query += " AND LOWER(t.tune_type) = LOWER(%s)"
                params.append(tune_type_filter)

            if search_query:
                # Search in both name_alias and tune name (accent-insensitive and quote-insensitive)
                # Using translate() to remove accents and normalize quotes for PostgreSQL compatibility
                # Normalizes all apostrophe/quote variants: ' ' ‛ ʼ ´ ` " "
                query += """ AND (
                    translate(
                        translate(LOWER(COALESCE(pt.name_alias, t.name)),
                                 'áàâäãåāéèêëēíìîïīóòôöõøōúùûüūýÿçñ',
                                 'aaaaaaaeeeeeiiiiioooooooouuuuuyycn'),
                        '''‛ʼ´`""',
                        ''''''''
                    )
                    LIKE
                    translate(
                        translate(LOWER(%s),
                                 'áàâäãåāéèêëēíìîïīóòôöõøōúùûüūýÿçñ',
                                 'aaaaaaaeeeeeiiiiioooooooouuuuuyycn'),
                        '''‛ʼ´`""',
                        ''''''''
                    )
                )"""
                params.append(f"%{search_query}%")

            # Get total count
            count_query = f"SELECT COUNT(*) FROM ({query}) AS filtered"
            cur.execute(count_query, params)
            total_count = cur.fetchone()[0]

            # Determine sort order based on sort_by parameter
            # Use COALESCE to sort by name_alias if it exists, otherwise by tune name
            sort_map = {
                'alpha-asc': 'LOWER(COALESCE(pt.name_alias, t.name)) ASC',
                'alpha-desc': 'LOWER(COALESCE(pt.name_alias, t.name)) DESC',
                'popularity-desc': 't.tunebook_count_cached DESC NULLS LAST, LOWER(COALESCE(pt.name_alias, t.name)) ASC',
                'popularity-asc': 't.tunebook_count_cached ASC NULLS LAST, LOWER(COALESCE(pt.name_alias, t.name)) ASC',
                'heard-desc': 'pt.heard_count DESC, t.tunebook_count_cached DESC NULLS LAST, LOWER(COALESCE(pt.name_alias, t.name)) ASC',
                'heard-asc': 'pt.heard_count ASC, t.tunebook_count_cached DESC NULLS LAST, LOWER(COALESCE(pt.name_alias, t.name)) ASC'
            }
            order_by = sort_map.get(sort_by, 'LOWER(COALESCE(pt.name_alias, t.name)) ASC')  # Default to alpha-asc

            # Add ordering and pagination
            query += f" ORDER BY {order_by} LIMIT %s OFFSET %s"
            offset = (page - 1) * per_page
            params.extend([per_page, offset])

            # Execute main query
            cur.execute(query, params)
            rows = cur.fetchall()

            # Build response
            tunes = []
            for row in rows:
                tune_data = {
                    'person_tune_id': row[0],
                    'person_id': row[1],
                    'tune_id': row[2],
                    'learn_status': row[3],
                    'heard_count': row[4],
                    'learned_date': row[5].isoformat() if row[5] else None,
                    'notes': row[6],
                    'setting_id': row[7],
                    'name_alias': row[8],
                    'created_date': row[9].isoformat() if row[9] else None,
                    'last_modified_date': row[10].isoformat() if row[10] else None,
                    'tune_name': row[11],
                    'tune_type': row[12],
                    'tunebook_count': row[13],
                    'thesession_url': f"https://thesession.org/tunes/{row[2]}" if row[2] else None
                }
                tunes.append(tune_data)

            return tunes, total_count

        finally:
            conn.close()