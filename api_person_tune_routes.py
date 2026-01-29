"""
API routes for personal tune management.

This module provides RESTful API endpoints for managing personal tune collections,
including CRUD operations, learning status updates, and heard count tracking.
"""

from flask import request, jsonify
from flask_login import current_user
from typing import Optional, Dict, Any
from functools import wraps
from services.person_tune_service import PersonTuneService, UNSET
from services.thesession_sync_service import ThesessionSyncService
from database import get_db_connection, get_current_user_id
import base64


def bytea_to_base64(data):
    """
    Convert PostgreSQL bytea data to base64 string.
    Handles different return formats: bytes, memoryview, hex string.
    """
    if not data:
        return None

    if isinstance(data, memoryview):
        data = data.tobytes()
    elif isinstance(data, str):
        # PostgreSQL returns bytea as hex string starting with \x
        if data.startswith('\\x'):
            data = bytes.fromhex(data[2:])
        else:
            data = data.encode('latin1')
    elif not isinstance(data, bytes):
        data = bytes(data)

    return base64.b64encode(data).decode('utf-8')


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

        # Get ABC notation and images from tune_setting
        # If setting_id is specified, use that; otherwise, use the first setting for this tune
        abc_notation = None
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            if person_tune.setting_id:
                # Use the specific setting_id if saved
                cur.execute(
                    "SELECT abc, incipit_abc, image, incipit_image, key FROM tune_setting WHERE setting_id = %s",
                    (person_tune.setting_id,)
                )
            else:
                # Fall back to the first setting for this tune (ordered by setting_id)
                cur.execute(
                    """SELECT abc, incipit_abc, image, incipit_image, key
                       FROM tune_setting
                       WHERE tune_id = %s
                       ORDER BY setting_id ASC
                       LIMIT 1""",
                    (person_tune.tune_id,)
                )
            abc_result = cur.fetchone()
            if abc_result:
                abc_notation = abc_result[0]
                response['incipit_abc'] = abc_result[1]
                response['image'] = bytea_to_base64(abc_result[2])
                response['incipit_image'] = bytea_to_base64(abc_result[3])
                response['setting_key'] = abc_result[4]
        finally:
            conn.close()
        response['abc'] = abc_notation

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
        
        # Add session popularity count and play history
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            # Get count of distinct session instances where this person attended and the tune was played
            cur.execute("""
                SELECT COUNT(DISTINCT SIT.session_instance_id)
                FROM session_instance_tune SIT
                INNER JOIN session_instance SI ON SIT.session_instance_id = SI.session_instance_id
                INNER JOIN session_instance_person SIP ON SI.session_instance_id = SIP.session_instance_id
                WHERE SIP.person_id = %s AND SIT.tune_id = %s
            """, (person_id, person_tune.tune_id))
            row = cur.fetchone()
            session_play_count = row[0] if row else 0
            response_data['session_play_count'] = session_play_count

            # Get detailed play history for sessions where person attended
            cur.execute("""
                SELECT
                    S.name,
                    S.path,
                    SI.date,
                    SIT.name,
                    SIT.key_override,
                    SIT.setting_override,
                    SI.session_instance_id,
                    ROW_NUMBER() OVER (PARTITION BY SIT.session_instance_id ORDER BY SIT.order_position) AS position_in_set
                FROM session_instance_tune SIT
                INNER JOIN session_instance SI ON SIT.session_instance_id = SI.session_instance_id
                INNER JOIN session S ON SI.session_id = S.session_id
                INNER JOIN session_instance_person SIP ON SI.session_instance_id = SIP.session_instance_id
                WHERE SIP.person_id = %s AND SIT.tune_id = %s
                ORDER BY SI.date DESC
            """, (person_id, person_tune.tune_id))

            play_instances_raw = cur.fetchall()
            play_instances = []
            for row in play_instances_raw:
                session_name = row[0]
                session_path = row[1]
                date = row[2]
                name_override = row[3]
                key_override = row[4]
                setting_override = row[5]
                session_instance_id = row[6]
                position_in_set = row[7]

                # Build full name for display: "Session Name - YYYY-MM-DD"
                full_name = f"{session_name} - {date.strftime('%Y-%m-%d')}" if date else session_name
                # Build link to session instance
                link = f"/sessions/{session_path}/{session_instance_id}"

                play_instances.append({
                    "full_name": full_name,
                    "session_name": session_name,
                    "session_path": session_path,
                    "date": date.isoformat() if date else None,
                    "position_in_set": position_in_set,
                    "name_override": name_override,
                    "key_override": key_override,
                    "setting_id_override": setting_override,
                    "session_instance_id": session_instance_id,
                    "link": link
                })

            response_data['play_instances'] = play_instances

            # Also get global play count (all sessions, not just where person attended)
            cur.execute("""
                SELECT COUNT(DISTINCT SIT.session_instance_id)
                FROM session_instance_tune SIT
                WHERE SIT.tune_id = %s
            """, (person_tune.tune_id,))
            row = cur.fetchone()
            global_play_count = row[0] if row else 0
            response_data['global_play_count'] = global_play_count
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

        # Check if tune exists and if it's a redirect
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT redirect_to_tune_id FROM tune WHERE tune_id = %s", (tune_id,))
            redirect_check = cur.fetchone()

            if redirect_check and redirect_check[0] is not None:
                # Tune is a redirect - get the destination tune's info
                redirect_to_id = redirect_check[0]
                cur.execute("SELECT name FROM tune WHERE tune_id = %s", (redirect_to_id,))
                redirect_tune = cur.fetchone()
                redirect_tune_name = redirect_tune[0] if redirect_tune else f"Tune #{redirect_to_id}"

                # Check if the destination tune is already in their tunebook
                person_id = get_user_person_id()
                cur.execute(
                    "SELECT person_tune_id FROM person_tune WHERE person_id = %s AND tune_id = %s",
                    (person_id, redirect_to_id)
                )
                existing_person_tune = cur.fetchone()

                if existing_person_tune:
                    # Already in tunebook
                    cur.close()
                    conn.close()
                    return jsonify({
                        "success": False,
                        "error": "tune_redirected_exists",
                        "message": f"This tune was merged with {redirect_tune_name}, which is already in your tunebook",
                        "redirect_to_tune_id": redirect_to_id,
                        "redirect_to_tune_name": redirect_tune_name
                    }), 409
                else:
                    # Add the destination tune instead
                    cur.close()
                    conn.close()

                    # Update tune_id to use the redirect destination
                    tune_id = redirect_to_id
                    # Clear new_tune data since we're using the existing redirected-to tune
                    data['new_tune'] = None
                    # Flag that we did a redirect so we can return the right message
                    data['_redirected_from'] = data.get('tune_id')
                    data['_redirect_tune_name'] = redirect_tune_name

            else:
                cur.close()
                conn.close()
        except Exception as e:
            conn.close()
            raise e

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
                    INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached, tunebook_count_cached_date, created_by_user_id)
                    VALUES (%s, %s, %s, %s, CURRENT_DATE, %s)
                    ON CONFLICT (tune_id) DO NOTHING
                    RETURNING tune_id
                """, (
                    new_tune_data.get('tune_id'),
                    new_tune_data.get('name'),
                    new_tune_data.get('tune_type'),
                    new_tune_data.get('tunebook_count', 0),
                    get_current_user_id()
                ))

                # If a new tune was actually inserted (not a conflict), cache the default setting
                inserted_tune = cur.fetchone()
                conn.commit()

                if inserted_tune:
                    # Cache the default setting and generate images
                    # Use lazy import to avoid circular dependency with api_routes
                    from api_routes import cache_default_tune_setting
                    # new_tune data from frontend doesn't include settings, so pass None
                    # to have the helper fetch full tune data from thesession.org
                    cache_default_tune_setting(tune_id, None, get_current_user_id(), sync=True)

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
        user_id = current_user.user_id if hasattr(current_user, 'user_id') else None

        # Create the person_tune
        success, message, person_tune = person_tune_service.create_person_tune(
            person_id=person_id,
            tune_id=tune_id,
            learn_status=learn_status,
            notes=notes,
            user_id=user_id
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

        # Check if we redirected from another tune
        if data.get('_redirected_from'):
            return jsonify({
                "success": True,
                "redirected": True,
                "message": f"This tune was merged with {data.get('_redirect_tune_name')}, added it to your tunebook",
                "redirect_to_tune_id": tune_id,
                "redirect_to_tune_name": data.get('_redirect_tune_name'),
                "person_tune": response_data
            }), 201

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

        # Extract fields from request - use UNSET for fields not provided
        learn_status = data.get('learn_status') if 'learn_status' in data else UNSET
        notes = data.get('notes') if 'notes' in data else UNSET
        setting_id = data.get('setting_id') if 'setting_id' in data else UNSET
        name_alias = data.get('name_alias') if 'name_alias' in data else UNSET
        heard_count = data.get('heard_count') if 'heard_count' in data else UNSET

        # Validate setting_id if provided
        if setting_id is not UNSET and setting_id is not None and setting_id != '':
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
        if heard_count is not UNSET and heard_count is not None:
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

        user_id = current_user.user_id if hasattr(current_user, 'user_id') else None

        # Update the person_tune
        success, message, person_tune = person_tune_service.update_person_tune(
            person_tune_id=person_tune_id,
            learn_status=learn_status,
            notes=notes,
            setting_id=setting_id,
            name_alias=name_alias,
            heard_count=heard_count,
            user_id=user_id
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
        user_id = current_user.user_id if hasattr(current_user, 'user_id') else None

        # Increment the heard count
        success, message, new_count = person_tune_service.increment_heard_count(
            person_tune_id=person_tune_id,
            user_id=user_id
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
            "new_count": new_count,  # Alias for consistency
            "person_tune": response_data
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error incrementing heard count: {str(e)}"
        }), 500


@person_tune_login_required
@require_person_tune_ownership
def decrement_tune_heard_count(person_tune_id):
    """
    DELETE /api/my-tunes/<person_tune_id>/heard

    Atomically decrement the heard count for a tune (minimum 0).

    Route Parameters:
        - person_tune_id (int): ID of the person_tune record

    Returns:
        JSON response with updated heard count
    """
    try:
        user_id = current_user.user_id if hasattr(current_user, 'user_id') else None

        # Decrement the heard count
        success, message, new_count = person_tune_service.decrement_heard_count(
            person_tune_id=person_tune_id,
            user_id=user_id
        )

        if not success:
            # Check if it's a validation error or not found error
            if "not found" in message.lower():
                return jsonify({
                    "success": False,
                    "error": message
                }), 404
            elif "validation" in message.lower():
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
            "new_count": new_count,  # Alias for consistency
            "person_tune": response_data
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error decrementing heard count: {str(e)}"
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
        user_id = current_user.user_id if hasattr(current_user, 'user_id') else None

        # Delete the person_tune
        success, message = person_tune_service.delete_person_tune(
            person_tune_id=person_tune_id,
            user_id=user_id
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
        - person_id (int, optional): Person ID for checking person_tune membership
        - session_id (int, optional): Session ID for checking session_tune membership

    Returns:
        JSON response with matching tunes, including:
        - in_person_tune (bool): Whether tune is in user's person_tune (if person_id provided)
        - learn_status (str): User's learning status for tune (if person_id provided and in person_tune)
        - in_session_tune (bool): Whether tune is in session's tune list (if session_id provided)

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

        # Get optional context parameters
        person_id = request.args.get('person_id', type=int)
        session_id = request.args.get('session_id', type=int)

        conn = get_db_connection()
        try:
            cur = conn.cursor()

            # Build query with optional LEFT JOINs based on context
            select_fields = ["t.tune_id", "t.name", "t.tune_type", "t.tunebook_count_cached"]
            joins = []
            order_by_fields = []
            query_params = []

            # Add person_tune join if person_id provided
            if person_id:
                select_fields.extend([
                    "pt.person_tune_id IS NOT NULL AS in_person_tune",
                    "pt.learn_status"
                ])
                joins.append("LEFT OUTER JOIN person_tune pt ON t.tune_id = pt.tune_id AND pt.person_id = %s")
                query_params.append(person_id)
                # Rank tunes already in person_tune below others
                order_by_fields.append("CASE WHEN pt.person_tune_id IS NOT NULL THEN 1 ELSE 0 END")

            # Add session_tune join if session_id provided
            if session_id:
                select_fields.append("st.session_id IS NOT NULL AS in_session_tune")
                joins.append("LEFT OUTER JOIN session_tune st ON t.tune_id = st.tune_id AND st.session_id = %s")
                query_params.append(session_id)
                # Rank tunes already in session_tune below others
                if not person_id:  # Only add if not already prioritizing by person_tune
                    order_by_fields.append("CASE WHEN st.session_id IS NOT NULL THEN 1 ELSE 0 END")

            # Build match priority case (accent insensitive)
            select_fields.append("""CASE
                           WHEN LOWER(unaccent(t.name)) = LOWER(unaccent(%s)) THEN 1
                           WHEN LOWER(unaccent(t.name)) LIKE LOWER(unaccent(%s)) THEN 2
                           ELSE 3
                       END AS match_priority""")

            # Build final query
            join_clause = " ".join(joins) if joins else ""
            select_clause = ", ".join(select_fields)

            # Construct ORDER BY: existing priority first, then match priority, then tunebook count, then name
            order_by_parts = order_by_fields + ["match_priority", "t.tunebook_count_cached DESC NULLS LAST", "t.name"]
            order_by_clause = ", ".join(order_by_parts)

            sql = f"""
                SELECT {select_clause}
                FROM tune t
                {join_clause}
                WHERE LOWER(unaccent(t.name)) LIKE LOWER(unaccent(%s))
                  AND t.redirect_to_tune_id IS NULL
                ORDER BY {order_by_clause}
                LIMIT %s
            """

            # Build final parameter list in order of appearance in SQL:
            # 1. query params for CASE statement (in SELECT)
            # 2. query_params for JOINs (person_id, session_id)
            # 3. query param for WHERE clause
            # 4. limit param
            final_params = [query, f"{query}%"] + query_params + [f"%{query}%", limit]
            cur.execute(sql, final_params)

            rows = cur.fetchall()

            tunes = []
            for row in rows:
                tune_data = {
                    'tune_id': row[0],
                    'name': row[1],
                    'tune_type': row[2],
                    'tunebook_count': row[3]
                }

                # Add person_tune fields if requested
                if person_id:
                    tune_data['in_person_tune'] = bool(row[4])
                    tune_data['learn_status'] = row[5] if row[4] else None

                # Add session_tune field if requested
                if session_id:
                    # Index depends on whether person_id was included
                    session_idx = 6 if person_id else 4
                    tune_data['in_session_tune'] = bool(row[session_idx])

                tunes.append(tune_data)

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
        user_id = current_user.user_id if hasattr(current_user, 'user_id') else None
        
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
            user_id=user_id
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


@person_tune_login_required
def get_common_tunes(other_person_id):
    """
    GET /api/my-tunes/common/<int:other_person_id>

    Get tunes that both the current user and another person have in their collections
    with "learned" or "learning" status.

    Route Parameters:
        - other_person_id (int): ID of the other person to compare with

    Query Parameters:
        - search (str, optional): Search query for tune names
        - tune_type (str, optional): Filter by tune type
        - sort (str, optional): Sort order (alpha-asc, alpha-desc, popularity-desc)

    Returns:
        JSON response with list of common tunes (basic info only)
    """
    try:
        person_id = get_user_person_id()

        # Get query parameters
        search_query = request.args.get('search', '').strip()
        tune_type_filter = request.args.get('tune_type', '').strip()
        sort_by = request.args.get('sort', 'alpha-asc')

        # Validate sort parameter
        valid_sorts = ['alpha-asc', 'alpha-desc', 'popularity-desc']
        if sort_by not in valid_sorts:
            sort_by = 'alpha-asc'

        # Build the SQL query
        conn = get_db_connection()
        try:
            cur = conn.cursor()

            # Base query to find common tunes where both users have learned/learning status
            query = """
                SELECT DISTINCT
                    t.tune_id,
                    t.name AS tune_name,
                    t.tune_type,
                    t.tunebook_count_cached
                FROM person_tune pt1
                INNER JOIN person_tune pt2 ON pt1.tune_id = pt2.tune_id
                INNER JOIN tune t ON pt1.tune_id = t.tune_id
                WHERE pt1.person_id = %s
                  AND pt2.person_id = %s
                  AND pt1.learn_status IN ('learned', 'learning')
                  AND pt2.learn_status IN ('learned', 'learning')
            """

            params = [person_id, other_person_id]

            # Add search filter if provided
            if search_query:
                query += " AND LOWER(t.name) LIKE LOWER(%s)"
                params.append(f"%{search_query}%")

            # Add tune type filter if provided
            if tune_type_filter:
                query += " AND t.tune_type = %s"
                params.append(tune_type_filter)

            # Add sorting
            if sort_by == 'alpha-asc':
                query += " ORDER BY t.name ASC"
            elif sort_by == 'alpha-desc':
                query += " ORDER BY t.name DESC"
            elif sort_by == 'popularity-desc':
                query += " ORDER BY t.tunebook_count_cached DESC NULLS LAST, t.name ASC"

            cur.execute(query, params)
            rows = cur.fetchall()

            # Build response
            tunes = []
            for row in rows:
                tunes.append({
                    'tune_id': row[0],
                    'tune_name': row[1],
                    'tune_type': row[2],
                    'tunebook_count': row[3] or 0
                })

            return jsonify({
                "success": True,
                "tunes": tunes,
                "count": len(tunes)
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
            "error": f"Error retrieving common tunes: {str(e)}"
        }), 500
