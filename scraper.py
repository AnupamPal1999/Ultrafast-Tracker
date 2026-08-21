import json
import re
from datetime import datetime
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

# Comprehensive keywords
KEYWORDS = [
    "attosecond", "atto", "high harmonic", "hhg", "sub-cycle", "strong field",
    "soft x-ray", "soft-x-ray", "water window", "xuv", "euv", "vuv", 
    "free electron laser", "fel", "xfel", "synchrotron", "linac",
    "ultrafast", "femtosecond", "picosecond", "nonlinear optics", "cpa",
    "fiber laser", "solid-state laser", "diode laser", "laser development"
]

# Strict indicators that a feed item is actually an event, not a news article
EVENT_INDICATORS = [
    "conference", "workshop", "school", "symposium", "meeting", 
    "seminar", "congress", "colloquium", "summit"
]

CATEGORIES = {
    "Soft X-Ray & Attosecond": ["attosecond", "atto", "hhg", "soft x-ray", "water window", "xuv", "euv", "vuv", "fel", "xfel", "synchrotron"],
    "Ultrafast Science & Non-Linear Optics": ["ultrafast", "femtosecond", "picosecond", "nonlinear", "cpa"],
    "Laser Sources & Development": ["fiber laser", "solid-state", "diode laser", "opcpa", "amplifier"]
}

# Expanded Feeds including Major Institutes
FEEDS = [
    {"name": "Optica Events", "url": "https://www.optica.org/events/rss"},
    {"name": "SPIE Conferences", "url": "https://spie.org/conferences-and-exhibitions/rss"},
    {"name": "Laserlab-Europe", "url": "https://www.laserlab-europe.eu/events/events-rss"},
    {"name": "Lightsources.org (Synchrotrons/FELs)", "url": "https://lightsources.org/feed/"},
    {"name": "SLAC National Accelerator", "url": "https://www6.slac.stanford.edu/news/feed"},
    {"name": "DESY News", "url": "https://www.desy.de/news/index_eng.xml"}
]

# Curated Gold-Standard List
CURATED_CONFERENCES = [
    {
        "title": "International School of Quantum Electronics (Erice)",
        "organizer": "Ettore Majorana Foundation",
        "category": "Soft X-Ray & Attosecond",
        "type": "School",
        "location": "Erice, Sicily, Italy",
        "date": "2027-05-15",
        "link": "https://www.ccsem.infn.it/",
        "description": "Legendary summer school in Sicily often focusing on intense laser physics and attosecond science."
    },
    {
        "title": "Les Houches School of Physics",
        "organizer": "Ecole de Physique des Houches",
        "category": "Ultrafast Science & Non-Linear Optics",
        "type": "School",
        "location": "Les Houches, France",
        "date": "2027-07-01",
        "link": "https://houches-school-physics.com/",
        "description": "Prestigious alpine physics school featuring periodic sessions on ultrafast quantum phenomena."
    },
    {
        "title": "WE-Heraeus Seminar on Ultrafast Physics",
        "organizer": "Wilhelm and Else Heraeus Foundation",
        "category": "Soft X-Ray & Attosecond",
        "type": "Workshop",
        "location": "Bad Honnef, Germany",
        "date": "2027-03-10",
        "link": "https://www.we-heraeus-stiftung.de/",
        "description": "Highly focused, fully funded workshops for PhD students and postdocs in Germany."
    },
    {
        "title": "ATTO: Int. Conf. on Attosecond Science",
        "organizer": "ATTO Committee",
        "category": "Soft X-Ray & Attosecond",
        "type": "Conference",
        "location": "International",
        "date": "2027-07-15",
        "link": "https://atto-conference.org",
        "description": "The flagship conference for attosecond physics and soft X-ray HHG."
    }
]

def extract_iso_date(text, fallback_date):
    """Attempts to find a date in the text, otherwise returns the fallback."""
    try:
        matches = list(date_parser.parse(text, fuzzy=True, ignoretz=True))
        if matches:
            return matches[0].strftime("%Y-%m-%d")
    except:
        pass
    return fallback_date

def classify_event(text):
    text_lower = text.lower()
    for cat, kw_list in CATEGORIES.items():
        if any(kw in text_lower for kw in kw_list): return cat
    return "Ultrafast Science & Non-Linear Optics"

def matches_physics_keywords(text):
    text_lower = text.lower()
    return any(re.search(r'\b' + re.escape(kw) + r'\b', text_lower) for kw in KEYWORDS)

def is_actual_event(text):
    """Ensures the post is an event, not a news article or press release."""
    text_lower = text.lower()
    # If it contains event words, it's valid
    if any(indicator in text_lower for indicator in EVENT_INDICATORS):
        # Additional safety: filter out explicit press releases even if they mention 'conference'
        if "press release" in text_lower or "hub launched" in text_lower:
            return False
        return True
    return False

def fetch_feed_events():
    events = list(CURATED_CONFERENCES)
    today = datetime.now()
    
    for feed_info in FEEDS:
        try:
            parsed = feedparser.parse(feed_info["url"])
            for entry in parsed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                combined = f"{title} {summary}"
                
                # Check for BOTH physics relevance AND event indicators
                if matches_physics_keywords(combined) and is_actual_event(combined):
                    
                    lower_combined = combined.lower()
                    
                    # Classify Type more accurately
                    if "school" in lower_combined: 
                        event_type = "School"
                    elif any(w in lower_combined for w in ["workshop", "symposium", "seminar"]): 
                        event_type = "Workshop"
                    else:
                        event_type = "Conference"
                    
                    # Parse Date
                    raw_date = entry.get("published", today.strftime("%Y-%m-%d"))
                    iso_date = extract_iso_date(raw_date, today.strftime("%Y-%m-%d"))
                    
                    events.append({
                        "title": title,
                        "organizer": feed_info["name"],
                        "category": classify_event(combined),
                        "type": event_type,
                        "location": "See Event Link",
                        "date": iso_date,
                        "link": entry.get("link", "#"),
                        "description": BeautifulSoup(summary, "html.parser").get_text()[:250] + "..."
                    })
        except Exception as e:
            print(f"Error parsing {feed_info['name']}: {e}")

    # Remove duplicates and past events
    valid_events = {}
    for ev in events:
        try:
            ev_date = datetime.strptime(ev['date'][:10], "%Y-%m-%d")
            # Only keep future events (or those from today onward)
            if ev_date >= today:
                clean_title = re.sub(r'[^a-zA-Z0-9]', '', ev['title']).lower()
                if clean_title not in valid_events:
                    valid_events[clean_title] = ev
        except:
            # If date parsing completely fails, include it just in case
            valid_events[ev['title']] = ev

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
    print(f"Successfully saved {len(collected)} actual events to events.json")
