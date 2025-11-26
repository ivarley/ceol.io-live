# Requirements Document

## Introduction

This feature enables users to maintain personal tune collections with learning-status tracking and synchronization capabilities from thesession.org. Users can manage their tune learning progress, sync their existing tunebooks from thesession.org, add tunes, and efficiently browse their collection on mobile devices with search and filtering capabilities.

## Requirements

### Requirement 1

**User Story:** As a musician, I want to track my learning progress for individual tunes, so that I can keep track of which tunes are on my "want to learn" list and how often I've heard them at sessions.

#### Acceptance Criteria

1. WHEN a user views a tune's detail page, THEN the system SHALL display the current learn_status ("want to learn", "learning", or "learned")
2. WHEN a user selects a different learn_status for a tune THEN the system SHALL update the person_tune record immediately
3. WHEN a user has not set a learn_status for a tune when it's added to their person_tune list THEN the system SHALL default to "want to learn"
4. IF a user changes a tune's status to "learned" THEN the system SHALL timestamp the change for progress tracking
5. WHEN a tune has "want to learn" status THEN the system SHALL display a "+" button to increment the heard_before_learning_count
6. WHEN a user clicks the "+" button THEN the system SHALL increment the heard_before_learning_count by 1 and display the updated count
7. WHEN a tune's status changes from "want to learn" to "learning" or "learned" THEN the system SHALL preserve the heard_before_learning_count value but no longer display it
8. WHEN displaying a tune with heard_before_learning_count > 0 THEN the system SHALL show the count next to the tune name

### Requirement 2

**User Story:** As a user with an existing thesession.org tunebook, I want to sync my tune collection, so that I don't have to manually re-enter all my tunes.

#### Acceptance Criteria

1. WHEN a user provides their thesession.org user ID THEN the system SHALL fetch their tunebook data from the JSON API
2. WHEN tunebook data is retrieved THEN the system SHALL create person_tune records for each tune not already in the user's collection
3. IF a tune already exists in the user's collection THEN the system SHALL preserve the existing learn_status
4. WHEN sync is complete THEN the system SHALL display a summary of tunes added and any errors encountered
5. IF the thesession.org API is unavailable THEN the system SHALL display an appropriate error message and allow retry
6. If a tune from the user's tunebook isn't in the tune table in our system (based on id), then it will first be added there, then added to person_tune (which has a foreign key relationship)

### Requirement 3

**User Story:** As a mobile user, I want to easily browse and search my tune collection on my phone, so that I can quickly find tunes during sessions or practice.

#### Acceptance Criteria

1. WHEN a user accesses their tune list on mobile THEN the system SHALL display a responsive interface optimized for touch interaction
2. WHEN a user types in the search box THEN the system SHALL filter tunes in real-time by tune name
3. WHEN a user selects a tune type filter THEN the system SHALL show only tunes matching that type (jig, reel, hornpipe, etc.)
4. WHEN a user selects a learn_status filter THEN the system SHALL show only tunes with that learning status
5. WHEN multiple filters are active THEN the system SHALL apply all filters simultaneously
6. WHEN no tunes match the current filters THEN the system SHALL display a "no results" message with option to clear filters
7. WHEN changes are made to search or filters, these are synchronized into the current URL so copying it returns to the exact same view

### Requirement 4

**User Story:** As a user, I want to view detailed information about each tune in my collection, so that I can access tune metadata and make informed decisions about my learning.

#### Acceptance Criteria

1. WHEN a user selects a tune from their list THEN the system SHALL display the common tune details page including name, type, key, popularity (tunebook count) on thesession.org, popularity (count in sessions I'm a member of), a link to the tune's page on thesession.org, and any other available metadata
2. WHEN tune details are displayed THEN the system SHALL show the current learn_status with option to change it
3. WHEN a user updates learn_status from the detail view THEN the system SHALL save the change and return to the filtered list

### Requirement 5

**User Story:** As a user, I want to manually add tunes to my collection, so that I can track tunes that aren't available on thesession.org or that I've learned from other sources.

#### Acceptance Criteria

1. WHEN a user chooses to add a new tune THEN the system SHALL provide a form with the tune name, which will use the same auto-complete search as on the beta session instance details page. If no tune is found in the tune table, they cannot yet add the tune (in the future we'll add that).
2. WHEN a user chooses a valid tune THEN the system SHALL create a new person_tune record with "want to learn" status for that tune id
3. WHEN a new tune is successfully added THEN the system SHALL redirect to the tune list and highlight the new entry

### Requirement 6

**User Story:** As a user viewing a session instance detail page, I want to add tunes from the session to my personal collection, so that I can easily track tunes I encounter during sessions.

#### Acceptance Criteria

1. WHEN a user right-clicks or long-presses a tune on the session_instance_detail page THEN the system SHALL display a context menu with "Add to My Tunes" option
2. WHEN a user selects "Add to My Tunes" from the context menu THEN the system SHALL add the tune to their personal collection with "want to learn" status
3. IF the tune is already in the user's collection THEN the system SHALL display the current learn_status and allow updating it
4. WHEN a tune is successfully added from a session THEN the system SHALL show a brief confirmation toast message

### Requirement 7

**User Story:** As a user, I want my personal tune collection to be private, so that only I can view and modify my learning progress and tune data.

#### Acceptance Criteria

1. WHEN a user accesses any personal tune functionality THEN the system SHALL verify the user is authenticated
2. WHEN displaying personal tune data THEN the system SHALL only show tunes belonging to the current logged-in user
3. WHEN a user attempts to modify tune data THEN the system SHALL verify they own that person_tune record or are a system admin
4. IF an unauthenticated user tries to access personal tune features THEN the system SHALL redirect to the login page
5. IF a user tries to access another user's tune data THEN the system SHALL return a 403 Forbidden error
6. WHEN a system admin accesses tune data THEN the system SHALL allow viewing and modifying any user's tune collection for support purposes