"""The Places admin API (spec 055 "Who may change a place"). Site admins only: a
place is a shared fact, and renaming "Austin" relabels every Austin session.

The rules live in places.py; these handlers parse, gate, commit and answer with
the page's payload (serializers.build_admin_places_payload) so the page redraws
from one shape.
"""

from flask import jsonify, request
from flask_login import current_user

import places
from api_auth import api_login_required
from database import get_db_connection


def _admin_only():
    if not getattr(current_user, "is_system_admin", False):
        return (
            jsonify({"success": False, "error": "Only a site admin can change places"}),
            403,
        )
    return None


def _parent_id(data):
    raw = data.get("parent_place_id")
    if raw in (None, ""):
        return None, None
    try:
        return int(raw), None
    except (TypeError, ValueError):
        return None, "That parent doesn't exist"


def _answer(conn, status=200, **extra):
    from serializers import build_admin_places_payload

    return jsonify({**build_admin_places_payload(conn), **extra}), status


def _refuse(conn, message, status=400):
    conn.rollback()
    return jsonify({"success": False, "error": message}), status


@api_login_required
def get_admin_places():
    """GET /api/admin/places — the page's payload."""
    refused = _admin_only()
    if refused:
        return refused
    conn = get_db_connection()
    try:
        return _answer(conn)
    finally:
        conn.close()


@api_login_required
def create_admin_place():
    """POST /api/admin/places {name, slug?, area, country, parent_place_id?} — a town
    or metro, typically a metro with no sessions of its own (Dallas, Waco)."""
    refused = _admin_only()
    if refused:
        return refused
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "error": "A name is required"}), 400
    slug = str(data.get("slug") or "").strip() or places.slugify(name)
    parent_id, error = _parent_id(data)
    if error:
        return jsonify({"success": False, "error": error}), 400
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        error = places.check_new_slug(cur, slug) or places.check_parent(
            cur, None, parent_id
        )
        if error:
            return _refuse(conn, error)
        country = places.normalize_country(data.get("country"))
        created = places.create_place(
            cur,
            slug,
            name,
            "place",
            parent_id,
            places.normalize_area(data.get("area"), country),
            country,
            current_user.user_id,
        )
        conn.commit()
        return _answer(conn, 201, place_id=created["place_id"])
    finally:
        conn.close()


@api_login_required
def update_admin_place(place_id):
    """PUT /api/admin/places/<id> {name, area, country, parent_place_id, slug?}. A
    changed slug is a rename: every path under it moves, with redirects."""
    refused = _admin_only()
    if refused:
        return refused
    data = request.get_json(silent=True) or {}
    parent_id, error = _parent_id(data)
    if error:
        return jsonify({"success": False, "error": error}), 400
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        place = places.get_place(cur, place_id)
        if place is None:
            return _refuse(conn, "Place not found", 404)
        error = places.update_place(
            cur,
            place,
            data.get("name", place["name"]),
            data.get("area"),
            data.get("country"),
            parent_id,
            current_user.user_id,
        )
        if error:
            return _refuse(conn, error)
        moved = []
        new_slug = str(data.get("slug") or "").strip()
        if new_slug and new_slug != place["slug"]:
            error, moved = places.rename_slug(
                cur, place, new_slug, current_user.user_id
            )
            if error:
                return _refuse(conn, error)
        conn.commit()
        return _answer(conn, moved=[{"from": a, "to": b} for a, b in moved])
    finally:
        conn.close()


@api_login_required
def delete_admin_place(place_id):
    """DELETE /api/admin/places/<id> — only a place with no sessions and no children."""
    refused = _admin_only()
    if refused:
        return refused
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        place = places.get_place(cur, place_id)
        if place is None:
            return _refuse(conn, "Place not found", 404)
        error = places.delete_place(cur, place)
        if error:
            return _refuse(conn, error)
        conn.commit()
        return _answer(conn)
    finally:
        conn.close()
