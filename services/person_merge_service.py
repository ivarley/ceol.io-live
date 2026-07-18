"""
Person merge service — combine two person rows that are the same human.

Hard merge, admin-only: every table referencing the loser's person_id is
repointed at the winner, colliding rows are FIELD-MERGED (never silently
dropped), the loser's profile fields fill the winner's NULL gaps, and the
loser row is then deleted. There is no redirect/tombstone (contrast
tune.redirect_to_tune_id): person ids don't circulate publicly, so history
tables — which keep the old person_id forever, per the app-wide audit
philosophy — are the merge's paper trail.

Two entry points sharing one analysis pass, so the preview can never drift
from what execute actually does:

    build_merge_preview(conn, loser_id, winner_id)
    execute_merge(conn, loser_id, winner_id, user_id, surviving_user_id=None)

The caller owns the transaction: execute_merge mutates through conn's cursor
and does NOT commit.

Field-merge rules (the "furthest along / most alive wins" doctrine):
  - learn_status / per-instrument status: learned > learning > want to learn
  - heard_count: SUM (hearings were split across two rows for one human)
  - learned_date: earliest non-null
  - notes / comment: concatenated when both differ
  - grant booleans (confirmed, is_admin, email prefs): OR
  - archived: AND — archived means "not around"; if either row says they're
    around, they're around
  - person_instrument.is_auto: AND — is_auto=False is a deliberately curated
    per-instrument list; curation survives the merge
  - relationship: member beats visitor
  - attendance: yes > maybe > no > unset; arrival_seq: MIN (earlier arrival)
  - scalar leftovers (name_alias, key, setting_id, logger color): winner's row
    stands as-is

Accounts: user_account.person_id is NOT NULL + UNIQUE, so at most one account
survives. With one account (either side) it is repointed to the winner. With
two, the admin must name surviving_user_id; the losing account's user-keyed
rows (corroboration, email_message, email_message_recipient, tune_merge_scan)
are repointed to the surviving user first — corroboration/recipient rows that
would collide on their uniques are dropped — then the losing account is
deleted (user_session cascades, login_history keeps rows with user NULLed).
"""

from typing import Any, Dict, List, Optional

import psycopg2.extras

from database import save_to_history


