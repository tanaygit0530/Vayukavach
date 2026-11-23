# VayuKavach: India's Year-Round Environmental Health Shield

Nov 22, 2026 · @Tanay Patil

## Overview

VayuKavach gives every district in India a daily environmental health risk score, and tells people whether the official air quality number can be trusted. It combines two modules on one free data pipeline: **Air Trust** (pollution data reliability, peaks October to February) and **Heat Shield** (humid-heat risk for outdoor workers, peaks March to September).

**Pitch:** Sameer tells you the AQI. VayuKavach tells you whether you can trust it and what to do about it, every season, in every district.

- **Domain:** Sustainability, public health, data engineering and AI
- **Coverage:** all of India, 12 months a year
- **Cost to build and run:** zero, using only free public data sources and free-tier tools

## Problem statement

India's two biggest environmental health threats, winter air pollution and summer humid heat, fail at the same two points: the data cannot be fully trusted, and warnings do not reach the people most at risk.

### 1. Winter: air quality numbers people cannot trust

- On Diwali, 8 November 2026, Delhi's average AQI was 376, its highest festival-day reading since 2021 ([Outlook India](https://www.outlookindia.com/national/delhi-smog-after-diwali-aqi-371-severe-air-pollution-stubble-burning-grap-stage-3)).
- The next morning, 10 of Delhi's 59 monitoring stations were not reporting ([ThePrint](https://theprint.in/feature/theres-a-data-gap-in-delhis-post-diwali-pollution-picture/3093881/)).
- 125 station-hour readings missing from CPCB's records were later released by DPCC, and all were above 1,000 µg/m³ ([The Wire](https://thewire.in/environment/delhis-missing-diwali-night-pollution-data-released-pm2-5-crosses-3700-politicians-cling-to-superstition)).
- CPCB acknowledged that readings above 999 µg/m³ are excluded from the AQI under a 2015 methodology ([Asianet Newsable](https://newsable.asianetnews.com/india/cpcb-reviews-outdated-aqi-methodology-amid-rising-pollution-concerns-articleshow-dquuv44)).
- A Hindustan Times analysis found data went missing more often in polluted hours than clean ones, which makes air look cleaner than it is ([Hindustan Times via Magzter](https://www.magzter.com/hi/stories/newspaper/Hindustan-Times-Gurugram/HOW-RELIABLE-IS-CITYS-POLLUTION-DATA)).
- The problem is not limited to Delhi: Gurgaon stations also show long PM2.5 and SO₂ gaps ([report](https://www.seaandjob.com/?p=55742)).

Today these gaps are found only by journalists, by hand, after the fact.

### 2. Summer and monsoon: heat that alerts underestimate

- Relative humidity across the Indo-Gangetic Plain has risen by up to 10% in a decade, turning Kanpur and Varanasi into zones of dangerous moist heat stress ([Down To Earth](https://www.downtoearth.org.in/climate-change/the-indo-gangetic-plains-heat-crisis-is-a-governance-failure-not-just-a-climate-one)).
- India lost a record 247 billion potential labour hours to heat in 2024, and 92% of the workforce is informal ([Carbon Copy](https://carboncopy.info/how-can-india-finance-its-heat-action-plans)).
- Experts say the weak point is the last mile, where a warning must become a clear, trusted instruction ([Business Standard](https://www.business-standard.com/india-news/indian-weather-warnings-system-issues-up-storm-viral-video-126052001090_1.html)), and call for worker-centric heat stress metrics ([Outlook Business](https://www.outlookbusiness.com/planet/why-indias-heat-planning-is-in-the-hot-seat)).

**Problem in one line:** Indians get an environmental number every day, but no way to know if it is complete, and no clear instruction on what to do about it.

## Existing solutions and the gap

Every existing tool shows the AQI number; none checks whether that number is complete, and none combines air and humid heat into one year-round view.

| Tool | What it does | What it misses |
| --- | --- | --- |
| [Sameer (CPCB)](https://www.freepressjournal.in/tech/how-to-check-aqi-near-your-home-office-or-childs-school-5-smart-ways) | Official hourly National AQI; map of nearby stations, AQI calendar, personal alerts | Never flags missing or excluded readings |
| SAFAR-Air (IITM) | AQI and forecasts for major metros | Few cities; no reliability view |
| IQAir, AQI.in | Government plus private sensor data, forecasts, alerts | US AQI scale; no audit of official data |
| Google Maps air layer | AQI on the map | No station-level detail or reliability |
| IMD heat alerts | Temperature-based heatwave warnings | Not humidity-first; not written for outdoor workers |

**Our gap:** an automated, public, all-India layer that audits data completeness, estimates what is missing, and adds humid-heat risk, so the tool matters in every season.

## Proposed solution

One platform with three modules shares a single hourly data pipeline. The focus shifts with the season, but every module runs all year.

### Module 1: Air Trust (all year, peaks October to February)

- **Data completeness score:** the share of expected hourly readings that actually arrived, for every station and city.
- **"Missing when it mattered" detector:** flags gaps that cluster in high-pollution hours, and stations that stop reporting together.
- **Shadow AQI:** recalculates the city AQI with gaps filled from nearby stations and satellite-model data, shown next to the official figure with a confidence band.
- **Cross-source check:** flags stations whose readings disagree with OpenAQ or model data for long periods.
- **Excluded-value flag:** marks hours where readings near or above 999 µg/m³ may have been left out of the official AQI.

**Pollution sources and full pollutant panel (part of the Air tab)**

- **Pollution sources:** share of today's PM2.5 by sector: transport, stubble fires in Punjab and Haryana, industry, household fuel, construction and demolition, waste burning, road dust. For Delhi this comes from IITM's Decision Support System, which estimates daily contributions of eight emission sectors ([Vajiram IAS summary](https://vajiramias.com/article/decoding-delhis-air-pollution-the-dss-explained/68e4c33ea750b91ff0bd4e0b)). Other cities show static shares from published source-apportionment studies, labelled with the study and year.
- **All AQI pollutants:** PM2.5, PM10, NO₂, CO, O₃, SO₂ and NH₃, each with its 24-hour value and India AQI sub-index bar; the highest sub-index sets the AQI.
- **CO₂ for context:** model value from the CAMS greenhouse-gas forecast, clearly marked as not part of India's AQI.
- **AQI chart with three views:** Hourly (past hours from CPCB with shadow-estimate marks, forecast hours faded), 10 days (daily low-to-high ranges), and Monthly (12-month history from stored data).
- **Wind status:** speed, gusts and direction, with a one-line note on whether wind is clearing or trapping smog.

### Module 2: Heat Shield (all year, peaks March to September)

- **Humid-heat risk:** heat index and wet-bulb temperature for every district, from temperature and humidity forecasts.
- **Morning worker alerts:** voice or WhatsApp/Telegram messages before 9 AM in Hindi, Marathi and other languages, for example "Work 7 to 11 AM, rest 12 to 4 PM, drink water every 20 minutes."
- **Contractor dashboard:** risk level per work site and a suggested safe shift schedule.

### Module 3: Unified risk view (all year)

- **India district map:** one daily risk score per district from air, heat or both.
- **Personal advice:** for any location, for example "Mask needed" or "Heat danger after 11 AM."
- **3 to 5 day forecasts** for planning.
- **Reports:** one-click data-gap reports for journalists and researchers.

**Tone rule:** the platform says "data completeness" and "reliability", never "manipulation". It shows what was measured and what is missing, and accuses no one.

### Module 4: Clean Air and Cool Places Finder

When air or heat risk is high, the app suggests a better place to be, shows it on the map with a route, and lists precautions for the trip. Every suggestion rests on a real reading; places with no data are never recommended.

**User flow**

1. A high-AQI or heat alert appears for the user's location.
2. The app asks where they want to go: Nearby (within 10 km), Day trip (within 150 km) or Vacation (anywhere in India).
3. Suggestions appear on the map, each with current AQI or temperature, a 3 to 5 day forecast, and a data label.
4. The user taps one to see the route, travel time and precautions for the journey.
5. For heat, the same flow suggests cooler places: parks, water bodies and hill stations.

**Data labels on every suggestion**

| Label | Meaning | Source |
| --- | --- | --- |
| Measured | A station or sensor near the place reports lower AQI now | CPCB, OpenAQ (including low-cost sensors) |
| Estimated | Model value for the wider area, not the exact spot | Open-Meteo (about 11 km grid) |
| Not shown | No reading available | Never recommended |

**What each part relies on**

| Feature | Data or tool (free) | Confidence |
| --- | --- | --- |
| Vacation and day-trip finder | CPCB and OpenAQ stations, Open-Meteo forecasts | High: regional AQI differences are large and measured |
| Cool-places finder (heat) | Satellite land-surface temperature (NASA/USGS Landsat, MODIS), Open-Meteo temperature | High: green and water areas are measurably cooler |
| Nearby clean-air parks | Only where a station or sensor sits nearby | Limited: most parks have no sensor, and model data cannot separate a park from the next street |
| Map and routes | Leaflet with OpenStreetMap; OSRM or OpenRouteService for routing | High |
| Precautions | Official CPCB AQI health guidance and NDMA heatwave guidance | High: official wording, not invented |

**Precautions shown with each route** are matched to the AQI category or heat level and to the user, for example: wear an N95 until out of the city, keep car windows closed in traffic, avoid travel in peak afternoon heat, carry water, and take extra care for children, elderly people and anyone with asthma or heart conditions.

**Why no tree-based predictions:** fine particles (PM2.5) spread across a whole city, so during severe smog a park is usually only slightly cleaner than the street outside. A model that assumes "more trees, lower AQI" would be a guess, so the app recommends a nearby park for air only when a real reading supports it.

**Scope:** build the vacation and day-trip finder and the cool-places finder after the Air Trust core. Park-level air suggestions stay future scope unless sensor data exists for the city.

### Module 5: Ask VayuKavach (data-grounded chatbot)

Users ask questions in plain language and get answers built only from VayuKavach's own data; anything outside air quality, heat and the app is politely refused.

**How it works**

1. The user asks, for example "Was yesterday's AQI in Lucknow complete?"
2. An LLM (Gemini free tier, or Gemma on Ollama for offline use) reads the question and calls one of our own data functions; it never answers from its general knowledge.
3. The function queries our database and returns numbers with their source, time and Measured or Estimated label.
4. The LLM writes a short answer from those numbers only, in Hindi, Marathi or English, and shows the source and timestamp under it.

**Data functions the chatbot may call**

| Function | Returns |
| --- | --- |
| get\_aqi(place, date) | Official AQI, category, main pollutant |
| get\_completeness(place, date) | Share of readings received, stations silent, hours missing |
| get\_shadow\_aqi(place, date) | Estimated AQI with confidence band and error |
| get\_forecast(place, days) | AQI and heat forecast for up to 5 days |
| get\_heat\_risk(place, date) | Heat index, wet-bulb, level, safe work hours |
| find\_places(goal, mode, from) | Cleaner or cooler places with labels, distance and route time |
| get\_precautions(level) | Official CPCB or NDMA guidance for that level |

**Guardrails**

- **Scope check first:** a small classifier or prompt rule sorts each question as in scope (air, heat, our data, app help) or out of scope. Out of scope gets a fixed reply: "I can only answer questions about air quality, heat and VayuKavach's data."
- **No data, no answer:** if a function returns nothing, the bot says the data is not available; it never guesses a number.
- **Every number cited:** each answer shows its source, time and Measured or Estimated label.
- **No medical diagnosis:** health questions get the official precautions and "see a doctor"; for heatstroke signs, call 108.
- **Neutral tone:** questions about blame or politics get the facts on data completeness only.
- **Prompt-injection safe:** text inside data records is treated as data, never as instructions.

**Example answers**

| Question | Bot behaviour |
| --- | --- |
| Is it safe to run in Pune tomorrow morning? | Gives forecast AQI and heat level, the matching precaution, source and time |
| Why is the official AQI different from your estimate? | Explains missing hours and the shadow AQI method, with today's completeness figure |
| Find me a clean place for a weekend trip from Jaipur | Calls find\_places and lists Measured or Estimated options with routes |
| Who will win the cricket match? | Out of scope: fixed polite refusal |

**Testing:** keep a set of about 50 questions (in scope, out of scope, trick and injection attempts) and check before each release that every answer cites data and every off-topic question is refused.

### Module 6: Temperature tab

A separate tab for everyday weather, built entirely from the free Open-Meteo forecast, so no model training is needed. Heat risk and work-safety advice stay on the Heat tab; the Temperature tab links to it.

| Panel | What it shows | Open-Meteo variables |
| --- | --- | --- |
| My location | Current temperature, sky condition, today's high and low | temperature\_2m, weather\_code, daily max and min |
| Feels like | Apparent temperature with a one-line reason | apparent\_temperature, wind\_speed\_10m, relative\_humidity\_2m |
| Temperature trend | Hourly bubbles from 7 AM to 7 PM, current hour highlighted | temperature\_2m (hourly) |
| 10-day forecast | Daily low-to-high bars and sky icon | temperature\_2m\_max and min, weather\_code (daily) |
| Sunrise and sunset | Sun path arc, sunrise, sunset, daylight duration | sunrise, sunset, daylight\_duration |
| UV index | Gauge with category and cover-up hours | uv\_index, uv\_index\_max |
| Current condition | Rainfall, humidity, dew point, pressure | precipitation, relative\_humidity\_2m, dew\_point\_2m, pressure\_msl |
| Extra rows | Cloud cover, rain chance, day and night swing | cloud\_cover, precipitation\_probability, daily max minus min |

Each value appears once on the tab; air-quality figures live only on the Air tab.

**Weather data checklist (everything the Temperature and Heat tabs need)**

| Need | Source | Notes |
| --- | --- | --- |
| City search to latitude and longitude | Open-Meteo Geocoding API | Free, no key; turns "Kanpur" into coordinates for every other call |
| Current conditions and hourly forecast | Open-Meteo Forecast API, current and hourly blocks | Add timezone=Asia/Kolkata so times are in IST |
| Earlier hours of today | Same API with past\_days=1 | These are model analysis values, not station measurements; label them so |
| 10-day daily forecast | Same API, daily block, forecast\_days=10 | Forecasts run up to 16 days |
| Sunrise, sunset, daylight, UV | Same API, daily block | uv\_index\_max for the gauge, hourly uv\_index for cover-up hours |
| Monthly and "normal for this date" comparisons | Open-Meteo Historical Weather API | Hourly archive back to 1940; store monthly averages once |
| Heat level, wet-bulb, feels-like reason | Computed by VayuKavach | Formulas in Key methods; no outside source |
| Optional official warnings | IMD district heatwave and cold-wave warnings | No open API; link to IMD rather than copy |

**Usage rules:** Open-Meteo data is licensed CC BY 4.0, so every screen credits Open-Meteo (and CAMS for air data). The free tier allows about 10,000 calls a day for non-commercial use ([details](https://mortenoh.github.io/prefect-examples/openmeteo)), so cache each district's forecast and refresh it hourly instead of calling the API per user.

## UI design direction

The product uses two looks: a friendly illustrated style for air quality, and a full-screen colour-gradient style for heat, where the background colour shows the danger level at a glance (blue when normal, dark red when extreme).

**Current direction (latest revision):** a light, glassy dashboard. The Air tab shows a full-width pollution map with floating circular metric bubbles and four cards below it (AQI chart, pollution sources, pollutants, wind). The Temperature tab uses a card grid on a soft sky background. A slim icon rail on the left links Air, Temperature, Heat, Maps and Ask; the city list opens only from the location button. The Heat tab keeps its colour-by-danger gradient. The illustrated and gradient sections below are the earlier exploration and remain the source of the colour scales.

### Air quality screens (reference 1: illustrated AQI app)

**Keep from the reference:** illustrated hero card with a location scene, semicircle AQI gauge, map with AQI number bubbles, 2x2 cards for PM2.5, wind, temperature and humidity, and a 5-day forecast strip.

**Adapt for VayuKavach:**

- **Gauge on India's scale:** 0 to 500 with the six CPCB categories; the reference uses a 0 to 300 scale.
- **Two needles:** official AQI (solid) and shadow AQI (outline), with a "Data completeness 82%" badge under the gauge.
- **Map bubbles:** filled with the category colour; solid ring = Measured, dashed ring = Estimated, grey bubble with "!" = station not reporting.
- **Illustrations:** Indian city and landscape scenes, drawn by the team or taken from free libraries such as unDraw or Storyset. Do not reuse the reference artwork.

| CPCB category | AQI range | Colour |
| --- | --- | --- |
| Good | 0 to 50 | Dark green #00B050 |
| Satisfactory | 51 to 100 | Light green #92D050 |
| Moderately polluted | 101 to 200 | Yellow #FFFF00 |
| Poor | 201 to 300 | Orange #FF9900 |
| Very poor | 301 to 400 | Red #FF0000 |
| Severe | 401 to 500 | Maroon #C00000 |

Colours follow the CPCB scheme as commonly published; confirm against the current CPCB bulletin before launch.

### Heat screens (reference 2: gradient weather app)

**Keep from the reference:** full-screen radial gradient background, large dot-matrix temperature number, an arc across the day, two cards, and a bottom action row.

**Adapt for VayuKavach:**

- **Background colour driven by heat level** (table below), so the risk is clear before any text is read.
- **Large number = feels-like temperature;** the line under it gives the level name and district.
- **Day arc = work timeline:** safe work windows highlighted, danger hours marked, a dot for the current time.
- **Two cards:** "Heat index and wet-bulb" and "Safe work hours today".
- **Bottom actions:** "Find cooler places" (Module 4) and "Send alert to my team" (for contractors).

| Heat level | Background gradient (centre to edge) | Mood |
| --- | --- | --- |
| Normal | Sky blue #38BDF8 to deep blue #1E3A8A | Calm |
| Caution | Light amber #FCD34D to amber #F59E0B | Take care |
| Danger | Red #DC2626 to burnt orange #EA580C | Limit outdoor work |
| Extreme | Crimson #B91C1C to dark red #7F1D1D, near-black edges | Stop outdoor work |

The temperature thresholds for each level come from the heat-risk method in Key methods and the local heat action plan, and are set during implementation.

### Web layout

- **Desktop:** a left sidebar (Home, Map, Finder, Alerts, Reports) replaces the mobile bottom bar. Home has three columns: hero card and gauge, live map, then metric cards and forecast.
- **Mode follows risk:** air mode uses the light illustrated theme; heat mode switches the page to the gradient theme. A toggle at the top lets users switch manually.
- **Responsive:** the same components stack into a single column on phones, matching the reference layouts.

### Accessibility rules

- Never use colour alone: every colour appears with its category word and number.
- White text on gradients must pass WCAG AA contrast (4.5:1); darken the gradient centre if needed.
- Use the dot-matrix font only for the big number; body text uses a plain sans-serif such as Inter or Poppins.
- Respect the reduced-motion setting for any animated gradient.

### Implementation notes

- React with Tailwind CSS; theme colours as CSS variables (for example --aqi-good, --heat-bg-centre, --heat-bg-edge), switched by level.
- Heat background: a CSS radial-gradient built from the current level's two colours, with a smooth transition between levels.
- Gauge and day arc: hand-drawn SVG components.
- Map: Leaflet with custom HTML markers for the AQI bubbles and Measured or Estimated rings.
- Fonts: a dot-matrix Google Font (such as Doto or DotGothic16) for the big number; Inter or Poppins for text.

### Reference images

The two references the look is based on are below: the illustrated AQI app (air mode) and the gradient weather app (heat mode).

**Heat mode reference:** gradient weather app

&#91;image: Gradient weather app reference: radial colour background, dot-matrix temperature, day arc, two cards\]

**Current direction references:** light glass dashboards (Air tab map and bubbles, Temperature tab card grid)

&#91;image: Light dashboard reference: 3D map with metric bubbles, AQI chart, pollution sources, wind compass\]

&#91;image: Analytics reference: temperature trend, week forecast, sunrise and sunset, UV gauge, pollutant bars\]

&#91;image: Map reference: pollution heat zones with floating metric bubbles, trend chart, air flow card\]

## Implementation spec (latest design)

Build the light glass design shown in the [VayuKavach UI Mockups](https://claude.ai/artifact/F1wEqcoi898gLdFoD7DjM4); this section is the single reference for developers, and earlier design notes are background only. All numbers in the mockups are sample data.

### Design tokens

| Token | Value |
| --- | --- |
| Font | Outfit (Google Fonts), weights 300 to 600; DotGothic16 only for the big number on the Heat tab |
| Text | Primary #17212B, secondary #5E6B77 |
| Page background | Air: #E9EEF2 under the map. Temperature: gradient #D3D9DF to #E4E8EC with soft white clouds |
| Cards | White at 88 to 92% opacity, 14 px backdrop blur, 26 px radius, shadow 0 8px 30px rgba(23,33,43,0.07) |
| Metric bubbles | Circles 160 to 210 px, white at 78%, 10 px blur |
| Accent | Green #1F9D55 (logo, map pin, current hour); dark #17212B for the active tab and primary buttons |
| AQI scale | Good #3BB44A, Satisfactory #A5D63F, Moderate #F5D547, Poor #F08A3C, Very poor #E5483F, Severe #9E1B32 |
| Heat levels | Normal blue, Caution amber, Danger red, Extreme dark red (gradients as in the Heat mockup) |
| Touch targets | At least 44 px; all icon buttons have an aria-label |

### App shell (every tab)

- **Icon rail (left, 74 px):** logo, then Air quality, Temperature, Heat, Maps and Finder, Ask VayuKavach; Alerts and Profile at the bottom. Active tab is a dark circle. On phones the rail becomes a bottom bar.
- **Header:** location button on the left (opens Places), time and data label on the right.
- **Places drawer:** slides in from the left only when the location button is pressed; search box plus saved cities with their AQI or temperature; closes on the X, outside click or choosing a city.

### Air tab

| Component | Shows | Data |
| --- | --- | --- |
| Pollution map | PM2.5 zones green to red, area names, your pin, station pins (solid ring Measured, dashed Estimated, grey Not reporting), legend, layer and zoom buttons | Leaflet + OpenStreetMap; CAMS grid + CPCB stations |
| Metric bubbles | AQI and category; main pollutant; visibility; data completeness with shadow AQI | CPCB, gap detector, Open-Meteo visibility |
| AQI chart | Tabs: Hourly (past CPCB, shadow marks, faded forecast), 10 days (low-high ranges, days 6-10 faded), Monthly | CPCB store, CAMS, outlook model |
| Pollution sources | Seven sectors with % and bar | IITM DSS (Delhi), studies elsewhere |
| Pollutants | PM2.5, PM10, NO₂, CO, O₃, SO₂, NH₃ with sub-index bars; CO₂ as context | CPCB, Open-Meteo, CAMS greenhouse-gas |
| Wind status | Speed, gusts, direction compass, smog note | Open-Meteo |
| What to do today | CPCB health advice for the category, button to Clean Air Finder | CPCB guidance text |

### Temperature tab

My location card, Feels like card (links to Heat), Temperature trend bubbles, 10-day forecast, Sunrise and sunset arc, UV gauge, Current condition grid and extra rows, Export CSV button. Data mapping: Module 6 table.

### Heat, Maps and Ask tabs

- **Heat:** keeps its colour-by-danger gradient; switch its sidebar to the icon rail during build.
- **Maps and Finder:** restyle to the light glass look (cards, rail, Outfit font) during build; behaviour as in Module 4.
- **Ask VayuKavach:** restyle to the light glass look; behaviour as in Module 5.

### States every component must handle

- **Loading:** grey skeleton shapes in the card's layout.
- **No data:** "No reading for this hour" text, never a zero.
- **Estimated:** dashed border or dashed ring, plus the word Estimated.
- **Stale:** "Updated 3 h ago" in amber when data is older than 2 hours.

### Suggested React components

AppShell, IconRail, PlacesDrawer, LocationButton, PollutionMap, MetricBubble, AqiChart (mode: hourly, daily, monthly), SourceList, PollutantBars, WindCompass, HealthAdvice, TempTrend, ForecastList, SunArc, UvGauge, ConditionGrid, HeatHero, ChatPanel.

## Data sources

Every source below is free. Station data (CPCB, OpenAQ) gives official readings; model data (Open-Meteo) fills districts with no station and supplies weather for the heat module.

| Source | Used for | Access | Limits and caveats |
| --- | --- | --- | --- |
| [CPCB real-time AQI via data.gov.in](https://data.gov.in/resource/real-time-air-quality-index-various-locations) | Live official readings: PM2.5, PM10, NO₂, SO₂, CO, O₃ per station, hourly | Free API key from your data.gov.in account dashboard | Current snapshot only, no history via API: store every hourly pull yourself. Live data is not QA-checked ([CEEW](https://www.ceew.in/blogs/india%E2%80%99s-air-pollution-democratising-air-quality-data)) |
| [OpenAQ API v3](https://docs.openaq.org/using-the-api/quick-start) | Historical station data, cross-checks, government plus low-cost sensors | Free key from explore.openaq.org, sent as X-API-Key header | 60 requests a minute, 2,000 an hour ([details](https://freeapihub.com/apis/openaq-api)); some stations go offline |
| [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api) | PM2.5, PM10, gases and forecasts for any coordinate, from CAMS at 11 km | No key needed | Gives US/EU AQI: compute Indian AQI from raw concentrations. Model estimates, not measurements |
| Open-Meteo Weather API | Temperature, humidity, forecasts for the heat module | No key needed | Same provider; fair-use limits |
| [WAQI / aqicn.org](https://aqicn.org/data-platform/token/) | Optional backup for live display | Free token | Data cannot be redistributed as cached or archived data; non-commercial |
| [UrbanEmissions AQI archive](https://urbanemissions.info/?p=4099) | City-level daily AQI history from CPCB bulletins, 2015 onward | Free download | Daily city values, not hourly stations |
| CPCB daily AQI bulletins | Official daily city AQI for validation | Free PDFs on cpcb.nic.in | PDFs need parsing |
| [CPCB station network (PIB)](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/sep/doc_9816_20260907_20291701.pdf) | Station list for coverage maps | Public | 1,646 stations in 603 cities, including manual ones that do not report live |

**Two rules for the pipeline:** compute every AQI on India's National AQI scale from raw concentrations, and keep a record of every missing hour as data, not as an error.

**Additional sources for sources, pollutants and weather**

| Source | Used for | Access | Limits and caveats |
| --- | --- | --- | --- |
| [IITM Decision Support System](https://gmd.copernicus.org/articles/17/2617/2024/) | Daily sector-wise PM2.5 contributions for Delhi, including stubble fires and neighbouring districts | Public website and bulletins | Delhi only; 5-day forecast on a 10 km grid; no official API, so values are collected from the published output |
| Published source-apportionment studies | Sector shares for other cities | Free reports | Static, one study per city; always show the study name and year |
| Open-Meteo Air Quality API (more variables) | NH₃ and dust in addition to PM, NO₂, SO₂, CO, O₃ ([variables](https://docs.anysite.io/api-reference/openmeteo/openmeteoair-quality.md)) | No key | Model values; CPCB station readings take priority where they exist |
| CAMS greenhouse-gas forecast via Open-Meteo | CO₂ context value | No key | Not part of India's AQI; shown as context only |
| Open-Meteo weather forecast | Everything on the Temperature and Heat tabs | No key | Hourly, up to 16 days ([details](https://mortenoh.github.io/prefect-examples/openmeteo)) |

## System architecture and tech stack

Everything runs on one hourly pipeline: collect, store, analyse, then serve the map and the alerts.

&#91;embedded content: VayuKavach architecture · 4 sources, 1 pipeline, 2 outputs\]

The collector stores missing hours as data, so the gap detector and shadow AQI can work on them later.

| Layer | Tool | Why |
| --- | --- | --- |
| Data collection | Python (requests), GitHub Actions cron, hourly | Free scheduler; retries on failure |
| Database | PostgreSQL on Supabase free tier | Time-series queries by station and hour |
| Analysis | pandas, NumPy, scikit-learn | AQI maths, anomaly detection, gap filling |
| Backend | FastAPI | Fast, simple JSON API |
| Frontend | React, Leaflet with OpenStreetMap tiles, Recharts | Free maps and charts |
| Alerts | Telegram Bot API; an LLM free tier for local-language messages | Free, reaches phones directly |
| Hosting | Vercel or Netlify (frontend), a free-tier backend host | Zero cost for the MVP |

## Key methods

Four calculations carry the product; each one is checked against real data before it is shown to users.

**1. India National AQI.** For each pollutant, convert its concentration C to a sub-index with CPCB's breakpoint table, using linear interpolation between the breakpoints Bₗₒ and Bₕᵢ that contain C:

```latex
I_p = \frac{I_{hi} - I_{lo}}{B_{hi} - B_{lo}} \,(C_p - B_{lo}) + I_{lo}
```

The AQI is the highest sub-index. Use 24-hour averages for PM2.5, PM10, NO₂, SO₂ and NH₃, and 8-hour averages for CO and O₃, as CPCB does.

**2. Gap detection.** For every station-hour, record whether a reading arrived. Then compare the missing rate in the most polluted hours with the missing rate in the cleanest hours of the same day. A large difference, or many stations going silent together, raises a flag.

**3. Shadow AQI.** Fill each missing reading from nearby reporting stations (inverse-distance weighting), corrected by Open-Meteo model values for that location. To prove it works, hide real readings that did arrive, estimate them, and report the average error (MAE in µg/m³). Show the shadow AQI with a confidence band, never as a replacement for the official figure.

**4. Humid-heat risk.** Compute heat index and wet-bulb temperature from hourly temperature and relative humidity forecasts (standard published formulas, such as Stull's wet-bulb approximation). Map the result to four risk levels with a safe work-rest schedule for each.

**5. Hourly and 10-day forecasts.** Weather comes straight from the source; air quality needs a small model for days 6 to 10.

| Forecast | Source | Model training needed? |
| --- | --- | --- |
| Hourly temperature, humidity, wind | Open-Meteo weather forecast | No |
| 10-day temperature and heat level | Open-Meteo weather forecast (up to 16 days) | No: heat level is a formula on the forecast |
| Hourly AQI, days 1 to 5 | Open-Meteo Air Quality API, from the CAMS global forecast (5 days, about 25 to 45 km grid) | Recommended: a simple bias correction trained on stored CPCB readings, because the global grid is coarse |
| AQI outlook, days 6 to 10 | No free all-India source; IITM's Air Quality Early Warning System publishes a 10-day forecast for Delhi only | Yes: a gradient-boosting model (for example LightGBM) trained on stored AQI history plus the 16-day weather forecast (wind, temperature, humidity, boundary layer height) |

Days 6 to 10 are shown as a lower-confidence outlook (faded, dashed bars), never with the same weight as days 1 to 5. Validate the model by forecasting past weeks and reporting its error per lead day.

## Users, impact and success metrics

Four groups use the platform, and each has one number that shows whether it worked.

| User | What they get | Success metric |
| --- | --- | --- |
| Citizens | Trustworthy air and heat advice for their district | Weekly active users; alerts opened |
| Outdoor workers and contractors | Morning heat alerts and safe shift schedules | Workers subscribed; alerts acknowledged |
| Journalists and researchers | Automated data-gap reports instead of manual analysis | Reports downloaded; stories citing them |
| District officials | One dashboard of where risk is highest today | Districts monitored; alerts acted on |

**Technical metrics to report:** stations and districts covered, pipeline uptime, hours ingested, shadow-AQI error (MAE) on held-out readings, and alert delivery time.

**Impact:** transparent, accountable air data without accusing anyone; protection for informal outdoor workers from humid heat; and a tool that is useful 12 months a year in every district, not only in Delhi's winter.

## Build plan, demo and risks

Build the data pipeline first: every feature depends on stored hourly readings, and CPCB's API keeps no history.

### Build order

1. Hourly collector for CPCB, OpenAQ and Open-Meteo, saving raw readings and missing hours to PostgreSQL.
2. India AQI calculator from raw concentrations, checked against CPCB's published values.
3. Completeness score and gap detector per station and city.
4. Shadow AQI with gap filling, plus its error measured on held-out readings.
5. Heat module: heat index and wet-bulb risk per district.
6. Dashboard: India district map, city view (official vs shadow AQI), station reliability table.
7. Telegram alert bot with messages in Hindi, Marathi and English.

### MVP scope

- [ ] Collector running hourly for all CPCB stations
- [ ] Completeness score, gap detector and shadow AQI for at least 10 cities
- [ ] Heat risk for all districts from Open-Meteo
- [ ] Map dashboard and Telegram alerts

* Out of scope for now: user accounts, mobile app, low-cost sensor hardware

### Demo script (3 minutes)

1. Replay Diwali night, 8 to 9 November 2026, in Delhi: stations go silent on the map as pollution peaks.
2. Show the official AQI next to the shadow AQI, with the confidence band.
3. Zoom out to all of India to show it is not a Delhi-only tool.
4. Switch to a May date: the map turns to heat risk, and a Hindi worker alert arrives on Telegram.
5. Close on one limitation slide: how gaps are estimated and how accurate the estimate is.

### Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| A free API changes or rate-limits us | Cache every pull; keep two sources for every city |
| Shadow AQI is seen as "the real number" | Always show it beside the official figure, with its error and confidence band |
| Model data is wrong where no station exists | Label model-only districts clearly as estimates |
| Political sensitivity | Neutral wording: completeness and reliability, never blame |

### Future scope

- Rain and flood alerts for the monsoon, on the same weather pipeline
- Low-cost sensor partnerships for districts with no station
- Public API for researchers

## Sources

- [Outlook India: Delhi records highest Diwali AQI since 2021](https://www.outlookindia.com/national/delhi-smog-after-diwali-aqi-371-severe-air-pollution-stubble-burning-grap-stage-3)
- [ThePrint: There's a data gap in Delhi's post-Diwali pollution picture](https://theprint.in/feature/theres-a-data-gap-in-delhis-post-diwali-pollution-picture/3093881/)
- [The Wire: Delhi's missing Diwali-night pollution data released](https://thewire.in/environment/delhis-missing-diwali-night-pollution-data-released-pm2-5-crosses-3700-politicians-cling-to-superstition)
- [Asianet Newsable: CPCB reviews AQI methodology](https://newsable.asianetnews.com/india/cpcb-reviews-outdated-aqi-methodology-amid-rising-pollution-concerns-articleshow-dquuv44)
- [Hindustan Times: How reliable is city's pollution data?](https://www.magzter.com/hi/stories/newspaper/Hindustan-Times-Gurugram/HOW-RELIABLE-IS-CITYS-POLLUTION-DATA)
- [Report on Gurgaon station data gaps](https://www.seaandjob.com/?p=55742)
- [Down To Earth: The Indo-Gangetic Plain's heat crisis](https://www.downtoearth.org.in/climate-change/the-indo-gangetic-plains-heat-crisis-is-a-governance-failure-not-just-a-climate-one)
- [Carbon Copy: How can India finance its heat action plans?](https://carboncopy.info/how-can-india-finance-its-heat-action-plans)
- [Business Standard: Why India's weather warnings still miss the last mile](https://www.business-standard.com/india-news/indian-weather-warnings-system-issues-up-storm-viral-video-126052001090_1.html)
- [Outlook Business: Why India's heat planning is in the hot seat](https://www.outlookbusiness.com/planet/why-indias-heat-planning-is-in-the-hot-seat)
- [Free Press Journal: How to check AQI near you](https://www.freepressjournal.in/tech/how-to-check-aqi-near-your-home-office-or-childs-school-5-smart-ways)
- [data.gov.in: Real-time Air Quality Index](https://data.gov.in/resource/real-time-air-quality-index-various-locations)
- [CEEW: Democratising air quality data](https://www.ceew.in/blogs/india%E2%80%99s-air-pollution-democratising-air-quality-data)
- [OpenAQ quick start](https://docs.openaq.org/using-the-api/quick-start) and [rate limits](https://freeapihub.com/apis/openaq-api)
- [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api)
- [WAQI data platform terms](https://aqicn.org/data-platform/token/)
- [UrbanEmissions: India AQI 2015 onward](https://urbanemissions.info/?p=4099)
- [PIB: CPCB monitoring network](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/sep/doc_9816_20260907_20291701.pdf)
