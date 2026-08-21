import json
import re
from datetime import datetime
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

KEYWORDS = [
    "attosecond", "atto", "high harmonic", "hhg", "sub-cycle", "strong field",
    "soft x-ray", "soft-x-ray", "water window", "xuv", "euv", "vuv", 
    "free electron laser", "fel", "xfel", "synchrotron", "linac",
    "ultrafast", "femtosecond", "picosecond", "nonlinear optics", "cpa",
    "fiber laser", "solid-state laser", "diode laser", "laser development"
]

EVENT_INDICATORS = [
    "conference", "workshop", "school", "symposium", "meeting", 
    "seminar", "congress", "colloquium", "summit", "deadline", 
    "exhibition", "webinar", "booth"
]

CATEGORIES = {
    "Soft X-Ray & Attosecond": ["attosecond", "atto", "hhg", "soft x-ray", "water window", "xuv", "euv", "vuv", "fel", "xfel", "synchrotron"],
    "Ultrafast Science & Non-Linear Optics": ["ultrafast", "femtosecond", "picosecond", "nonlinear", "cpa"],
    "Laser Sources & Development": ["fiber laser", "solid-state", "diode laser", "opcpa", "amplifier"]
}

# --- THE ULTIMATE MASTER LIST ---
FEEDS = [
    # Swiss & German Academic Powerhouses
    {"name": "ETH Zurich", "url": "https://phys.ethz.ch/news-and-events.xml"},
    {"name": "EPFL", "url": "https://actu.epfl.ch/api/v1/channels/1/news/rss/"},
    {"name": "CALA / LMU Munich", "url": "https://www.physik.lmu.de/en/news/rss.xml"},
    {"name": "Max Born Institute (MBI Berlin)", "url": "https://mbi-berlin.de/rss.xml"},
    {"name": "Max Planck (MPQ)", "url": "https://www.mpq.mpg.de/rss.xml"},
    {"name": "Helmholtz Association", "url": "https://www.helmholtz.de/newsroom/rss.xml"},

    # UK Physics Hubs (Attosecond & Laser-Plasma)
    {"name": "Oxford Physics", "url": "https://www.physics.ox.ac.uk/events/rss"},
    {"name": "Imperial College", "url": "https://www.imperial.ac.uk/physics/news/rss/"},
    {"name": "King's College London", "url": "https://www.kcl.ac.uk/news/rss"},
    {"name": "Queen's University Belfast", "url": "https://www.qub.ac.uk/news/rss"},

    # Top Global Institutes
    {"name": "Lund Laser Centre", "url": "https://www.llc.lu.se/rss"},
    {"name": "ARCNL Netherlands", "url": "https://arcnl.nl/feed"},
    {"name": "Univ of Rochester (LLE)", "url": "https://www.lle.rochester.edu/feed/"},

    # Major Accelerators & FELs
    {"name": "CERN (Indico Events)", "url": "https://indico.cern.ch/export/feed/rss.xml"},
    {"name": "Paul Scherrer Institute (PSI)", "url": "https://www.psi.ch/en/media/rss.xml"},
    {"name": "GSI / FAIR", "url": "https://www.gsi.de/en/bottommenu/press_releases.xml"},
    {"name": "FERMI (Elettra Trieste)", "url": "https://www.elettra.eu/news.xml?format=feed&type=rss"},
    {"name": "LCLS / SLAC National Accelerator", "url": "https://www6.slac.stanford.edu/news/feed"},
    {"name": "European XFEL", "url": "https://www.xfel.eu/news_and_events/news/rss/index_eng.xml"},
    {"name": "ESRF (European Synchrotron)", "url": "https://www.esrf.fr/news/rss.xml"},
    {"name": "ELI Beams", "url": "https://www.eli-beams.eu/feed/"},
    {"name": "ELI ALPS", "url": "https://www.eli-alps.hu/en/rss"},
    
    # European Networks & Funding
    {"name": "Erasmus+ & CORDIS (EU Events)", "url": "https://cordis.europa.eu/rss/events_en.xml"},
    {"name": "Laserlab-Europe", "url": "https://www.laserlab-europe.eu/events/events-rss"},
    {"name": "Laser4EU", "url": "https://laser4eu.eu/feed/"},
    {"name": "Lightsources.org", "url": "https://lightsources.org/feed/"},

    # Corporate Giants (Lasers, EUV & Metrology)
    {"name": "ASML", "url": "https://www.asml.com/rss/news.xml"},
    {"name": "TRUMPF Lasers", "url": "https://www.trumpf.com/en_INT/newsroom/rss.xml"},
    {"name": "ZEISS SMT", "url": "https://www.zeiss.com/semiconductor-manufacturing-technology/news.rss"},
    {"name": "Thales Group", "url": "https://www.thalesgroup.com/en/rss.xml"},
    {"name": "Amplitude Lasers", "url": "https://amplitude-laser.com/feed/"},

    # Global Societies
    {"name": "Optica Events", "url": "https://www.optica.org/events/rss"},
    {"name": "SPIE Conferences", "url": "https://spie.org/conferences-and-exhibitions/rss"},
    {"name": "APS Physics", "url": "https://physics.aps.org/feeds/all"},
    {"name": "EPS", "url": "https://www.eps.org/events/event_list.asp?show=&rss=1"}
]

