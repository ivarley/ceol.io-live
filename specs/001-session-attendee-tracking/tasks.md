# Tasks: Session Attendee Tracking

**Input**: Design documents from `/specs/001-session-attendee-tracking/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/

Now some additional tasks to get it to where I want it, in individual sections.

## Complete

### T045 - Session Peson Records

Adding someone as attending a session (i.e. inserting in session_instance_person) should simultaneously add a record to session_person for them if it doesn't already exist, with is_regular defaulted to false. (If it already exists, no change is needed.)

If the last record for a person is deleted from session_instance_person (i.e. if no records remain in session_instance_person with that session_id and person_id) then they should be deleted from session_person for that session_id as well. (They may well exist for other sessions; this only affects the current session.)

Add tests for these cases first, and show them failing, and then implement the required changes and show the tests passing.

### T046 - Link To Edit Session person

For system and session admins, show an edit icon on the right edge of the person row in the attendance tab that takes you to the session admin page for that person (admin/sessions/{path}/players/{person_id}). This replaces the two non-functional buttons to the right of the yes/maybe/no buttons that aren't displaying correctly anyway. When you arrive at this page from this route, instead of:

"Player details for {session name}. ← Back to players list"

you should see:

"Player details for {session name}. ← Back to session on {session instance date}"

and it should return you to the attendance tab of the session instance detail page. 

### T047 - Always show regulars

The attendance list should always show the session regulars in the list, even if there's no record in the session_instance_person table for them (i.e. it should be an outer join). If they're not in session_instance_person for this session, they show as "unknown" status, which is a new fourth status in addition to "yes", "maybe" and "no" (which should also show in the totals, and has a blue color).

### T048 - Search players

Make the search work to find non-regulars and add them. Clicking the name adds them immediately in the UI and asynchronously updates the database.

## In Progress

### T048.1 - Search enhancements

Preload all the non-regulars on page load in a javascript data structure so search is instant.
In place of "No people found", have it say "Add a new person ..."
When you hit "enter" (or "return" or "tab"), it adds the top person in the search results (if there are any) or brings up the "Add" modal with the name they typed prepopulated (split between first and last if there's a space in their input).
Remove the "Add Person" and "Refresh" buttons.

### T048.2 - UI enhancements

A couple other nits:

- Cancel not working on modal
- Closing modal, screen still dim

## Backlog

### T049 - Allow session admins to edit some person information

When a session admin clicks through to the person admin page (/admin/sessions/{path}/players/{person_id}), you can update some things, depending on whether they have a linked user account.

If the person has a user account, you can only update their "regular player" checkbox.

If the person does not have a linked user account, a session admin can edit:
- Name
- Email
- SMS Number
- TheSession.org ID
- City
- State
- Country

### T050 - Edit instruments

You can also edit instruments in the same situation as other details (i.e. if there's not a linked user account).

### T051 - Convert to Typescript

Our implementation of attendance.js is in javascript, but all the other important js code in this app is in typescript. Convert it.

Other
- Clean up console logging
- white tab in dark mode
- Thinner rows
- Remove "Session Attendance", move counts to align right
- Remove "Back to this session" from the bottom of this and tune page
- Clicking counts filters (search unfilters)