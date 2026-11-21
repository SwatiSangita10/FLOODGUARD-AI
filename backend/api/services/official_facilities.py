"""Curated facility entries transcribed from public Odisha government pages."""
from datetime import datetime, timezone


CMRF_SHELTER_SOURCE = "Chief Minister's Relief Fund, Odisha"
CMRF_SHELTER_URL = "https://cmrfodisha.gov.in/?q=node/5"
ODISHA_CONTACTS_SOURCE = "Government of Odisha emergency contacts"
ODISHA_CONTACTS_URL = "https://odisha.gov.in/en/contacts/emergency"
ODISHA_POLICE_SOURCE = "Odisha Police model police station list"
ODISHA_POLICE_URL = (
    "https://police.odisha.gov.in/en/sun/homepage/police-initiative"
)

SOURCE_REVIEWED_AT = datetime(2026, 11, 21, tzinfo=timezone.utc)

OFFICIAL_FACILITIES = (
    {
        "source_record_id": "cmrfodisha-shelter-1",
        "name": "CMRF shelter listing 1",
        "category": "multipurpose_cyclone_shelter",
        "state": "Odisha",
        "district": "Balasore",
        "block": "Bahanaga",
        "gram_panchayat": "Anji",
        "village": "Anji",
        "address": "A P High School",
        "source_name": CMRF_SHELTER_SOURCE,
        "source_url": CMRF_SHELTER_URL,
        "verification_status": "unverified",
        "last_verified_at": None,
    },
    {
        "source_record_id": "cmrfodisha-shelter-2",
        "name": "CMRF shelter listing 2",
        "category": "multipurpose_flood_shelter",
        "state": "Odisha",
        "district": "Baragada",
        "block": "Ambabhona",
        "gram_panchayat": "Bhainatura",
        "village": "Ganthiapali",
        "address": "Community place in the entrance of the village",
        "source_name": CMRF_SHELTER_SOURCE,
        "source_url": CMRF_SHELTER_URL,
        "verification_status": "unverified",
        "last_verified_at": None,
    },
    {
        "source_record_id": "cmrfodisha-shelter-5",
        "name": "CMRF shelter listing 5",
        "category": "multipurpose_cyclone_shelter",
        "state": "Odisha",
        "district": "Bhadrak",
        "block": "Basudevpur",
        "gram_panchayat": "Adhuan",
        "village": "Nandapur",
        "address": "Near Nandapur ME School",
        "source_name": CMRF_SHELTER_SOURCE,
        "source_url": CMRF_SHELTER_URL,
        "verification_status": "unverified",
        "last_verified_at": None,
    },
    {
        "source_record_id": "cmrfodisha-shelter-7",
        "name": "CMRF shelter listing 7",
        "category": "multipurpose_flood_shelter",
        "state": "Odisha",
        "district": "Bhadrak",
        "block": "Tihidi",
        "gram_panchayat": "Bahabalpur",
        "village": "Bahabalpur",
        "address": "NK High School Campus",
        "source_name": CMRF_SHELTER_SOURCE,
        "source_url": CMRF_SHELTER_URL,
        "verification_status": "unverified",
        "last_verified_at": None,
    },
    {
        "source_record_id": "odisha-police-model-station-jajpur-jajpur-road",
        "name": "Jajpur Road Model Police Station",
        "category": "police_station",
        "state": "Odisha",
        "district": "Jajpur",
        "source_name": ODISHA_POLICE_SOURCE,
        "source_url": ODISHA_POLICE_URL,
        "verification_status": "unverified",
        "last_verified_at": None,
    },
    {
        "source_record_id": "odisha-police-model-station-khordha-khordha",
        "name": "Khordha Model Police Station",
        "category": "police_station",
        "state": "Odisha",
        "district": "Khordha",
        "source_name": ODISHA_POLICE_SOURCE,
        "source_url": ODISHA_POLICE_URL,
        "verification_status": "unverified",
        "last_verified_at": None,
    },
    {
        "source_record_id": "odisha-police-model-station-puri-town",
        "name": "Town Model Police Station",
        "category": "police_station",
        "state": "Odisha",
        "district": "Puri",
        "source_name": ODISHA_POLICE_SOURCE,
        "source_url": ODISHA_POLICE_URL,
        "verification_status": "unverified",
        "last_verified_at": None,
    },
    {
        "source_record_id": "odisha-government-hospital-capital",
        "name": "Capital Hospital",
        "category": "hospital",
        "state": "Odisha",
        "district": None,
        "address": "Bhubaneswar",
        "latitude": 20.2600254,
        "longitude": 85.8232656,
        "contact_number": "0674-2391983",
        "source_name": ODISHA_CONTACTS_SOURCE,
        "source_url": ODISHA_CONTACTS_URL,
        "verification_status": "verified",
        "last_verified_at": SOURCE_REVIEWED_AT,
    },
)
