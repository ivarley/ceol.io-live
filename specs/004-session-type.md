# 004 Session Type

Currently in the system, the session table holds what are effectively "regular" sessions. They have recurrence and many instances associated with them. However, there are other types of sessions. We're going to add a new one. 

Add a "session_type" field to the session table, defaulted to "regular". The other possible value for now is "festival".

The initiation_date and termination_date fields, for a festival, are the start & end date. Recurrence should be blank.

On the session details page, if type is festival, there are a few differences:

- the "Logs" tab should say "Sessions".
- Instead of being separated by year, it should be separated by day (as there will likely be multiple sessions per day).
- And instead of listing each session by date, it should show the location_override field and time field (Like "Advanced Session @ Jim Bowie, 8:00pm-11:00pm" or "After-Hours Session @ Hotel, 11:00 - ?")
