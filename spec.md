FLOODGUARD AI – FINAL PROJECT SPECIFICATION

Project Name: FLOODGUARD AI

Tagline: Predict. Prepare. Protect.

Project Category: AI, Machine Learning, Climate Technology and Disaster Management

Hackathon Track: Track 2 – Climate, Resource Infrastructure & Global Supply Resilience

Project Type: Full-Stack AI-Powered Web Application

Initial Pilot Location: Bhubaneswar, Odisha, India

Version: 2.0 – Final Specification



1. PROJECT OVERVIEW

FLOODGUARD AI is an AI-powered hyperlocal flood monitoring, risk assessment, early warning and emergency response platform.

The platform aims to help people understand potential flood situations, identify affected locations, access emergency resources and make informed decisions during heavy rainfall and flooding.

It combines weather information, geographical data, historical flood information and community-submitted incident reports to provide location-based flood risk insights.

The application features an interactive flood monitoring dashboard, AI-assisted flood risk assessment, citizen reporting, safe route suggestions, emergency resource management and an AI-powered Emergency Relief Companion.

Its primary objective is to bridge the gap between environmental information and practical emergency assistance.

2. PROBLEM STATEMENT

Flooding and urban waterlogging create serious problems for communities, particularly during heavy monsoon rainfall.

Residents often struggle to find reliable answers to important questions:

- Is my area at risk of flooding?
- Which nearby locations are experiencing waterlogging?
- Which roads have been affected?
- Where can I find an alternative route?
- Where are the nearest emergency shelters?
- What should I do during a flood emergency?

Traditional weather applications mainly provide general weather forecasts and may not provide sufficient neighbourhood-level incident information or integrated emergency assistance.

There is a need for an accessible platform that connects environmental monitoring, community reporting, risk awareness and emergency guidance.

3. PROPOSED SOLUTION

FLOODGUARD AI proposes a unified intelligent platform that helps communities monitor potential flood risks and access emergency information.

The platform will:

1. Collect available weather and precipitation information.
2. Analyse environmental and geographical indicators.
3. Estimate potential flood risk.
4. Display risk information on an interactive map.
5. Allow citizens to report waterlogging and flooding.
6. Help users assess routes alongside available verified flood reports and weather risk data.
7. Display manually managed emergency resource records and official reference links.
8. Provide an in-app alert centre for available backend alert records and official source links.
9. Provide AI-powered emergency guidance in multiple languages.

4. PROJECT OBJECTIVES

- Improve local flood-risk awareness.
- Make environmental information understandable.
- Support early preparedness through risk indicators.
- Encourage community participation through citizen reporting.
- Help users identify potentially affected roads.
- Improve access to emergency resources.
- Provide multilingual AI-powered safety assistance.
- Support informed community-level emergency decisions.

5. TARGET USERS

- Residents of flood-prone communities.
- Local authorities and disaster management teams.
- Emergency response volunteers.
- Community organisations.
- Travellers and commuters.
- People requiring emergency assistance.

6. CORE MODULES AND FUNCTIONAL REQUIREMENTS

MODULE 1: AI FLOOD RISK PREDICTION

Purpose: Estimate potential flood risk using available environmental information.

Features:

- Analyse current rainfall information.
- Analyse precipitation forecasts.
- Consider historical flood information where available.
- Incorporate available geographical and elevation indicators.
- Display estimated flood-risk levels.
- Explain the factors contributing to a risk assessment.

Risk categories:

- Low Risk
- Moderate Risk
- High Risk

Initial implementation:
A transparent rule-based risk-scoring engine using available indicators.

Future enhancement:
Machine learning-based prediction using suitable historical datasets and validated models.

Important: Risk estimates must not be represented as confirmed flooding or scientifically validated street-level predictions without supporting data.

MODULE 2: CITIZEN FLOOD REPORTING

Purpose: Allow people to report local flooding and waterlogging.

Features:

- Submit a flood or waterlogging report.
- Select or provide a geographical location.
- Upload an optional incident photograph.
- Add a description.
- Select an incident category.
- Record the submission date and time.
- Track report verification status.

Report statuses:

- Pending Verification
- Verified
- Rejected

Administrators can review and verify submitted reports.

Only verified reports should be presented as confirmed incidents.

MODULE 3: SAFE ROUTE FINDER

Purpose: Provide informational road routes together with available, clearly qualified flood and weather information.

Features:

- Search for a starting place and destination using Open-Meteo geocoding.
- Request the user's current location only after an explicit user action and browser permission.
- Display OSRM driving geometry, provider-estimated distance and travel time, and provider alternatives where available.
- Display verified flood reports within 500 metres of the route; pending and rejected reports are excluded.
- Reuse the weather service and preliminary risk assessment at up to three points on the route.
- Classify route risk as Low, Moderate, High or Unknown and explain the evidence.
- Save minimal route assessment history to the `route_assessments` MongoDB collection when MongoDB is available.

