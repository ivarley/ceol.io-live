# 004 Session Type

Currently in the system, the session table holds what are effectively "regular" sessions. They have recurrence and many instances associated with them. However, there are other types of sessions. We're going to add a new one. 

Add a "session_type" field to the session table, defaulted to "regular". The other possible value for now is "festival".

The initiation_date and termination_date fields, for a festival, are the start & end date. Recurrence should be blank.

On the session details page, if type is festival, there are a few differences:

- the "Logs" tab should say "Sessions", and the tab order should be flipped (Sessions first)
- Instead of being separated by year, it should be separated by day (as there will likely be multiple sessions per day).
- And instead of listing each session by date, it should show the location_override field and time field (Like "Advanced Session @ Jim Bowie, 8:00pm-11:00pm" or "After-Hours Session @ Hotel, 11:00 - ?")

We'll also need to remove the idx_session_instance_no_overlap index, since session instances for the same session can now overlap.

Now that we allow overlapping session instances for a session, the "Add Session" modal on the session details page (/sessions/{path}) should not give you the error "Session instance for {date} already exists", and the "Edit Session" modal on the session instance details page (/sessions/{path}/date should not give you that error if you attempt to update a session instance to be concurrent with another session instance.

We'll also need to change the link for a session instance to also accept the session_instance_id instead of the date.