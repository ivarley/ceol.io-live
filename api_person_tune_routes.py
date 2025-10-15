"""
API routes for personal tune management.

This module provides RESTful API endpoints for managing personal tune collections,
including CRUD operations, learning status updates, and heard count tracking.
"""

from flask import request, jsonify
from flask_login import current_user
from typing import Optional, Dict, Any
from functools import wraps
from services.person_tune_service import PersonTuneService
from services.thesession_sync_service import ThesessionSyncService
from database import get_db_connection


# Initialize services
person_tune_service = PersonTuneService()
thesession_sync_service = ThesessionSyncService()


# Auth helpers (temporary - will be moved to person_tune_auth module)
def api_login_required(f):
    """
    Decorator for API endpoints that require authentication.
    Returns JSON error response instead of redirecting to login page.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"success": False, "error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function


def get_user_person_id() -> int:
    """Get the person_id for the current logged-in user."""
    if not current_user.is_authenticated:
        raise AttributeError("User is not authenticated")
    return current_user.person_id


def require_person_tune_ownership(func):
    """Decorator to verify user owns the person_tune record."""
    @wraps(func)
    def wrapper(person_tune_id, *args, **kwargs):
        # Get the person_tune to check ownership
        person_tune = person_tune_service.get_person_tune_by_id(person_tune_id)
        if not person_tune:
            return jsonify({"success": False, "error": "Tune not found"}), 404

        # Check if the current user owns this person_tune
        if person_tune.person_id != current_user.person_id:
            return jsonify({"success": False, "error": "You do not have permission to access this tune"}), 403

        return func(person_tune_id, *args, **kwargs)
    return wrapper


# Alias for consistency
person_tune_login_required = api_login_required


def _get_tune_details(tune_id: int) -> Optional[Dict[str, Any]]:
    """
    Helper function to fetch tune details from the database.
    
    Args:
        tune_id: The tune ID to look up
        
    Returns:
        Dictionary with tune details or None if not found
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT tune_id, name, tune_type, tunebook_count_cached
            FROM tune
            WHERE tune_id = %s
        """, (tune_id,))
        
        row = cur.fetchone()
        if row:
            return {
                'tune_id': row[0],
                'name': row[1],
                'type': row[2],
                'tunebook_count': row[3]
            }
        return None
    finally:
        conn.close()


def _build_person_tune_response(person_tune, include_tune_details: bool = True) -> Dict[str, Any]:
    """
    Helper function to build a response dictionary for a PersonTune.

    Args:
        person_tune: PersonTune instance
        include_tune_details: Whether to include full tune details

    Returns:
        Dictionary with person_tune data and optional tune details
    """
    response = person_tune.to_dict()

    if include_tune_details:
        tune_details = _get_tune_details(person_tune.tune_id)
        if tune_details:
            # Use name_alias if it exists, otherwise use the official tune name
            response['tune_name'] = person_tune.name_alias if person_tune.name_alias else tune_details['name']
            response['tune_type'] = tune_details['type']
            response['tunebook_count'] = tune_details['tunebook_count']
            # Build thesession.org URL with setting_id if available
            base_url = f"https://thesession.org/tunes/{person_tune.tune_id}"
            if person_tune.setting_id:
                response['thesession_url'] = f"{base_url}?setting={person_tune.setting_id}#setting{person_tune.setting_id}"
            else:
                response['thesession_url'] = base_url

    return response


@person_tune_login_required
def get_my_tunes():
    """
    GET /api/my-tunes

    Retrieve the current user's tune collection with pagination and filtering.

    Query Parameters:
        - page (int): Page number (default: 1)
        - per_page (int): Items per page (default: 2000, max: 2000)
        - learn_status (str): Filter by learning status
        - tune_type (str): Filter by tune type
        - search (str): Search by tune name

    Returns:
        JSON response with tune collection and metadata

    Requirements: 1.2, 3.2, 3.3, 3.4

    Performance optimizations:
        - Uses composite indexes for efficient filtering
        - Implements pagination to limit result sets
        - Optimizes query to fetch only needed columns
    """
    try:
        # Parse and validate query parameters
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(2000, max(1, int(request.args.get('per_page', 2000))))
        learn_status_filter = request.args.get('learn_status')
        tune_type_filter = request.args.get('tune_type')
        search_query = request.args.get('search', '').strip()
        sort_by = request.args.get('sort', 'alpha-asc')

        # Validate learn_status if provided
        if learn_status_filter and learn_status_filter not in ['want to learn', 'learning', 'learned']:
            return jsonify({
                "success": False,
                "error": "Invalid learn_status. Must be 'want to learn', 'learning', or 'learned'"
            }), 400

        # Validate sort_by if provided
        valid_sorts = ['alpha-asc', 'alpha-desc', 'popularity-desc', 'popularity-asc', 'heard-desc', 'heard-asc']
        if sort_by not in valid_sorts:
            return jsonify({
                "success": False,
                "error": f"Invalid sort. Must be one of: {', '.join(valid_sorts)}"
            }), 400

        person_id = get_user_person_id()

        # Get tunes from service layer
        tunes, total_count = person_tune_service.get_person_tunes_with_details(
            person_id=person_id,
            learn_status_filter=learn_status_filter,
            tune_type_filter=tune_type_filter,
            search_query=search_query if search_query else None,
            page=page,
            per_page=per_page,
            sort_by=sort_by
        )

        # Calculate pagination metadata
        total_pages = (total_count + per_page - 1) // per_page

        response = jsonify({
            "success": True,
            "tunes": tunes,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            },
            "filters": {
                "learn_status": learn_status_filter,
                "tune_type": tune_type_filter,
                "search": search_query
            }
        })

        # Disable caching to ensure fresh data after updates
        # User-specific data that changes frequently should not be cached
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

        return response, 200

    except AttributeError as e:
        return jsonify({
            "success": False,
            "error": "User authentication error"
        }), 401
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": f"Invalid parameter: {str(e)}"
        }), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error retrieving tunes: {str(e)}"
        }), 500


@person_tune_login_required
@require_person_tune_ownership
def get_person_tune_detail(person_tune_id):
    """
    GET /api/my-tunes/<person_tune_id>
    
    Get detailed information about a specific tune in the user's collection.
    
    Route Parameters:
        - person_tune_id (int): ID of the person_tune record
        
    Returns:
        JSON response with person_tune data and tune details
        
    Requirements: 4.1, 4.2
    """
    try:
        person_id = get_user_person_id()
        
        # Get the person_tune record (ownership already verified by decorator)
        person_tune = person_tune_service.get_person_tune_by_id(person_tune_id)
        
        if not person_tune:
            return jsonify({
                "success": False,
                "error": "Tune not found"
            }), 404
        
        # Build response with tune details
        response_data = _build_person_tune_response(person_tune, include_tune_details=True)
        
        # Add session popularity count
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            # Get count of distinct session instances where this person is a member and the tune has been played
            cur.execute("""
                SELECT COUNT(DISTINCT SIT.session_instance_id)
                FROM session_instance_tune SIT
                INNER JOIN session_instance SI ON SIT.session_instance_id = SI.session_instance_id
                INNER JOIN session_person SIP ON SI.session_id = SIP.session_id
                WHERE SIP.person_id = %s AND SIT.tune_id = %s
            """, (person_id, person_tune.tune_id))
            row = cur.fetchone()
            session_play_count = row[0] if row else 0
            response_data['session_play_count'] = session_play_count
        finally:
            conn.close()
        
        return jsonify({
            "success": True,
            "person_tune": response_data
        }), 200
        
    except AttributeError:
        return jsonify({
            "success": False,
            "error": "User authentication error"
        }), 401
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error retrieving tune details: {str(e)}"
        }), 500


@person_tune_login_required
def add_my_tune():
    """
    POST /api/my-tunes

    Add a tune to the current user's collection.

    Request Body:
        - tune_id (int, required): ID of the tune to add
        - learn_status (str, optional): Initial learning status (default: 'want to learn')
        - notes (str, optional): Optional notes
        - new_tune (dict, optional): Tune details from TheSession.org if tune doesn't exist locally
            - tune_id (int): TheSession.org tune ID
            - name (str): Tune name
            - tune_type (str): Tune type
            - tunebook_count (int): Popularity count

    Returns:
        JSON response with created person_tune data

    Requirements: 5.2
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400

        tune_id = data.get('tune_id')
        if not tune_id:
            return jsonify({
                "success": False,
                "error": "tune_id is required"
            }), 400

        # Check if tune exists locally
        tune_details = _get_tune_details(tune_id)

        # If tune doesn't exist and new_tune data is provided, insert it
        if not tune_details and data.get('new_tune'):
            new_tune_data = data.get('new_tune')
            conn = get_db_connection()
            try:
                cur = conn.cursor()

                # Insert the tune into the tune table
                cur.execute("""
                    INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached, last_modified_date)
                    VALUES (%s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'))
                    ON CONFLICT (tune_id) DO NOTHING
                    RETURNING tune_id
                """, (
                    new_tune_data.get('tune_id'),
                    new_tune_data.get('name'),
                    new_tune_data.get('tune_type'),
                    new_tune_data.get('tunebook_count', 0)
                ))

                conn.commit()

                # Get the tune details after insertion
                tune_details = _get_tune_details(tune_id)

            except Exception as e:
                conn.rollback()
                return jsonify({
                    "success": False,
                    "error": f"Error inserting tune: {str(e)}"
                }), 500
            finally:
                conn.close()

        # Validate tune exists (either was already there or just inserted)
        if not tune_details:
            return jsonify({
                "success": False,
                "error": f"Tune with ID {tune_id} not found"
            }), 404

        learn_status = data.get('learn_status', 'want to learn')
        notes = data.get('notes')

        person_id = get_user_person_id()
        changed_by = current_user.username if hasattr(current_user, 'username') else 'system'

        # Create the person_tune
        success, message, person_tune = person_tune_service.create_person_tune(
            person_id=person_id,
            tune_id=tune_id,
            learn_status=learn_status,
            notes=notes,
            changed_by=changed_by
        )

        if not success:
            if "already exists" in message:
                return jsonify({
                    "success": False,
                    "error": message
                }), 409  # Conflict
            else:
                return jsonify({
                    "success": False,
                    "error": message
                }), 400

        # Build response with tune details
        response_data = _build_person_tune_response(person_tune, include_tune_details=True)

        return jsonify({
            "success": True,
            "message": "Tune added to your collection successfully",
            "person_tune": response_data
        }), 201

    except AttributeError:
        return jsonify({
            "success": False,
            "error": "User authentication error"
        }), 401
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error adding tune: {str(e)}"
        }), 500