Important:
OSRM geometry and estimates do not verify live road closures. Weather data is model-based and sampled at only a few points; verified reports can be incomplete or absent. Only the 100 newest verified reports are checked; when more reports exist and none are near the route, classify risk as Unknown. A lack of reports does not mean a road is safe. Alternatives are not separately risk-assessed. Do not claim road flooding or closures without reliable verified data, and do not guarantee a route is safe. If route evidence is incomplete, show Unknown or explain the missing source. Use official evacuation guidance and never enter floodwater.

Endpoint: `POST /api/routes/safe-route/` accepts `{ "origin": { "latitude": 20.2961, "longitude": 85.8245 }, "destination": { "latitude": 19.8135, "longitude": 85.8312 } }`. The public OSRM demo service may impose usage limits; no additional API key or environment variable is used. When MongoDB is unavailable, route history is explicitly marked unsaved.

MODULE 4: EMERGENCY RESOURCES

Purpose: Make emergency information accessible from one dashboard.

Features:

- Display manually managed resource records with name/location search and category, district and verification filters.
- Show address, district, source URL and verification timestamp where available.
- Show a call action only for valid numbers on verified resource records.
- Show a map link only when verified coordinates are available.
- Display official emergency reference links even when MongoDB or the manually managed directory is unavailable.

Resource categories:

- Hospitals and medical centres
- Emergency shelters and relief centres
- Fire and rescue services
- Police stations
- Disaster management offices
- Ambulance services
- Emergency helplines

Resource entries are stored in the `emergency_resources` MongoDB collection and maintained by authenticated Django staff. An empty collection remains empty; the application does not seed demonstration facilities. Unverified records are labelled and do not expose coordinates, call actions or operating hours. Published hours do not prove a facility is currently open, and the application does not confirm capacity or contact a service. The OSDMA office contact numbers shown from its official page are not represented as confirmed emergency hotlines. SRC Odisha, Odisha Government emergency directory and NDMA SACHET are reference links only when their page contents cannot be verified automatically.

API: `GET /api/resources/`, `GET /api/resources/<resource_id>/`, and `GET /api/resources/categories/`. The list supports category, district, search, verification-status and pagination filters. Staff-only writes use `POST /api/resources/` and `PATCH /api/resources/<resource_id>/`. MongoDB failures return an explicit service-unavailable error.

MODULE 5: AI FLOOD RISK MONITORING DASHBOARD

Purpose: Present flood-related information through an interactive dashboard.

Dashboard components:

- Open-Meteo weather and rainfall summary.
- Preliminary weather-based risk indicator when a location is selected.
- Active backend alerts and real unread count.
- Latest reports marked verified in FLOODGUARD.
- Resource records matching the selected place. This is a text search, not a distance/proximity calculation.

The dashboard does not display a fabricated map layer or seeded alert, report or resource metrics. Pending/unverified reports are excluded from the verified-report summary. Use distinct visual indicators for risk and alert severity.

The dashboard should distinguish estimated risks from verified incidents.

MODULE 6: AI EMERGENCY RELIEF COMPANION

Purpose: Provide people with accessible, multilingual AI-powered emergency assistance.

This is an important differentiating feature of FLOODGUARD AI.

Features:

1. AI Emergency Chatbot

- Allow users to ask emergency-related questions.
- Provide general flood safety instructions.
- Explain risk warnings.
- Answer questions about platform features.

2. Location-Based Assistance

- Link to the manually maintained emergency resource directory.
- Search resources by selected place; this is not a proximity calculation.
- Use browser geolocation only after a deliberate user action in the Safe Route Finder.

3. Flood Safety Guidance

- Explain what to do before, during and after flooding.
- Provide basic preparedness recommendations.
- Explain potential hazards.

4. Risk Explanation

- Explain why a particular area has a specific risk category.
- Describe the environmental indicators used.
- Clarify limitations of the available data.

5. Multilingual Support

- English
- Hindi
- Odia

6. Emergency Quick Actions

- Find Emergency Shelters
- Get Safety Instructions
- Find Emergency Contacts
- Check Local Flood Reports
- Find Alternative Routes

7. Voice Assistance – Future Enhancement

- Voice input.
- Speech-based responses.
- Improved accessibility for users who cannot easily type.

Technology: Gemini API integrated through the Django backend.

Safety requirements:

- Never invent live emergency information.
- Do not provide unverified shelter availability.
- Do not guarantee route safety.
- Prioritise official emergency services when users face immediate danger.
- Never delay urgent assistance by requiring chatbot interaction.

