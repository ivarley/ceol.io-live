"""
API routes for personal tune management.

This module provides RESTful API endpoints for managing personal tune collections,
including CRUD operations, learning status updates, and heard count tracking.
"""

from flask import request, jsonify
from flask_login import current_user
from typing import Optional, Dict, Any
from functools import wraps
from services.person_tune_service import PersonTuneService, UNSET, normalize_tags
from services.thesession_sync_service import ThesessionSyncService
from database import (get_db_connection, get_current_user_id, normalize_quotes,
                      normalize_quotes_sql, ABC_MATCH_SQL, abc_search_terms)
import base64


import psycopg2.extras

from serializers import (
    bytea_to_base64,
    build_my_tunes_payload,
    build_person_tune_detail,
    load_person_instruments,
    _attach_instrument_overrides,
    _attach_person_play_counts,
    VALID_PERSON_TUNE_SORTS,
)


# Initialize services
person_tune_service = PersonTuneService()
thesession_sync_service = ThesessionSyncService()


from api_auth import api_login_required, public_api


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


def _person_tune_detail_response(person_tune_id: int) -> Optional[Dict[str, Any]]:
    """Full detail dict for one person_tune, via the shared serializer
    (serializers.py) — the same core shape /api/my-tunes list rows use."""
    conn = get_db_connection()
    try:
        return build_person_tune_detail(conn, person_tune_id)
    finally:
        conn.close()


def _cache_setting_if_needed(tune_id: int, setting_id, user_id) -> None:
    """Make sure an explicitly chosen setting is in the local tune_setting cache.
    The deep-search preview pages settings straight off thesession.org (the backfill),
    so the one the person picked is often one we've never imported."""
    if not setting_id:
        return
    from api_routes import cache_default_tune_setting
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT setting_id FROM tune_setting WHERE setting_id = %s", (setting_id,))
        if not cur.fetchone():
            cache_default_tune_setting(tune_id, None, user_id, sync=True, target_setting_id=setting_id)
    finally:
        conn.close()


