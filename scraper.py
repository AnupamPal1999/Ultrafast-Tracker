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
    "seminar", "congress", "colloquium", "summit", "deadline"
]

CATEGORIES = {
    "Soft X-Ray & Attosecond": ["attosecond", "atto", "hhg", "soft x-ray", "water window", "xuv", "euv", "vuv", "fel", "xfel", "synchrotron"],
    "Ultrafast Science & Non-Linear Optics": ["ultrafast", "femtosecond", "picosecond", "nonlinear", "cpa"],
    "Laser Sources & Development": ["fiber laser", "solid-state", "diode laser", "opcpa", "amplifier"]
}

# The expanded list of global and European laser/X-ray facilities
FEEDS = [
    {"name": "Laserlab-Europe", "url": "https://www.laserlab-europe.eu/events/events-rss"},
    {"name": "Laser4EU", "url": "https://laser4eu.eu/feed/"},
    {"name": "European XFEL", "url": "https://www.xfel.eu/news_and_events/news/rss/index_eng.xml"},
    {"name": "ESRF (European Synchrotron)", "url": "https://www.esrf.fr/news/rss.xml"},
    {"name": "Optica Events", "url": "https://www.optica.org/events/rss"},
    {"name": "SPIE Conferences", "url": "https://spie.org/conferences-and-exhibitions/rss"},
    {"name": "Lightsources.org", "url": "https://lightsources.org/feed/"},
    {"name": "SLAC National Accelerator", "url": "https://www6.slac.stanford.edu/news/feed"},
    {"name": "DESY News", "url": "https://www.desy.de/news/index_eng.xml"},
    {"name": "Max Planck (MPQ)", "url": "https://www.mpq.mpg.de/rss.xml"},
    {"name": "ELI Beams", "url": "https://www.eli-beams.eu/feed/"},
    {"name": "ELI ALPS", "url": "https://www.eli-alps.hu/en/rss"},
    {"name": "APS Physics", "url": "https://physics.aps.org/feeds/all"},
    {"name": "EPS", "url": "https://www.eps.org/events/event_list.asp?show=&rss=1"}
]

def extract_exact_dates(text):
    """
    Smarter date parser that grabs exact strings like '14-16 October 2026'
    or falls back to 'October 2026' if the exact day isn't announced yet.
    """
    months_regex = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    
    # Matches: Month DD-DD, YYYY (e.g., October 12-14, 2026)
    p1 = rf'\b({months_regex})\s+(\d{{1,2}})(?:\s*-\s*\d{{1,2}})?(?:st|nd|rd|th)?(?:,\s*)?\s+(202[4-9])\b'
    # Matches: DD-DD Month YYYY (e.g., 12-14 October 2026)
    p2 = rf'\b(\d{{1,2}})(?:\s*-\s*\d{{1,2}})?(?:st|nd|rd|th)?\s+({months_regex})\s+(202[4-9])\b'
    # Matches: Month YYYY (e.g., October 2026)
    p3 = rf'\b({months_regex})\s+(202[4-9])\b'
    
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
            
        m3 = re.search(p3, text, re.IGNORECASE)
        if m3:
            month, year = m3.groups()
            sort_date = date_parser.parse(f"{month} 1 {year}").strftime("%Y-%m-%d")
            return f"{month.capitalize()} {year} (Dates TBA)", sort_date
    except:
        pass
        
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
    today = datetime.now()
    
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
            print(f"Error parsing {feed_info['name']}: {e}")

    valid_events = {}
    for ev in events:
        try:
            ev_date = datetime.strptime(ev['date'], "%Y-%m-%d")
            if ev_date >= today:
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
    print(f"Successfully saved {len(collected)} exact events.")