MODULE 7: FLOOD ALERTS AND NOTIFICATION CENTRE

Purpose: Present available alert records with their source, severity, affected location, publication time and browser-scoped read state.

Alert sources:

- Staff-managed official notices with an approved government source URL and verification metadata.
- Open-Meteo weather assessments, always labelled Advisory and never promoted to an official Warning or Emergency.
- Recent verified FLOODGUARD reports that meet the documented high-severity or nearby-report criteria, labelled as community reports and not government alerts.

Severity categories are Information (general preparedness), Advisory (potentially concerning conditions such as weather estimates), Warning (verified significant risk information) and Emergency (verified official government source plus publication timestamp). Weather estimates are never automatically promoted to Warning or Emergency. Empty results remain empty; a missing official feed is not replaced with generated warnings. There is no live OSDMA, SRC Odisha, Odisha Government or SACHET feed, web scraping, SMS, WhatsApp, push delivery or emergency dispatch.

Endpoints: `GET /api/alerts/`, `GET /api/alerts/<alert_id>/`, `POST /api/alerts/mark-read/`, and staff-only `POST /api/alerts/`. Listing supports severity, source, verification status, district, search and pagination filters. Read receipts are stored in the `user_notifications` MongoDB collection using a random browser-scoped UUID, not personal identity. MongoDB or provider failures are surfaced explicitly.

7. TECHNOLOGY STACK

Layer| Technology
Frontend| React.js + Vite
Styling| CSS
Backend| Python + Django REST Framework
Database| MongoDB Atlas using PyMongo
AI Assistant| Gemini API
Risk Analysis| Python
Future ML| Scikit-learn
Data Processing| Pandas, NumPy
Weather API| Open-Meteo
Maps| React Leaflet + OpenStreetMap tiles; OSRM driving routes; OpenStreetMap resource-location links
Charts| Chart.js
Deployment| Vercel + Render

8. EXTERNAL DATA SOURCES

Open-Meteo
Weather, rainfall and precipitation forecast information.

Website: https://open-meteo.com/

OpenStreetMap
Geographical and road network information.

Website: https://www.openstreetmap.org/

ISRO
Relevant satellite and earth observation resources.

Website: https://www.isro.gov.in/

NDMA
Disaster management information and official guidance.

Website: https://ndma.gov.in/

Odisha official emergency reference links:

- OSDMA: https://www.osdma.org/emergency-contacts/
- Special Relief Commissioner, Odisha: https://srcodisha.nic.in/contact_sdma.php
- Government of Odisha emergency contacts: https://odisha.gov.in/en/contacts/emergency
- NDMA SACHET: https://sachet.ndma.gov.in/

These are official reference links, not a live integrated alert feed. Do not treat an unavailable/unread page as verification of its current numbers or notices. Weather-based advisories are sourced from Open-Meteo and are not official alerts; community alerts come only from verified FLOODGUARD reports and are labelled separately.

Historical Flood Datasets
Suitable publicly available datasets for future risk model development.

All sources must be appropriately attributed. Data availability, freshness and geographical coverage must be checked before using information in the application.

9. DATABASE DESIGN

Initial MongoDB collections:

Users

- user_id
- name
- email
- role

FloodReports

- report_id
- user_id
- latitude
- longitude
- description
- image_url
- incident_type
- verification_status
- created_at

WeatherRecords

- location
- latitude
- longitude

RouteAssessments

- origin and destination coordinates
- assessed_at
- route distance and duration
- risk classification and factors
- routing and weather source names
- temperature
- precipitation
- forecast
- recorded_at

RiskAssessments

- location
- risk_score
- risk_level
- assessment_factors
- assessed_at

EmergencyResources

- resource_id
- name and category
- address
- district and optional verified coordinates
- contact number and optional published hours
- official source URL and verification timestamp
- verification_status

FloodAlerts

- alert_id, title, description and severity
- affected location and district
- source type, source URL and verification status
- source publication, creation, and optional expiry timestamps
- active/resolved/expired status

UserNotifications

- browser-scoped random client UUID
- alert_id
- read_at and expiry timestamp

ChatHistory

- conversation_id
- user_id
- message
- response
- language
- created_at

Store only necessary information and protect user data.

10. USER INTERFACE AND DESIGN REQUIREMENTS

Design direction: Modern, professional disaster-management dashboard.

Visual theme:

- Dark navy background.
- Cyan and blue highlights.
- Red for critical warnings.
- Yellow for moderate warnings.
- Green for low-risk indicators.

Main navigation:

1. Dashboard
2. Emergency Resources
3. Flood Alerts
4. Citizen Flood Reporting
5. Safe Route Finder
6. AI Flood Risk Prediction
7. AI Emergency Assistant