def _apply_to_existing_person_tune(person_id: int, tune_id: int, setting_id, notes, user_id) -> Dict[str, Any]:
    """Apply the EXPLICIT parts of an add request to a person_tune that already exists,
    and report what changed as {"setting_id": <id>} / {"notes": true}.

    Only what the caller actually asked for is touched, and the two fields have
    deliberately different rules:
      - setting_id: applied even over an existing one. Picking a setting is an explicit,
        cheap-to-redo choice, and the caller just pointed at this one.
      - notes: applied only when the existing row has none. Free text is lossy to
        overwrite, so an existing note wins and the caller keeps theirs on screen.
    """
    applied: Dict[str, Any] = {}
    existing = person_tune_service.get_person_tune_by_person_and_tune(person_id, tune_id)
    if not existing:
        return applied

    if setting_id and setting_id != existing.setting_id:
        _cache_setting_if_needed(tune_id, setting_id, user_id)
        ok, _msg, _pt = person_tune_service.update_person_tune(
            person_tune_id=existing.person_tune_id,
            setting_id=setting_id,
            user_id=user_id,
        )
        if ok:
            applied["setting_id"] = setting_id

    if notes and not (existing.notes or "").strip():
        ok, _msg, _pt = person_tune_service.update_person_tune(
            person_tune_id=existing.person_tune_id,
            notes=notes,
            user_id=user_id,
        )
        if ok:
            applied["notes"] = True

    return applied


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
        if sort_by not in VALID_PERSON_TUNE_SORTS:
            return jsonify({
                "success": False,
                "error": f"Invalid sort. Must be one of: {', '.join(VALID_PERSON_TUNE_SORTS)}"
            }), 400

        person_id = get_user_person_id()

        # The whole response body comes from the shared serializer; the /my-tunes
        # page shell embeds the same function's output, so they can't drift.
        conn = get_db_connection()
        try:
            payload = build_my_tunes_payload(
                conn,
                person_id,
                learn_status=learn_status_filter,
                tune_type=tune_type_filter,
                search=search_query if search_query else None,
                sort=sort_by,
                page=page,
                per_page=per_page,
            )
        finally:
            conn.close()

        response = jsonify(payload)

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
        # Ownership already verified by decorator. session_play_count,
        # global_play_count, and person_list_count all come from the serializer.
        # Play history is NOT fetched here — the modal lazily loads it from
        # /api/tunes/<id>/history?person=me when the History tab is first viewed.
        response_data = _person_tune_detail_response(person_tune_id)

        if not response_data:
            return jsonify({
                "success": False,
                "error": "Tune not found"
            }), 404

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

        # thesession.org import (spec 026 pattern): a thesession_id (int, numeric
        # string, or tunes URL) is also an acceptable target — thesession ids ARE our
        # tune ids, so it doubles as tune_id and, when the tune isn't local yet, we
        # import it server-side below (the add pane's remote picks + paste-a-URL).
        from live_logging_routes import _parse_thesession_id
        thesession_id = _parse_thesession_id(data.get('thesession_id'))
        if not tune_id and thesession_id is not None:
            tune_id = thesession_id
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

        # Not local but identified by thesession_id: import it (tune row + default
        # setting ABC; notation images render lazily). Same helper the live logger's
        # add op uses, so imports behave identically in both flows.
        if not tune_details and thesession_id is not None:
            from live_logging_routes import _import_tune_for_live
            from api_routes import TuneImportError
            conn = get_db_connection()
            try:
                cur = conn.cursor()
                _import_tune_for_live(cur, tune_id, get_current_user_id())
                conn.commit()
            except TuneImportError as e:
                conn.rollback()
                return jsonify({
                    "success": False,
                    "error": f"Could not import tune from thesession.org: {e.message}"
                }), 502
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
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
        setting_id = data.get('setting_id')

        person_id = get_user_person_id()
        user_id = current_user.user_id if hasattr(current_user, 'user_id') else None

        # Create the person_tune
        success, message, person_tune = person_tune_service.create_person_tune(
            person_id=person_id,
            tune_id=tune_id,
            learn_status=learn_status,
            notes=notes,
            setting_id=setting_id,
            user_id=user_id
        )

        if not success:
            if "already exists" in message:
                # The tune is already on the list, so there is nothing to CREATE — but the
                # caller still asked for a specific setting (and maybe notes), and the add
                # surfaces can't always tell you the tune is already there (a pasted
                # thesession.org link resolves to a synthetic result with no on-list flag).
                # Dropping the request on the floor loses exactly what the user configured,
                # so apply it to the existing row and say what was applied.
                applied = _apply_to_existing_person_tune(person_id, tune_id, setting_id, notes, user_id)
                existing = person_tune_service.get_person_tune_by_person_and_tune(person_id, tune_id)
                body = {
                    "success": False,
                    "error": message,
                    "applied": applied,
                }
                if existing:
                    body["person_tune"] = _person_tune_detail_response(existing.person_tune_id)
                return jsonify(body), 409  # Conflict
            else:
                return jsonify({
                    "success": False,
                    "error": message
                }), 400

        _cache_setting_if_needed(tune_id, setting_id, user_id)

        # Build response with tune details via the shared serializer
        response_data = _person_tune_detail_response(person_tune.person_tune_id)

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
        - key (str): "I play this in ..." (null/empty string clears) — spec 037
        - tags (list[str]): Freeform per-person tags (spec 042); re-normalized server-side
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
        key = data.get('key') if 'key' in data else UNSET
        tags = data.get('tags') if 'tags' in data else UNSET
        heard_count = data.get('heard_count') if 'heard_count' in data else UNSET

        # tags must be a list when provided (normalized in the service). Reject a
        # non-list rather than silently coercing so client bugs surface.
        if tags is not UNSET and tags is not None and not isinstance(tags, list):
            return jsonify({
                "success": False,
                "error": "tags must be a list of strings"
            }), 400

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

        # Empty string clears the key ("no preference — whatever the setting says")
        if key == '':
            key = None

        user_id = current_user.user_id if hasattr(current_user, 'user_id') else None

        # Update the person_tune
        success, message, person_tune = person_tune_service.update_person_tune(
            person_tune_id=person_tune_id,
            learn_status=learn_status,
            notes=notes,
            setting_id=setting_id,
            name_alias=name_alias,
            key=key,
            tags=tags,
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

        # Build response with tune details via the shared serializer
        response_data = _person_tune_detail_response(person_tune.person_tune_id)

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

        # Full response via the shared serializer
        response_data = _person_tune_detail_response(person_tune_id)

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

        # Full response via the shared serializer
        response_data = _person_tune_detail_response(person_tune_id)

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
def my_tunes_op():
    """
    POST /api/my-tunes/ops

    Idempotent, tune_id-keyed My-Tunes mutation endpoint for the offline op-queue
    (Tier 2). One op per request:

        {op_id, type, tune_id, ...}

    Every op type is *naturally idempotent* against the UNIQUE(person_id, tune_id)
    row, so a client may replay queued ops after reconnecting without a dedup table:
      - add        -> INSERT ... ON CONFLICT DO NOTHING (never clobbers existing state)
      - set_status -> UPDATE learn_status            (absolute set)
      - set_heard  -> UPDATE heard_count = <count>   (absolute set; client sends the
                       target count, NOT a delta, so a replayed +1 can't double-count)
      - set_notes  -> UPDATE notes
      - set_tags   -> UPDATE tags                    (absolute set; normalized server-side)
      - remove     -> DELETE

    Keyed by tune_id (not the server-assigned person_tune_id) so an offline
    add->heard->status sequence composes without a server round-trip.
    """
    try:
        person_id = get_user_person_id()
        data = request.get_json(silent=True) or {}
        op_type = data.get("type")
        tune_id = data.get("tune_id")
        if not op_type or tune_id is None:
            return jsonify({"success": False, "error": "type and tune_id are required"}), 400
        user_id = getattr(current_user, "user_id", None)

        conn = get_db_connection()
        cur = conn.cursor()
        heard_count = None
        try:
            # A merged-away tune_id remaps to the canonical tune (spec 030): a replayed
            # offline op means the merged tune. Uniform across op types — without this,
            # a replayed `add` would resurrect the tombstoned tune on the list.
            remapped_from = None
            cur.execute("SELECT redirect_to_tune_id FROM tune WHERE tune_id = %s", (tune_id,))
            rrow = cur.fetchone()
            if rrow and rrow[0] is not None:
                remapped_from = tune_id
                tune_id = rrow[0]

            if op_type == "add":
                learn_status = data.get("learn_status") or "want to learn"
                if learn_status not in ("want to learn", "learning", "learned"):
                    return jsonify({"success": False, "error": "invalid learn_status"}), 400
                cur.execute(
                    """INSERT INTO person_tune (person_id, tune_id, learn_status, heard_count, created_by_user_id)
                       VALUES (%s, %s, %s, 0, %s)
                       ON CONFLICT (person_id, tune_id) DO NOTHING""",
                    (person_id, tune_id, learn_status, user_id),
                )
            elif op_type == "set_status":
                learn_status = data.get("learn_status")
                if learn_status not in ("want to learn", "learning", "learned"):
                    return jsonify({"success": False, "error": "invalid learn_status"}), 400
                cur.execute(
                    """UPDATE person_tune SET learn_status=%s, last_modified_user_id=%s
                       WHERE person_id=%s AND tune_id=%s""",
                    (learn_status, user_id, person_id, tune_id),
                )
            elif op_type == "set_heard":
                hc = data.get("heard_count")
                if not isinstance(hc, int) or hc < 0:
                    return jsonify({"success": False, "error": "heard_count must be a non-negative integer"}), 400
                cur.execute(
                    """UPDATE person_tune SET heard_count=%s, last_modified_user_id=%s
                       WHERE person_id=%s AND tune_id=%s RETURNING heard_count""",
                    (hc, user_id, person_id, tune_id),
                )
                row = cur.fetchone()
                heard_count = row[0] if row else None
            elif op_type == "set_notes":
                cur.execute(
                    """UPDATE person_tune SET notes=%s, last_modified_user_id=%s
                       WHERE person_id=%s AND tune_id=%s""",
                    (data.get("notes"), user_id, person_id, tune_id),
                )
            elif op_type == "set_tags":
                # Absolute set of the person's tags on this tune (spec 042). Client
                # sends the full list; server re-normalizes so the stored value is
                # canonical regardless of the writer (drawer, replayed op, sync).
                cur.execute(
                    """UPDATE person_tune SET tags=%s, last_modified_user_id=%s
                       WHERE person_id=%s AND tune_id=%s""",
                    (normalize_tags(data.get("tags")), user_id, person_id, tune_id),
                )
            elif op_type == "remove":
                cur.execute(
                    "DELETE FROM person_tune WHERE person_id=%s AND tune_id=%s",
                    (person_id, tune_id),
                )
            elif op_type == "set_instrument_status":
                # Per-instrument status override. Absolute set (idempotent on replay):
                #   status given  -> UPSERT the override, UNLESS it's an auto instrument
                #                    being set back to learn_status (snap back -> delete row)
                #   status null    -> DELETE the override (manual: removes from that instrument)
                instrument = (data.get("instrument") or "").strip()
                status = data.get("status")
                if not instrument:
                    return jsonify({"success": False, "error": "instrument is required"}), 400
                if status is not None and status not in ("want to learn", "learning", "learned"):
                    return jsonify({"success": False, "error": "invalid status"}), 400
                # Resolve against the person's profile (case-insensitive) + get the auto flag.
                cur.execute(
                    "SELECT instrument, is_auto FROM person_instrument WHERE person_id=%s AND LOWER(instrument)=LOWER(%s)",
                    (person_id, instrument),
                )
                inst_row = cur.fetchone()
                if not inst_row:
                    return jsonify({"success": False, "error": "instrument not on your profile"}), 400
                canonical_instrument, is_auto = inst_row[0], inst_row[1]
                # The tune must be on the person's list (the FK also enforces this).
                cur.execute(
                    "SELECT learn_status FROM person_tune WHERE person_id=%s AND tune_id=%s",
                    (person_id, tune_id),
                )
                pt_row = cur.fetchone()
                if not pt_row:
                    return jsonify({"success": False, "error": "tune not on your list"}), 400
                learn_status = pt_row[0]
                if status is None or (is_auto and status == learn_status):
                    cur.execute(
                        "DELETE FROM person_tune_instrument WHERE person_id=%s AND tune_id=%s AND instrument=%s",
                        (person_id, tune_id, canonical_instrument),
                    )
                else:
                    cur.execute(
                        """INSERT INTO person_tune_instrument
                               (person_id, tune_id, instrument, status, created_by_user_id, last_modified_user_id)
                           VALUES (%s, %s, %s, %s, %s, %s)
                           ON CONFLICT (person_id, tune_id, instrument)
                           DO UPDATE SET status = EXCLUDED.status,
                                         last_modified_user_id = EXCLUDED.last_modified_user_id""",
                        (person_id, tune_id, canonical_instrument, status, user_id, user_id),
                    )
            else:
                return jsonify({"success": False, "error": f"unknown op type: {op_type}"}), 400
            conn.commit()
        finally:
            cur.close()
            conn.close()

        resp = {"success": True, "op_id": data.get("op_id"), "type": op_type, "tune_id": tune_id}
        if remapped_from is not None:
            resp["remapped_from"] = remapped_from
        if heard_count is not None:
            resp["heard_count"] = heard_count
        return jsonify(resp), 200

    except Exception as e:
        return jsonify({"success": False, "error": f"Error applying my-tunes op: {str(e)}"}), 500


@person_tune_login_required
def set_instrument_auto():
    """
    PUT /api/my-tunes/instrument-auto

    Set whether one of the current user's instruments is "auto" (linked — follows
    person_tune.learn_status) or manual (a curated per-instrument list). Body:
        {"instrument": "Concertina", "is_auto": false}
    """
    try:
        person_id = get_user_person_id()
        data = request.get_json(silent=True) or {}
        instrument = (data.get("instrument") or "").strip()
        is_auto = data.get("is_auto")
        if not instrument or not isinstance(is_auto, bool):
            return jsonify({"success": False, "error": "instrument and boolean is_auto are required"}), 400
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE person_instrument SET is_auto=%s WHERE person_id=%s AND LOWER(instrument)=LOWER(%s)",
                (is_auto, person_id, instrument),
            )
            if cur.rowcount == 0:
                return jsonify({"success": False, "error": "instrument not on your profile"}), 400
            conn.commit()
        finally:
            cur.close()
            conn.close()
        return jsonify({"success": True, "instrument": instrument, "is_auto": is_auto}), 200
    except Exception as e:
        return jsonify({"success": False, "error": f"Error setting instrument auto flag: {str(e)}"}), 500


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


