# Data Model: Session Attendee Tracking

## Entity Relationship Diagram

```
┌─────────────┐       ┌──────────────────┐       ┌───────────────────┐
│   Person    │───────│ Person_Instrument│       │ Session_Instance  │
└─────────────┘   1:N └──────────────────┘       └───────────────────┘
      │                                                    │
      │                                                    │
      │ N:M                                               │
      └─────────────┬──────────────────────────┬──────────┘
                    │                          │
              ┌─────────────────────────┐     │
              │Session_Instance_Person │─────┘
              └─────────────────────────┘
                           │
                           │ 1:N
                    ┌──────────────┐
                    │Session_Person│
                    └──────────────┘
```

## Entities

### Person (Existing)
**Purpose**: Represents individuals who can attend sessions

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| person_id | SERIAL | PRIMARY KEY | Unique identifier |
| first_name | VARCHAR(100) | NOT NULL | Person's first name |
| last_name | VARCHAR(100) | NOT NULL | Person's last name |
| email | VARCHAR(255) | UNIQUE, NULL | Contact email |
| sms_number | VARCHAR(20) | NULL | Phone number |
| created_date | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| last_modified_date | TIMESTAMPTZ | DEFAULT NOW() | Last update |

**Display Format**: `{first_name} {last_name[0]}` (e.g., "John S")

### Person_Instrument (New)
**Purpose**: Links people to the instruments they play

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| person_id | INTEGER | FK → Person, NOT NULL | Person reference |
| instrument | VARCHAR(50) | NOT NULL | Instrument name |
| created_date | TIMESTAMPTZ | DEFAULT NOW() | Record creation |

**Constraints**:
- PRIMARY KEY (person_id, instrument) - Composite primary key
- Instrument must be from enum: `['fiddle', 'flute', 'tin whistle', 'low whistle', 'uilleann pipes', 'concertina', 'button accordion', 'piano accordion', 'bodhrán', 'harp', 'tenor banjo', 'mandolin', 'guitar', 'bouzouki', 'viola']`

### Session_Instance_Person (Existing, Modified)
**Purpose**: Tracks attendance for specific session instances

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| session_instance_person_id | SERIAL | PRIMARY KEY | Unique identifier |
| session_instance_id | INTEGER | FK → Session_Instance | Session occurrence |
| person_id | INTEGER | FK → Person | Attendee |
| attendance | VARCHAR(5) | CHECK IN ('yes','maybe','no') | Attendance status |
| comment | TEXT | NULL | Notes about attendance |
| created_date | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| last_modified_date | TIMESTAMPTZ | DEFAULT NOW() | Last update |


### Session_Person (Existing)
**Purpose**: Links people to sessions they regularly attend

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| session_person_id | SERIAL | PRIMARY KEY | Unique identifier |
| session_id | INTEGER | FK → Session | Regular session |
| person_id | INTEGER | FK → Person | Regular attendee |
| is_regular | BOOLEAN | DEFAULT FALSE | Regular attendee flag |
| is_admin | BOOLEAN | DEFAULT FALSE | Can manage session |
| receive_email | BOOLEAN | DEFAULT FALSE | Email notifications |

## Business Rules

### Attendance Management
1. **Unique Attendance**: One person can only have one attendance record per session instance
2. **Default State**: No record means attendance unknown (not tracked)
3. **Regular Priority**: Regulars always in attendance list (regardless of status) but list is alphabetical so if non-regulars are added they show in alphabetical order
4. **Self Check-in**: Logged-in users can check themselves into any session
5. **Admin Override**: Session admins can modify any attendance record

### Instrument Management
1. **Multiple Instruments**: People can play multiple instruments
2. **No Duplicates**: Same instrument cannot be added twice for same person
3. **Display Order**: Instruments shown alphabetically
4. **Validation**: Only approved instrument names allowed

### Privacy Rules
1. **View Restrictions**: 
   - Public: Cannot see attendance
   - Logged-in non-attendee: Cannot see attendance
   - Attendee/Regular: Can see attendance list
   - Admin: Can see and edit all fields
2. **Data Minimization**: Only show name and instruments in lists
3. **Contact Privacy**: Email/phone only visible to admins

### Display Rules
1. **Name Format**: "FirstName L" unless ambiguous
2. **Disambiguation**: 
   - Same name+initial+instrument list: Show more letters
   - Identical names+instrument list: Add (1), (2) ... suffix
3. **Instrument Display**: Small text below name
4. **Color Coding**:
   - Green: Attending (yes)
   - Red: Not attending (no)
   - Yellow: Maybe attending
   - Gray: Unknown

## Indexes

### Performance Optimization
```sql
-- Existing indexes
CREATE INDEX idx_session_instance_person_session_instance_id 
    ON session_instance_person(session_instance_id);
CREATE INDEX idx_session_instance_person_person_id 
    ON session_instance_person(person_id);
CREATE INDEX idx_session_instance_person_attendance 
    ON session_instance_person(attendance);

-- New indexes
CREATE INDEX idx_person_instrument_person_id 
    ON person_instrument(person_id);
CREATE INDEX idx_person_instrument_instrument 
    ON person_instrument(instrument);
```

## Migration Strategy

### Phase 1: Schema Addition
```sql
-- Create person_instrument table
CREATE TABLE person_instrument (
    person_id INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    instrument VARCHAR(50) NOT NULL,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    PRIMARY KEY (person_id, instrument)
);
```

### Phase 2: History Tracking
```sql
-- Add history table for person_instrument
CREATE TABLE person_instrument_history (
    LIKE person_instrument INCLUDING ALL,
    history_id SERIAL PRIMARY KEY,
    history_date TIMESTAMPTZ DEFAULT NOW(),
    history_user_id INTEGER,
    history_action VARCHAR(10)
);
```

## API Data Transfer

### Attendance Response
```json
{
  "person_id": 123,
  "display_name": "John S.",
  "instruments": ["fiddle", "tin whistle"],
  "attendance": "yes",
  "is_regular": true,
  "comment": "Bringing a friend"
}
```

### Check-in Request
```json
{
  "person_id": 123,
  "attendance": "yes"
}
```

### New Person Request
```json
{
  "first_name": "John",
  "last_name": "Smith",
  "instruments": ["fiddle", "tin whistle"],
  "attendance": "yes"
}