class MergeValidationError(Exception):
    """A merge request that cannot proceed; .status is the HTTP status."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


_LEARN_RANK = {"want to learn": 1, "learning": 2, "learned": 3}
_ATTEND_RANK = {None: 0, "no": 1, "maybe": 2, "yes": 3}

# Winner-NULL gaps these profile fields fill from the loser. Name and `active`
# are deliberately absent: the winner's identity always stands.
_PROFILE_FILL_FIELDS = (
    "email",
    "sms_number",
    "city",
    "state",
    "country",
    "thesession_user_id",
    "at_active_session_instance_id",
)


# ---------------------------------------------------------------------------
# field-merge rules — pure functions over row dicts, used by BOTH preview
# (to show the outcome) and execute (to compute the UPDATE)
# ---------------------------------------------------------------------------


def _further_status(a: Optional[str], b: Optional[str]) -> Optional[str]:
    ranked = [s for s in (a, b) if s in _LEARN_RANK]
    return max(ranked, key=lambda s: _LEARN_RANK[s]) if ranked else (a or b)


def _concat_text(a: Optional[str], b: Optional[str]) -> Optional[str]:
    a = (a or "").strip()
    b = (b or "").strip()
    if a and b and a != b:
        return f"{a}\n\n{b}"
    return a or b or None


def _earliest(a, b):
    stamps = [t for t in (a, b) if t is not None]
    return min(stamps) if stamps else None


def merge_person_tune_fields(winner: Dict, loser: Dict) -> Dict[str, Any]:
    return {
        "learn_status": _further_status(winner["learn_status"], loser["learn_status"]),
        "heard_count": (winner["heard_count"] or 0) + (loser["heard_count"] or 0),
        "learned_date": _earliest(winner["learned_date"], loser["learned_date"]),
        "notes": _concat_text(winner["notes"], loser["notes"]),
        # scalar leftovers: the winner's row stands, NULLs included
        "setting_id": winner["setting_id"],
        "name_alias": winner["name_alias"],
        "key": winner["key"],
    }


def merge_person_instrument_fields(winner: Dict, loser: Dict) -> Dict[str, Any]:
    return {"is_auto": winner["is_auto"] and loser["is_auto"]}


def merge_person_tune_instrument_fields(winner: Dict, loser: Dict) -> Dict[str, Any]:
    return {"status": _further_status(winner["status"], loser["status"])}


def merge_session_person_fields(winner: Dict, loser: Dict) -> Dict[str, Any]:
    member = "member" in (winner["relationship"], loser["relationship"])
    return {
        "relationship": "member" if member else "visitor",
        "confirmed": winner["confirmed"] or loser["confirmed"],
        "archived": winner["archived"] and loser["archived"],
        "is_admin": bool(winner["is_admin"] or loser["is_admin"]),
        "gets_email_reminder": bool(winner["gets_email_reminder"] or loser["gets_email_reminder"]),
        "gets_email_followup": bool(winner["gets_email_followup"] or loser["gets_email_followup"]),
    }


def merge_session_instance_person_fields(winner: Dict, loser: Dict) -> Dict[str, Any]:
    attendance = max(
        (winner["attendance"], loser["attendance"]), key=lambda a: _ATTEND_RANK.get(a, 0)
    )
    seqs = [s for s in (winner["arrival_seq"], loser["arrival_seq"]) if s is not None]
    return {
        "attendance": attendance,
        "comment": _concat_text(winner["comment"], loser["comment"]),
        "arrival_seq": min(seqs) if seqs else None,
    }


# ---------------------------------------------------------------------------
# analysis — one pass computing every move and collision, shared by
# preview and execute
# ---------------------------------------------------------------------------


def _fetch_person(cur, person_id: int) -> Optional[Dict]:
    cur.execute(
        """
        SELECT person_id, first_name, last_name, email, sms_number, city, state,
               country, thesession_user_id, active, at_active_session_instance_id
        FROM person WHERE person_id = %s
        """,
        (person_id,),
    )
    return cur.fetchone()


def _fetch_account(cur, person_id: int) -> Optional[Dict]:
    cur.execute(
        """
        SELECT user_id, person_id, username, user_email, email_verified, is_active
        FROM user_account WHERE person_id = %s
        """,
        (person_id,),
    )
    return cur.fetchone()


def _split_rows(loser_rows: List[Dict], winner_rows: List[Dict], key):
    """Partition the loser's rows into clean moves vs collisions with the
    winner's rows (matched on `key`)."""
    winner_by_key = {key(r): r for r in winner_rows}
    moves, collisions = [], []
    for row in loser_rows:
        w = winner_by_key.get(key(row))
        if w is None:
            moves.append(row)
        else:
            collisions.append({"winner": w, "loser": row})
    return moves, collisions