@public_api  # backs the hamburger "Find a tune" overlay, offered to logged-out users on every page (templates/hamburger_menu.html else-branch → frontend/src/tunesheet/FindTune.svelte)
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
        query = normalize_quotes(request.args.get('q', '').strip())

        if not query:
            return jsonify({
                "success": False,
                "error": "Search query is required"
            }), 400

        # A thesession.org tune URL (or a bare tune id) is a POINTER, not a name — resolve
        # it to that one tune instead of running a hopeless LIKE over names. This is what
        # makes pasting a link work in every plain tune-search box (the hamburger "Find a
        # tune" overlay, the legacy search component); the deep search resolves links
        # client-side because it can also preview not-yet-imported tunes.
        from live_logging_routes import _parse_thesession_id
        ref_tune_id = _parse_thesession_id(query)

        if ref_tune_id is None and len(query) < 2:
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
        # List membership/learn_status is private to the list owner: only honor
        # person_id for self (or a system admin) — anyone else gets catalog-only
        # results instead of a probe into another person's list.
        if person_id is not None:
            own = getattr(current_user, 'person_id', None) if current_user.is_authenticated else None
            is_admin = current_user.is_authenticated and current_user.is_system_admin
            if person_id != own and not is_admin:
                person_id = None
        session_id = request.args.get('session_id', type=int)
        # Soft type preference (the type of the set you're logging into): matching-type
        # tunes sort above other types. None => no effect.
        prefer_type = (request.args.get('prefer_type') or '').strip() or None
        # Search mode, matching the deep search's vocabulary (live_logging_routes.
        # _parse_deep_search_args): 'mixed' blends name + notation, 'name'/'abc' narrow to
        # one. No caller passes it yet -- the overlay relies on the 'mixed' default -- but
        # the two searches answering the same `mode` is what keeps them interchangeable.
        mode = (request.args.get('mode') or '').strip().lower()
        if mode not in ('name', 'abc', 'mixed'):
            mode = 'mixed'

        conn = get_db_connection()
        try:
            cur = conn.cursor()

            # Build query with optional LEFT JOINs based on context
            select_fields = ["t.tune_id", "t.name", "t.tune_type", "t.tunebook_count_cached"]
            joins = []
            order_by_fields = []
            query_params = []   # JOIN params
            select_params = []  # SELECT-clause params (abc_only, match_priority, type_pref)

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

            # Notation (ABC) blend. Same rules as the deep search and the abc-filter
            # endpoint -- abc_search_terms owns the decision, so a note-shaped query
            # behaves the same here as it does in the live logger's deep search. A
            # pasted thesession.org link is a POINTER, not a query, so it never blends.
            use_abc, abc_pattern = (False, None) if ref_tune_id is not None \
                else abc_search_terms(query, mode)
            use_name = ref_tune_id is not None or mode in ("name", "mixed")

            _nm = f"LOWER(unaccent({normalize_quotes_sql('t.name')}))"
            name_like = f"%{query}%"

            # abc_only: this row matched the notation but NOT the name, so the client can
            # badge it as a notation hit rather than a puzzling name result.
            if use_abc and use_name:
                select_fields.append(f"({ABC_MATCH_SQL} AND NOT ({_nm} LIKE LOWER(unaccent(%s)))) AS abc_only")
                select_params.extend([abc_pattern, name_like])
            elif use_abc:
                select_fields.append("TRUE AS abc_only")
            else:
                select_fields.append("FALSE AS abc_only")

            # Build match priority case (accent + smart-quote insensitive). With notation
            # blended in, rows can qualify WITHOUT a name match, so the "contains" tier
            # becomes explicit and notation-only rows fall to the bottom tier.
            if use_abc and use_name:
                select_fields.append(f"""CASE
                               WHEN {_nm} = LOWER(unaccent(%s)) THEN 1
                               WHEN {_nm} LIKE LOWER(unaccent(%s)) THEN 2
                               WHEN {_nm} LIKE LOWER(unaccent(%s)) THEN 3
                               ELSE 4
                           END AS match_priority""")
                select_params.extend([query, f"{query}%", name_like])
            else:
                select_fields.append(f"""CASE
                               WHEN {_nm} = LOWER(unaccent(%s)) THEN 1
                               WHEN {_nm} LIKE LOWER(unaccent(%s)) THEN 2
                               ELSE 3
                           END AS match_priority""")
                select_params.extend([query, f"{query}%"])
            # Soft type preference (matching the set's type sorts first)
            select_fields.append("CASE WHEN t.tune_type = %s THEN 0 ELSE 1 END AS type_pref")
            select_params.append(prefer_type)

            # Build final query
            join_clause = " ".join(joins) if joins else ""
            select_clause = ", ".join(select_fields)

            # Construct ORDER BY: matching type first (soft preference), then existing
            # person/session priority, match priority, tunebook count, name
            order_by_parts = ["type_pref"] + order_by_fields + ["match_priority", "t.tunebook_count_cached DESC NULLS LAST", "t.name"]
            order_by_clause = ", ".join(order_by_parts)

            # An id/URL query matches exactly one tune (its merge target if it was merged
            # away — a pasted permalink for a merged tune should land on the survivor);
            # everything else is the name LIKE, optionally OR'd with the notation match.
            where_params = []
            if ref_tune_id is not None:
                from api_routes import follow_tune_redirect
                ref_tune_id, _redirected_from = follow_tune_redirect(cur, ref_tune_id)
                where_sql = "t.tune_id = %s"
                where_params.append(ref_tune_id)
            else:
                where_clauses = []
                if use_name:
                    where_clauses.append(f"{_nm} LIKE LOWER(unaccent(%s))")
                    where_params.append(name_like)
                if use_abc:
                    where_clauses.append(ABC_MATCH_SQL)
                    where_params.append(abc_pattern)
                if not where_clauses:
                    # mode='abc' on something that normalizes to nothing (e.g. a query
                    # that is only a chord symbol): no notation to match, and name search
                    # was excluded by the mode. Answer honestly rather than emit `WHERE ()`.
                    return jsonify({"success": True, "tunes": [], "count": 0,
                                    "query_tune_id": None}), 200
                where_sql = "(" + " OR ".join(where_clauses) + ")"

            sql = f"""
                SELECT {select_clause}
                FROM tune t
                {join_clause}
                WHERE {where_sql}
                  AND t.redirect_to_tune_id IS NULL
                ORDER BY {order_by_clause}
                LIMIT %s
            """

            # Parameter order follows the SQL text: SELECT clause, then the JOINs, then
            # the WHERE, then LIMIT.
            cur.execute(sql, select_params + query_params + where_params + [limit])

            # Read results by COLUMN NAME, not position: the SELECT list is assembled
            # conditionally, and the old positional mapping ("session_idx = 6 if person_id
            # else 4") silently mis-maps the moment another optional column is added.
            cols = [d[0] for d in cur.description]
            tunes = []
            for row in cur.fetchall():
                r = dict(zip(cols, row))
                tune_data = {
                    'tune_id': r['tune_id'],
                    'name': r['name'],
                    'tune_type': r['tune_type'],
                    'tunebook_count': r['tunebook_count_cached'],
                    'abc_only': bool(r['abc_only']),
                }

                # Add person_tune fields if requested
                if person_id:
                    tune_data['in_person_tune'] = bool(r['in_person_tune'])
                    tune_data['learn_status'] = r['learn_status'] if r['in_person_tune'] else None

                # Add session_tune field if requested
                if session_id:
                    tune_data['in_session_tune'] = bool(r['in_session_tune'])

                tunes.append(tune_data)

            return jsonify({
                "success": True,
                "tunes": tunes,
                "count": len(tunes),
                # Echoed when the query was a tune id / thesession.org URL: the canonical
                # id it resolved to. An empty `tunes` alongside it means "that tune isn't
                # in the local catalog yet" (an import, not a typo) — the clients say so.
                "query_tune_id": ref_tune_id,
            }), 200

        finally:
            conn.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error searching tunes: {str(e)}"
        }), 500


