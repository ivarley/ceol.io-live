"""
Test data generators and fixtures for comprehensive testing.

This module provides factory functions and realistic sample data
for testing all aspects of the Irish music session application.
"""

import factory
import factory.fuzzy
from datetime import datetime, date, timedelta
import random
import bcrypt
from faker import Faker

fake = Faker()

# Traditional Irish tune types (must match database CHECK constraint exactly)
TUNE_TYPES = ['Reel', 'Jig', 'Slip Jig', 'Hornpipe', 'Polka', 'Slide', 'Waltz', 'Barndance', 
              'Strathspey', 'Three-Two', 'Mazurka', 'March']

# Common Irish tune names (realistic examples)
IRISH_TUNE_NAMES = [
    "The Butterfly", "Morrison's Jig", "The Musical Priest", "Out on the Ocean",
    "The Banshee", "The Kesh Jig", "The Foggy Dew", "The Irish Rover",
    "Drowsy Maggie", "The Silver Spear", "The Tailor's Twist", "Cooley's Reel",
    "The Blackbird", "Star of the County Down", "The Wild Mountain Thyme",
    "The Humours of Whiskey", "The Rights of Man", "The Siege of Ennis",
    "The Trip to Sligo", "Carolan's Concerto", "The Ash Plant", "The Road to Lisdoonvarna",
    "The Fisherman's Hornpipe", "The Cook in the Kitchen", "The Frost is All Over",
    "Napoleon Crossing the Alps", "The Congress Reel", "Rakish Paddy",
    "The Boys of Malin", "Planxty Irwin", "The Bucks of Oranmore",
    "Lord McDonald's Reel", "The Moving Bog", "The Pipe on the Hob",
    "The Galway Hornpipe", "Jenny's Chickens", "The Earl's Chair",
    "The Maid Behind the Bar", "Whiskey in the Jar", "The Reconciliation Reel"
]

# US cities where Irish sessions commonly occur
SESSION_CITIES = [
    ('New York', 'NY'), ('Boston', 'MA'), ('Chicago', 'IL'), ('San Francisco', 'CA'),
    ('Philadelphia', 'PA'), ('Washington', 'DC'), ('Seattle', 'WA'), ('Portland', 'OR'),
    ('Austin', 'TX'), ('Nashville', 'TN'), ('Atlanta', 'GA'), ('Denver', 'CO'),
    ('Milwaukee', 'WI'), ('Minneapolis', 'MN'), ('Cleveland', 'OH'), ('Pittsburgh', 'PA'),
    ('Baltimore', 'MD'), ('Richmond', 'VA'), ('Charleston', 'SC'), ('Savannah', 'GA')
]

# Common venue types for Irish sessions
VENUE_TYPES = [
    "Irish Pub", "Celtic Pub", "Traditional Pub", "Music Hall", "Community Center",
    "Library", "Coffee House", "Restaurant", "Hotel", "Cultural Center"
]

# Realistic timezone mappings
TIMEZONE_MAP = {
    ('New York', 'NY'): 'America/New_York',
    ('Boston', 'MA'): 'America/New_York', 
    ('Philadelphia', 'PA'): 'America/New_York',
    ('Washington', 'DC'): 'America/New_York',
    ('Atlanta', 'GA'): 'America/New_York',
    ('Chicago', 'IL'): 'America/Chicago',
    ('Austin', 'TX'): 'America/Chicago',
    ('Nashville', 'TN'): 'America/Chicago',
    ('Milwaukee', 'WI'): 'America/Chicago',
    ('Minneapolis', 'MN'): 'America/Chicago',
    ('Denver', 'CO'): 'America/Denver',
    ('San Francisco', 'CA'): 'America/Los_Angeles',
    ('Seattle', 'WA'): 'America/Los_Angeles',
    ('Portland', 'OR'): 'America/Los_Angeles'
}


class PersonFactory(factory.Factory):
    """Factory for generating realistic person data."""
    
    class Meta:
        model = dict
    
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name') 
    email = factory.LazyAttribute(lambda obj: f"{obj.first_name.lower()}.{obj.last_name.lower()}@example.com")
    city = factory.LazyFunction(lambda: random.choice(SESSION_CITIES)[0])
    state = factory.LazyAttribute(lambda obj: next((state for city, state in SESSION_CITIES if city == obj.city), 'NY'))
    country = 'USA'
    thesession_user_id = factory.fuzzy.FuzzyInteger(1000, 99999)
    sms_number = factory.Faker('phone_number')