def extract_exact_dates(text):
    """
    STRICT MODE: The text MUST contain a specific Day, Month, and Year.
    Generic mentions of "October 2026" or "annually" will be rejected.
    """
    months_regex = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    
    # Pattern 1: Month DD-DD, YYYY (e.g., October 12-14, 2026)
    p1 = rf'\b({months_regex})\s+(\d{{1,2}})(?:\s*-\s*\d{{1,2}})?(?:st|nd|rd|th)?(?:,\s*)?\s+(202[4-9])\b'
    # Pattern 2: DD-DD Month YYYY (e.g., 12-14 October 2026)
    p2 = rf'\b(\d{{1,2}})(?:\s*-\s*\d{{1,2}})?(?:st|nd|rd|th)?\s+({months_regex})\s+(202[4-9])\b'
    
    try:
        m1 = re.search(p1, text, re.IGNORECASE)
        if m1:
            month, start_day, year = m1.groups()
            sort_date = date_parser.parse(f"{month} {start_day} {year}").strftime("%Y-%m-%d")
            return m1.group(0).strip(), sort_date
            
        m2 = re.search(p2, text, re.IGNORECASE)
        if m2:
            start_day, month, year = m2.groups()
            sort_date = date_parser.parse(f"{month} {start_day} {year}").strftime("%Y-%m-%d")
            return m2.group(0).strip(), sort_date
    except:
        pass
        
    # If no exact day is found, return None. The event is rejected.
    return None, None

def classify_event(text):
    for cat, kw_list in CATEGORIES.items():
        if any(kw in text.lower() for kw in kw_list): return cat
    return "Ultrafast Science & Non-Linear Optics"

def is_actual_event(text):
    text_lower = text.lower()
    if any(indicator in text_lower for indicator in EVENT_INDICATORS):
        if "press release" in text_lower or "hub launched" in text_lower: return False
        return True
    return False

def fetch_feed_events():
    events = []
    # Grab the exact current date to strictly filter out the past
    today_date = datetime.now().date()
    
    for feed_info in FEEDS:
        try:
            parsed = feedparser.parse(feed_info["url"])
            for entry in parsed.entries:
                title = entry.get("title", "")
                summary_raw = entry.get("summary", "") or entry.get("description", "")
                summary = BeautifulSoup(summary_raw, "html.parser").get_text()
                combined = f"{title} {summary}"
                
                if any(kw in combined.lower() for kw in KEYWORDS) and is_actual_event(combined):
                    
                    event_type = "Conference"
                    if "school" in combined.lower(): event_type = "School"
                    elif any(w in combined.lower() for w in ["workshop", "symposium", "seminar"]): event_type = "Workshop"
                    
                    # Call the strict date extractor
                    display_date, sort_date = extract_exact_dates(combined)
                    
                    if display_date and sort_date:
                        events.append({
                            "title": title,
                            "organizer": feed_info["name"],
                            "category": classify_event(combined),
                            "type": event_type,
                            "location": "See Official Link",
                            "display_date": display_date,
                            "date": sort_date,
                            "link": entry.get("link", "#"),
                            "description": summary[:250] + "..."
                        })
        except Exception as e:
            pass

    valid_events = {}
    for ev in events:
        try:
            # STRICT FUTURE FILTER: Compare event date strictly against today's midnight
            ev_date_obj = datetime.strptime(ev['date'], "%Y-%m-%d").date()
            if ev_date_obj >= today_date:
                clean_title = re.sub(r'[^a-zA-Z0-9]', '', ev['title']).lower()
                if clean_title not in valid_events:
                    valid_events[clean_title] = ev
        except:
            pass

    return list(valid_events.values())

if __name__ == "__main__":
    collected = fetch_feed_events()
    output_data = {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "total_events": len(collected),
        "events": collected
    }
    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"Successfully saved {len(collected)} strictly scheduled future events.")