@public_api  # session pages are publicly viewable, so their Tunes tab must filter logged out
def abc_filter_tunes():
    """
    POST /api/tunes/abc-filter  ->  {"q": "...", "tune_ids": [...]}

    Which of THESE tunes match this notation query? Returns {"tune_ids": [...]}.

    Three screens filter a list they have already loaded -- My Tunes, a session's Tunes
    tab, the admin session-tunes tab. Name matching happens in the browser against data
    it already holds; notation matching cannot, because the full ABC is far too large to
    ship with the page (a 300-tune list would gain 150-250KB). So the client sends the
    ids it is showing and gets back the subset whose notation matches, then unions that
    into the same filter pass. One endpoint for all three: the caller already knows its
    own list, so there is no scope to model, and no per-surface auth story.

    Unauthenticated by design. It reveals only which PUBLIC catalog tunes match public
    catalog notation, and only among ids the caller supplied -- nothing it could not
    learn from the tune pages themselves.
    """
    try:
        data = request.get_json(silent=True) or {}
        q = (data.get("q") or "").strip()
        if len(q) > 200:
            return jsonify({"success": False, "error": "Query too long"}), 400

        tune_ids = data.get("tune_ids") or []
        if not isinstance(tune_ids, list):
            return jsonify({"success": False, "error": "tune_ids must be a list"}), 400
        if len(tune_ids) > 2000:
            return jsonify({"success": False, "error": "Too many tune_ids (max 2000)"}), 400
        try:
            tune_ids = [int(t) for t in tune_ids]
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "tune_ids must be integers"}), 400

        # Ordinary name typing costs nothing: if the query is not note-shaped (or is too
        # short to discriminate), say "no notation matches" without touching the database.
        use_abc, pattern = abc_search_terms(q)
        if not use_abc or not tune_ids:
            return jsonify({"success": True, "tune_ids": []}), 200

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT ts.tune_id
                FROM tune_setting ts
                WHERE ts.tune_id = ANY(%s)
                  AND abc_search_key(ts.abc) LIKE %s
                """,
                (tune_ids, pattern),
            )
            return jsonify({"success": True, "tune_ids": [r[0] for r in cur.fetchall()]}), 200
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"success": False, "error": f"Error matching notation: {str(e)}"}), 500


@person_tune_login_required
def get_popular_tunes():
    """
    GET /api/tunes/popular?limit=100

    The most-bookmarked catalog tunes (by tunebook_count_cached). The My Tunes page
    caches this client-side so a user can search for and add popular tunes while
    offline (the offline op-queue handles the add).
    """
    try:
        try:
            limit = min(200, max(1, int(request.args.get("limit", 100))))
        except (ValueError, TypeError):
            limit = 100
        person_id = get_user_person_id()
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT t.tune_id, t.name, t.tune_type, t.tunebook_count_cached,
                       pt.person_tune_id IS NOT NULL AS in_person_tune, pt.learn_status
                FROM tune t
                LEFT OUTER JOIN person_tune pt
                       ON pt.tune_id = t.tune_id AND pt.person_id = %s
                WHERE t.redirect_to_tune_id IS NULL
                ORDER BY t.tunebook_count_cached DESC NULLS LAST, t.name ASC
                LIMIT %s
                """,
                (person_id, limit),
            )
            tunes = [
                {
                    "tune_id": r[0],
                    "name": r[1],
                    "tune_type": r[2],
                    "tunebook_count": r[3] or 0,
                    "in_person_tune": bool(r[4]),
                    "learn_status": r[5] if r[4] else None,
                }
                for r in cur.fetchall()
            ]
            return jsonify({"success": True, "tunes": tunes, "count": len(tunes)}), 200
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"success": False, "error": f"Error fetching popular tunes: {str(e)}"}), 500