@person_tune_login_required
@require_person_tune_ownership
def update_person_tune(person_tune_id):
    """
    PUT /api/my-tunes/<person_tune_id>

    Update any fields of a tune in the user's collection.
    All fields are optional - only provided fields will be updated.

    Route Parameters:
        - person_tune_id (int): ID of the person_tune record

    Request Body (all optional):
        - learn_status (str): Learning status ('want to learn', 'learning', 'learned')
        - notes (str): Notes about the tune (empty string clears notes)
        - setting_id (int): thesession.org setting ID (null/empty string clears)
        - name_alias (str): Custom name/alias for the tune (null/empty string clears)
        - heard_count (int): Heard count (must be >= 0)

    Returns:
        JSON response with updated person_tune data
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400

        # Extract fields from request
        learn_status = data.get('learn_status') if 'learn_status' in data else None
        notes = data.get('notes') if 'notes' in data else None
        setting_id = data.get('setting_id') if 'setting_id' in data else None
        name_alias = data.get('name_alias') if 'name_alias' in data else None
        heard_count = data.get('heard_count') if 'heard_count' in data else None

        # Validate setting_id if provided
        if setting_id is not None and setting_id != '':
            try:
                setting_id = int(setting_id)
                if setting_id <= 0:
                    return jsonify({
                        "success": False,
                        "error": "setting_id must be a positive integer"
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    "success": False,
                    "error": "setting_id must be a valid integer"
                }), 400
        elif setting_id == '':
            setting_id = None

        # Validate heard_count if provided
        if heard_count is not None:
            try:
                heard_count = int(heard_count)
                if heard_count < 0:
                    return jsonify({
                        "success": False,
                        "error": "heard_count cannot be negative"
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    "success": False,
                    "error": "heard_count must be a valid integer"
                }), 400

        # Handle empty string for name_alias (means clear it)
        if name_alias == '':
            name_alias = None

        # Convert empty string to None for notes if needed
        if notes == '':
            notes = None

        changed_by = current_user.username if hasattr(current_user, 'username') else 'system'

        # Update the person_tune
        success, message, person_tune = person_tune_service.update_person_tune(
            person_tune_id=person_tune_id,
            learn_status=learn_status,
            notes=notes,
            setting_id=setting_id,
            name_alias=name_alias,
            heard_count=heard_count,
            changed_by=changed_by
        )

        if not success:
            if "not found" in message:
                return jsonify({
                    "success": False,
                    "error": message
                }), 404
            else:
                return jsonify({
                    "success": False,
                    "error": message
                }), 400

        # Build response with tune details
        response_data = _build_person_tune_response(person_tune, include_tune_details=True)

        return jsonify({
            "success": True,
            "message": message,
            "person_tune": response_data
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error updating tune: {str(e)}"
        }), 500


@person_tune_login_required
@require_person_tune_ownership
def increment_tune_heard_count(person_tune_id):
    """
    POST /api/my-tunes/<person_tune_id>/heard

    Increment the heard_count for a tune.

    Route Parameters:
        - person_tune_id (int): ID of the person_tune record

    Returns:
        JSON response with updated heard count

    Requirements: 1.6, 1.7, 1.8
    """
    try:
        changed_by = current_user.username if hasattr(current_user, 'username') else 'system'

        # Increment the heard count
        success, message, new_count = person_tune_service.increment_heard_count(
            person_tune_id=person_tune_id,
            changed_by=changed_by
        )

        if not success:
            if "not found" in message:
                return jsonify({
                    "success": False,
                    "error": message
                }), 404
            elif "want to learn" in message:
                return jsonify({
                    "success": False,
                    "error": message
                }), 422  # Unprocessable Entity
            else:
                return jsonify({
                    "success": False,
                    "error": message
                }), 400

        # Get updated person_tune for full response
        person_tune = person_tune_service.get_person_tune_by_id(person_tune_id)
        response_data = _build_person_tune_response(person_tune, include_tune_details=True)

        return jsonify({
            "success": True,
            "message": message,
            "heard_count": new_count,
            "person_tune": response_data
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error incrementing heard count: {str(e)}"
        }), 500


@person_tune_login_required
@require_person_tune_ownership
def delete_person_tune(person_tune_id):
    """
    DELETE /api/my-tunes/<person_tune_id>

    Delete a tune from the current user's collection.

    Route Parameters:
        - person_tune_id (int): ID of the person_tune record

    Returns:
        JSON response with success status
    """
    try:
        changed_by = current_user.username if hasattr(current_user, 'username') else 'system'

        # Delete the person_tune
        success, message = person_tune_service.delete_person_tune(
            person_tune_id=person_tune_id,
            changed_by=changed_by
        )

        if not success:
            if "not found" in message:
                return jsonify({
                    "success": False,
                    "error": message
                }), 404
            else:
                return jsonify({
                    "success": False,
                    "error": message
                }), 400

        return jsonify({
            "success": True,
            "message": message
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error deleting tune: {str(e)}"
        }), 500


@person_tune_login_required
def update_my_profile():
    """
    PATCH /api/person/me
    
    Update the current user's person record (limited fields).
    
    Request Body:
        - thesession_user_id (int, optional): thesession.org user ID
        
    Returns:
        JSON response with success status
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        person_id = get_user_person_id()
        
        # Only allow updating thesession_user_id for now
        thesession_user_id = data.get('thesession_user_id')
        
        if thesession_user_id is not None:
            # Validate it's a positive integer
            try:
                thesession_user_id = int(thesession_user_id)
                if thesession_user_id <= 0:
                    raise ValueError("Must be positive")
            except (ValueError, TypeError):
                return jsonify({
                    "success": False,
                    "error": "Invalid thesession_user_id. Must be a positive integer."
                }), 400
        
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            
            # Update person record
            cur.execute("""
                UPDATE person
                SET thesession_user_id = %s,
                    last_modified_date = (NOW() AT TIME ZONE 'UTC')
                WHERE person_id = %s
            """, (thesession_user_id, person_id))
            
            conn.commit()
            
            return jsonify({
                "success": True,
                "message": "Profile updated successfully"
            }), 200
            
        finally:
            conn.close()
            
    except AttributeError:
        return jsonify({
            "success": False,
            "error": "User authentication error"
        }), 401
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error updating profile: {str(e)}"
        }), 500


