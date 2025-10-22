# 005 Current Session Instance

I'd like the add the notion of an "active" session instance, both from the perspective of an instance of a regular session, and from the perspective of a player. This is based on the recurrence pattern of the session, where "active" is true starting one hour before the stated start time, and stops being true one hour after the stated end time.

We'll update the session instance table and person table to each have a column that indicates "active" status:

- I'd like the session instance table to have a boolean "active" which is true only for that same time period. 
- And I'd like the person table to have a "active_session_instance" column that points to the session they're at right now, which also requires that the "active" bit is true for that same session. I'd like people to be able to set that by saying "I'm at a session instance" (which you can already do in the UI through the "people" tab by checking in as a "Yes" at the session instance) and have that set their currently_at_session_instance value. If there's another session happening in the same geographical location (i.e. same Country & City), they should also see the option to check in there (which would change their at_active_session_instance value to that one)

Since these are database values that should change automatically at certain times, I'd like to use some kind of regular or scheduled job to check for and update the status on the session and session_instance table based on the session's recurrence pattern, time zone, and the current date & time in the time zone where the session happens, so that:

- at session start trigger (X minutes before start time)
  - it switches the active bit on for the right session instance, and ensures it's the only row with that true
  - any people who have already checked in as "yes" for the session are marked as having that session as their active session unless they're active in a different session instance that itself is active (say, there may be two concurrent sessions that overlap and they plan to go to both)
- at session end trigger (X minutes after end time)
  - it switches the active bit off for the ended session instance
  - all people who had that session set as active have it nulled out
  - it also checks to see if there's another abutting or overlapping session instance for the same session that should be currently active and goes through the "start session" process for it

In the session table, we'll save a "active_buffer_minutes_before" and "active_buffer_minutes_after" which has a default value of 60 for all rows. This controls the precise time sessions should ideally be switched to active and inactive.

When a person is checked in as "yes" for multiple overlapping sessions, their active_session_instance is based on which one starts first, and on ties, use the one they most recently checked in to.

All times related to this task should be in the local time zone of the session (not the user).

Because we're only running the cron job every 15 minutes, it's important to also hook on events:

- When a session's recurrence is saved, if there are any sessions that should currently be active based on the new recurrence but aren't, make them active. Likewise, vice versa, if a session is changed to cancelled or its recurrence is changed such that it no longer overlaps the current time but it was already set to active, set it back to inactive.

## Cron Job details

Create jobs/check_active_sessions.py - Script to run via cron that:

- Calls update_active_sessions() from the active session manager
- Logs results for monitoring
- Runs every 15 minutes at 14/29/44/59 minutes after the hour, looking one minute ahead (since most session will start on a 15 minute time boundary, this allows it to set them to active just before they should start)

Update render.yaml to add cron job service that runs every 15 minutes