@person_tune_login_required
def get_offline_bundle():
    """
    GET /api/offline/bundle

    Everything the client needs to make the user's OWN data work offline, in one
    predictable payload it mirrors into IndexedDB:
      - tunes:   the whole tunebook with INCIPIT notation (small "dots" preview + abc)
                 so the list, drawer, and offline search all work without per-tune fetches.
      - popular: top catalog tunes so offline add-search can find tunes not yet owned.

    PARITY RULE: each tunes entry must carry every field the offline drawer path
    (offlinePayload in frontend/src/tunesheet/logic.js) maps into the detail-payload
    shape — the drift guards in tests/integration/test_tune_detail_payload.py and
    frontend/tests/tunesheet.test.js fail when a rendered detail field is missing here.
    Full-size notation stays online-only to keep this bounded.
    """
    try:
        person_id = get_user_person_id()
        conn = get_db_connection()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """
                SELECT pt.person_tune_id, pt.tune_id, t.name, t.tune_type,
                       pt.learn_status, pt.heard_count, pt.notes, pt.name_alias,
                       pt.setting_id, pt.key, pt.tags, pt.learned_date,
                       t.tunebook_count_cached, t.tunebook_count_cached_date,
                       ts.incipit_abc, ts.incipit_image, ts.key AS setting_key,
                       gp.n AS global_play_count, plc.n AS person_list_count
                FROM person_tune pt
                JOIN tune t ON t.tune_id = pt.tune_id
                LEFT JOIN LATERAL (
                    SELECT incipit_abc, incipit_image, key
                    FROM tune_setting ts2
                    WHERE ts2.tune_id = pt.tune_id
                      AND (pt.setting_id IS NULL OR ts2.setting_id = pt.setting_id)
                    ORDER BY (ts2.setting_id = pt.setting_id) DESC, ts2.setting_id ASC
                    LIMIT 1
                ) ts ON TRUE
                LEFT JOIN LATERAL (
                    SELECT COUNT(*) AS n FROM session_instance_tune sit
                    WHERE sit.tune_id = pt.tune_id AND sit.deleted = FALSE
                ) gp ON TRUE
                LEFT JOIN LATERAL (
                    SELECT COUNT(*) AS n FROM person_tune p2 WHERE p2.tune_id = pt.tune_id
                ) plc ON TRUE
                WHERE pt.person_id = %s
                ORDER BY t.name ASC
                """,
                (person_id,),
            )
            # The person's instrument list is per-person, not per-tune; embed it in
            # each entry so the drawer's offline path reads one self-contained record.
            instruments = load_person_instruments(conn, person_id)
            tunes = [
                {
                    "person_tune_id": r["person_tune_id"],
                    "tune_id": r["tune_id"],
                    "tune_name": r["name"],
                    "name": r["name"],
                    "tune_type": r["tune_type"],
                    "learn_status": r["learn_status"],
                    "heard_count": r["heard_count"] or 0,
                    "notes": r["notes"],
                    "name_alias": r["name_alias"],
                    "setting_id": r["setting_id"],
                    # "I play this in ..." (spec 037). pt.key, not ts.key — the latter is
                    # the setting's own key and is aliased to setting_key below.
                    "key": r["key"],
                    # Freeform per-person tags (spec 042); PARITY RULE with the drawer.
                    "tags": r["tags"] or [],
                    "learned_date": r["learned_date"].isoformat() if r["learned_date"] else None,
                    "tunebook_count": r["tunebook_count_cached"] or 0,
                    "tunebook_count_cached_date": (
                        r["tunebook_count_cached_date"].isoformat()
                        if r["tunebook_count_cached_date"]
                        else None
                    ),
                    "setting_key": r["setting_key"],
                    "incipit_abc": r["incipit_abc"],
                    "incipit_image": bytea_to_base64(r["incipit_image"]) if r["incipit_image"] is not None else None,
                    "global_play_count": r["global_play_count"],
                    "person_list_count": r["person_list_count"],
                    "instruments": instruments,
                }
                for r in cur.fetchall()
            ]
            _attach_instrument_overrides(cur, person_id, tunes)
            _attach_person_play_counts(cur, person_id, tunes)

            # Popular tunes carry incipit notation too, so a popular tune added offline
            # still shows its dots/ABC in the drawer — plus the same stats fields, so
            # the drawer's not-on-list (Add) view renders the stats it shows online.
            cur.execute(
                """
                SELECT t.tune_id, t.name, t.tune_type,
                       t.tunebook_count_cached, t.tunebook_count_cached_date,
                       ts.incipit_abc, ts.incipit_image, ts.key AS setting_key,
                       gp.n AS global_play_count, plc.n AS person_list_count
                FROM tune t
                LEFT JOIN LATERAL (
                    SELECT incipit_abc, incipit_image, key
                    FROM tune_setting ts2
                    WHERE ts2.tune_id = t.tune_id
                    ORDER BY ts2.setting_id ASC
                    LIMIT 1
                ) ts ON TRUE
                LEFT JOIN LATERAL (
                    SELECT COUNT(*) AS n FROM session_instance_tune sit
                    WHERE sit.tune_id = t.tune_id AND sit.deleted = FALSE
                ) gp ON TRUE
                LEFT JOIN LATERAL (
                    SELECT COUNT(*) AS n FROM person_tune p2 WHERE p2.tune_id = t.tune_id
                ) plc ON TRUE
                WHERE t.redirect_to_tune_id IS NULL
                ORDER BY t.tunebook_count_cached DESC NULLS LAST, t.name ASC
                LIMIT 100
                """
            )
            popular = [
                {
                    "tune_id": r["tune_id"],
                    "name": r["name"],
                    "tune_type": r["tune_type"],
                    "tunebook_count": r["tunebook_count_cached"] or 0,
                    "tunebook_count_cached_date": (
                        r["tunebook_count_cached_date"].isoformat()
                        if r["tunebook_count_cached_date"]
                        else None
                    ),
                    "setting_key": r["setting_key"],
                    "incipit_abc": r["incipit_abc"],
                    "incipit_image": bytea_to_base64(r["incipit_image"]) if r["incipit_image"] is not None else None,
                    "global_play_count": r["global_play_count"],
                    "person_list_count": r["person_list_count"],
                }
                for r in cur.fetchall()
            ]

            return jsonify({"success": True, "tunes": tunes, "popular": popular}), 200
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"success": False, "error": f"Error building offline bundle: {str(e)}"}), 500


