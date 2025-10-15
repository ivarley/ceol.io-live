"""
PersonTune model for managing personal tune collections with learning status tracking.

This module provides the PersonTune class for handling individual user tune collections,
including learning status management, heard count tracking, and validation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from database import get_db_connection, save_to_history
from timezone_utils import now_utc


class PersonTune:
    """
    Model representing a person's relationship with a tune, including learning status
    and progress tracking.
    """
    
    # Valid learning status values
    VALID_LEARN_STATUSES = {'want to learn', 'learning', 'learned'}
    DEFAULT_LEARN_STATUS = 'want to learn'
    
    def __init__(
        self,
        person_tune_id: Optional[int] = None,
        person_id: Optional[int] = None,
        tune_id: Optional[int] = None,
        learn_status: str = DEFAULT_LEARN_STATUS,
        heard_count: int = 0,
        learned_date: Optional[datetime] = None,
        notes: Optional[str] = None,
        setting_id: Optional[int] = None,
        name_alias: Optional[str] = None,
        created_date: Optional[datetime] = None,
        last_modified_date: Optional[datetime] = None
    ):
        self.person_tune_id = person_tune_id
        self.person_id = person_id
        self.tune_id = tune_id
        self.learn_status = learn_status
        self.heard_count = heard_count
        self.learned_date = learned_date
        self.notes = notes
        self.setting_id = setting_id
        self.name_alias = name_alias
        self.created_date = created_date
        self.last_modified_date = last_modified_date

        # Validate on initialization
        self._validate()
    
    def _validate(self) -> None:
        """
        Validate the PersonTune instance data.
        
        Raises:
            ValueError: If validation fails
        """
        # Validate learn_status
        if self.learn_status not in self.VALID_LEARN_STATUSES:
            raise ValueError(
                f"learn_status must be one of {self.VALID_LEARN_STATUSES}, "
                f"got '{self.learn_status}'"
            )
        
        # Validate heard_count
        if self.heard_count < 0:
            raise ValueError(
                f"heard_count must be non-negative, "
                f"got {self.heard_count}"
            )
        
        # Validate person_id and tune_id if provided
        if self.person_id is not None and self.person_id <= 0:
            raise ValueError(f"person_id must be positive, got {self.person_id}")
        
        if self.tune_id is not None and self.tune_id <= 0:
            raise ValueError(f"tune_id must be positive, got {self.tune_id}")
        
        # Validate learned_date logic
        if self.learn_status == 'learned' and self.learned_date is None:
            # This is allowed - learned_date can be set later
            pass
        elif self.learn_status != 'learned' and self.learned_date is not None:
            raise ValueError(
                f"learned_date should only be set when learn_status is 'learned', "
                f"but learn_status is '{self.learn_status}'"
            )
    
    def validate_for_save(self) -> None:
        """
        Validate that the instance has all required fields for database save.
        
        Raises:
            ValueError: If required fields are missing
        """
        self._validate()  # Run standard validation first
        
        if self.person_id is None:
            raise ValueError("person_id is required for save")
        
        if self.tune_id is None:
            raise ValueError("tune_id is required for save")
    
    def set_learn_status(self, new_status: str, changed_by: str = 'system') -> bool:
        """
        Update the learning status, handling learned_date automatically.
        
        Args:
            new_status: New learning status
            changed_by: User who made the change
            
        Returns:
            bool: True if status was changed, False if already at that status
            
        Raises:
            ValueError: If new_status is invalid
        """
        if new_status not in self.VALID_LEARN_STATUSES:
            raise ValueError(
                f"learn_status must be one of {self.VALID_LEARN_STATUSES}, "
                f"got '{new_status}'"
            )
        
        if self.learn_status == new_status:
            return False
        
        old_status = self.learn_status
        self.learn_status = new_status
        
        # Set learned_date when transitioning to 'learned'
        if new_status == 'learned' and old_status != 'learned':
            self.learned_date = now_utc()
        # Clear learned_date when transitioning away from 'learned'
        elif old_status == 'learned' and new_status != 'learned':
            self.learned_date = None
        
        # Update in database if this is a persisted record
        if self.person_tune_id is not None:
            self._update_in_database(changed_by)
        
        return True
    
    def increment_heard_count(self, changed_by: str = 'system') -> int:
        """
        Increment the heard_count by 1.

        Args:
            changed_by: User who made the change

        Returns:
            int: New heard count value
        """
        self.heard_count += 1

        # Update in database if this is a persisted record
        if self.person_tune_id is not None:
            self._update_in_database(changed_by)

        return self.heard_count
    
    def _update_in_database(self, changed_by: str = 'system') -> None:
        """
        Update the record in the database.
        
        Args:
            changed_by: User who made the change
        """
        if self.person_tune_id is None:
            raise ValueError("Cannot update record without person_tune_id")
        
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("BEGIN")
            
            # Save to history before update
            save_to_history(cur, 'person_tune', 'UPDATE', self.person_tune_id, changed_by)
            
            # Update the record
            cur.execute("""
                UPDATE person_tune
                SET learn_status = %s,
                    heard_count = %s,
                    learned_date = %s,
                    notes = %s,
                    setting_id = %s,
                    name_alias = %s,
                    last_modified_date = (NOW() AT TIME ZONE 'UTC')
                WHERE person_tune_id = %s
            """, (
                self.learn_status,
                self.heard_count,
                self.learned_date,
                self.notes,
                self.setting_id,
                self.name_alias,
                self.person_tune_id
            ))
            
            cur.execute("COMMIT")
            self.last_modified_date = now_utc()
            
        except Exception as e:
            cur.execute("ROLLBACK")
            raise e
        finally:
            conn.close()
    
    def save(self, changed_by: str = 'system') -> 'PersonTune':
        """
        Save the PersonTune to the database.
        
        Args:
            changed_by: User who created/modified the record
            
        Returns:
            PersonTune: The saved instance with updated fields
            
        Raises:
            ValueError: If validation fails or required fields are missing
        """
        self.validate_for_save()
        
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("BEGIN")
            
            if self.person_tune_id is None:
                # Insert new record
                cur.execute("""
                    INSERT INTO person_tune (
                        person_id, tune_id, learn_status, heard_count,
                        learned_date, notes, setting_id, name_alias, created_date, last_modified_date
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                             (NOW() AT TIME ZONE 'UTC'), (NOW() AT TIME ZONE 'UTC'))
                    RETURNING person_tune_id, created_date, last_modified_date
                """, (
                    self.person_id,
                    self.tune_id,
                    self.learn_status,
                    self.heard_count,
                    self.learned_date,
                    self.notes,
                    self.setting_id,
                    self.name_alias
                ))
                
                result = cur.fetchone()
                self.person_tune_id = result[0]
                self.created_date = result[1]
                self.last_modified_date = result[2]
                
                # Log INSERT to history
                cur.execute("""
                    INSERT INTO person_tune_history (
                        person_tune_id, person_id, tune_id, learn_status,
                        heard_count, learned_date, notes,
                        setting_id, name_alias,
                        operation, changed_by, changed_at, created_date
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                             (NOW() AT TIME ZONE 'UTC'), %s)
                """, (
                    self.person_tune_id, self.person_id, self.tune_id,
                    self.learn_status, self.heard_count,
                    self.learned_date, self.notes, self.setting_id, self.name_alias,
                    'INSERT', changed_by,
                    self.created_date
                ))
                
            else:
                # Update existing record
                self._update_in_database(changed_by)
            
            cur.execute("COMMIT")
            return self
            
        except Exception as e:
            cur.execute("ROLLBACK")
            raise e
        finally:
            conn.close()
    
    @classmethod
    def get_by_id(cls, person_tune_id: int) -> Optional['PersonTune']:
        """
        Retrieve a PersonTune by its ID.
        
        Args:
            person_tune_id: The person_tune_id to look up
            
        Returns:
            PersonTune instance or None if not found
        """
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT person_tune_id, person_id, tune_id, learn_status,
                       heard_count, learned_date, notes,
                       setting_id, name_alias,
                       created_date, last_modified_date
                FROM person_tune
                WHERE person_tune_id = %s
            """, (person_tune_id,))

            row = cur.fetchone()
            if row:
                return cls(
                    person_tune_id=row[0],
                    person_id=row[1],
                    tune_id=row[2],
                    learn_status=row[3],
                    heard_count=row[4],
                    learned_date=row[5],
                    notes=row[6],
                    setting_id=row[7],
                    name_alias=row[8],
                    created_date=row[9],
                    last_modified_date=row[10]
                )
            return None
            
        finally:
            conn.close()
    
    @classmethod
    def get_by_person_and_tune(cls, person_id: int, tune_id: int) -> Optional['PersonTune']:
        """
        Retrieve a PersonTune by person_id and tune_id.
        
        Args:
            person_id: The person's ID
            tune_id: The tune's ID
            
        Returns:
            PersonTune instance or None if not found
        """
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT person_tune_id, person_id, tune_id, learn_status,
                       heard_count, learned_date, notes,
                       setting_id, name_alias,
                       created_date, last_modified_date
                FROM person_tune
                WHERE person_id = %s AND tune_id = %s
            """, (person_id, tune_id))

            row = cur.fetchone()
            if row:
                return cls(
                    person_tune_id=row[0],
                    person_id=row[1],
                    tune_id=row[2],
                    learn_status=row[3],
                    heard_count=row[4],
                    learned_date=row[5],
                    notes=row[6],
                    setting_id=row[7],
                    name_alias=row[8],
                    created_date=row[9],
                    last_modified_date=row[10]
                )
            return None
            
        finally:
            conn.close()
    
    @classmethod
    def get_for_person(
        cls, 
        person_id: int, 
        learn_status_filter: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List['PersonTune']:
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
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            
            query = """
                SELECT person_tune_id, person_id, tune_id, learn_status,
                       heard_count, learned_date, notes,
                       setting_id, name_alias,
                       created_date, last_modified_date
                FROM person_tune
                WHERE person_id = %s
            """
            params = [person_id]

            if learn_status_filter:
                query += " AND learn_status = %s"
                params.append(learn_status_filter)

            query += " ORDER BY created_date DESC"

            if limit:
                query += " LIMIT %s"
                params.append(limit)

            if offset > 0:
                query += " OFFSET %s"
                params.append(offset)

            cur.execute(query, params)
            rows = cur.fetchall()

            return [
                cls(
                    person_tune_id=row[0],
                    person_id=row[1],
                    tune_id=row[2],
                    learn_status=row[3],
                    heard_count=row[4],
                    learned_date=row[5],
                    notes=row[6],
                    setting_id=row[7],
                    name_alias=row[8],
                    created_date=row[9],
                    last_modified_date=row[10]
                )
                for row in rows
            ]
            
        finally:
            conn.close()
    
    def delete(self, changed_by: str = 'system') -> bool:
        """
        Delete the PersonTune from the database.
        
        Args:
            changed_by: User who deleted the record
            
        Returns:
            bool: True if deleted, False if record didn't exist
        """
        if self.person_tune_id is None:
            return False
        
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("BEGIN")
            
            # Save to history before delete
            save_to_history(cur, 'person_tune', 'DELETE', self.person_tune_id, changed_by)
            
            # Delete the record
            cur.execute("""
                DELETE FROM person_tune WHERE person_tune_id = %s
            """, (self.person_tune_id,))
            
            deleted = cur.rowcount > 0
            cur.execute("COMMIT")
            
            if deleted:
                self.person_tune_id = None
            
            return deleted
            
        except Exception as e:
            cur.execute("ROLLBACK")
            raise e
        finally:
            conn.close()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the PersonTune to a dictionary representation.

        Returns:
            Dict containing all PersonTune fields
        """
        return {
            'person_tune_id': self.person_tune_id,
            'person_id': self.person_id,
            'tune_id': self.tune_id,
            'learn_status': self.learn_status,
            'heard_count': self.heard_count,
            'learned_date': self.learned_date.isoformat() if self.learned_date else None,
            'notes': self.notes,
            'setting_id': self.setting_id,
            'name_alias': self.name_alias,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'last_modified_date': self.last_modified_date.isoformat() if self.last_modified_date else None
        }

    def __repr__(self) -> str:
        return (
            f"PersonTune(person_tune_id={self.person_tune_id}, "
            f"person_id={self.person_id}, tune_id={self.tune_id}, "
            f"learn_status='{self.learn_status}', "
            f"heard_count={self.heard_count}, "
            f"setting_id={self.setting_id}, name_alias='{self.name_alias}')"
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, PersonTune):
            return False
        return (
            self.person_tune_id == other.person_tune_id and
            self.person_id == other.person_id and
            self.tune_id == other.tune_id and
            self.learn_status == other.learn_status and
            self.heard_count == other.heard_count and
            self.learned_date == other.learned_date and
            self.notes == other.notes and
            self.setting_id == other.setting_id and
            self.name_alias == other.name_alias
        )