class UserAccountFactory(factory.Factory):
    """Factory for generating user account data."""
    
    class Meta:
        model = dict
    
    username = factory.LazyAttribute(lambda obj: f"{fake.user_name()}{random.randint(1, 999)}")
    user_email = factory.Faker('email')
    hashed_password = factory.LazyFunction(
        lambda: bcrypt.hashpw('testpassword123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    )
    timezone = factory.LazyFunction(lambda: random.choice(list(TIMEZONE_MAP.values())))
    is_active = True
    is_system_admin = factory.fuzzy.FuzzyChoice([True, False], probability_true=0.1)  # 10% admins
    email_verified = factory.fuzzy.FuzzyChoice([True, False], probability_true=0.9)  # 90% verified
    auto_save_tunes = factory.fuzzy.FuzzyChoice([True, False], probability_true=0.3)  # 30% use auto-save


class SessionFactory(factory.Factory):
    """Factory for generating realistic Irish music session data."""
    
    class Meta:
        model = dict
    
    name = factory.LazyFunction(lambda: f"{random.choice(SESSION_CITIES)[0]} Irish Session")
    path = factory.LazyAttribute(lambda obj: obj.name.lower().replace(' ', '-').replace("'", ""))
    
    city = factory.LazyFunction(lambda: random.choice(SESSION_CITIES)[0])
    state = factory.LazyAttribute(lambda obj: next((state for city, state in SESSION_CITIES if city == obj.city), 'NY'))
    country = 'USA'
    
    location_name = factory.LazyAttribute(lambda obj: f"The {random.choice(['Celtic', 'Irish', 'Shamrock', 'Clover', 'Harp'])} {random.choice(VENUE_TYPES)}")
    location_website = factory.LazyAttribute(lambda obj: f"https://{obj.location_name.lower().replace(' ', '').replace('the', '')}.com")
    location_phone = factory.Faker('phone_number')
    location_street = factory.Faker('street_address')
    
    timezone = factory.LazyAttribute(lambda obj: TIMEZONE_MAP.get((obj.city, obj.state), 'America/New_York'))
    
    comments = factory.LazyFunction(
        lambda: random.choice([
            "Weekly traditional Irish music session. All levels welcome!",
            "Bring your instrument and join us for traditional tunes.",
            "Every Tuesday night - slow session, beginners encouraged.",
            "Fast-paced session for experienced players.",
            "Family-friendly session with teaching component.",
            "Session focuses on County Clare repertoire.",
            "Sliabh Notes session - intermediate to advanced players."
        ])
    )
    
    unlisted_address = factory.fuzzy.FuzzyChoice([True, False], probability_true=0.1)  # 10% unlisted
    
    initiation_date = factory.LazyFunction(
        lambda: fake.date_between(start_date='-5y', end_date='-1y')
    )
    termination_date = factory.LazyFunction(
        lambda: None if random.random() > 0.1 else fake.date_between(start_date='-1y', end_date='today')
    )  # 10% terminated sessions
    
    recurrence = factory.fuzzy.FuzzyChoice([
        'weekly', 'biweekly', 'monthly', 'first-tuesday', 'last-friday', 'irregular'
    ])


class TuneFactory(factory.Factory):
    """Factory for generating Irish tune data."""
    
    class Meta:
        model = dict
    
    tune_id = factory.Sequence(lambda n: n + 1000)  # Start at 1000 to avoid conflicts
    name = factory.LazyFunction(lambda: random.choice(IRISH_TUNE_NAMES))
    tune_type = factory.LazyFunction(lambda: random.choice(TUNE_TYPES))
    tunebook_count_cached = factory.fuzzy.FuzzyInteger(1, 300)
    tunebook_count_cached_date = factory.LazyFunction(
        lambda: fake.date_between(start_date='-1y', end_date='today')
    )


class SessionInstanceFactory(factory.Factory):
    """Factory for generating session instance data."""
    
    class Meta:
        model = dict
    
    date = factory.LazyFunction(lambda: fake.date_between(start_date='-6m', end_date='+1m'))
    start_time = factory.LazyFunction(
        lambda: fake.time_object().replace(
            hour=random.choice([19, 20, 21]),  # 7-9 PM typical start times
            minute=random.choice([0, 15, 30]),
            second=0,
            microsecond=0
        )
    )
    end_time = factory.LazyAttribute(
        lambda obj: datetime.combine(date.today(), obj.start_time) + timedelta(hours=random.choice([2, 3, 4]))
    )
    
    is_cancelled = factory.fuzzy.FuzzyChoice([True, False], probability_true=0.05)  # 5% cancelled
    
    comments = factory.LazyFunction(
        lambda: random.choice([
            "Great turnout tonight!",
            "Lots of new faces at the session.",
            "Focused on slow airs and hornpipes.",
            "Brilliant session with visiting musicians from Ireland.",
            "Small but enthusiastic crowd.",
            "Session ran late - lots of energy!",
            "Teaching session for beginners.",
            "Special guest musician led several sets.",
            None, None, None  # 60% have no comments
        ])
    )
    
    location_override = factory.LazyFunction(
        lambda: None if random.random() > 0.1 else f"Temporarily at {fake.company()}"
    )  # 10% have location overrides
    
    log_complete_date = factory.LazyFunction(
        lambda: None if random.random() > 0.7 else fake.date_time_between(start_date='-1m', end_date='now')
    )  # 70% have complete logs


class SessionInstanceTuneFactory(factory.Factory):
    """Factory for generating session instance tune data."""
    
    class Meta:
        model = dict
    
    name = factory.LazyFunction(lambda: random.choice(IRISH_TUNE_NAMES))
    order_number = factory.Sequence(lambda n: n + 1)
    continues_set = factory.LazyFunction(lambda: random.choice([True, False, False]))  # 33% continue sets
    
    played_timestamp = factory.LazyFunction(
        lambda: fake.date_time_between(start_date='-6m', end_date='now')
    )
    inserted_timestamp = factory.LazyAttribute(lambda obj: obj.played_timestamp + timedelta(minutes=random.randint(0, 30)))
    
    key_override = factory.LazyFunction(
        lambda: None if random.random() > 0.2 else random.choice(['D', 'G', 'A', 'C', 'F', 'Bb', 'Eb'])
    )  # 20% have key overrides
    
    setting_override = factory.LazyFunction(
        lambda: None if random.random() > 0.1 else random.randint(1, 5)
    )  # 10% have setting overrides


def generate_sample_people(count=50):
    """Generate sample person records."""
    return [PersonFactory() for _ in range(count)]


def generate_sample_users(count=30):
    """Generate sample user account records."""
    return [UserAccountFactory() for _ in range(count)]


def generate_sample_sessions(count=20):
    """Generate sample session records."""
    sessions = []
    used_names = set()
    used_paths = set()
    
    for _ in range(count):
        session = SessionFactory()
        
        # Ensure unique names and paths
        base_name = session['name']
        base_path = session['path']
        counter = 1
        
        while session['name'] in used_names or session['path'] in used_paths:
            session['name'] = f"{base_name} {counter}"
            session['path'] = f"{base_path}-{counter}"
            counter += 1
        
        used_names.add(session['name'])
        used_paths.add(session['path'])
        sessions.append(session)
    
    return sessions


def generate_sample_tunes(count=100):
    """Generate sample tune records."""
    tunes = []
    used_names = set()
    
    for i in range(count):
        tune = TuneFactory()
        tune['tune_id'] = 1000 + i  # Ensure unique IDs
        
        # Ensure unique names
        base_name = tune['name']
        counter = 1
        
        while tune['name'] in used_names:
            tune['name'] = f"{base_name} #{counter}"
            counter += 1
        
        used_names.add(tune['name'])
        tunes.append(tune)
    
    return tunes


def generate_sample_session_instances(session_ids, count_per_session=10):
    """Generate sample session instances for given session IDs."""
    instances = []
    
    for session_id in session_ids:
        for _ in range(count_per_session):
            instance = SessionInstanceFactory()
            instance['session_id'] = session_id
            instances.append(instance)
    
    return instances


def generate_sample_session_instance_tunes(instance_ids, tune_ids, tunes_per_instance=8):
    """Generate sample session instance tunes."""
    instance_tunes = []
    
    for instance_id in instance_ids:
        selected_tunes = random.sample(tune_ids, min(tunes_per_instance, len(tune_ids)))
        
        for order, tune_id in enumerate(selected_tunes, 1):
            tune_entry = SessionInstanceTuneFactory()
            tune_entry['session_instance_id'] = instance_id
            tune_entry['tune_id'] = tune_id
            tune_entry['order_number'] = order
            
            # Adjust continues_set logic for first tune
            if order == 1:
                tune_entry['continues_set'] = False
            
            instance_tunes.append(tune_entry)
    
    return instance_tunes


def generate_realistic_test_dataset():
    """Generate a complete realistic test dataset."""
    # Generate people and users
    people = generate_sample_people(50)
    users = generate_sample_users(30)
    
    # Generate sessions and tunes
    sessions = generate_sample_sessions(20)
    tunes = generate_sample_tunes(100)
    
    # Generate session instances
    session_ids = list(range(1, len(sessions) + 1))
    instances = generate_sample_session_instances(session_ids, count_per_session=12)
    
    # Generate session instance tunes
    instance_ids = list(range(1, len(instances) + 1))
    tune_ids = [tune['tune_id'] for tune in tunes]
    instance_tunes = generate_sample_session_instance_tunes(instance_ids, tune_ids)
    
    return {
        'people': people,
        'users': users,
        'sessions': sessions,
        'tunes': tunes,
        'session_instances': instances,
        'session_instance_tunes': instance_tunes
    }


def generate_edge_case_data():
    """Generate edge case test data."""
    return {
        'empty_values': {
            'person': {'first_name': '', 'last_name': '', 'email': '', 'city': ''},
            'tune': {'name': '', 'tune_type': ''},
            'session': {'name': '', 'path': '', 'city': ''}
        },
        
        'boundary_values': {
            'very_long_name': 'A' * 255,
            'very_short_name': 'X',
            'special_characters': "O'Brien's Céilí & Seisiún",
            'unicode_characters': "Tánaiste's Taoiseach Céilí",
            'sql_injection_attempt': "'; DROP TABLE session; --",
            'xss_attempt': '<script>alert("xss")</script>'
        },
        
        'date_edge_cases': {
            'far_past': date(1900, 1, 1),
            'far_future': date(2099, 12, 31),
            'leap_year': date(2024, 2, 29),
            'year_boundary': date(2023, 12, 31)
        },
        
        'numeric_edge_cases': {
            'zero': 0,
            'negative': -1,
            'large_number': 999999,
            'float_as_int': 123.0
        }
    }


# Pre-generated sample data for quick access
SAMPLE_IRISH_SESSIONS = [
    {
        'name': 'Dublin Pub Weekly Session',
        'path': 'dublin-pub-weekly',
        'city': 'Boston',
        'state': 'MA',
        'location_name': 'The Dublin Pub',
        'timezone': 'America/New_York',
        'comments': 'Traditional session every Thursday. All levels welcome!'
    },
    {
        'name': 'Celtic Music Society',
        'path': 'celtic-music-society',
        'city': 'Chicago',
        'state': 'IL',
        'location_name': 'Irish Cultural Center',
        'timezone': 'America/Chicago',
        'comments': 'Monthly session focusing on historical repertoire.'
    },
    {
        'name': 'Sligo Session',
        'path': 'sligo-session',
        'city': 'San Francisco',
        'state': 'CA',
        'location_name': 'The Celtic House',
        'timezone': 'America/Los_Angeles',
        'comments': 'Fast-paced session for experienced players.'
    }
]

SAMPLE_TUNE_SETS = [
    # Reel set
    ['The Butterfly', 'Out on the Ocean', 'The Musical Priest'],
    # Jig set  
    ['Morrison\'s Jig', 'The Kesh Jig', 'Drowsy Maggie'],
    # Hornpipe set
    ['The Fisherman\'s Hornpipe', 'The Galway Hornpipe', 'Rights of Man'],
    # Slip jig set
    ['The Butterfly', 'The Road to Lisdoonvarna', 'Banish Misfortune']
]

SAMPLE_USER_PROFILES = [
    {
        'username': 'fiddler_jane',
        'first_name': 'Jane',
        'last_name': 'O\'Sullivan',
        'email': 'jane.osullivan@example.com',
        'city': 'Boston',
        'state': 'MA',
        'timezone': 'America/New_York'
    },
    {
        'username': 'bodhran_master',
        'first_name': 'Mike',
        'last_name': 'Murphy',
        'email': 'mike.murphy@example.com', 
        'city': 'Chicago',
        'state': 'IL',
        'timezone': 'America/Chicago'
    },
    {
        'username': 'whistle_wizard',
        'first_name': 'Sarah',
        'last_name': 'Kelly',
        'email': 'sarah.kelly@example.com',
        'city': 'Austin',
        'state': 'TX',
        'timezone': 'America/Chicago'
    }
]