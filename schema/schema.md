# schema.md

This file serves as a spec for the database schema of this site.

The database will be a Postgres database. The basic entities in my model will be as follows.

## Session Info

- **session** - This represents an ongoing regular musical event gathering called a “session”. Each session will have basic details (like where it happens, and what its regular schedule is) which can change over time. Each session will then be related to many individual session_instances that represent single occurrences of the session on a particular date and time, during which they play tunes. Sessions have these attributes:
    - session_id - Unique ID, auto-generated, primary key
    - thesession_id - integer, points to the ID used for this session on thesession.org, if it exists.
    - Name (string), which should generally be the same as the name on thesession.org
    - path, string that's a URL-safe version of the name that is used as the permanent web URL for this session (e.g. "mueller")
    - location_name - If different from the session name, this is the name of the establishment where it's held (e.g. "BD Riley's Pub")
    - location_website
    - location_phone
    - city - string
    - state
    - country
    - path - a URL safe path under the site root for this session (e.g. 'austin/mueller')
    - comments - text field where admins can explain more about how the session works, whether it’s open, etc.
    - unlisted_address - a bit to represent whether the address is shown, in case it’s at someone’s house and they don’t want to broadcast their address to the internet.
    - initiation date - the first session ever
    - termination dates - the last session ever (null if the session is ongoing)
    - recurrence - a standard recurrence schema that is at most daily, but also supports patterns like "every other thursday" and "first and third sundays of the month", and also includes start and end time
    - active_buffer_minutes_before - integer, minutes before session start time when it becomes active (default 60) - Feature 005
    - active_buffer_minutes_after - integer, minutes after session end time when it stops being active (default 60) - Feature 005

- **session_instance** - This is one instance of a session that happens on a particular date and time. Session instances can be in the past or future. The same session should not ever have multiple instances  that overlap in time. Attributes:
    - session_id
    - date
    - start time
    - end time
    - location_override - if null, assume the location is the standard one for the session
    - bit for "is_cancelled" defaulting to false
    - a comment text field (eg "We'll play in the back room this week", "it's sarah's birthday!", etc. )
    - is_active - boolean, whether this instance is currently active (multiple instances per session can be active simultaneously)

- **tune** - This is a musical composition with a unique id, a name, and a tune_type. Any data that can be synchronized and cached from thesession.org is. Attributes:
    - tune_id - integer, this matches the ids of tunes on thesession.org. As such, it's just an integer primary key but not automatically generated.
    - name - string
    - tune_type - an enumeration of {jig, reel, slip jig, hornpipe, polka, slide, waltz, barndance, strathspey, three-two, mazurka, march}
    - tunebook_count_cached - integer

- **session_tune** - A relationship between a session and a tune, which first comes into being at the point a tune has been recorded as having been played at the session, and includes:
    - a setting_id (which setting is commonly played at this session)
    - key (defaulted from the key of that default setting, but editable)
    - alias (a name used in this session, if different from the primary name).

- **session_instance_tune** - An instance of one tune being played at one session. This entity is a little odd because we want to account for the fact that people can play things in a session that are unidentified or vaguely identified (like "an unknown reel", or a tune with a name that doesn't correspond to any known tune, like "the squirrely hobbit"); this means a tune can have a tune_id, name, or both (but must have one or the other). The same tune can be played in the same session (or even the same set) more than once.  Attributes:
    - session_instance_id
    - tune_id - foreign key to the tune table, but can be null if this tune isn't matched to a known session_tune
    - name - a string, which can be null if there's a tune_id (the name from the tune is assumed in that case)
    - order - an integer indicating what order tunes were played in
    - continues-set - a bit; when true, means this tune immediately followed the previous one in a set (which is the used to create derived set_number attribute). When false, means it started a new set.
    - played_timestamp - a timestamp of when the tune was played. An async process could detect if there are cases where ordering and timestamps appear to conflict.
    - inserted_timestamp - a timestamp (also not shown in the UI) of when the record was inserted
    - key_override - optional field meaning that this instance of playing the tune was in a different key from the key on the tune record / session_tune record.
    setting_override”, in case this instance of playing the tune differs from that which is mapped as the standard for this session.