def search_tunes():
    """
    GET /api/tunes/search
    
    Search for tunes in the tune table by name.
    
    Query Parameters:
        - q (str, required): Search query
        - limit (int, optional): Maximum number of results (default: 20, max: 50)
        
    Returns:
        JSON response with matching tunes
        
    Requirements: 5.1
    """
    try:
        query = request.args.get('q', '').strip()
        
        if not query:
            return jsonify({
                "success": False,
                "error": "Search query is required"
            }), 400
        
        if len(query) < 2:
            return jsonify({
                "success": False,
                "error": "Search query must be at least 2 characters"
            }), 400
        
        # Get limit parameter
        try:
            limit = min(50, max(1, int(request.args.get('limit', 20))))
        except (ValueError, TypeError):
            limit = 20
        
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            
            # Search tunes by name (case-insensitive, partial match)
            # Prioritize exact matches, then starts-with, then contains
            cur.execute("""
                SELECT tune_id, name, tune_type, tunebook_count_cached,
                       CASE
                           WHEN LOWER(name) = LOWER(%s) THEN 1
                           WHEN LOWER(name) LIKE LOWER(%s) THEN 2
                           ELSE 3
                       END AS match_priority
                FROM tune
                WHERE LOWER(name) LIKE LOWER(%s)
                ORDER BY match_priority, tunebook_count_cached DESC NULLS LAST, name
                LIMIT %s
            """, (query, f"{query}%", f"%{query}%", limit))
            
            rows = cur.fetchall()
            
            tunes = []
            for row in rows:
                tunes.append({
                    'tune_id': row[0],
                    'name': row[1],
                    'tune_type': row[2],
                    'tunebook_count': row[3]
                })
            
            return jsonify({
                "success": True,
                "tunes": tunes,
                "count": len(tunes)
            }), 200
            
        finally:
            conn.close()
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error searching tunes: {str(e)}"
        }), 500