UI requirements:

- Responsive desktop and mobile layouts.
- Clear navigation.
- Interactive maps.
- Easy-to-understand risk indicators.
- Readable emergency notifications.
- Consistent design across all modules.
- Accessible AI assistance.

The AI Emergency Assistant should be accessible from the main navigation and through a floating assistant button.

11. MVP DEVELOPMENT SCOPE

The first hackathon version will include:

1. Functional React dashboard.
2. Django REST API.
3. MongoDB integration.
4. Open-Meteo weather integration.
5. Rule-based flood risk assessment.
6. Interactive flood map.
7. Citizen flood reporting.
8. Report verification.
9. Basic safe route suggestions.
10. Emergency resource dashboard.
11. Gemini-powered AI Emergency Relief Companion.
12. English, Hindi and Odia language support.

All core modules should be connected and functional.

12. FEATURES OUTSIDE THE INITIAL MVP

To maintain a realistic development scope, the following are excluded from the first version:

- Dedicated Android and iOS applications.
- Advanced deep learning models.
- IoT water-level monitoring hardware.
- Automated rescue vehicle dispatch.
- Direct government control-room integration.
- Nationwide real-time flood monitoring.
- Automated emergency response.

These may be considered in future versions.

13. SYSTEM ARCHITECTURE

Frontend Layer
React.js provides the user interface, dashboard, maps, reporting forms, route finder and AI chat interface.

Backend Layer
Django REST Framework manages API requests, risk calculations, report verification, emergency resources and AI assistant communication.

Database Layer
MongoDB Atlas stores configured flood reports, risk assessments, emergency resources, flood alerts, browser-scoped read receipts, and other application data. Missing MongoDB data is surfaced as unavailable; no fake resources or alerts are inserted.

External Services

- Open-Meteo for weather information.
- OpenStreetMap for maps and road information.
- Gemini API for AI assistance.
- Relevant public datasets for future model development.

Application Flow

1. User accesses the React application.
2. Frontend communicates with the Django backend.
3. Backend retrieves weather and geographical information.
4. Risk assessment logic analyses available indicators.
5. Citizen reports are processed and stored.
6. Verified information is displayed on the dashboard.
7. AI assistant receives relevant application context when answering user questions.
8. Results are returned to the frontend.

14. NON-FUNCTIONAL REQUIREMENTS

Performance

- Responsive user interface.
- Efficient API requests.
- Optimised map loading.

Security

- Environment variables for API keys.
- Secure backend configuration.
- Input validation.
- Protected administrative operations.
- Appropriate user-data protection.

Reliability

- Handle unavailable external APIs.
- Display timestamps for time-sensitive information.
- Clearly identify missing or stale data.
- Avoid displaying unverified reports as confirmed incidents.
- Distinguish official alerts, Open-Meteo advisories and verified community reports.
- Do not imply emergency dispatch, facility opening status, or guaranteed route safety.

Usability

- Simple navigation.
- Mobile-friendly interface.
- Multilingual assistance.
- Clear warning messages.
- Accessible emergency information.

15. EXPECTED IMPACT

FLOODGUARD AI aims to:

- Improve flood-risk awareness.
- Support community participation.
- Make emergency information easier to access.
- Help people understand potential hazards.
- Support informed route planning.
- Improve local disaster preparedness.
- Connect environmental information with practical community assistance.

16. FUTURE SCOPE

Potential future enhancements:

- ML-based flood prediction using validated datasets.
- Satellite-based flood detection.
- IoT water-level sensors.
- Advanced multilingual voice assistant.
- SMS and WhatsApp notifications.
- Integration with official disaster-management systems.
- Expanded geographical coverage.
- Improved emergency resource coordination.

17. PROJECT SUCCESS CRITERIA

The MVP will be considered successful when:

1. Frontend and backend operate correctly.
2. Weather information is retrieved from a real API.
3. Risk assessment produces understandable results.
4. Interactive maps display relevant geographical information.
5. Users can submit flood reports.
6. Administrators can verify reports.
7. Route suggestions account for known affected roads.
8. Emergency resources are displayed accurately.
9. AI assistant answers relevant questions.
10. English, Hindi and Odia assistance works.
11. The application handles unavailable data safely.
12. The complete project can be demonstrated successfully.

18. FINAL PROJECT VISION

FLOODGUARD AI is designed to go beyond traditional weather monitoring.

It connects environmental intelligence, community reporting, geographical awareness and AI-powered emergency assistance into one platform.

Its vision is to help people understand potential flood risks, access reliable information and make better-informed decisions during emergencies.

FLOODGUARD AI – Predict. Prepare. Protect.