# VayuKavach: 3-minute demo

**Set-up (before you start):**
- Open the app on Delhi. Use the live URL, or run it locally (`npm run dev` and the API).
- Open two tabs:
  1. `/reports?place=delhi&date=2026-11-09`
  2. `/air?place=delhi`
- On your phone, sign up on the Alerts page first (WhatsApp sandbox joined), so a real message
  is on screen.
- Have the README "Limitations" section ready as the last slide.

Every number below is real stored data; the times on screen show when it was measured.

---

### 0:00 – 0:20 · The problem

> "Every day Indians get one air-quality number. Nobody tells you whether it is complete, or what
> to do about it. On Diwali night 2026, Delhi's stations went quiet exactly when the air was
> worst."

### 0:20 – 1:00 · Diwali, replayed from our data (Reports tab, 9 Nov)

- Point at **93% complete**. Then point at the gap check:
  - **42.6%** of readings were missing in the 6 most polluted hours;
  - only **3.6%** were missing in the cleanest hours.
  - The amber chip says **flagged**.
- Scroll to the silent stations (NSIT Dwarka twice, Alipur, New Delhi). Then the **19 PM
  readings at or near 999 µg/m³**: CPCB drops 999+ from the AQI.
- Switch the date to **8 Nov** and back: Diwali itself was not flagged (17.9 points apart), the
  morning after was.
- Say: "The AQI from the readings that arrived was 320. With the missing hours estimated, the
  shadow AQI is 340. We show both, side by side, never one instead of the other."
- Tap **Download CSV**: a journalist gets the station-hour list in one click.

### 1:00 – 1:25 · Today, all of India (Air tab)

- Air tab, Delhi, live:
  - the official AQI bubble, and the **data completeness** bubble with its shadow AQI;
  - station pins: solid = measured, dashed = estimated, grey "!" = silent.
- Open the **location button**: all 10 cities with their AQI. Pick **Shimla**: no CPCB
  station, so the screen says the value is a labelled model estimate.
- Back to Delhi: tap **10 days** on the chart. Days 1–5 are corrected CAMS (about 64% less
  error than raw CAMS in a year-long backtest); days 6–10 are a wider outlook.

### 1:25 – 1:50 · Temperature and Heat

- **Temperature**: "feels like" with its reason, the 7 AM–7 PM trend and the 10-day ranges.
- **Heat**: the page colour is the danger level. Heat index and wet-bulb, and the **safe work
  hours** for outdoor workers: the arc is solid when it is safe, dotted when to take care.

### 1:50 – 2:10 · Finder

- **Maps and Finder → Cleaner air → Day trip**:
  - towns ranked by measured AQI and a 3-day outlook;
  - tap the first one: route, travel time, official precautions, **Start navigation**.

### 2:10 – 2:35 · Ask VayuKavach

- Ask: **"Is it safe to go for a run tomorrow morning?"**
  - The answer uses the forecast and CPCB's advice.
  - Point at the **source chips**: source, time, Measured or Estimated.
- Ask: **"Who will win the cricket match?"**: a polite refusal (amber). It never reaches the model.
- Optional: switch language to **हिंदी** and ask "आज हवा कैसी है?"

### 2:35 – 2:50 · Alerts

- Show your phone: the **7 AM WhatsApp summary** with the AQI, heat level, safe work hours and
  a stop link. It is sent instantly when the air turns Very poor or Severe, or the heat reaches
  Danger.

### 2:50 – 3:00 · Limitations (README slide)

> "What it does not do yet: our shadow estimate recovers only part of what Diwali-style gaps
> hide, and we publish that measurement. We cover 10 districts, and SMS to every Indian number
> needs DLT registration. Everything runs on free tiers: the running cost is zero."

---

**If something fails live:**
- **API asleep** (free Render plan): open `/health` a minute before you start.
- **Gemini rate-limited:** the chatbot answers from templates, with the same sources.
- **No network:** run `npm run e2e`'s seeded API (`frontend/e2e/start-api.sh`) and Vite
  locally. It replays a synthetic Diwali day; say so on screen.
