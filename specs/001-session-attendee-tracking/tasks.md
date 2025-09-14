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


### T048.1 - Search enhancements

Preload all the non-regulars on page load in a javascript data structure so search is instant.
In place of "No people found", have it say "Add a new person ..."
When you hit "enter" (or "return" or "tab"), it adds the top person in the search results (if there are any) or brings up the "Add" modal with the name they typed prepopulated (split between first and last if there's a space in their input).
Remove the "Add Person" and "Refresh" buttons.

### T048.2 - UI enhancements

A couple other nits:

- There's an invisible button to the right of the search box, get rid of it
- Cancel button is not working on modal
- Closing the modal, the screen still stays dimmed and shouldn't
- The selected tab is white even in dark mode and shouldn't be
- I'd like the rows in the player UI to be vertically thinner by about 10px
- Remove the "Session Attendance" albel, and move the status counts to align right
- Remove "Back to this session" from the bottom of this (and from the tunes tab, if it's shared)
- Put the the search and the status counts in the same line
- Once you've done the action from the search box (adding an existing or new player), empty the box


### T049 - Allow session admins to edit some person information

When a session admin clicks through to the person admin page (/admin/sessions/{path}/players/{person_id}), you can update some things, depending on whether they have a linked user account.

If the person has a user account, you can only update their "regular player" checkbox.

If the person does not have a linked user account, a session (or system) admin can edit:
- Name
- Email
- SMS Number
- TheSession.org ID
- City
- State
- Country


### T050 - Edit instruments

On the same person admin page, you can also edit instruments (in the same situation as other details, i.e. if there's not a linked user account).

Show it as the same kind of checkbox list. Fix the issue where it can't save "Other" instruments not in the list.


### T051 - Filter by status

Clicking the count icons in the players view should temporarily filter the list to only those in that status. Putting focus in the search box, changing tabs, or (obviously) clicking the "Total" reverts it to unfiltered. Changing a status while in filtered mode should correctly change the status, which would make it drop out of the current view, but that's a confusing UX so instead show it as dimmed out if that happens (and remove the dimming if the status is changed back to something that would show in this filter, or if total is clicked, or anything else that would reset the filter).

### T052 - Convert to Typescript

Our implementation of attendance.js is in javascript, but all the other important js code in this app is in typescript. Convert it.

While you're at it, clean up all the console logging.

### T053 - Return links

I want to make sure navigation is consistent throughout the app. When you're on the session instance details page (regular or beta):

sessions/{path}/{date}
sessions/{path}/{date}/beta

The session name is listed at the top. Just to the right of that, put a "return" arrow (⮐) that's a link back to the session home page:

sessions/{path}/11

The link should be dim (meaning, dark blue in dark mode, or light blue in light mode).

## In Progress

### T054 Bulk Player Import

Build a new screen in the session admin screen allowing a session organizer to bulk import people (linked from a button on the "People" tab). It should have two screens; the first has a big text box  allowing you to paste in comma separated (csv) data, with or without header, with any of the following fields:
- First Name
- Last Name
- Name or Full Name (which is separated into first and last based on splitting at the final space)
- Email - looks like an email
- SMS - looks like a phone number
- City - only include if there's a header row; if blank, default to the city of this session.
- State - only include if there's a header row; if blank, default to the state of this session.
- Country - only include if there's a header row; if blank, default to the country of this session.
- Regular - a boolean field where the values "x", "true", "yes", and "t" all work for true and any other value is false. Only include if there's a header row
- Instruments (which is itself a comma delimited list, either quote enclosed or not if it's at the end of the row).

Name is mandatory, everything else is optional. If there's no header row, try to determine the content of the data from context using the rules above.

So for example if a row has "John Smith, john@smith.com, Flute, Fiddle" then it should figure out that John is the first ame, Smith is the last name, john@smith.com is the email, and there are two instruments to add, Flute & Fiddle

For duplicate resolution, first look for a person with the same email or phone number, as that's definitely a duplicate; then look for the same name on a person already associated with this session and if there is one, count that as a match.

Add a breif explanation of the required format on the page.

The entry page has a "Next" button which brings you to the second stage: a preview of what would get created, shown as a grid, with "instruments" as a single comma-delimited column. The grid clearly shows which records are not being imported because they're duplicates. A "Back" button lets you go back to your initial textbox view and make changes. A "Save" button lets you perform the actual insert.

Begin by writing a set of failing tests that exercise the two new API endpoints (bulk person pre-process, and bulk person save) thoroughly, where all the tests initially fail; then implement the API such that the tests pass; then build the UI.

Show a spinner while moving from one screen to the next.

## Backlog
