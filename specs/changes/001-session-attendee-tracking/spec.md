# Feature Specification: Session Attendee Tracking

**Feature Branch**: `001-session-attendee-tracking`  
**Created**: 2025-09-12  
**Status**: Draft  
**Input**: User description: "Storing information about people attending sessions"

## User Scenarios & Testing *(mandatory)*

### Primary User Story

As a session organizer or regular attendee, I want to track who attends each music session, and allow users to check themselves in, so that I can maintain a record of participants, understand attendance patterns, coordinate with regular attendees, and track further information about the connections between people and tunes.

People in the system can be users (with login information) or not, and can be associated with a session as an attendee (have ever attended) or regular (attends regularly); the user interface for marking attendance allows:

- one-click check-in for regulars (by self, if you're logged in, or by another organizer or regular)
- a quick search/add over previous attendees who aren't regulars
- a data entry screen to add a new person to the system with their first and last names and instrument(s), for attendees who have never attended this session before.

Users can check themselves into any session.

Except for during initial entry, names are always shown as "First Name, Last Initial" with an intstrument list in small type below. For example:

John Smith
(small type) Banjo, Concertina

### Acceptance Scenarios

1. **Given** an organizer or logged-in regular is viewing a session instance details page, **When** they click the "attendees" tab of the page, **Then** they see a list of icons & names for all regulars (in green if attending, red if not, or greyscale if unkown). In the list they also see other non-regulars who have been marked as attending this session instance.
2. **Given** an organizer or logged in regular is viewing the "attendees" tab of a session instance details page, **When** they add an attendee, **Then** the attendee appears in the list of people present at that session
3. **Given** a session instance has attendees recorded, **When** a logged in user who's associated with that session is viewing the session details, **Then** attendees for that session instance are displayed with their information
4. **Given** a user is recording attendees, **When** they search for a person by name, **Then** matching existing attendees for this session are suggested to avoid duplicates.
5. **Given** multiple session instances exist, **When** viewing a person's profile, **Then** all sessions they attended are listed
6. **Given** a session organizer is viewing information about their sessions, **When** they view the admin screen, **Then** they can see counts of attendance by person with trends over time.
7. **Given** a person appears in the attendance list for a session, **When** an authorized users clicks their name, **Then** they are taken to a modal screen where they can add details like email address, edit the name, and edit the instrument list, as well as change the attendance status (attending, not attending, unknown) or be deleted from this session instance entirely.

### Edge Cases

- If a person is manually added as attending a session, they may be a duplicate of an existing person, but that's OK (we'll have an admin merge screen later).
- If two people have the same first name and last initial and instrument list, then more letters of their name are shown to a point where there's no ambiguity.
- If two people have the same full first and last name and instrument list, then a number in parens is shown after the name (e.g. "(1)", "(2)", etc.)
- If there's an anonymous or guest attendee at the session who doesn't give a name or doesn't want to be tracked, they can simply be left off.
- For privacy reasons, you can only see the attendance tab if you're a logged in user AND you're either a regular at this session or in attendance at this session. You cannot see anything other than the display name and instrument list if you're not an admin (organizer) of this session.


### Key Entities

All of these entities already exist (schema is in the schema folder):

- **Person**: Represents an individual who can attend sessions. Key attributes include name and email.
- - **Session Instance**: A specific occurrence of a session on a particular date/time that attendees can be associated with.
- **Session_Instance_Person**: Represents the participation of a person in a specific session instance. Links a person to a session instance with an "attendance" value of "Yes", "Maybe", or "No". This record only exists once there's some signal about the person's attendance.

New entities:

- **Person_Instrument** - One record per person per instrument. Instruments are stored as strings, exist as an enum in the system's python code with these values:
fiddle, flute, tin whistle, low whistle, uilleann pipes, concertina, button accordion, piano accordion, bodhrán, harp, tenor banjo, mandolin, guitar, bouzouki, viola
