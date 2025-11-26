# Design Document

## Overview

The Personal Tune Management feature enables users to maintain private collections of tunes with learning status tracking, synchronization from thesession.org, and mobile-optimized browsing capabilities. The system extends the existing tune and person infrastructure to support personal tune collections with learning progress tracking.

## Architecture

### Database Schema Extensions

The feature requires a new `person_tune` table to link users to tunes with learning metadata:

```sql
CREATE TABLE person_tune (
    person_tune_id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    tune_id INTEGER NOT NULL REFERENCES tune(tune_id) ON DELETE CASCADE,
    learn_status VARCHAR(20) NOT NULL DEFAULT 'want to learn' 
        CHECK (learn_status IN ('want to learn', 'learning', 'learned')),
    heard_before_learning_count INTEGER DEFAULT 0,
    learned_date TIMESTAMPTZ, -- Set when status changes to 'learned'
    notes TEXT,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    UNIQUE(person_id, tune_id)
);
```

### API Integration

**thesession.org Integration**
- Tunebook API: `https://thesession.org/members/{user_id}/tunebook?format=json`
- Tune Details API: `https://thesession.org/tunes/{tune_id}?format=json`
- Sync process will use the thesession.org tune ID directly as our tune_id (since tune table uses thesession.org IDs as primary keys)
- For missing tunes, fetch complete metadata from tune details API including name, type, and tunebook count (following the pattern in `link_tune_ajax`)
- Create missing tune records with full metadata, then create `person_tune` records
- Error handling for API unavailability, rate limiting, and invalid tune IDs

### URL Structure

- `/my-tunes` - Main tune collection page
- `/my-tunes/sync` - thesession.org sync interface  
- `/my-tunes/add` - Manual tune addition form
- `/api/my-tunes/*` - RESTful API endpoints for tune management

## Components and Interfaces

### Frontend Components

**TuneCollectionView**
- Responsive grid/list layout optimized for mobile
- Real-time search filtering by tune name
- Filter dropdowns for tune type and learn_status
- Pagination for large collections
- Touch-friendly interaction elements

**TuneCard Component**
- Displays tune name, type, key, learn_status
- Shows heard_before_learning_count when > 0
- Quick status change buttons
- "+" button for incrementing heard count (want to learn status only)
- Link to tune details/thesession.org if available

**SyncInterface**
- Uses existing thesession_user_id from person table (no manual input needed)
- Progress indicator during sync
- Results summary with counts and errors
- Retry mechanism for failed syncs
- Option to update thesession_user_id if not set

**Context Menu Extension**
- Extends existing session_instance_detail context menu
- "Add to My Tunes" option for authenticated users if it's not already in their tunes
- "Increment Heard Count" option for authenticated users if it is already in their tunes

### Backend Services

**PersonTuneService**
- CRUD operations for person_tune records
- Learning status management with timestamp tracking
- Heard count increment functionality
- Bulk operations for sync processes

**ThesessionSyncService**
- HTTP client for thesession.org API
- Data transformation from thesession format to internal format
- Duplicate detection and merge logic
- Error handling and retry mechanisms

**TuneSearchService**
- Extends existing tune search for autocomplete
- Filters for personal collections
- Integration with session tune suggestions

## Data Models

### PersonTune Model
```python
class PersonTune:
    person_tune_id: int
    person_id: int
    tune_id: int  # References tune.tune_id (which is thesession.org ID)
    learn_status: str  # 'want to learn', 'learning', 'learned'
    heard_before_learning_count: int
    learned_date: Optional[datetime]
    notes: Optional[str]
    created_date: datetime
    last_modified_date: datetime
    
    # Relationships
    person: Person
    tune: Tune
```

### API Response Models
```python
class TuneCollectionResponse:
    tunes: List[PersonTuneDetail]
    total_count: int
    filtered_count: int
    filters_applied: Dict[str, Any]

class PersonTuneDetail:
    person_tune_id: int
    tune_name: str
    tune_type: str
    tune_key: Optional[str]
    learn_status: str
    heard_before_learning_count: int
    thesession_url: Optional[str]
    learned_date: Optional[str]
    notes: Optional[str]
```

## Error Handling

### API Error Responses
- 401 Unauthorized: User not authenticated
- 403 Forbidden: Accessing another user's data
- 404 Not Found: Tune or person_tune record not found
- 409 Conflict: Duplicate tune in collection
- 422 Unprocessable Entity: Invalid learn_status or other validation errors
- 503 Service Unavailable: thesession.org API unavailable

### Frontend Error Handling
- Network connectivity issues during sync
- Invalid thesession.org user IDs
- API rate limiting from thesession.org
- Graceful degradation when offline
- User-friendly error messages with retry options

### Data Integrity
- Foreign key constraints ensure valid person and tune references
- Check constraints validate learn_status values
- Unique constraints prevent duplicate person-tune combinations
- Cascade deletes maintain referential integrity

## Testing Strategy

### Unit Tests
- PersonTuneService CRUD operations
- ThesessionSyncService API integration (with mocked responses)
- Data validation and constraint enforcement
- Learning status transition logic
- Heard count increment functionality

### Integration Tests
- End-to-end sync process from thesession.org
- Context menu integration with session_instance_detail
- Authentication and authorization flows
- Database transaction handling
- API endpoint responses and error codes

### Frontend Tests
- Mobile responsiveness across device sizes
- Search and filtering functionality
- Touch interactions and gesture handling
- Context menu behavior
- Real-time updates and state management

### Performance Tests
- Large tune collection rendering (1000+ tunes)
- Search performance with filtering
- Sync performance with large tunebooks
- Mobile performance on slower devices
- Database query optimization

## Security Considerations

### Authentication & Authorization
- All personal tune endpoints require authentication
- Users can only access their own tune collections
- System admins have read-only access for support
- Session-based authentication using existing Flask-Login system

### Data Privacy
- Personal tune collections are private by default
- No sharing or public visibility features
- Secure handling of thesession.org user credentials
- GDPR compliance for personal data storage

### Input Validation
- Sanitize all user inputs for XSS prevention
- Validate thesession.org user IDs format
- Rate limiting on sync operations
- SQL injection prevention through parameterized queries

## Mobile Optimization

### Responsive Design
- Mobile-first CSS approach
- Touch-friendly button sizes (minimum 44px)
- Optimized typography for small screens
- Efficient use of screen real estate

### Performance
- Lazy loading for large tune lists
- Optimized images and assets
- Minimal JavaScript bundle size
- Efficient API pagination

### User Experience
- Swipe gestures for navigation
- Pull-to-refresh for sync updates
- Offline capability indicators
- Fast search with debounced input

## Implementation Phases

### Phase 1: Core Infrastructure
- Database schema creation
- Basic PersonTune model and service
- Authentication integration
- Simple CRUD API endpoints

### Phase 2: Web Interface
- Basic tune collection page
- Search and filtering functionality
- Manual tune addition
- Learning status management

### Phase 3: thesession.org Integration
- Sync service implementation
- Sync interface and progress tracking
- Error handling and retry logic
- Bulk import capabilities

### Phase 4: Mobile Optimization
- Responsive design improvements
- Touch interaction enhancements
- Performance optimizations
- Context menu integration

### Phase 5: Advanced Features
- Heard count tracking
- Enhanced filtering options
- Export capabilities
- Analytics and progress tracking

Do the database schema updates as a first task by itself.