def _analyze(cur, loser_id: int, winner_id: int) -> Dict[str, Any]:
    a: Dict[str, Any] = {}

    def rows(sql, pid):
        cur.execute(sql, (pid,))
        return cur.fetchall()

    # person_instrument
    sql = "SELECT person_id, instrument, is_auto FROM person_instrument WHERE person_id = %s"
    a["person_instrument"] = _split_rows(
        rows(sql, loser_id), rows(sql, winner_id), key=lambda r: r["instrument"]
    )

    # person_tune (+ tune names for the preview)
    sql = """
        SELECT pt.person_id, pt.tune_id, pt.learn_status, pt.heard_count,
               pt.learned_date, pt.notes, pt.setting_id, pt.name_alias, pt.key,
               t.name AS tune_name
        FROM person_tune pt JOIN tune t ON t.tune_id = pt.tune_id
        WHERE pt.person_id = %s
    """
    a["person_tune"] = _split_rows(
        rows(sql, loser_id), rows(sql, winner_id), key=lambda r: r["tune_id"]
    )

    # person_tune_instrument, split by parent fate: clean-move parents carry
    # their children along (FK ON UPDATE CASCADE); colliding parents need the
    # children reconciled row-by-row before the parent rows merge.
    colliding_tunes = {c["loser"]["tune_id"] for c in a["person_tune"][1]}
    sql = """
        SELECT person_id, tune_id, instrument, status
        FROM person_tune_instrument WHERE person_id = %s
    """
    loser_pti = rows(sql, loser_id)
    winner_pti = rows(sql, winner_id)
    carried = [r for r in loser_pti if r["tune_id"] not in colliding_tunes]
    contested = [r for r in loser_pti if r["tune_id"] in colliding_tunes]
    pti_moves, pti_collisions = _split_rows(
        contested, winner_pti, key=lambda r: (r["tune_id"], r["instrument"])
    )
    a["person_tune_instrument"] = {
        "carried": carried,  # ride along with their parent's UPDATE
        "moves": pti_moves,
        "collisions": pti_collisions,
    }

    # session_person (+ session names)
    sql = """
        SELECT sp.person_id, sp.session_id, sp.relationship, sp.confirmed, sp.archived,
               sp.is_admin, sp.gets_email_reminder, sp.gets_email_followup,
               s.name AS session_name
        FROM session_person sp JOIN session s ON s.session_id = sp.session_id
        WHERE sp.person_id = %s
    """
    a["session_person"] = _split_rows(
        rows(sql, loser_id), rows(sql, winner_id), key=lambda r: r["session_id"]
    )

    # session_instance_person (+ session name/date)
    sql = """
        SELECT sip.person_id, sip.session_instance_id, sip.attendance, sip.comment,
               sip.arrival_seq, si.date, s.name AS session_name
        FROM session_instance_person sip
        JOIN session_instance si ON si.session_instance_id = sip.session_instance_id
        JOIN session s ON s.session_id = si.session_id
        WHERE sip.person_id = %s
    """
    a["session_instance_person"] = _split_rows(
        rows(sql, loser_id), rows(sql, winner_id), key=lambda r: r["session_instance_id"]
    )

    # session_logger_color — collision keeps the winner's color (pure cosmetics)
    sql = "SELECT person_id, session_id, color FROM session_logger_color WHERE person_id = %s"
    a["session_logger_color"] = _split_rows(
        rows(sql, loser_id), rows(sql, winner_id), key=lambda r: r["session_id"]
    )

    # simple repoints (no uniqueness to collide with)
    cur.execute(
        "SELECT session_instance_tune_id FROM session_instance_tune WHERE started_by_person_id = %s",
        (loser_id,),
    )
    a["started_by_ids"] = [r["session_instance_tune_id"] for r in cur.fetchall()]

    cur.execute("SELECT recording_id FROM recording WHERE person_id = %s", (loser_id,))
    a["recording_ids"] = [r["recording_id"] for r in cur.fetchall()]

    cur.execute(
        "SELECT user_id FROM user_account WHERE referred_by_person_id = %s", (loser_id,)
    )
    a["referred_by_user_ids"] = [r["user_id"] for r in cur.fetchall()]

    return a


