"""Horizon — Travel AI capstone UI (single-file).

Enhanced version:
  • Working custom sidebar nav with real active state
  • Chat with proactive clarification (PRD §2.1) + persisted replies
  • Destination-aware itineraries with confidence + evidence cards (PRD §2.3/§2.5)
  • Travel DNA radar + learned preferences + DNALearner change feed (PRD §2.2)
  • Explore Top-10 with offline SVG art, wired to the itinerary page
  • One-click, in-memory, styled PDF export

Run: streamlit run app.py
"""

import base64
import html
from datetime import datetime

import plotly.graph_objects as go
import streamlit as st
from fpdf import FPDF
import sys
import os
from src.orchestrator import RootOrchestrator
from src.models.state import TravelState
from src.models.preferences import TravelPreferences
from src.auth import db as auth_db
from src.auth import service as auth_service
from src.auth.service import AuthError
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = RootOrchestrator()
if "auth_conn" not in st.session_state:
    st.session_state.auth_conn = auth_db.get_connection()
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None  # None = logged out; a User model once logged in
if "travel_state" not in st.session_state:
    st.session_state.travel_state = TravelState(session_id="hirak_001")
else:
    # A session kept open across a deploy that added new TravelPreferences fields
    # (e.g. departure_time) still holds an instance built from the old class —
    # Python doesn't retroactively add fields to it, so reading a new one raises
    # AttributeError instead of returning None. Re-casting through the current
    # schema on every rerun is a cheap, idempotent fix: known fields carry over,
    # newly-added ones default in.
    st.session_state.travel_state.preferences = TravelPreferences(
        **st.session_state.travel_state.preferences.model_dump())
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# ============================================================================
# Design tokens — slate night + sunset (coral → amber)
# ============================================================================
NIGHT = "#0F172A"
SURFACE = "#1E2937"
SURFACE_2 = "#28354A"
LINE = "#334155"
CORAL = "#FF6B6B"
AMBER = "#FFB800"
LAGOON = "#5EEAD4"     # high confidence only
ROSE = "#F87171"       # low confidence / uncertainty
INK = "#F1F5F9"
MUTED = "#94A3B8"
FAINT = "#64748B"
GRAD = f"linear-gradient(90deg,{CORAL},{AMBER})"

CONF = {
    "high":   (LAGOON, "High confidence"),
    "medium": (AMBER, "Medium confidence"),
    "low":    (ROSE, "Low confidence"),
}


def conf_band(score: int) -> str:
    return "high" if score >= 80 else "medium" if score >= 55 else "low"


# ============================================================================
# Profile preference vocabulary — used by Sign Up and Profile pages
# ============================================================================
PROFILE_FOOD_PREF_LABELS = {
    "vegetarian": "🥗 Vegetarian", "vegan": "🌱 Vegan",
    "non_veg": "🍗 Non-vegetarian", "no_restrictions": "🍽️ No restrictions",
}
TRAVEL_PREF_LABELS = {
    "adventure": "🧗 Adventure", "relaxation": "🏖️ Relaxation", "culture_heritage": "🏛️ Culture & heritage",
    "nature_wildlife": "🌿 Nature & wildlife", "nightlife": "🌃 Nightlife", "shopping": "🛍️ Shopping",
    "wellness_spa": "💆 Wellness & spa", "family_friendly": "👨‍👩‍👧 Family-friendly",
    "solo_travel": "🎒 Solo travel", "budget_conscious": "💸 Budget-conscious",
    "luxury": "✨ Luxury", "photography": "📷 Photography",
}
INFLIGHT_PREF_LABELS = {
    "window_seat": "🪟 Window seat", "aisle_seat": "🚶 Aisle seat", "extra_legroom": "🦵 Extra legroom",
    "vegetarian_meal": "🥗 Vegetarian meal", "quiet_zone": "🤫 Quiet zone",
    "early_boarding": "⏱️ Early boarding", "extra_baggage": "🧳 Extra baggage", "wifi": "📶 In-flight Wi-Fi",
}
HOTEL_BUDGET_TIER_LABELS = {"budget": "💰 Budget", "medium": "🏨 Medium", "high": "✨ High-end"}
BED_TYPE_OPTIONS = ["No preference", "Single", "Double", "Twin", "King"]
VIEW_TYPE_OPTIONS = ["No preference", "Sea view", "City view", "Garden view"]
SEX_OPTIONS = ["Prefer not to say", "Female", "Male", "Non-binary", "Other"]