@person_tune_login_required
def get_my_sessions():
    """
    GET /api/my-sessions?limit=25

    The current user's sessions (path + name + relationship), most-recently-active
    first. Used to background-prefetch session pages so they're available offline
    without having to visit each one, and by the tune drawer's "At a different
    session ..." picker (spec 037).
    """
    try:
        try:
            limit = min(100, max(1, int(request.args.get("limit", 25))))
        except (ValueError, TypeError):
            limit = 25
        person_id = get_user_person_id()
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            # Deliberately NOT filtered to relationship='member' (spec 033): a
            # visitor legitimately revisits the session pages of sessions they've
            # been to, and prefetching them for offline is a feature, not a leak.
            # `relationship` is returned so a caller that DOES want only real
            # memberships (the 037 session picker) can filter without a second
            # endpoint.
            cur.execute(
                """
                SELECT s.path, s.name, sp.relationship, MAX(si.date) AS last_date
                FROM session_person sp
                JOIN session s ON sp.session_id = s.session_id
                LEFT JOIN session_instance si ON si.session_id = s.session_id
                WHERE sp.person_id = %s
                GROUP BY s.path, s.name, sp.relationship
                ORDER BY MAX(si.date) DESC NULLS LAST, s.name
                LIMIT %s
                """,
                (person_id, limit),
            )
            sessions = [{"path": r[0], "name": r[1], "relationship": r[2]} for r in cur.fetchall()]
            return jsonify({"success": True, "sessions": sessions, "count": len(sessions)}), 200
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"success": False, "error": f"Error fetching sessions: {str(e)}"}), 500


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
