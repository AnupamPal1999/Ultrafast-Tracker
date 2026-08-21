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
    "seminar", "congress", "colloquium", "summit"
]

CATEGORIES = {
    "Soft X-Ray & Attosecond": ["attosecond", "atto", "hhg", "soft x-ray", "water window", "xuv", "euv", "vuv", "fel", "xfel", "synchrotron"],
    "Ultrafast Science & Non-Linear Optics": ["ultrafast", "femtosecond", "picosecond", "nonlinear", "cpa"],
    "Laser Sources & Development": ["fiber laser", "solid-state", "diode laser", "opcpa", "amplifier"]
}

# The expanded list of exact organizations and institutes
FEEDS = [
    {"name": "Optica Events", "url": "https://www.optica.org/events/rss"},
    {"name": "SPIE Conferences", "url": "https://spie.org/conferences-and-exhibitions/rss"},
    {"name": "Laserlab-Europe", "url": "https://www.laserlab-europe.eu/events/events-rss"},
    {"name": "Lightsources.org (Synchrotrons/FELs)", "url": "https://lightsources.org/feed/"},
    {"name": "SLAC National Accelerator", "url": "https://www6.slac.stanford.edu/news/feed"},
    {"name": "DESY News", "url": "https://www.desy.de/news/index_eng.xml"},
    {"name": "Max Planck Institute of Quantum Optics (MPQ)", "url": "https://www.mpq.mpg.de/rss.xml"},
    {"name": "Extreme Light Infrastructure (ELI)", "url": "https://www.eli-beams.eu/feed/"},
    {"name": "APS Physics", "url": "https://physics.aps.org/feeds/all"},
    {"name": "European Physical Society (EPS)", "url": "https://www.eps.org/events/event_list.asp?show=&rss=1"},
    {"name": "CERN / Indico Physics Events", "url": "https://indico.cern.ch/export/feed/rss.xml"}
]

def extract_exact_dates(text):
    """
    Strictly scans text for exact dates. If it doesn't find a specific 
    Day, Month, and Year, it rejects the event.
    """
    months = r'Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?'
    
    # 1. Matches: October 12-14, 2026 OR October 12, 2026
    pattern1 = rf'\b({months})\s+(\d{{1,2}})(?:\s*-\s*(\d{{1,2}}))?(?:st|nd|rd|th)?(?:,\s*)?\s+(\d{{4}})\b'
    # 2. Matches: 12-14 October 2026 OR 12 October 2026
    pattern2 = rf'\b(\d{{1,2}})(?:\s*-\s*(\d{{1,2}}))?(?:st|nd|rd|th)?\s+({months})\s+(\d{{4}})\b'

    match1 = re.search(pattern1, text, re.IGNORECASE)
    if match1:
        month, start_day, end_day, year = match1.groups()
        display = f"{month.capitalize()} {start_day}" + (f"-{end_day}" if end_day else "") + f", {year}"
        sort_date = date_parser.parse(f"{month} {start_day} {year}").strftime("%Y-%m-%d")
        return display, sort_date
            
    match2 = re.search(pattern2, text, re.IGNORECASE)
    if match2:
        start_day, end_day, month, year = match2.groups()
        display = f"{start_day}" + (f"-{end_day}" if end_day else "") + f" {month.capitalize()} {year}"
        sort_date = date_parser.parse(f"{month} {start_day} {year}").strftime("%Y-%m-%d")
        return display, sort_date

    # If no exact date is found, return None (This allows us to delete generic events)
    return None, None

def classify_event(text):
    for cat, kw_list in CATEGORIES.items():
        if any(kw in text.lower() for kw in kw_list): return cat
    return "Ultrafast Science & Non-Linear Optics"

def is_actual_event(text):
    text_lower = text.lower()
    if any(indicator in text_lower for indicator in EVENT_INDICATORS):
        if "press release" in text_lower or "hub launched" in text_lower:
            return False
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
                summary = BeautifulSoup(entry.get("summary", "") or entry.get("description", ""), "html.parser").get_text()
                combined = f"{title} {summary}"
                
                # Check for keywords and ensure it's an event
                if any(kw in combined.lower() for kw in KEYWORDS) and is_actual_event(combined):
                    
                    event_type = "Conference"
                    if "school" in combined.lower(): event_type = "School"
                    elif any(w in combined.lower() for w in ["workshop", "symposium", "seminar"]): event_type = "Workshop"
                    
                    # STRICT RULE: Try to find an exact date
                    display_date, sort_date = extract_exact_dates(combined)
                    
                    # If an exact date is found, add it. If not, drop it completely.
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

    # Remove duplicates and past events
    valid_events = {}
    for ev in events:
        try:
            ev_date = datetime.strptime(ev['date'], "%Y-%m-%d")
            # Only keep future events (from today onward)
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
    print(f"Successfully saved {len(collected)} exact, confirmed events.")