def _checked_in_label(cur, person: Dict) -> Optional[str]:
    """'currently checked in at <session> on <date>' warning text, or None."""
    instance_id = person.get("at_active_session_instance_id")
    if not instance_id:
        return None
    cur.execute(
        """
        SELECT s.name, si.date
        FROM session_instance si JOIN session s ON s.session_id = si.session_id
        WHERE si.session_instance_id = %s
        """,
        (instance_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return (
        f"{person['first_name']} {person['last_name']} is currently checked in at "
        f"{row['name']} ({row['date'].isoformat()})"
    )


def _validate(cur, loser_id: int, winner_id: int):
    if loser_id == winner_id:
        raise MergeValidationError("Cannot merge a person into themselves")
    loser = _fetch_person(cur, loser_id)
    if not loser:
        raise MergeValidationError(f"Person {loser_id} not found", 404)
    winner = _fetch_person(cur, winner_id)
    if not winner:
        raise MergeValidationError(f"Person {winner_id} not found", 404)
    return loser, winner


def _person_summary(person: Dict, account: Optional[Dict]) -> Dict[str, Any]:
    return {
        "person_id": person["person_id"],
        "name": f"{person['first_name']} {person['last_name']}",
        "email": person["email"],
        "active": person["active"],
        "account": (
            {
                "user_id": account["user_id"],
                "username": account["username"],
                "user_email": account["user_email"],
            }
            if account
            else None
        ),
    }


def _profile_changes(winner: Dict, loser: Dict) -> Dict[str, Dict[str, Any]]:
    """fills: loser values that patch winner NULLs; discards: loser values
    lost because the winner already has one."""
    fills, discards = {}, {}
    for field in _PROFILE_FILL_FIELDS:
        if loser[field] is None:
            continue
        if winner[field] is None:
            fills[field] = loser[field]
        elif winner[field] != loser[field]:
            discards[field] = loser[field]
    return {"fills": fills, "discards": discards}


# ---------------------------------------------------------------------------
# preview
# ---------------------------------------------------------------------------


def build_merge_preview(conn, loser_id: int, winner_id: int) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    loser, winner = _validate(cur, loser_id, winner_id)
    loser_acct = _fetch_account(cur, loser_id)
    winner_acct = _fetch_account(cur, winner_id)
    a = _analyze(cur, loser_id, winner_id)

    pti = a["person_tune_instrument"]
    pti_by_tune: Dict[int, List[Dict]] = {}
    for c in pti["collisions"]:
        entry = {
            "instrument": c["loser"]["instrument"],
            "winner_status": c["winner"]["status"],
            "loser_status": c["loser"]["status"],
            "result": merge_person_tune_instrument_fields(c["winner"], c["loser"]),
        }
        pti_by_tune.setdefault(c["loser"]["tune_id"], []).append(entry)
    for m in pti["moves"]:
        pti_by_tune.setdefault(m["tune_id"], []).append(
            {
                "instrument": m["instrument"],
                "winner_status": None,
                "loser_status": m["status"],
                "result": {"status": m["status"]},
            }
        )

    def strip(row: Dict, *drop: str) -> Dict:
        omit = set(drop) | {"person_id"}
        return {k: v for k, v in row.items() if k not in omit}

    collisions: Dict[str, List[Dict]] = {
        "person_tune": [
            {
                "tune_id": c["loser"]["tune_id"],
                "tune_name": c["loser"]["tune_name"],
                "winner": strip(c["winner"], "tune_id", "tune_name"),
                "loser": strip(c["loser"], "tune_id", "tune_name"),
                "result": merge_person_tune_fields(c["winner"], c["loser"]),
                "instrument_overrides": pti_by_tune.get(c["loser"]["tune_id"], []),
            }
            for c in a["person_tune"][1]
        ],
        "person_instrument": [
            {
                "instrument": c["loser"]["instrument"],
                "winner": strip(c["winner"], "instrument"),
                "loser": strip(c["loser"], "instrument"),
                "result": merge_person_instrument_fields(c["winner"], c["loser"]),
            }
            for c in a["person_instrument"][1]
        ],
        "session_person": [
            {
                "session_id": c["loser"]["session_id"],
                "session_name": c["loser"]["session_name"],
                "winner": strip(c["winner"], "session_id", "session_name"),
                "loser": strip(c["loser"], "session_id", "session_name"),
                "result": merge_session_person_fields(c["winner"], c["loser"]),
            }
            for c in a["session_person"][1]
        ],
        "session_instance_person": [
            {
                "session_instance_id": c["loser"]["session_instance_id"],
                "session_name": c["loser"]["session_name"],
                "date": c["loser"]["date"].isoformat(),
                "winner": strip(c["winner"], "session_instance_id", "session_name", "date"),
                "loser": strip(c["loser"], "session_instance_id", "session_name", "date"),
                "result": merge_session_instance_person_fields(c["winner"], c["loser"]),
            }
            for c in a["session_instance_person"][1]
        ],
        "session_logger_color": [
            {
                "session_id": c["loser"]["session_id"],
                "winner_color": c["winner"]["color"],
                "loser_color": c["loser"]["color"],
            }
            for c in a["session_logger_color"][1]
        ],
    }

    moves = {
        "person_tune": len(a["person_tune"][0]),
        "person_instrument": len(a["person_instrument"][0]),
        "person_tune_instrument": len(pti["carried"]) + len(pti["moves"]),
        "session_person": len(a["session_person"][0]),
        "session_instance_person": len(a["session_instance_person"][0]),
        "session_logger_color": len(a["session_logger_color"][0]),
        "set_starter_attributions": len(a["started_by_ids"]),
        "recordings": len(a["recording_ids"]),
        "referred_by_pointers": len(a["referred_by_user_ids"]),
    }

    both_accounts = bool(loser_acct and winner_acct)
    warnings: List[str] = []
    for p in (winner, loser):
        checked_in = _checked_in_label(cur, p)
        if checked_in:
            warnings.append(checked_in)
    if winner["active"] != loser["active"]:
        keep = "active" if winner["active"] else "inactive"
        warnings.append(
            f"The two people have different active flags; the survivor stays {keep}."
        )
    if both_accounts:
        warnings.append(
            "Both people have login accounts — you must choose which account survives; "
            "the other will be deleted."
        )
    elif loser_acct:
        warnings.append(
            f"The account '{loser_acct['username']}' will be re-linked to the surviving person."
        )
    changes = _profile_changes(winner, loser)
    for field, value in changes["discards"].items():
        warnings.append(f"Discarding {field} “{value}” (survivor already has one).")

    return {
        "success": True,
        "preview": True,
        "loser": _person_summary(loser, loser_acct),
        "winner": _person_summary(winner, winner_acct),
        "accounts": {
            "situation": "both" if both_accounts else ("one" if (loser_acct or winner_acct) else "none"),
            "needs_choice": both_accounts,
        },
        "moves": moves,
        "collisions": collisions,
        "profile": changes,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# execute
# ---------------------------------------------------------------------------


def _merge_accounts(cur, loser_id, winner_id, loser_acct, winner_acct, surviving_user_id, user_id):
    """Resolve user_account.person_id (NOT NULL + UNIQUE). Returns the losing
    user_id when an account was deleted, else None."""
    if not loser_acct and not winner_acct:
        return None

    if loser_acct and not winner_acct:
        save_to_history(cur, "user_account", "UPDATE", loser_acct["user_id"], user_id)
        cur.execute(
            "UPDATE user_account SET person_id = %s WHERE user_id = %s",
            (winner_id, loser_acct["user_id"]),
        )
        return None

    if winner_acct and not loser_acct:
        return None  # already attached to the survivor

    # Both have accounts: the admin named the survivor.
    ids = {loser_acct["user_id"], winner_acct["user_id"]}
    if surviving_user_id not in ids:
        raise MergeValidationError(
            "Both people have accounts; surviving_user_id must be one of "
            f"{sorted(ids)}"
        )
    losing_user_id = (ids - {surviving_user_id}).pop()

    # Repoint the losing user's user-keyed data at the surviving user before
    # the account goes away. corroboration has UNIQUE(record_id, user_id) and
    # email_message_recipient has PK(email_message_id, user_id): where both
    # users already have a row, the losing user's duplicate is dropped.
    cur.execute(
        """
        DELETE FROM corroboration c
        WHERE c.user_id = %(losing)s
          AND EXISTS (SELECT 1 FROM corroboration c2
                      WHERE c2.record_id = c.record_id AND c2.user_id = %(surviving)s)
        """,
        {"losing": losing_user_id, "surviving": surviving_user_id},
    )
    cur.execute(
        "UPDATE corroboration SET user_id = %s WHERE user_id = %s",
        (surviving_user_id, losing_user_id),
    )
    cur.execute(
        """
        DELETE FROM email_message_recipient r
        WHERE r.user_id = %(losing)s
          AND EXISTS (SELECT 1 FROM email_message_recipient r2
                      WHERE r2.email_message_id = r.email_message_id
                        AND r2.user_id = %(surviving)s)
        """,
        {"losing": losing_user_id, "surviving": surviving_user_id},
    )
    cur.execute(
        "UPDATE email_message_recipient SET user_id = %s WHERE user_id = %s",
        (surviving_user_id, losing_user_id),
    )
    cur.execute(
        "UPDATE email_message SET sent_by_user_id = %s WHERE sent_by_user_id = %s",
        (surviving_user_id, losing_user_id),
    )
    cur.execute(
        "UPDATE tune_merge_scan SET started_by_user_id = %s WHERE started_by_user_id = %s",
        (surviving_user_id, losing_user_id),
    )

    # Delete the losing account FIRST (frees the UNIQUE(person_id) slot),
    # then repoint the survivor if it belonged to the losing person.
    save_to_history(cur, "user_account", "DELETE", losing_user_id, user_id)
    cur.execute("DELETE FROM user_account WHERE user_id = %s", (losing_user_id,))

    cur.execute("SELECT person_id FROM user_account WHERE user_id = %s", (surviving_user_id,))
    if cur.fetchone()["person_id"] != winner_id:
        save_to_history(cur, "user_account", "UPDATE", surviving_user_id, user_id)
        cur.execute(
            "UPDATE user_account SET person_id = %s WHERE user_id = %s",
            (winner_id, surviving_user_id),
        )
    return losing_user_id


def execute_merge(
    conn,
    loser_id: int,
    winner_id: int,
    user_id: Optional[int],
    surviving_user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Perform the merge inside the caller's transaction (no commit here)."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    loser, winner = _validate(cur, loser_id, winner_id)
    loser_acct = _fetch_account(cur, loser_id)
    winner_acct = _fetch_account(cur, winner_id)
    if loser_acct and winner_acct and surviving_user_id is None:
        raise MergeValidationError(
            "Both people have accounts; surviving_user_id is required"
        )
    a = _analyze(cur, loser_id, winner_id)

    # --- person_instrument ---------------------------------------------------
    for row in a["person_instrument"][0]:
        save_to_history(cur, "person_instrument", "UPDATE", (loser_id, row["instrument"]), user_id)
        cur.execute(
            "UPDATE person_instrument SET person_id = %s, last_modified_user_id = %s "
            "WHERE person_id = %s AND instrument = %s",
            (winner_id, user_id, loser_id, row["instrument"]),
        )
    for c in a["person_instrument"][1]:
        merged = merge_person_instrument_fields(c["winner"], c["loser"])
        if merged["is_auto"] != c["winner"]["is_auto"]:
            save_to_history(cur, "person_instrument", "UPDATE", (winner_id, c["winner"]["instrument"]), user_id)
            cur.execute(
                "UPDATE person_instrument SET is_auto = %s, last_modified_user_id = %s "
                "WHERE person_id = %s AND instrument = %s",
                (merged["is_auto"], user_id, winner_id, c["winner"]["instrument"]),
            )
        save_to_history(cur, "person_instrument", "DELETE", (loser_id, c["loser"]["instrument"]), user_id)
        cur.execute(
            "DELETE FROM person_instrument WHERE person_id = %s AND instrument = %s",
            (loser_id, c["loser"]["instrument"]),
        )

    # --- person_tune_instrument under COLLIDING parents -----------------------
    # (children of clean-move parents ride the parent UPDATE via FK cascade)
    pti = a["person_tune_instrument"]
    for row in pti["moves"]:
        save_to_history(
            cur, "person_tune_instrument", "UPDATE",
            (loser_id, row["tune_id"], row["instrument"]), user_id,
        )
        cur.execute(
            "UPDATE person_tune_instrument SET person_id = %s, "
            "last_modified_date = (NOW() AT TIME ZONE 'UTC'), last_modified_user_id = %s "
            "WHERE person_id = %s AND tune_id = %s AND instrument = %s",
            (winner_id, user_id, loser_id, row["tune_id"], row["instrument"]),
        )
    for c in pti["collisions"]:
        merged = merge_person_tune_instrument_fields(c["winner"], c["loser"])
        if merged["status"] != c["winner"]["status"]:
            save_to_history(
                cur, "person_tune_instrument", "UPDATE",
                (winner_id, c["winner"]["tune_id"], c["winner"]["instrument"]), user_id,
            )
            cur.execute(
                "UPDATE person_tune_instrument SET status = %s, "
                "last_modified_date = (NOW() AT TIME ZONE 'UTC'), last_modified_user_id = %s "
                "WHERE person_id = %s AND tune_id = %s AND instrument = %s",
                (merged["status"], user_id, winner_id, c["winner"]["tune_id"], c["winner"]["instrument"]),
            )
        save_to_history(
            cur, "person_tune_instrument", "DELETE",
            (loser_id, c["loser"]["tune_id"], c["loser"]["instrument"]), user_id,
        )
        cur.execute(
            "DELETE FROM person_tune_instrument WHERE person_id = %s AND tune_id = %s AND instrument = %s",
            (loser_id, c["loser"]["tune_id"], c["loser"]["instrument"]),
        )

    # --- person_tune ----------------------------------------------------------
    for c in a["person_tune"][1]:
        merged = merge_person_tune_fields(c["winner"], c["loser"])
        save_to_history(cur, "person_tune", "UPDATE", (winner_id, c["winner"]["tune_id"]), user_id)
        cur.execute(
            """
            UPDATE person_tune
            SET learn_status = %s, heard_count = %s, learned_date = %s, notes = %s,
                last_modified_date = (NOW() AT TIME ZONE 'UTC'), last_modified_user_id = %s
            WHERE person_id = %s AND tune_id = %s
            """,
            (
                merged["learn_status"], merged["heard_count"], merged["learned_date"],
                merged["notes"], user_id, winner_id, c["winner"]["tune_id"],
            ),
        )
        save_to_history(cur, "person_tune", "DELETE", (loser_id, c["loser"]["tune_id"]), user_id)
        cur.execute(
            "DELETE FROM person_tune WHERE person_id = %s AND tune_id = %s",
            (loser_id, c["loser"]["tune_id"]),
        )
    for row in a["person_tune"][0]:
        save_to_history(cur, "person_tune", "UPDATE", (loser_id, row["tune_id"]), user_id)
        for child in pti["carried"]:
            if child["tune_id"] == row["tune_id"]:
                save_to_history(
                    cur, "person_tune_instrument", "UPDATE",
                    (loser_id, child["tune_id"], child["instrument"]), user_id,
                )
    if a["person_tune"][0]:
        # children follow via person_tune_instrument's FK ON UPDATE CASCADE
        cur.execute(
            "UPDATE person_tune SET person_id = %s, "
            "last_modified_date = (NOW() AT TIME ZONE 'UTC'), last_modified_user_id = %s "
            "WHERE person_id = %s",
            (winner_id, user_id, loser_id),
        )

    # --- session_person --------------------------------------------------------
    for row in a["session_person"][0]:
        save_to_history(cur, "session_person", "UPDATE", (row["session_id"], loser_id), user_id)
        cur.execute(
            "UPDATE session_person SET person_id = %s, "
            "last_modified_date = (NOW() AT TIME ZONE 'UTC'), last_modified_user_id = %s "
            "WHERE session_id = %s AND person_id = %s",
            (winner_id, user_id, row["session_id"], loser_id),
        )
    for c in a["session_person"][1]:
        merged = merge_session_person_fields(c["winner"], c["loser"])
        save_to_history(cur, "session_person", "UPDATE", (c["winner"]["session_id"], winner_id), user_id)
        cur.execute(
            """
            UPDATE session_person
            SET relationship = %s, confirmed = %s, archived = %s, is_admin = %s,
                gets_email_reminder = %s, gets_email_followup = %s,
                last_modified_date = (NOW() AT TIME ZONE 'UTC'), last_modified_user_id = %s
            WHERE session_id = %s AND person_id = %s
            """,
            (
                merged["relationship"], merged["confirmed"], merged["archived"],
                merged["is_admin"], merged["gets_email_reminder"], merged["gets_email_followup"],
                user_id, c["winner"]["session_id"], winner_id,
            ),
        )
        save_to_history(cur, "session_person", "DELETE", (c["loser"]["session_id"], loser_id), user_id)
        cur.execute(
            "DELETE FROM session_person WHERE session_id = %s AND person_id = %s",
            (c["loser"]["session_id"], loser_id),
        )

    # --- session_instance_person ----------------------------------------------
    for row in a["session_instance_person"][0]:
        save_to_history(
            cur, "session_instance_person", "UPDATE", (row["session_instance_id"], loser_id), user_id
        )
        cur.execute(
            "UPDATE session_instance_person SET person_id = %s, "
            "last_modified_date = (NOW() AT TIME ZONE 'UTC'), last_modified_user_id = %s "
            "WHERE session_instance_id = %s AND person_id = %s",
            (winner_id, user_id, row["session_instance_id"], loser_id),
        )
    for c in a["session_instance_person"][1]:
        merged = merge_session_instance_person_fields(c["winner"], c["loser"])
        # loser's row goes FIRST: UNIQUE(session_instance_id, arrival_seq)
        # would reject the winner inheriting the loser's (earlier) seq while
        # the loser's row still holds it.
        save_to_history(
            cur, "session_instance_person", "DELETE",
            (c["loser"]["session_instance_id"], loser_id), user_id,
        )
        cur.execute(
            "DELETE FROM session_instance_person WHERE session_instance_id = %s AND person_id = %s",
            (c["loser"]["session_instance_id"], loser_id),
        )
        save_to_history(
            cur, "session_instance_person", "UPDATE",
            (c["winner"]["session_instance_id"], winner_id), user_id,
        )
        cur.execute(
            """
            UPDATE session_instance_person
            SET attendance = %s, comment = %s, arrival_seq = %s,
                last_modified_date = (NOW() AT TIME ZONE 'UTC'), last_modified_user_id = %s
            WHERE session_instance_id = %s AND person_id = %s
            """,
            (
                merged["attendance"], merged["comment"], merged["arrival_seq"],
                user_id, c["winner"]["session_instance_id"], winner_id,
            ),
        )

    # --- session_logger_color (no history table; winner's color stands) --------
    for c in a["session_logger_color"][1]:
        cur.execute(
            "DELETE FROM session_logger_color WHERE session_id = %s AND person_id = %s",
            (c["loser"]["session_id"], loser_id),
        )
    cur.execute(
        "UPDATE session_logger_color SET person_id = %s WHERE person_id = %s",
        (winner_id, loser_id),
    )

    # --- set-starter attributions ----------------------------------------------
    for sit_id in a["started_by_ids"]:
        save_to_history(cur, "session_instance_tune", "UPDATE", sit_id, user_id)
    cur.execute(
        "UPDATE session_instance_tune SET started_by_person_id = %s WHERE started_by_person_id = %s",
        (winner_id, loser_id),
    )

    # --- recordings --------------------------------------------------------------
    for rec_id in a["recording_ids"]:
        save_to_history(cur, "recording", "UPDATE", rec_id, user_id)
    cur.execute(
        "UPDATE recording SET person_id = %s WHERE person_id = %s", (winner_id, loser_id)
    )

    # --- referred_by pointers ------------------------------------------------------
    for ref_user_id in a["referred_by_user_ids"]:
        save_to_history(cur, "user_account", "UPDATE", ref_user_id, user_id)
    cur.execute(
        "UPDATE user_account SET referred_by_person_id = %s WHERE referred_by_person_id = %s",
        (winner_id, loser_id),
    )

    # --- accounts ---------------------------------------------------------------
    deleted_user_id = _merge_accounts(
        cur, loser_id, winner_id, loser_acct, winner_acct, surviving_user_id, user_id
    )

    # --- the person rows ----------------------------------------------------------
    # Delete the loser FIRST: that frees the partial-unique email index so the
    # winner can inherit the loser's email in the same transaction. Every
    # reference has been moved by now, so nothing cascades away.
    changes = _profile_changes(winner, loser)
    save_to_history(cur, "person", "DELETE", loser_id, user_id)
    cur.execute("DELETE FROM person WHERE person_id = %s", (loser_id,))

    if changes["fills"]:
        save_to_history(cur, "person", "UPDATE", winner_id, user_id)
        sets = ", ".join(f"{field} = %s" for field in changes["fills"])
        cur.execute(
            f"UPDATE person SET {sets}, "
            "last_modified_date = (NOW() AT TIME ZONE 'UTC'), last_modified_user_id = %s "
            "WHERE person_id = %s",
            (*changes["fills"].values(), user_id, winner_id),
        )

    pti_counts = a["person_tune_instrument"]
    return {
        "success": True,
        "merged_person_id": loser_id,
        "surviving_person_id": winner_id,
        "deleted_user_id": deleted_user_id,
        "moved": {
            "person_tune": len(a["person_tune"][0]),
            "person_instrument": len(a["person_instrument"][0]),
            "person_tune_instrument": len(pti_counts["carried"]) + len(pti_counts["moves"]),
            "session_person": len(a["session_person"][0]),
            "session_instance_person": len(a["session_instance_person"][0]),
            "session_logger_color": len(a["session_logger_color"][0]),
            "set_starter_attributions": len(a["started_by_ids"]),
            "recordings": len(a["recording_ids"]),
            "referred_by_pointers": len(a["referred_by_user_ids"]),
        },
        "field_merged": {
            "person_tune": len(a["person_tune"][1]),
            "person_instrument": len(a["person_instrument"][1]),
            "person_tune_instrument": len(pti_counts["collisions"]),
            "session_person": len(a["session_person"][1]),
            "session_instance_person": len(a["session_instance_person"][1]),
            "session_logger_color": len(a["session_logger_color"][1]),
        },
        "profile_fills": changes["fills"],
    }
