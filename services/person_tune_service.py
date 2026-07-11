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

# The list loader (with its plays-sort expression) lives in serializers.py.


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
        setting_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Tuple[bool, str, Optional[PersonTune]]:
        """
        Create a new PersonTune record.

        Args:
            person_id: ID of the person
            tune_id: ID of the tune
            learn_status: Initial learning status (defaults to 'want to learn')
            notes: Optional notes
            setting_id: Optional thesession.org setting ID
            user_id: ID of user who created the record

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
                notes=notes,
                setting_id=setting_id
            )
            
            # Save to database
            saved_person_tune = person_tune.save(user_id=user_id)
            
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
        user_id: Optional[int] = None
    ) -> Tuple[bool, str, Optional[PersonTune]]:
        """
        Update the learning status of a PersonTune.
        
        Args:
            person_tune_id: ID of the PersonTune to update
            new_status: New learning status
            user_id: ID of user who made the change
            
        Returns:
            Tuple of (success, message, updated_person_tune)
        """
        try:
            person_tune = PersonTune.get_by_id(person_tune_id)
            if not person_tune:
                return False, f"PersonTune with ID {person_tune_id} not found", None
            
            # Attempt to set the new status
            status_changed = person_tune.set_learn_status(new_status, user_id=user_id)
            
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
        user_id: Optional[int] = None
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Increment the heard_count for a PersonTune.
        
        Args:
            person_tune_id: ID of the PersonTune to update
            user_id: ID of user who made the change
            
        Returns:
            Tuple of (success, message, new_heard_count)
        """
        try:
            person_tune = PersonTune.get_by_id(person_tune_id)
            if not person_tune:
                return False, f"PersonTune with ID {person_tune_id} not found", None
            
            # Increment the heard count
            new_count = person_tune.increment_heard_count(user_id=user_id)
            
            return True, f"Heard count incremented to {new_count}", new_count
            
        except ValueError as e:
            return False, f"Validation error: {str(e)}", None
        except Exception as e:
            return False, f"Error incrementing heard count: {str(e)}", None

    def decrement_heard_count(
        self,
        person_tune_id: int,
        user_id: Optional[int] = None
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Decrement the heard_count for a PersonTune (minimum 0).

        Args:
            person_tune_id: ID of the PersonTune to update
            user_id: ID of user who made the change

        Returns:
            Tuple of (success, message, new_heard_count)
        """
        try:
            person_tune = PersonTune.get_by_id(person_tune_id)
            if not person_tune:
                return False, f"PersonTune with ID {person_tune_id} not found", None

            # Decrement the heard count
            new_count = person_tune.decrement_heard_count(user_id=user_id)

            return True, f"Heard count decremented to {new_count}", new_count

        except ValueError as e:
            return False, f"Validation error: {str(e)}", None
        except Exception as e:
            return False, f"Error decrementing heard count: {str(e)}", None

    def update_person_tune(
        self,
        person_tune_id: int,
        learn_status=UNSET,
        notes=UNSET,
        setting_id=UNSET,
        name_alias=UNSET,
        heard_count=UNSET,
        user_id: Optional[int] = None
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
            user_id: ID of user who made the change

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
                status_changed = person_tune.set_learn_status(learn_status, user_id=user_id)
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
                person_tune.save(user_id=user_id)
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
        user_id: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Delete a PersonTune record.
        
        Args:
            person_tune_id: ID of the PersonTune to delete
            user_id: ID of user who deleted the record
            
        Returns:
            Tuple of (success, message)
        """
        try:
            person_tune = PersonTune.get_by_id(person_tune_id)
            if not person_tune:
                return False, f"PersonTune with ID {person_tune_id} not found"
            
            deleted = person_tune.delete(user_id=user_id)
            
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
        user_id: Optional[int] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Create multiple PersonTune records for a person.
        
        Args:
            person_id: ID of the person
            tune_ids: List of tune IDs to add
            learn_status: Learning status for all tunes
            user_id: ID of user who created the records
            
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
                user_id=user_id
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

    def get_person_instruments(self, person_id: int) -> List[Dict[str, Any]]:
        """The person's instruments with their auto/manual flag.

        `is_auto` instruments follow person_tune.learn_status; manual ones are a
        curated per-instrument list. The client uses this to resolve per-instrument
        status alongside the sparse overrides.
        """
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT instrument, is_auto FROM person_instrument WHERE person_id = %s ORDER BY instrument",
                (person_id,)
            )
            return [{'instrument': r[0], 'is_auto': r[1]} for r in cur.fetchall()]
        finally:
            conn.close()

    def get_instrument_overrides(self, person_id: int, tune_id: int) -> Dict[str, str]:
        """Sparse per-instrument status overrides for a single (person, tune)."""
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT instrument, status FROM person_tune_instrument WHERE person_id = %s AND tune_id = %s",
                (person_id, tune_id)
            )
            return {r[0]: r[1] for r in cur.fetchall()}
        finally:
            conn.close()