st.set_page_config(page_title="Horizon • Travel AI", page_icon="🌊",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,500;0,700;1,500&family=Schibsted+Grotesk:wght@400;500;700&family=Spline+Sans+Mono:wght@400;500&display=swap');

html, body, [class*="css"], .stApp {{ font-family:'Schibsted Grotesk',sans-serif; color:{INK}; }}
.stApp {{ background:{NIGHT}; }}
[data-testid="stHeader"] {{ background:transparent; }}
h1,h2,h3 {{ font-family:'Playfair Display',serif !important; color:{INK} !important; letter-spacing:-.01em; }}

/* ---------- sidebar nav (active = primary button) ---------- */
[data-testid="stSidebar"] {{
  background:linear-gradient(180deg,#111C33 0%,{NIGHT} 100%);
  border-right:1px solid {LINE};
}}
[data-testid="stSidebar"] button {{
  justify-content:flex-start !important; text-align:left;
  border-radius:12px; font-weight:500;
  transition:transform .25s cubic-bezier(.16,1,.3,1), background .2s;
}}
[data-testid="stSidebar"] button:hover {{ transform:translateX(6px); }}
[data-testid="stSidebar"] button[kind="secondary"] {{
  background:transparent; border:1px solid transparent; color:{MUTED};
}}
[data-testid="stSidebar"] button[kind="secondary"]:hover {{
  background:{SURFACE_2}; color:{INK};
}}
button[kind="primary"] {{
  background:{GRAD} !important; color:#221108 !important; border:0 !important;
  font-weight:700 !important; box-shadow:0 4px 16px rgba(255,107,107,.35);
}}
.stDownloadButton > button {{
  background:{GRAD}; color:#221108; border:0; border-radius:12px; font-weight:700;
}}

/* ---------- signature: horizon line ---------- */
.hz-rule {{ height:2px; border:0; margin:1.4rem 0;
  background:linear-gradient(90deg,transparent,{CORAL} 30%,{AMBER} 70%,transparent);
  box-shadow:0 0 16px 1px rgba(255,107,107,.4); }}

.hz-hero {{ position:relative; overflow:hidden; padding:3rem 2.4rem 2.5rem;
  border-radius:20px; border:1px solid {LINE};
  background:
    radial-gradient(120% 95% at 50% 120%, rgba(255,107,107,.30) 0%, rgba(255,184,0,.12) 35%, transparent 62%),
    {SURFACE}; }}
.hz-hero::after {{ content:""; position:absolute; left:8%; right:8%; bottom:0; height:2px;
  background:linear-gradient(90deg,transparent,{CORAL} 25%,{AMBER} 75%,transparent);
  box-shadow:0 0 24px 3px rgba(255,150,60,.5); }}
.hz-hero h1 {{ font-size:2.9rem; line-height:1.08; margin:.4rem 0 .6rem; }}
.hz-hero h1 em {{ font-style:italic; background:{GRAD};
  -webkit-background-clip:text; background-clip:text; color:transparent; }}
.hz-hero p {{ color:{MUTED}; max-width:48ch; }}
.hz-eyebrow {{ font-family:'Spline Sans Mono',monospace; font-size:.7rem;
  letter-spacing:.18em; text-transform:uppercase; color:{AMBER}; }}

/* ---------- cards ---------- */
.hz-card {{ background:{SURFACE}; border:1px solid {LINE}; border-radius:16px;
  padding:1.1rem 1.25rem; margin-bottom:.85rem;
  transition:transform .2s cubic-bezier(.16,1,.3,1), box-shadow .2s, border-color .2s; }}
.hz-card:hover {{ transform:translateY(-4px); border-color:#46557A;
  box-shadow:0 14px 32px rgba(255,107,107,.12); }}
.hz-kicker {{ font-family:'Spline Sans Mono',monospace; font-size:.68rem;
  letter-spacing:.14em; text-transform:uppercase; color:{FAINT}; }}
.hz-title {{ font-family:'Playfair Display',serif; font-size:1.16rem; font-weight:700; margin:.15rem 0 .3rem; }}
.hz-body {{ color:{MUTED}; font-size:.92rem; line-height:1.55; }}
.hz-meta {{ display:flex; flex-wrap:wrap; gap:.45rem; margin-top:.65rem; }}
.hz-chip {{ font-family:'Spline Sans Mono',monospace; font-size:.72rem;
  padding:.22rem .6rem; border-radius:999px; background:{SURFACE_2};
  border:1px solid {LINE}; color:{MUTED}; }}
.hz-chip b {{ color:{INK}; font-weight:500; }}
.hz-time {{ font-family:'Spline Sans Mono',monospace; font-size:.8rem; color:{CORAL}; }}

/* confidence badge — color + label, never color alone */
.hz-conf {{ display:inline-flex; align-items:center; gap:.45rem;
  font-family:'Spline Sans Mono',monospace; font-size:.74rem;
  padding:.26rem .7rem; border-radius:999px; border:1px solid; }}
.hz-conf .dot {{ width:7px; height:7px; border-radius:50%; }}
.hz-evidence {{ margin:.4rem 0 0; padding:0; list-style:none; }}
.hz-evidence li {{ font-size:.84rem; color:{MUTED}; padding:.3rem 0; border-top:1px dashed {LINE}; }}
.hz-evidence li b {{ color:{AMBER}; font-weight:500; }}
.hz-uncert {{ font-size:.84rem; color:{ROSE}; background:rgba(248,113,113,.08);
  border:1px solid rgba(248,113,113,.25); border-radius:10px; padding:.5rem .7rem; margin-top:.5rem; }}

/* day header */
.hz-day {{ display:flex; align-items:baseline; gap:.9rem; flex-wrap:wrap;
  padding:.85rem 1.1rem; border-radius:14px; margin:1.3rem 0 .8rem;
  background:linear-gradient(90deg,rgba(255,107,107,.14),rgba(255,184,0,.05) 60%,transparent);
  border-left:3px solid {CORAL}; }}
.hz-day .n {{ font-family:'Playfair Display',serif; font-size:1.45rem; font-weight:700; }}
.hz-day .t {{ color:{MUTED}; font-size:.9rem; }}
.hz-day .w {{ margin-left:auto; font-family:'Spline Sans Mono',monospace; font-size:.75rem; color:{AMBER}; }}

/* destination cards */
.hz-dest {{ padding:0; overflow:hidden; display:flex; flex-direction:column; min-height:330px; }}
.hz-dest img {{ width:100%; height:150px; object-fit:cover; display:block; }}
.hz-dest .inner {{ padding:1rem 1.2rem 1.1rem; display:flex; flex-direction:column; flex:1; }}
.hz-dest .match {{ font-family:'Spline Sans Mono',monospace; color:{LAGOON}; font-size:.85rem; }}
.hz-dest .why {{ margin-top:auto; padding-top:.6rem; font-size:.8rem; color:{FAINT};
  border-top:1px dashed {LINE}; }}

/* stats */
.hz-stat {{ text-align:center; }}
.hz-stat .v {{ font-family:'Playfair Display',serif; font-size:1.9rem; font-weight:700;
  background:{GRAD}; -webkit-background-clip:text; background-clip:text; color:transparent; }}
.hz-stat .l {{ font-family:'Spline Sans Mono',monospace; font-size:.68rem;
  letter-spacing:.12em; text-transform:uppercase; color:{FAINT}; }}

[data-testid="stChatMessage"] {{ background:{SURFACE}; border:1px solid {LINE}; border-radius:16px; }}
[data-testid="stExpander"] {{ border:1px solid {LINE}; border-radius:12px; background:{SURFACE}; }}

@media (prefers-reduced-motion: reduce) {{ * {{ transition:none !important; }} }}
</style>
""", unsafe_allow_html=True)


# ============================================================================
# Offline destination art — gradient SVG scenes as data URIs (no network)
# ============================================================================
def scene_svg(c1: str, c2: str, emoji: str) -> str:
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 600 280'>
<defs><linearGradient id='sky' x1='0' y1='0' x2='0' y2='1'>
<stop offset='0' stop-color='{c1}'/><stop offset='1' stop-color='{c2}'/></linearGradient></defs>
<rect width='600' height='280' fill='url(#sky)'/>
<circle cx='470' cy='84' r='38' fill='#FFE8B0' opacity='.9'/>
<circle cx='470' cy='84' r='58' fill='#FFE8B0' opacity='.18'/>
<path d='M0 210 L110 150 L200 205 L300 140 L410 208 L520 155 L600 200 L600 280 L0 280 Z'
      fill='#0F172A' opacity='.55'/>
<path d='M0 235 L140 190 L260 238 L390 185 L600 232 L600 280 L0 280 Z'
      fill='#0F172A' opacity='.8'/>
<rect y='206' width='600' height='3' fill='#FFB800' opacity='.55'/>
<text x='40' y='120' font-size='64'>{emoji}</text></svg>"""
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


# ============================================================================
# Data — destinations + destination-aware itineraries
# ============================================================================
DESTINATIONS = [
    {"name": "Kyoto, Japan", "emoji": "⛩️", "match": 97, "c": ("#B44069", "#2A2150"),
     "desc": "Timeless temples, serene gardens, and the best food city you can cross on foot.",
     "months": "Nov · Apr", "budget": "¥12–18k/day",
     "why": "Culture 94 + food 88 + photography 95 all peak here"},
    {"name": "Bali, Indonesia", "emoji": "🌴", "match": 92, "c": ("#F2994A", "#14532D"),
     "desc": "Golden beaches, lush rice terraces, spiritual retreats and vivid Hindu culture.",
     "months": "May–Sep", "budget": "$40–70/day",
     "why": "Relax + photography blend; you loved it in 2023 — new regions to cover"},
    {"name": "Santorini, Greece", "emoji": "🏛️", "match": 91, "c": ("#3B82F6", "#0C4A6E"),
     "desc": "Cliffside villages, dramatic sunsets, and white-washed lanes built for a camera.",
     "months": "May · Sep–Oct", "budget": "€90–140/day",
     "why": "Photography 95 match — golden-hour capital of the Aegean"},
    {"name": "Paris, France", "emoji": "🗼", "match": 88, "c": ("#8B5CF6", "#312E81"),
     "desc": "Seine walks, world-class museums, and café culture as a daily rhythm.",
     "months": "Apr–Jun · Sep", "budget": "€100–160/day",
     "why": "Culture 94 anchor; food adventure covered by market streets"},
    {"name": "Barcelona, Spain", "emoji": "🦎", "match": 87, "c": ("#F59E0B", "#7C2D12"),
     "desc": "Gaudí's fever-dream architecture, Mediterranean beaches, and tapas grazing.",
     "months": "May–Jun · Sep", "budget": "€85–130/day",
     "why": "You rated Sagrada Família 5★ — unfinished business in the Gothic quarter"},
    {"name": "Swiss Alps, Switzerland", "emoji": "🏔️", "match": 85, "c": ("#60A5FA", "#1E3A5F"),
     "desc": "Majestic peaks and scenic trains through an alpine postcard.",
     "months": "Jun–Sep · Dec", "budget": "CHF 150–220/day",
     "why": "Scenic-transit match; walking 81 handles the valley trails"},
    {"name": "Banff, Canada", "emoji": "🐻", "match": 82, "c": ("#34D399", "#064E3B"),
     "desc": "Turquoise glacial lakes, towering peaks, and wildlife on the trail.",
     "months": "Jun–Sep", "budget": "C$130–190/day",
     "why": "Adventure 72 + photography — lake-light at dawn suits your pattern"},
    {"name": "Dubai, UAE", "emoji": "🏙️", "match": 81, "c": ("#F472B6", "#4C1D95"),
     "desc": "Futuristic skyline, desert safaris, and maximal everything.",
     "months": "Nov–Mar", "budget": "AED 500–900/day",
     "why": "Short-haul stopover fit; low walking days available"},
    {"name": "Marrakech, Morocco", "emoji": "🕌", "match": 79, "c": ("#FB7185", "#7F1D1D"),
     "desc": "Bustling souks, riad courtyards, and mint tea diplomacy.",
     "months": "Oct–Apr", "budget": "$60–100/day",
     "why": "Market-grazing food style matches; strong photo texture"},
    {"name": "Queenstown, New Zealand", "emoji": "🪂", "match": 76, "c": ("#38BDF8", "#134E4A"),
     "desc": "Bungee capital with fjord landscapes an hour away.",
     "months": "Dec–Feb", "budget": "NZ$140–200/day",
     "why": "Adventure 72 says yes; long-haul cost holds the score down"},
]

EV = {
    "dna": "Travel DNA history", "live": "Live data", "local": "Local insights",
    "web": "Internet reviews", "comm": "Community experiences", "pref": "Your stated preferences",
}


def seg(time, dur, icon, title, desc, conf, evidence, *, transport=None, walk=0.0,
        cost=None, crowd=None, note=None, alt=None):
    return {"time": time, "dur": dur, "icon": icon, "title": title, "desc": desc,
            "conf": conf, "evidence": evidence, "transport": transport, "walk": walk,
            "cost": cost, "crowd": crowd, "note": note, "alt": alt}


ITINERARIES = {
    "Kyoto, Japan": {
        "summary": "Three days built around light: dawn shrines before the crowds, foliage at "
                   "eye level, deliberate rest so the last day lands well. ~6–8 km on foot per day.",
        "month": "November", "group": 2, "budget_label": "₹95,000", "currency": "¥",
        "overall": (94, [("dna", "Built on 17 learned preferences from 4 completed trips"),
                         ("live", "Weather, crowd and transit feeds checked 2h ago"),
                         ("local", "Timings validated against local photographer guides")],
                    "Sunday's river boat is the one weather-sensitive block — fallback pre-planned."),
        "days": [
            {"n": 1, "date": "Sat, 14 Nov", "theme": "Southern Higashiyama on foot",
             "weather": "14°C · clear", "walk": 7.8, "segments": [
                seg("06:45", 150, "⛩️", "Fushimi Inari at dawn",
                    "Climb the first 2,000 torii before the crowds; turn at the Yotsutsuji viewpoint.",
                    95, [("dna", "You rated Fushimi Inari 5★ on the 2024 side-visit"),
                         ("live", "Crowd feed <15% capacity before 08:00 in November")],
                    transport="JR Nara line → Tofukuji (5 min)", walk=4.2, cost=0, crowd="low",
                    alt=("Tofukuji gardens first", "Peak maples, but 09:00 gates lose the crowd-free window.")),
                seg("09:30", 45, "☕", "Vermillion espresso bar",
                    "Third-wave coffee at the trail foot. Yuzu toast is the move.",
                    84, [("web", "4.6★ across 900+ reviews"),
                         ("dna", "You pick specialty coffee over hotel breakfast 7 of 8 times")],
                    walk=0.4, cost=1400, crowd="moderate"),
                seg("10:45", 180, "🏯", "Kiyomizu-dera + Sannenzaka lanes",
                    "The wooden stage over the maple valley, then the preserved Edo lanes. "
                    "Best light before 13:00.",
                    74, [("comm", "Foliage week draws heavy foot traffic after 11:00"),
                         ("pref", "Matches your temples + photography interests")],
                    walk=2.6, cost=400, crowd="busy",
                    note="Crowds in peak foliage week are volatile — I re-check live data the night before.",
                    alt=("Eikan-dō evening illumination", "Equal foliage, thinner crowds, +¥1,000 ticket.")),
                seg("14:00", 60, "🍜", "Omen Kodai-ji — udon lunch",
                    "Hand-cut udon with seasonal vegetables, exactly on your walking route.",
                    88, [("dna", "Japanese is your top-rated cuisine"),
                         ("web", "Consistently rated best udon in Higashiyama")],
                    walk=0.6, cost=2600, crowd="moderate"),
            ]},
            {"n": 2, "date": "Sun, 15 Nov", "theme": "Arashiyama — bamboo & river light",
             "weather": "13°C · partly cloudy", "walk": 6.1, "segments": [
                seg("07:30", 90, "🎋", "Bamboo grove before the buses",
                    "Enter from the Nonomiya side; low sun through the culms is the shot.",
                    92, [("local", "Grove near-empty before 08:30 even in peak season"),
                         ("dna", "Photography 95 — dawn slots consistently accepted")],
                    walk=1.8, cost=0, crowd="low"),
                seg("10:00", 120, "🛶", "Hozugawa river boat descent",
                    "Two hours through the gorge, maples at eye level. Book the 10:00 run.",
                    68, [("comm", "Highly rated but cancelled on rain days"),
                         ("live", "40% rain probability Sunday afternoon")],
                    transport="JR Sagano line back (8 min)", walk=0.9, cost=4500, crowd="moderate",
                    note="If rain hits I swap to the Sagano scenic railway automatically and re-time lunch.",
                    alt=("Sagano scenic railway", "Covered carriages, same gorge, runs in light rain.")),
                seg("12:45", 75, "🍱", "Shigetsu — shojin ryori",
                    "Zen temple vegetarian kaiseki inside Tenryu-ji. A different register from street food.",
                    80, [("pref", "You asked for one proper sit-down meal per day"),
                         ("web", "Michelin-listed; reservation availability confirmed")],
                    walk=0.5, cost=3800, crowd="low"),
                seg("15:30", 120, "🌙", "Ryokan onsen + rest block",
                    "Deliberate empty space — day 3 starts early. Bath, tea, feet up.",
                    89, [("dna", "Your past trips show energy dips on day-2 afternoons")],
                    walk=0.0, cost=0, crowd="low"),
            ]},
            {"n": 3, "date": "Mon, 16 Nov", "theme": "Golden pavilion, market grazing, dusk departure",
             "weather": "15°C · sunny", "walk": 5.4, "segments": [
                seg("08:50", 75, "🏆", "Kinkaku-ji at opening",
                    "The gold pavilion over the mirror pond — Monday opening is the week's thinnest crowd.",
                    87, [("live", "Monday-morning footfall runs 35% below weekend"),
                         ("pref", "On your must-see list")],
                    transport="Bus 205 → Nishiki (25 min)", walk=1.6, cost=500, crowd="moderate"),
                seg("11:30", 90, "🍡", "Nishiki market grazing lunch",
                    "Stall by stall: tamagoyaki, tako skewers, black-sesame soft serve. Stop when happy.",
                    85, [("dna", "Market grazing beat sit-down lunches 3:1 in your history"),
                         ("comm", "Top last-day pick among food-focused travellers")],
                    walk=1.2, cost=2500, crowd="busy"),
                seg("16:10", 80, "🚄", "Haruka express to Kansai Airport",
                    "Reserved seats, luggage space confirmed. 2h40m buffer before the flight.",
                    96, [("live", "On-time performance 98% this month")],
                    walk=0.6, cost=3600, crowd="low"),
            ]},
        ],
    },
    "Bali, Indonesia": {
        "summary": "Three days across two Balis: Ubud's ridgewalks and rice terraces, then the "
                   "Bukit's cliff temples and surf-watching sunsets. Paced slow on purpose.",
        "month": "June", "group": 2, "budget_label": "₹80,000", "currency": "Rp ",
        "overall": (88, [("dna", "You completed Bali 2023 — this route covers what you missed"),
                         ("live", "Dry-season forecasts stable for the window"),
                         ("comm", "Route pattern validated by repeat-visitor reports")], None),
        "days": [
            {"n": 1, "date": "Day 1", "theme": "Ubud — ridge walk & terraces",
             "weather": "29°C · sunny", "walk": 6.4, "segments": [
                seg("07:00", 90, "🌾", "Campuhan ridge walk",
                    "Grass-spine ridge above two river valleys — cool air and empty before 08:30.",
                    91, [("local", "Locals walk it at dawn; midday heat makes it brutal"),
                         ("dna", "Photography 95 — dawn slots consistently accepted")],
                    walk=3.8, cost=0, crowd="low"),
                seg("10:00", 120, "🛕", "Tirta Empul water temple",
                    "Purification pools and spring-fed shrines. Sarongs provided at the gate.",
                    82, [("web", "4.7★; strongest-rated temple experience near Ubud"),
                         ("pref", "Matches your culture interest")],
                    transport="Grab car (25 min)", walk=1.1, cost=50000, crowd="moderate",
                    alt=("Gunung Kawi", "Fewer visitors, dramatic rock-cut shrines, +200 stairs.")),
                seg("13:00", 75, "🥥", "Warung lunch over the paddies",
                    "Nasi campur with a terrace view — order the sambal matah on the side.",
                    86, [("dna", "You favour local warungs over hotel dining 5:1")],
                    walk=0.5, cost=90000, crowd="low"),
            ]},
            {"n": 2, "date": "Day 2", "theme": "Bukit — cliffs & surf light",
             "weather": "30°C · clear", "walk": 4.2, "segments": [
                seg("09:00", 150, "🏖️", "Bingin & Padang Padang beaches",
                    "Cliff-stair beaches on the Bukit's west face; watch the reef break from the warung.",
                    84, [("comm", "Best swell-watching without surfing yourself"),
                         ("live", "Mid-tide window 09:00–12:00 for beach width")],
                    transport="Scooter or Grab (20 min hops)", walk=2.4, cost=15000, crowd="moderate"),
                seg("17:30", 120, "🌅", "Uluwatu temple at sunset + kecak",
                    "Cliff-edge temple, then the fire-chant kecak dance as the sun drops.",
                    72, [("web", "Iconic but heavily attended; kecak sells out"),
                         ("live", "Sunset 18:10; haze risk moderate this week")],
                    walk=1.4, cost=150000, crowd="busy",
                    note="If the kecak sells out I book the 19:30 second show and shift dinner.",
                    alt=("Sunset at Karang Boma cliff", "Same light, no crowds, no dance — bring water.")),
            ]},
            {"n": 3, "date": "Day 3", "theme": "Slow morning, market, departure",
             "weather": "29°C · sunny", "walk": 3.1, "segments": [
                seg("08:00", 90, "🏊", "Pool + long breakfast",
                    "Deliberate empty block — you land better after slow final mornings.",
                    90, [("dna", "Trip-completion pattern: rushed last days rated 2★ lower")],
                    walk=0.0, cost=0, crowd="low"),
                seg("10:30", 90, "🧺", "Ubud art market sweep",
                    "Rattan, textiles, coffee beans. Haggle from 40% of the opening price, kindly.",
                    78, [("comm", "Morning stock is freshest; afternoon is tour-bus pricing")],
                    walk=1.6, cost=200000, crowd="moderate"),
                seg("13:30", 90, "🚗", "Transfer to DPS airport",
                    "Pre-booked car; Friday traffic buffer included.",
                    93, [("live", "Route running 12 min over baseline — buffer absorbs it")],
                    walk=0.4, cost=350000, crowd="low"),
            ]},
        ],
    },
}


def generic_itinerary(dest: str) -> dict:
    """Fallback template for destinations without a hand-built plan."""
    city = dest.split(",")[0]
    d = next((x for x in DESTINATIONS if x["name"] == dest), None)
    flavor = d["desc"] if d else "the city's signature sights"
    return {
        "summary": f"A balanced three-day first pass at {city} — anchor sights at low-crowd "
                   f"hours, one standout meal a day, and slack built in for wandering.",
        "month": "Flexible", "group": 2, "budget_label": "TBD", "currency": "",
        "overall": (76, [("web", f"Route assembled from top-rated {city} traveller reports"),
                         ("dna", "Paced to your walking tolerance (81/100)")],
                    "First-pass plan — confidence rises once dates and budget are locked."),
        "days": [
            {"n": i, "date": f"Day {i}", "theme": t, "weather": "—", "walk": w, "segments": [
                seg("09:00", 180, "📍", f"{city}: {t.lower()}",
                    f"Morning block: {flavor}",
                    76, [("web", "Aggregated from recent traveller reviews")],
                    walk=w * 0.6, crowd="moderate"),
                seg("13:00", 75, "🍽️", "Signature lunch spot",
                    "Highest-rated local-cuisine pick within walking distance of the morning block.",
                    74, [("web", "4.5★+ with consistent recent reviews"),
                         ("dna", "Cuisine style matched to your food profile")],
                    walk=0.5, crowd="moderate"),
                seg("15:30", 150, "🌇", "Golden-hour viewpoint",
                    "The classic photo vantage, timed for late light.",
                    78, [("comm", "Community-tagged best-light location"),
                         ("dna", "Photography 95 — always your highest-rated block")],
                    walk=w * 0.3, crowd="busy"),
            ]}
            for i, (t, w) in enumerate(
                [("Arrival & old town", 4.5), ("Anchor sights", 6.5), ("Nature & departure", 5.0)], 1)
        ],
    }


def get_itinerary(dest: str) -> dict:
    return ITINERARIES.get(dest) or generic_itinerary(dest)


DNA_AXES = {"Adventure": 72, "Culture": 94, "Food": 88, "Photography": 95,
            "Relax": 68, "Walking": 81, "Nightlife": 34}

DNA_PREFS = [
    ("cuisines", "Japanese · Thai · South Indian"),
    ("hotel style", "Boutique, design-forward — twin, high floor"),
    ("flying", "ANA / Vistara · window seat"),
    ("visa history", "Japan (2024) · Thailand (2023) · Schengen (2022)"),
    ("loved before", "Fushimi Inari · Wat Arun · Sagrada Família"),
]

DNA_EVENTS = [
    ("03 Jul · 14:20", "Photography", "Photography 91 → 95",
     "You asked for golden-hour slots at three viewpoints in one session"),
    ("03 Jul · 11:05", "Food", "Food 84 → 88",
     "Accepted the standing-bar izakaya over the hotel restaurant"),
    ("01 Jul · 18:40", "Culture", "Culture 90 → 94",
     "Extended the temple loop twice on the last trip"),
    ("28 Jun · 09:15", "Walking", "Walking 85 → 81",
     "Trimmed the 14 km loop to 9 km on day 2 — pace preference updated"),
]


# ============================================================================
# Render helpers
# ============================================================================
def rule():
    st.markdown('<hr class="hz-rule">', unsafe_allow_html=True)


def conf_badge_html(score: int) -> str:
    color, label = CONF[conf_band(score)]
    return (f'<span class="hz-conf" style="color:{color};border-color:{color}55;'
            f'background:{color}14"><span class="dot" style="background:{color}">'
            f'</span>{score}% · {label}</span>')


def evidence_block(score: int, evidence: list, note: str | None, key: str):
    st.markdown(conf_badge_html(score), unsafe_allow_html=True)
    with st.expander("Why this score — evidence"):
        items = "".join(f"<li><b>{EV.get(s, str(s).title())}</b> — {html.escape(str(d))}</li>" for s, d in evidence)
        st.markdown(f'<ul class="hz-evidence">{items}</ul>', unsafe_allow_html=True)
        if note:
            st.markdown(f'<div class="hz-uncert">⚠ {html.escape(note)}</div>',
                        unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=3600)
def cached_place_photo(photo_name: str, api_key: str):
    """Fetched server-side and cached by Streamlit — the API key never reaches
    the browser, and repeat renders (Streamlit reruns the whole script on every
    interaction) don't re-hit the Google API for the same photo."""
    from src.tools import google_maps
    try:
        return google_maps.fetch_place_photo(photo_name, api_key)
    except Exception:
        return None


@st.cache_data(show_spinner=False, ttl=3600)
def cached_street_view(lat: float, lng: float, api_key: str):
    from src.tools import google_maps
    try:
        return google_maps.fetch_street_view_image(lat, lng, api_key)
    except Exception:
        return None


def segment_card(s: dict, currency: str, key: str):
    chips = []
    if s["walk"]:
        chips.append(f'<span class="hz-chip">🚶 <b>{s["walk"]:.1f} km</b></span>')
    if s["cost"] is not None:
        c = "free" if s["cost"] == 0 else f"{currency}{s['cost']:,}"
        chips.append(f'<span class="hz-chip">💰 <b>{c}</b></span>')
    if s["crowd"]:
        icon = {"low": "◌", "moderate": "◐", "busy": "●"}[s["crowd"]]
        chips.append(f'<span class="hz-chip">{icon} {s["crowd"]} crowd</span>')
    if s["transport"]:
        chips.append(f'<span class="hz-chip">→ next: <b>{html.escape(s["transport"])}</b></span>')
    if s.get("rating"):
        chips.append(f'<span class="hz-chip">⭐ <b>{s["rating"]}</b> Google</span>')
    address_line = (f'<div class="hz-body" style="font-size:.8rem;color:{FAINT}">'
                     f'📍 {html.escape(s["address"])}</div>' if s.get("address") else "")
    st.markdown(
        f"""<div class="hz-card">
              <div class="hz-kicker"><span class="hz-time">{s['time']}</span>
                &nbsp;·&nbsp;{s['dur']} min</div>
              <div class="hz-title">{s['icon']} {html.escape(s['title'])}</div>
              <div class="hz-body">{html.escape(s['desc'])}</div>
              {address_line}
              <div class="hz-meta">{''.join(chips)}</div>
            </div>""", unsafe_allow_html=True)
    if s.get("image_bytes"):
        st.image(s["image_bytes"], width="stretch")
    evidence_block(s["conf"], s["evidence"], s["note"], key)
    if s["alt"]:
        with st.expander("Alternative"):
            st.markdown(f"**{s['alt'][0]}** — {s['alt'][1]}")


def stat(value: str, label: str):
    st.markdown(f'<div class="hz-card hz-stat"><div class="v">{value}</div>'
                f'<div class="l">{label}</div></div>', unsafe_allow_html=True)


def dna_radar() -> go.Figure:
    labels = list(DNA_AXES) + [list(DNA_AXES)[0]]
    values = list(DNA_AXES.values()) + [list(DNA_AXES.values())[0]]
    fig = go.Figure(go.Scatterpolar(
        r=values, theta=labels, fill="toself",
        fillcolor="rgba(255,107,107,0.22)",
        line=dict(color=CORAL, width=2.5), marker=dict(size=7, color=AMBER),
        hovertemplate="%{theta}: %{r}/100<extra></extra>"))
    fig.update_layout(
        polar=dict(bgcolor="rgba(0,0,0,0)",
                   radialaxis=dict(range=[0, 100], showticklabels=False,
                                   gridcolor=LINE, linecolor=LINE),
                   angularaxis=dict(gridcolor=LINE, linecolor=LINE,
                                    tickfont=dict(family="Spline Sans Mono",
                                                  size=11, color=MUTED))),
        paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
        margin=dict(l=60, r=60, t=40, b=40), height=420)
    return fig


def itinerary_pdf(dest: str, it: dict) -> bytes:
    def A(s):  # latin-1 safe
        return (s.replace("—", "-").replace("–", "-").replace("·", "|")
                 .replace("’", "'").replace("“", '"').replace("”", '"')
                 .replace("¥", "JPY ").replace("₹", "INR ")
                 .encode("latin-1", "replace").decode("latin-1"))

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_fill_color(15, 23, 42)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")
    pdf.set_draw_color(255, 107, 107)
    pdf.set_line_width(0.8)
    pdf.line(15, 18, pdf.w - 15, 18)
    pdf.set_y(24)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(241, 245, 249)
    pdf.cell(0, 11, A(f"Horizon | {dest}"), ln=1)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(148, 163, 184)
    pdf.multi_cell(0, 5.5, A(it["summary"]))
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(255, 184, 0)
    pdf.cell(0, 8, A(f"Overall confidence {it['overall'][0]}% | {it['month']} | group of {it['group']} | budget {it['budget_label']}"), ln=1)
    pdf.ln(2)
    for day in it["days"]:
        y = pdf.get_y()
        pdf.set_fill_color(30, 41, 55)
        pdf.rect(15, y, pdf.w - 30, 11, style="F")
        pdf.set_line_width(1.0)
        pdf.line(15, y, 15, y + 11)
        pdf.set_xy(19, y + 2)
        pdf.set_font("Helvetica", "B", 11.5)
        pdf.set_text_color(241, 245, 249)
        pdf.cell(0, 7, A(f"Day {day['n']} - {day['date']}  |  {day['theme']}  "
                         f"({day['walk']:.1f} km on foot)"))
        pdf.set_y(y + 14)
        for s in day["segments"]:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(255, 107, 107)
            pdf.cell(18, 6, A(s["time"]))
            pdf.set_text_color(241, 245, 249)
            pdf.cell(0, 6, A(s["title"]), new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(33)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(148, 163, 184)
            pdf.multi_cell(0, 4.8, A(s["desc"]))
            meta = [f"{s['dur']} min"]
            if s["walk"]:
                meta.append(f"{s['walk']:.1f} km walk")
            if s["crowd"]:
                meta.append(f"crowd: {s['crowd']}")
            meta.append(f"confidence {s['conf']}%")
            pdf.set_x(33)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(255, 184, 0)
            pdf.multi_cell(0, 4.4, A("  |  ".join(meta)))
            pdf.ln(1.2)
        pdf.ln(2)
    return bytes(pdf.output())


# ============================================================================
# Navigation
# ============================================================================
if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"
if "current_destination" not in st.session_state:
    st.session_state.current_destination = "Kyoto, Japan"
if "reset_stage" not in st.session_state:
    st.session_state.reset_stage = "request"  # "request" -> "confirm", for Forgot Password
if "reset_identifier" not in st.session_state:
    st.session_state.reset_identifier = None
if "reset_dev_token" not in st.session_state:
    st.session_state.reset_dev_token = None


def set_page(p: str):
    st.session_state.current_page = p
    st.rerun()


with st.sidebar:
    st.markdown(
        """<div style="padding:.3rem 0 1.1rem">
             <div style="font-family:'Playfair Display',serif;font-size:1.6rem;font-weight:700">
               🌊 Horizon</div>
             <div style="font-family:'Spline Sans Mono',monospace;font-size:.64rem;
                         letter-spacing:.16em;text-transform:uppercase;color:#FFB800">
               your intelligent travel companion</div>
           </div>""", unsafe_allow_html=True)

    PAGES = [("Home", "🏠"), ("Chat", "💬"), ("Itinerary", "🗺️"),
             ("Travel DNA", "🧬"), ("Explore", "✨")]
    auth_user = st.session_state.auth_user
    PAGES.append(("Profile", "👤") if auth_user else ("Login", "🔑"))
    if not auth_user:
        PAGES.append(("Sign Up", "📝"))
    for p, icon in PAGES:
        active = st.session_state.current_page == p
        if st.button(f"{icon}  {p}", key=f"nav_{p}", width="stretch",
                     type="primary" if active else "secondary"):
            set_page(p)

    if auth_user:
        st.caption(f"Logged in as **{auth_user.email or auth_user.phone}**")
        if st.button("🚪 Log Out", key="nav_logout", width="stretch"):
            st.session_state.auth_user = None
            set_page("Home")

    st.markdown(
        """<div style="margin-top:1.6rem;padding-top:1rem;border-top:1px solid #334155;
                    font-size:.72rem;color:#64748B">
             Horizon Travel AI · Capstone demo<br>UI shell · mock data mode</div>""",
        unsafe_allow_html=True)

    rule()
    st.markdown("### 🛠️ Backend Debug")
    if "travel_state" in st.session_state:
        state = st.session_state.travel_state
        st.json(state.preferences.model_dump(), expanded=False)
        st.write(f"**Agent**: {state.active_agent}")

page = st.session_state.current_page


# ============================================================================
# HOME
# ============================================================================
if page == "Home":
    st.markdown(
        """<div class="hz-hero">
             <div class="hz-eyebrow">Horizon · autonomous travel intelligence</div>
             <h1>Welcome back, Hirak.<br>Plans that show <em>their work</em>.</h1>
             <p>Every recommendation carries a confidence score and the evidence behind it.
                Horizon learns your Travel DNA trip after trip — and asks before it guesses.</p>
           </div>""", unsafe_allow_html=True)
    st.write("")

    it = get_itinerary(st.session_state.current_destination)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        stat(f"{it['overall'][0]}%", "plan confidence")
    with c2:
        stat("4", "trips completed")
    with c3:
        stat("78", "dna signals learned")
    with c4:
        stat("4", "cities visited")

    rule()
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown("### Your active plan")
        st.markdown(
            f"""<div class="hz-card">
                  <div class="hz-kicker">{it['month']} · {len(it['days'])} days · group of {it['group']}</div>
                  <div class="hz-title">📍 {html.escape(st.session_state.current_destination)}</div>
                  <div class="hz-body">{html.escape(it['summary'])}</div>
                </div>""", unsafe_allow_html=True)
        evidence_block(*it["overall"], key="home-conf")
        st.write("")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("🗺️ Open the full itinerary", width="stretch"):
                set_page("Itinerary")
        with b2:
            if st.button("💬 Change something in chat", width="stretch"):
                set_page("Chat")
    with right:
        st.markdown("### System status")
        st.markdown(
            """<div class="hz-card">
                 <div class="hz-kicker">monitoring · circuit breaker</div>
                 <div class="hz-title">🟢 Live monitoring active</div>
                 <div class="hz-body">Weather, crowd and transit feeds refreshing. Monitoring
                 pauses after 3 minutes of inactivity to avoid stale checks — and resumes
                 the moment you're back.</div>
               </div>
               <div class="hz-card">
                 <div class="hz-kicker">how horizon decides</div>
                 <div class="hz-body"><b style="color:#F1F5F9">Transparency over convenience.</b>
                 Confidence under 70% always ships with an uncertainty note and a pre-planned
                 fallback. You approve every booking-grade action — autonomy stops at your
                 wallet.</div>
               </div>""", unsafe_allow_html=True)


# ============================================================================
# CHAT — Wired to RootOrchestrator backend
# ============================================================================
elif page == "Chat":
    from src.orchestrator import RootOrchestrator, HOTEL_NIGHTLY_RATES
    from src.models.state import TravelState

    TRANSPORT_MODE_ICONS = {"flight": "✈️", "train": "🚆", "bus": "🚌", "ship": "🚢"}
    HOTEL_TIER_CARDS = [
        ("budget", "💰", "Budget", "Hostels & simple stays"),
        ("mid_range", "🏨", "Mid-range", "3-star comfort"),
        ("luxury", "✨", "Luxury", "5-star resorts"),
        ("boutique", "🎨", "Boutique", "Unique, design-forward stays"),
        ("no_hotel", "🚫", "No hotel needed", "Staying with family/friends or already sorted"),
    ]
    FOOD_PREF_LABELS = {
        "vegetarian": "🥗 Vegetarian", "vegan": "🌱 Vegan",
        "non_veg": "🍗 Non-vegetarian", "no_restrictions": "🍽️ No restrictions",
    }

    head_col, replan_col = st.columns([4, 1])
    with head_col:
        st.markdown("## 💬 Chat with Horizon")
        st.markdown('<p style="color:#94A3B8;margin-top:-.4rem">Describe the trip in your own '
                    "words. Horizon uses multi-agent orchestration to plan your trip.</p>", unsafe_allow_html=True)
    with replan_col:
        st.write("")
        if st.button("🔄 Replan trip", width="stretch",
                     help="Clear this conversation and start planning a new trip from scratch"):
            st.session_state.travel_state = TravelState(session_id="hirak_001")
            st.rerun()
    rule()

    # Initialize backend in session state
    if "orchestrator" not in st.session_state:
        st.session_state.orchestrator = RootOrchestrator()
    if "travel_state" not in st.session_state:
        st.session_state.travel_state = TravelState(session_id="hirak_001")

    state = st.session_state.travel_state

    stage_labels = {
        "basic_info": "Gathering trip basics",
        "transport": "Transport & return journey",
        "hotel_food": "Hotel & food preferences",
        "ready_to_plan": "Awaiting your go-ahead",
        "planning": "Building itinerary…",
        "complete": "Itinerary ready",
    }
    current_stage = state.preferences.planning_stage
    st.markdown(
        f'<span class="hz-chip">📍 <b>{stage_labels.get(current_stage, current_stage)}</b></span>',
        unsafe_allow_html=True)
    st.write("")

    # Display chat history
    for msg in state.messages:
        with st.chat_message(msg["role"], avatar="🧭" if msg["role"] == "assistant" else None):
            st.markdown(msg["content"])

    orchestrator = st.session_state.orchestrator

    # --- "Not sure yet" budget shortcut ---
    if current_stage == "basic_info" and orchestrator.is_only_missing_budget(state):
        if st.button("🤷 Not sure yet — estimate my budget for me", width="stretch"):
            orchestrator.mark_budget_flexible(state)
            st.rerun()
        st.caption("Or just tell me a number in the chat below.")

    # --- Interactive transport option cards (outbound) ---
    if (current_stage == "transport" and state.preferences.arrival_time
            and not state.preferences.transport_suggestions and state.transport_options):
        st.markdown("#### ✈️ Choose your transport")
        cols = st.columns(len(state.transport_options))
        for col, option in zip(cols, state.transport_options):
            with col:
                icon = TRANSPORT_MODE_ICONS.get(option["mode"].lower(), "📍")
                st.markdown(
                    f"""<div class="hz-card">
                          <div class="hz-title">{icon} {html.escape(option['mode'].title())}</div>
                          <div class="hz-body">₹{option['price']:,} · {html.escape(option['duration'])}<br>
                          {html.escape(option['departure'])} → {html.escape(option['arrival'])}</div>
                          <div class="hz-body" style="font-size:.8rem;color:#64748B">
                          {html.escape(option['why'])}</div>
                        </div>""", unsafe_allow_html=True)
                if st.button(f"Select {option['mode'].title()}",
                             key=f"transport_{option['mode']}_{option['price']}", width="stretch"):
                    orchestrator.select_transport_option(state, option)
                    st.rerun()
        st.caption("Or just type which one you'd like below.")

    # --- Interactive transport option cards (return journey) ---
    elif (current_stage == "transport" and state.preferences.departure_time
            and not state.preferences.return_transport_suggestions and state.transport_options):
        st.markdown("#### 🔁 Choose your return transport")
        cols = st.columns(len(state.transport_options))
        for col, option in zip(cols, state.transport_options):
            with col:
                icon = TRANSPORT_MODE_ICONS.get(option["mode"].lower(), "📍")
                st.markdown(
                    f"""<div class="hz-card">
                          <div class="hz-title">{icon} {html.escape(option['mode'].title())}</div>
                          <div class="hz-body">₹{option['price']:,} · {html.escape(option['duration'])}<br>
                          {html.escape(option['departure'])} → {html.escape(option['arrival'])}</div>
                          <div class="hz-body" style="font-size:.8rem;color:#64748B">
                          {html.escape(option['why'])}</div>
                        </div>""", unsafe_allow_html=True)
                if st.button(f"Select {option['mode'].title()}",
                             key=f"return_transport_{option['mode']}_{option['price']}", width="stretch"):
                    orchestrator.select_return_transport_option(state, option)
                    st.rerun()
        st.caption("Or just type which one you'd like below.")

    # --- Interactive hotel tier cards ---
    elif current_stage == "hotel_food" and not state.preferences.hotel_type:
        st.markdown("#### 🏨 Choose your hotel tier")
        days = state.preferences.days or 1
        cols = st.columns(len(HOTEL_TIER_CARDS))
        for col, (tier, icon, label, desc) in zip(cols, HOTEL_TIER_CARDS):
            rate = HOTEL_NIGHTLY_RATES.get(tier, 4000)
            cost_line = (f"~₹{rate:,}/night<br><b>₹{rate * days:,}</b> for {days} nights"
                         if tier != "no_hotel" else "<b>₹0</b> — nothing budgeted for lodging")
            with col:
                st.markdown(
                    f"""<div class="hz-card">
                          <div class="hz-title">{icon} {label}</div>
                          <div class="hz-body">{desc}<br>{cost_line}</div>
                        </div>""", unsafe_allow_html=True)
                if st.button(f"Select {label}", key=f"hotel_{tier}", width="stretch"):
                    orchestrator.select_hotel_tier(state, tier)
                    st.rerun()
        st.caption("Or just type your preference below.")

    # --- Interactive food preference chips ---
    elif current_stage == "hotel_food" and state.preferences.hotel_type and not state.preferences.food_preferences:
        st.markdown("#### 🍽️ Food preferences")
        selected = st.multiselect(
            "Pick one or more", options=list(FOOD_PREF_LABELS.keys()),
            format_func=lambda k: FOOD_PREF_LABELS[k], key="food_pref_select")
        if st.button("Continue", disabled=not selected, width="stretch", type="primary"):
            orchestrator.select_food_preferences(state, selected)
            st.rerun()
        st.caption("Or just type your preference below.")

    # --- Ready to build ---
    elif current_stage == "ready_to_plan" and not state.itinerary_data:
        if st.button("🚀 Build my itinerary", width="stretch", type="primary"):
            with st.spinner("Building your itinerary..."):
                orchestrator.process_turn(state, "yes")
            st.rerun()
        st.caption("Or tell me in the chat if you'd like to change anything first.")

    # --- Live running budget, once real transport/hotel numbers are known ---
    if state.preferences.transport_cost is not None or state.preferences.hotel_cost_per_night is not None:
        bd = orchestrator.budget_breakdown(state)
        badge_color = "#F87171" if bd["over_budget"] else "#5EEAD4"
        over_note = (f" ⚠️ over your ₹{bd['budget']:,} budget" if bd["over_budget"] else "")
        st.markdown(
            f"""<div class="hz-card" style="border-color:{badge_color}55">
                  <div class="hz-kicker">running budget estimate</div>
                  <div class="hz-body">Transport ₹{bd['transport']:,} · Hotel ₹{bd['hotel_total']:,} ·
                  Activities (est.) ₹{bd['activities_buffer']:,}</div>
                  <div class="hz-title" style="color:{badge_color}">Total ≈ ₹{bd['grand_total']:,}{over_note}</div>
                </div>""", unsafe_allow_html=True)

    # Handle user input
    if prompt := st.chat_input("e.g. “Kyoto in November — we love food and temples”"):
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.spinner("Horizon is thinking..."):
            # Call the Root Orchestrator
            response = st.session_state.orchestrator.process_turn(state, prompt)
            
        with st.chat_message("assistant", avatar="🧭"):
            st.markdown(response)
        
        st.rerun()
# ============================================================================
# ITINERARY — destination-aware, rich cards, one-click PDF
# ============================================================================
elif page == "Itinerary":
    st.markdown("## 📍 Your AI-Generated Itinerary")
    
    # Check if the Architect has populated the state
    # Safely access state
    ts = st.session_state.get("travel_state")
    if not ts or not getattr(ts, "itinerary_data", None):
        st.info("Your itinerary is still being planned. Please complete your chat request first!")
    else:
        it = ts.itinerary_data
        days = it.get("itinerary", [])
        activities_total = sum((seg.get("cost") or 0) for day in days for seg in day.get("segments", []))

        # Hotel + transport aren't part of the LLM-authored day-by-day segments, so they're
        # estimated deterministically here rather than depending on the model to account for
        # them — otherwise "Total Estimated Spend" silently excludes two of the biggest
        # trip costs and looks far cheaper than the trip will actually be. Prefer the
        # traveler's actual selected transport price + hotel tier when available (set via
        # the Chat page's interactive cards or matched text), falling back to the flat
        # per-day heuristic only if those were never captured.
        orchestrator = st.session_state.get("orchestrator")
        p = ts.preferences
        if orchestrator and p.transport_cost is not None and p.hotel_cost_per_night is not None:
            hotel_transport_estimate = ((p.transport_cost or 0) + (p.return_transport_cost or 0)
                                         + p.hotel_cost_per_night * (p.days or 0))
        elif orchestrator:
            hotel_transport_estimate = orchestrator.estimate_trip_cost(p.destination, p.days, p.hotel_type)
        else:
            hotel_transport_estimate = 0
        grand_total = activities_total + hotel_transport_estimate
        budget = ts.preferences.budget

        # Summary Header
        st.markdown("### Plan Overview")
        hotel_label = ts.preferences.hotel_type.replace('_', ' ').title() if ts.preferences.hotel_type else "N/A"
        st.write(f"Hotel tier: **{hotel_label}**")
        st.write(f"Activities & food: ₹{activities_total:,}")
        st.write(f"Estimated hotel & transport (approx., {ts.preferences.days or '?'} days): "
                 f"₹{hotel_transport_estimate:,}")
        st.write(f"**Estimated grand total: ₹{grand_total:,}**")
        st.write(f"Your budget: ₹{budget:,}" if budget else "Your budget: N/A")
        if budget and grand_total > budget:
            st.warning(f"⚠️ This plan is approximately ₹{grand_total - budget:,} over your stated budget.")
        if ts.preferences.checkin_advice:
            st.write(f"🛫 Outbound: {ts.preferences.checkin_advice}")
        if ts.preferences.return_checkin_advice:
            st.write(f"🛬 Return: {ts.preferences.return_checkin_advice}")
        rule()

        # Real place photo / Street View imagery — only attempted when a Google
        # Maps key is configured and a segment was actually grounded to a real
        # place (has a photo_name or coordinates). Cached per photo/coordinate so
        # a Streamlit rerun (triggered by any click anywhere) doesn't re-hit the
        # Google API for images already fetched this session.
        google_api_key = os.environ.get("GOOGLE_MAPS_API_KEY")

        # Render Day Cards
        for day in days:
            day_total = sum((seg.get("cost") or 0) for seg in day.get("segments", []))
            st.markdown(f"""<div class="hz-day">
                            <span class="n">Day {day.get('n', '?')}</span>
                            <span class="t">{html.escape(day.get('theme', day.get('date', '')))}</span>
                            <span class="w">Total: ₹{day_total:,}</span>
                        </div>""", unsafe_allow_html=True)

            for i, seg in enumerate(day.get("segments", [])):
                evidence = seg.get("evidence") or [("pref", "Based on your preferences")]
                alt = seg.get("alt")

                image_bytes = None
                if google_api_key:
                    if seg.get("photo_name"):
                        image_bytes = cached_place_photo(seg["photo_name"], google_api_key)
                    elif seg.get("lat") is not None and seg.get("lng") is not None:
                        image_bytes = cached_street_view(seg["lat"], seg["lng"], google_api_key)

                segment_card({
                    "time": seg.get("time", "—"),
                    "dur": seg.get("dur", 60),
                    "icon": seg.get("icon", "📍"),
                    "title": seg.get("title", "Activity"),
                    "desc": seg.get("desc", ""),
                    "conf": seg.get("conf", 80),
                    "evidence": [tuple(e) for e in evidence],
                    "cost": seg.get("cost"),
                    "transport": seg.get("transport"),
                    "walk": seg.get("walk", 0.0) or 0.0,
                    "crowd": seg.get("crowd"),
                    "note": seg.get("note"),
                    "alt": tuple(alt) if alt else None,
                    "rating": seg.get("rating"),
                    "address": seg.get("address"),
                    "image_bytes": image_bytes,
                }, "₹", key=f"d{day.get('n', 0)}s{i}")


# ============================================================================
# TRAVEL DNA — radar + preferences + learning feed (PRD §2.2)
# ============================================================================
elif page == "Travel DNA":
    st.markdown("## 🧬 Your Travel DNA")
    st.markdown('<p style="color:#94A3B8;margin-top:-.4rem">What Horizon has learned about '
                "how you travel — refined after every interaction, private by default.</p>",
                unsafe_allow_html=True)
    rule()

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.plotly_chart(dna_radar(), width="stretch", config={"displayModeBar": False})
        st.markdown('<div class="hz-kicker" style="text-align:center">each axis 0–100 · '
                    "hover for values · shaped by 4 completed trips</div>",
                    unsafe_allow_html=True)
    with right:
        st.markdown("#### Learned preferences")
        for kicker, value in DNA_PREFS:
            st.markdown(
                f'<div class="hz-card" style="padding:.75rem 1.05rem">'
                f'<div class="hz-kicker">{kicker}</div>'
                f'<div style="font-weight:500">{html.escape(value)}</div></div>',
                unsafe_allow_html=True)

    rule()
    st.markdown("#### Recent learning")
    st.markdown('<p style="color:#94A3B8;margin-top:-.4rem;font-size:.9rem">The DNALearner '
                "agent explains every change it makes — nothing shifts silently.</p>",
                unsafe_allow_html=True)
    for ts, dim, change, trigger in DNA_EVENTS:
        st.markdown(
            f"""<div class="hz-card" style="padding:.8rem 1.05rem">
                  <div class="hz-kicker">{ts} · {dim}</div>
                  <div style="font-family:'Spline Sans Mono',monospace;color:#FFB800;
                              font-size:.9rem;margin:.2rem 0">{change}</div>
                  <div class="hz-body">{html.escape(trigger)}</div>
                </div>""", unsafe_allow_html=True)


# ============================================================================
# EXPLORE — Top 10, offline art, wired to itinerary
# ============================================================================
elif page == "Explore":
    st.markdown("## ✨ Top 10 Destinations")
    st.markdown('<p style="color:#94A3B8;margin-top:-.4rem">Ranked against your Travel DNA — '
                "with the reason for every score, not just the number.</p>",
                unsafe_allow_html=True)
    rule()

    cols = st.columns(2, gap="medium")
    for i, d in enumerate(DESTINATIONS):
        with cols[i % 2]:
            st.markdown(
                f"""<div class="hz-card hz-dest">
                      <img src="{scene_svg(d['c'][0], d['c'][1], d['emoji'])}" alt="">
                      <div class="inner">
                        <div style="display:flex;justify-content:space-between;align-items:baseline">
                          <div class="hz-title">{html.escape(d['name'])}</div>
                          <span class="match">{d['match']}% match</span>
                        </div>
                        <div class="hz-body">{html.escape(d['desc'])}</div>
                        <div class="hz-meta">
                          <span class="hz-chip">📅 <b>{d['months']}</b></span>
                          <span class="hz-chip">💰 <b>{d['budget']}</b></span>
                        </div>
                        <div class="why">{html.escape(d['why'])}</div>
                      </div>
                    </div>""", unsafe_allow_html=True)
            if st.button(f"🌟 Plan {d['name'].split(',')[0]}", key=f"plan_{i}",
                         width="stretch"):
                st.session_state.current_destination = d["name"]
                set_page("Itinerary")

# ============================================================================
# LOGIN — holiday-vibe entry point
# ============================================================================
elif page == "Login":
    st.markdown(
        f'<img src="{scene_svg("#F2994A", "#7C2D12", "🏖️")}" '
        'style="width:100%;border-radius:20px;margin-bottom:1.2rem" alt="">',
        unsafe_allow_html=True)
    st.markdown(
        """<div style="text-align:center">
             <div class="hz-eyebrow">🌴 welcome back, wanderer</div>
             <h1 style="font-family:'Playfair Display',serif;font-size:2.1rem;margin:.3rem 0 .6rem">
               Your next getaway is one login away</h1>
             <p style="color:#94A3B8">Sign in to pick up your trip planning, saved preferences, and Travel DNA.</p>
           </div>""", unsafe_allow_html=True)
    rule()

    _, col_mid, _ = st.columns([1, 1.3, 1])
    with col_mid:
        with st.form("login_form"):
            identifier = st.text_input("Email or phone number")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("🔑 Log In", type="primary", width="stretch")
        if submitted:
            user = auth_service.login(st.session_state.auth_conn, identifier, password)
            if user:
                st.session_state.auth_user = user
                set_page("Home")
            else:
                st.error("Invalid email/phone or password.")

        link_l, link_r = st.columns(2)
        with link_l:
            if st.button("Forgot password?", key="goto_forgot", width="stretch"):
                st.session_state.reset_stage = "request"
                set_page("Forgot Password")
        with link_r:
            if st.button("Create an account", key="goto_signup", width="stretch"):
                set_page("Sign Up")

# ============================================================================
# SIGN UP
# ============================================================================
elif page == "Sign Up":
    st.markdown(
        f'<img src="{scene_svg("#FBBF24", "#312E81", "🧳")}" '
        'style="width:100%;border-radius:20px;margin-bottom:1.2rem" alt="">',
        unsafe_allow_html=True)
    st.markdown("## 📝 Create your account")
    st.markdown('<p style="color:#94A3B8;margin-top:-.4rem">Sign up now — fill in your travel '
                "profile now or anytime later from the Profile page.</p>", unsafe_allow_html=True)
    rule()

    _, col_mid, _ = st.columns([1, 1.4, 1])
    with col_mid:
        name = st.text_input("Full name", key="signup_name")
        email = st.text_input("Email address", key="signup_email")
        phone = st.text_input("Phone number", key="signup_phone")
        password = st.text_input("Password", type="password", key="signup_password",
                                  help="At least 8 characters.")
        confirm_password = st.text_input("Confirm password", type="password", key="signup_confirm")

        with st.expander("✨ Fill in your travel profile now (optional)"):
            dob = st.date_input("Date of birth", value=None, key="signup_dob",
                                 min_value=datetime(1900, 1, 1), max_value=datetime.now())
            sex = st.selectbox("Sex", SEX_OPTIONS, key="signup_sex")
            address = st.text_area("Address", key="signup_address")
            food_prefs = st.multiselect("Food preferences", options=list(PROFILE_FOOD_PREF_LABELS.keys()),
                                         format_func=lambda k: PROFILE_FOOD_PREF_LABELS[k], key="signup_food")
            travel_prefs = st.multiselect("Travel preferences", options=list(TRAVEL_PREF_LABELS.keys()),
                                           format_func=lambda k: TRAVEL_PREF_LABELS[k], key="signup_travel")
            inflight_prefs = st.multiselect("In-flight preferences", options=list(INFLIGHT_PREF_LABELS.keys()),
                                             format_func=lambda k: INFLIGHT_PREF_LABELS[k], key="signup_inflight")
            st.markdown("**Hotel preferences**")
            hcol1, hcol2, hcol3 = st.columns(3)
            with hcol1:
                budget_tier = st.selectbox("Budget tier", options=list(HOTEL_BUDGET_TIER_LABELS.keys()),
                                            format_func=lambda k: HOTEL_BUDGET_TIER_LABELS[k], key="signup_tier")
            with hcol2:
                bed_type = st.selectbox("Bed type", BED_TYPE_OPTIONS, key="signup_bed")
            with hcol3:
                view = st.selectbox("View", VIEW_TYPE_OPTIONS, key="signup_view")
            acol1, acol2, acol3 = st.columns(3)
            with acol1:
                pool = st.checkbox("🏊 Pool", key="signup_pool")
            with acol2:
                gym = st.checkbox("🏋️ Gym", key="signup_gym")
            with acol3:
                spa = st.checkbox("💆 Spa", key="signup_spa")

        if st.button("Create Account", type="primary", width="stretch"):
            if password != confirm_password:
                st.error("Passwords don't match.")
            else:
                try:
                    conn = st.session_state.auth_conn
                    user = auth_service.sign_up(conn, email or None, phone or None, password, name=name or None)
                    user = auth_service.update_profile(
                        conn, user.id,
                        date_of_birth=dob.isoformat() if dob else None,
                        sex=sex if sex != "Prefer not to say" else None,
                        address=address or None,
                        food_preferences=food_prefs,
                        travel_preferences=travel_prefs,
                        inflight_preferences=inflight_prefs,
                        hotel_preferences={
                            "budget_tier": budget_tier, "bed_type": bed_type,
                            "view": view, "pool": pool, "gym": gym, "spa": spa,
                        },
                    )
                    st.session_state.auth_user = user
                    set_page("Home")
                except AuthError as e:
                    st.error(str(e))

        if st.button("Already have an account? Log in", key="goto_login", width="stretch"):
            set_page("Login")

# ============================================================================
# FORGOT PASSWORD — two-step: identifier -> token + new password
# ============================================================================
elif page == "Forgot Password":
    st.markdown("## 🔓 Forgot Password")
    rule()
    _, col_mid, _ = st.columns([1, 1.3, 1])
    with col_mid:
        if st.session_state.reset_stage == "request":
            st.write("Enter the email address or phone number on your account, and we'll send "
                     "you an 8-character reset code.")
            identifier = st.text_input("Email or phone number", key="forgot_identifier")
            if st.button("Send Reset Code", type="primary", width="stretch"):
                result = auth_service.request_password_reset(st.session_state.auth_conn, identifier)
                if not result["found"]:
                    st.error("No account found with that email or phone number.")
                else:
                    st.session_state.reset_identifier = identifier
                    st.session_state.reset_dev_token = result["dev_token"]
                    st.session_state.reset_stage = "confirm"
                    if result["delivered"]:
                        st.success(f"A reset code was sent via {result['channel']}.")
                    st.rerun()

        else:
            if st.session_state.reset_dev_token:
                st.warning(f"⚠️ DEV MODE — email/SMS delivery isn't configured (or failed), so here's "
                           f"your code directly: **{st.session_state.reset_dev_token}**")
            st.write(f"Enter the code sent for **{st.session_state.reset_identifier}**, and choose a new password.")
            token = st.text_input("Reset code", key="forgot_token")
            new_password = st.text_input("New password", type="password", key="forgot_new_password",
                                          help="At least 8 characters.")
            confirm_new_password = st.text_input("Confirm new password", type="password",
                                                  key="forgot_confirm_password")
            if st.button("Reset Password", type="primary", width="stretch"):
                if new_password != confirm_new_password:
                    st.error("Passwords don't match.")
                else:
                    try:
                        if auth_service.reset_password(st.session_state.auth_conn, token, new_password):
                            st.session_state.reset_stage = "request"
                            st.session_state.reset_dev_token = None
                            st.success("Password reset! Please log in with your new password.")
                            set_page("Login")
                        else:
                            st.error("That code is invalid or has expired. Please request a new one.")
                    except AuthError as e:
                        st.error(str(e))
            if st.button("Start over", key="forgot_start_over"):
                st.session_state.reset_stage = "request"
                st.rerun()

# ============================================================================
# PROFILE
# ============================================================================
elif page == "Profile":
    if not st.session_state.auth_user:
        st.info("Log in to view and edit your profile.")
        if st.button("Go to Login", type="primary"):
            set_page("Login")
    else:
        conn = st.session_state.auth_conn
        user = st.session_state.auth_user
        profile = user.profile

        st.markdown("## 👤 Your Profile")
        st.caption(user.email or user.phone)
        rule()

        name = st.text_input("Full name", value=profile.name or "")
        dob_value = datetime.fromisoformat(profile.date_of_birth).date() if profile.date_of_birth else None
        dob = st.date_input("Date of birth", value=dob_value, min_value=datetime(1900, 1, 1), max_value=datetime.now())
        sex_index = SEX_OPTIONS.index(profile.sex) if profile.sex in SEX_OPTIONS else 0
        sex = st.selectbox("Sex", SEX_OPTIONS, index=sex_index)
        address = st.text_area("Address", value=profile.address or "")

        food_prefs = st.multiselect("Food preferences", options=list(PROFILE_FOOD_PREF_LABELS.keys()),
                                     default=[f for f in profile.food_preferences if f in PROFILE_FOOD_PREF_LABELS],
                                     format_func=lambda k: PROFILE_FOOD_PREF_LABELS[k])
        travel_prefs_known = [t for t in profile.travel_preferences if t in TRAVEL_PREF_LABELS]
        travel_prefs = st.multiselect("Travel preferences", options=list(TRAVEL_PREF_LABELS.keys()),
                                       default=travel_prefs_known, format_func=lambda k: TRAVEL_PREF_LABELS[k])
        inflight_prefs_known = [i for i in profile.inflight_preferences if i in INFLIGHT_PREF_LABELS]
        inflight_prefs = st.multiselect("In-flight preferences", options=list(INFLIGHT_PREF_LABELS.keys()),
                                         default=inflight_prefs_known, format_func=lambda k: INFLIGHT_PREF_LABELS[k])

        st.markdown("#### 🏨 Hotel preferences")
        hcol1, hcol2, hcol3 = st.columns(3)
        with hcol1:
            tier_index = list(HOTEL_BUDGET_TIER_LABELS.keys()).index(profile.hotel_preferences.budget_tier) \
                if profile.hotel_preferences.budget_tier in HOTEL_BUDGET_TIER_LABELS else 0
            budget_tier = st.selectbox("Budget tier", options=list(HOTEL_BUDGET_TIER_LABELS.keys()),
                                        format_func=lambda k: HOTEL_BUDGET_TIER_LABELS[k], index=tier_index)
        with hcol2:
            bed_value = profile.hotel_preferences.bed_type or "No preference"
            bed_index = BED_TYPE_OPTIONS.index(bed_value) if bed_value in BED_TYPE_OPTIONS else 0
            bed_type = st.selectbox("Bed type", BED_TYPE_OPTIONS, index=bed_index)
        with hcol3:
            view_value = profile.hotel_preferences.view or "No preference"
            view_index = VIEW_TYPE_OPTIONS.index(view_value) if view_value in VIEW_TYPE_OPTIONS else 0
            view = st.selectbox("View", VIEW_TYPE_OPTIONS, index=view_index)
        acol1, acol2, acol3 = st.columns(3)
        with acol1:
            pool = st.checkbox("🏊 Pool", value=profile.hotel_preferences.pool)
        with acol2:
            gym = st.checkbox("🏋️ Gym", value=profile.hotel_preferences.gym)
        with acol3:
            spa = st.checkbox("💆 Spa", value=profile.hotel_preferences.spa)

        if st.button("💾 Save Profile", type="primary"):
            updated = auth_service.update_profile(
                conn, user.id,
                name=name or None, date_of_birth=dob.isoformat() if dob else None,
                sex=sex if sex != "Prefer not to say" else None, address=address or None,
                food_preferences=food_prefs, travel_preferences=travel_prefs,
                inflight_preferences=inflight_prefs,
                hotel_preferences={"budget_tier": budget_tier, "bed_type": bed_type, "view": view,
                                    "pool": pool, "gym": gym, "spa": spa},
            )
            st.session_state.auth_user = updated
            st.success("Profile saved!")
            st.rerun()

        rule()
        st.markdown("#### 🧬 Travel DNA")
        if profile.travel_dna_notes:
            for note in profile.travel_dna_notes:
                st.markdown(f"- {note}")
        else:
            st.caption("No Travel DNA insights learned yet — plan a trip in Chat to start building one.")

        travel_state = st.session_state.get("travel_state")
        has_learnings = travel_state and (travel_state.dna_insights or travel_state.itinerary_data)
        if has_learnings:
            if st.button("🔄 Sync Travel DNA from my latest trip"):
                updated = auth_service.sync_travel_dna_into_profile(
                    conn, user.id, travel_state.preferences, travel_state.dna_insights)
                st.session_state.auth_user = updated
                st.success("Profile updated with insights from your latest trip!")
                st.rerun()
        else:
            st.caption("Plan and complete a trip in Chat, then come back here to sync what Horizon learned.")

st.caption("Horizon Travel AI • Capstone Demo")
