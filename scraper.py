import json
import re
import feedparser
from bs4 import BeautifulSoup
import trafilatura
from datetime import datetime
from dateutil import parser as date_parser

KEYWORDS = [
    "attosecond", "atto", "high harmonic", "hhg", "sub-cycle", "strong field",
    "soft x-ray", "soft-x-ray", "water window", "xuv", "euv", "vuv", 
    "free electron laser", "fel", "xfel", "synchrotron", "linac",
    "ultrafast", "femtosecond", "picosecond", "nonlinear optics", "cpa",
    "fiber laser", "solid-state laser", "diode laser", "laser development",
    "optics", "photonics"
]

EVENT_INDICATORS = [
    "conference", "workshop", "school", "symposium", "meeting", 
    "seminar", "congress", "colloquium", "summit", "deadline", 
    "exhibition", "webinar", "call for proposals"
]

CATEGORIES = {
    "Soft X-Ray & Attosecond": ["attosecond", "atto", "hhg", "soft x-ray", "water window", "xuv", "euv", "vuv", "fel", "xfel", "synchrotron"],
    "Ultrafast Science & Non-Linear Optics": ["ultrafast", "femtosecond", "picosecond", "nonlinear", "cpa"],
    "Laser Sources & Development": ["fiber laser", "solid-state", "diode laser", "opcpa", "amplifier"]
}

# --- 1. DIRECT RSS & EVENT FEEDS (Laserlab, Lightsources, Societies, Facilities) ---
DIRECT_FEEDS = [
    {"name": "Laserlab-Europe", "url": "https://laserlab-europe.eu/events/category/laserlab-europe/feed/"},
    {"name": "Laser4EU", "url": "https://laser4eu.eu/feed/"},
    {"name": "Lightsources.org", "url": "https://lightsources.org/for-users/events/feed/"},
    {"name": "Optica Events", "url": "https://www.optica.org/events/rss"},
    {"name": "SPIE Conferences", "url": "https://spie.org/conferences-and-exhibitions/rss"},
    {"name": "APS Physics", "url": "https://physics.aps.org/feeds/all"},
    {"name": "EPS", "url": "https://www.eps.org/events/event_list.asp?show=&rss=1"},
    {"name": "European XFEL", "url": "https://www.xfel.eu/news_and_events/news/rss/index_eng.xml"},
    {"name": "CERN Indico", "url": "https://indico.cern.ch/export/feed/rss.xml"},
    {"name": "ELI Beams", "url": "https://www.eli-beams.eu/feed/"},
    {"name": "ELI ALPS", "url": "https://www.eli-alps.hu/en/rss"}
]

# --- 2. DEEP-CRAWL HUBS (Institutes & Academic Labs) ---
EVENT_HUBS = [
    "https://mbi-berlin.de/news-and-events",
    "https://www.llc.lu.se/events",
    "https://arcnl.nl/en/news-events",
    "https://www.lle.rochester.edu/events/",
    "https://phys.ethz.ch/news-and-events.html",
    "https://actu.epfl.ch/",
    "https://www.psi.ch/en/media/events",
    "https://www.gsi.de/en/news/events",
    "https://www.elettra.eu/news.html",
    "https://www.physics.ox.ac.uk/events",
    "https://www.imperial.ac.uk/physics/events/",
    "https://www.kcl.ac.uk/news",
    "https://www.qub.ac.uk/News/"
]

def extract_dates(text):
    months_regex = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    p1 = rf'\b({months_regex})\s+(\d{{1,2}})(?:\s*-\s*\d{{1,2}})?(?:st|nd|rd|th)?(?:,\s*)?\s+(202[4-9])\b'
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
    return None, None

def classify_event(text):
    for cat, kw_list in CATEGORIES.items():
        if any(kw in text.lower() for kw in kw_list): return cat
    return "Ultrafast Science & Non-Linear Optics"

def is_valid_event(text):
    text_lower = text.lower()
    return any(ind in text_lower for ind in EVENT_INDICATORS) and not "press release" in text_lower

def fetch_all_events():
    events = {}
    today_date = datetime.now().date()

    # --- ENGINE 1: Direct Feeds ---
    for feed in DIRECT_FEEDS:
        try:
            parsed = feedparser.parse(feed["url"])
            for entry in parsed.entries:
                title = entry.get("title", "")
                summary = BeautifulSoup(entry.get("summary", "") or entry.get("description", ""), "html.parser").get_text()
                combined = f"{title} {summary}"
                
                if any(kw in combined.lower() for kw in KEYWORDS) and is_valid_event(combined):
                    disp_date, sort_date = extract_dates(combined)
                    if disp_date and sort_date:
                        if datetime.strptime(sort_date, "%Y-%m-%d").date() >= today_date:
                            clean_title = re.sub(r'[^a-zA-Z0-9]', '', title).lower()
                            events[clean_title] = {
                                "title": title,
                                "organizer": feed["name"],
                                "category": classify_event(combined),
                                "type": "School" if "school" in combined.lower() else "Conference",
                                "location": "See Official Link",
                                "display_date": disp_date,
                                "date": sort_date,
                                "link": entry.get("link", "#"),
                                "description": summary[:250] + "..."
                            }
        except Exception:
            pass

    # --- ENGINE 2: Deep Hub Crawler ---
    for hub in EVENT_HUBS:
        try:
            hub_content = trafilatura.fetch_url(hub)
            if not hub_content: continue
            links = trafilatura.extract_links(hub_content)
            
            for link_info in links:
                url = link_info.get('url')
                if url and any(w in url.lower() for w in ['event', 'conf', 'school', 'workshop']):
                    page_data = trafilatura.fetch_url(url)
                    if not page_data: continue
                    text = trafilatura.extract(page_data)
                    if not text or not any(kw in text.lower() for kw in KEYWORDS): continue
                    
                    disp_date, sort_date = extract_dates(text)
                    if disp_date and sort_date:
                        if datetime.strptime(sort_date, "%Y-%m-%d").date() >= today_date:
                            title = trafilatura.extract_metadata(page_data).title or "Academic Event"
                            clean_title = re.sub(r'[^a-zA-Z0-9]', '', title).lower()
                            if clean_title not in events:
                                events[clean_title] = {
                                    "title": title,
                                    "organizer": "Institute Hub Crawler",
                                    "category": classify_event(text),
                                    "type": "School" if "school" in text.lower() else "Conference",
                                    "location": "See Official Link",
                                    "display_date": disp_date,
                                    "date": sort_date,
                                    "link": url,
                                    "description": text[:250] + "..."
                                }
        except Exception:
            pass

    sorted_events = sorted(list(events.values()), key=lambda x: x['date'])
    return sorted_events

if __name__ == "__main__":
    collected = fetch_all_events()
    output_data = {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "total_events": len(collected),
        "events": collected
    }
    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"Successfully saved {len(collected)} total events.")