@person_tune_login_required
def sync_my_tunes():
    """
    POST /api/my-tunes/sync
    
    Sync the current user's tune collection from thesession.org.
    
    Request Body:
        - thesession_user_id (int, optional): thesession.org user ID (uses person.thesession_user_id if not provided)
        - learn_status (str, optional): Default learning status for synced tunes (default: 'want to learn')
        - retry_failed (bool, optional): Whether to retry previously failed tunes (default: false)
        
    Returns:
        JSON response with sync results and statistics
        
    Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
    """
    try:
        data = request.get_json() or {}
        person_id = get_user_person_id()
        changed_by = current_user.username if hasattr(current_user, 'username') else 'system'
        
        # Get thesession_user_id from request or person record
        thesession_user_id = data.get('thesession_user_id')
        
        if not thesession_user_id:
            # Try to get from person record
            conn = get_db_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT thesession_user_id FROM person WHERE person_id = %s",
                    (person_id,)
                )
                row = cur.fetchone()
                if row and row[0]:
                    thesession_user_id = row[0]
            finally:
                conn.close()
        
        if not thesession_user_id:
            return jsonify({
                "success": False,
                "error": "thesession_user_id is required. Please provide it in the request or set it in your profile."
            }), 400
        
        # Validate thesession_user_id is a positive integer
        try:
            thesession_user_id = int(thesession_user_id)
            if thesession_user_id <= 0:
                raise ValueError("Must be positive")
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": "Invalid thesession_user_id. Must be a positive integer."
            }), 400
        
        # Get optional parameters
        learn_status = data.get('learn_status', 'want to learn')
        
        # Validate learn_status
        if learn_status not in ['want to learn', 'learning', 'learned']:
            return jsonify({
                "success": False,
                "error": "Invalid learn_status. Must be 'want to learn', 'learning', or 'learned'"
            }), 400
        
        # Perform the sync
        success, message, results = thesession_sync_service.sync_tunebook_to_person(
            person_id=person_id,
            thesession_user_id=thesession_user_id,
            learn_status=learn_status,
            changed_by=changed_by
        )
        
        # Build response
        response = {
            "success": success,
            "message": message,
            "results": {
                "tunes_fetched": results['tunes_fetched'],
                "tunes_created": results['tunes_created'],
                "person_tunes_added": results['person_tunes_added'],
                "person_tunes_skipped": results['person_tunes_skipped'],
                "errors": results['errors'],
                "status": results.get('status', 'completed'),
                "progress_percent": results.get('progress_percent', 100)
            }
        }
        
        # Determine appropriate status code
        if not success:
            if "not found" in message or "User #" in message:
                status_code = 404
            elif "timed out" in message or "Could not connect" in message:
                status_code = 503  # Service Unavailable
            else:
                status_code = 500
        else:
            status_code = 200
        
        return jsonify(response), status_code
        
    except AttributeError:
        return jsonify({
            "success": False,
            "error": "User authentication error"
        }), 401
    except Exception as e:
        import traceback
        import sys
        # Log the full traceback for debugging
        print(f"ERROR in sync_my_tunes: {str(e)}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({
            "success": False,
            "error": f"Error syncing tunes: {str(e)}",
            "results": {
                "tunes_fetched": 0,
                "tunes_created": 0,
                "person_tunes_added": 0,
                "person_tunes_skipped": 0,
                "errors": [str(e)]
            }
        }), 500
