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
    "seminar", "congress", "colloquium", "summit", "deadline", "exhibition"
]

CATEGORIES = {
    "Soft X-Ray & Attosecond": ["attosecond", "atto", "hhg", "soft x-ray", "water window", "xuv", "euv", "vuv", "fel", "xfel", "synchrotron"],
    "Ultrafast Science & Non-Linear Optics": ["ultrafast", "femtosecond", "picosecond", "nonlinear", "cpa"],
    "Laser Sources & Development": ["fiber laser", "solid-state", "diode laser", "opcpa", "amplifier"]
}

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

EVENT_HUBS = [
    "https://mbi-berlin.de/news-and-events",
    "https://www.llc.lu.se/events",
    "https://arcnl.nl/en/news-events",
    "https://www.lle.rochester.edu/events/",
    "https://phys.ethz.ch/news-and-events.html",
    "https://actu.epfl.ch/",
    "https://www.psi.ch/en/media/events",
    "https://www.gsi.de/en/news/events",
    "https://www.physics.ox.ac.uk/events",
    "https://www.imperial.ac.uk/physics/events/"
]

def parse_smart_date(month_str, day_str, year_str=None):
    """Parses date, assuming current or next year if the year isn't explicitly written."""
    today = datetime.now().date()
    try:
        year = int(year_str) if year_str else today.year
        tmp_date = date_parser.parse(f"{month_str} {day_str} {year}").date()
        if not year_str and tmp_date < today:
            year += 1
            tmp_date = date_parser.parse(f"{month_str} {day_str} {year}").date()
        return tmp_date.strftime("%Y-%m-%d")
    except:
        return None

def extract_dates(text):
    months_regex = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    
    # Optional year capture to handle sites that just say "October 12"
    p1 = rf'\b({months_regex})\s+(\d{{1,2}})(?:\s*-\s*\d{{1,2}})?(?:st|nd|rd|th)?(?:(?:,\s*|\s+)(202[4-9]))?\b'
    p2 = rf'\b(\d{{1,2}})(?:\s*-\s*\d{{1,2}})?(?:st|nd|rd|th)?\s+({months_regex})(?:(?:,\s*|\s+)(202[4-9]))?\b'
    
    for pattern in [p1, p2]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Re-order based on which pattern matched
            if pattern == p1:
                month, start_day, year = match.groups()
            else:
                start_day, month, year = match.groups()
                
            sort_date = parse_smart_date(month, start_day, year)
            if sort_date:
                return match.group(0).strip(), sort_date
    return None, None

def classify_event(text):
    for cat, kw_list in CATEGORIES.items():
        if any(kw in text.lower() for kw in kw_list): return cat
    return "Ultrafast Science & Non-Linear Optics"

def is_valid_event(text):
    text_lower = text.lower()
    return any(ind in text_lower for ind in EVENT_INDICATORS) and "press release" not in text_lower

def fetch_events():
    events = {}
    today_date = datetime.now().date()

    print("--- Scanning RSS Feeds ---")
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
                                "title": title, "organizer": feed["name"], "category": classify_event(combined),
                                "type": "School" if "school" in combined.lower() else "Conference",
                                "location": "See Official Link", "display_date": disp_date,
                                "date": sort_date, "link": entry.get("link", "#"), "description": summary[:250] + "..."
                            }
                            print(f"Found: {title}")
        except Exception as e:
            print(f"Error on {feed['name']}: {e}")

    print("\n--- Scanning Deep Hubs ---")
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
                    title = trafilatura.extract_metadata(page_data).title or "Academic Event"
                    
                    if disp_date and sort_date:
                        if datetime.strptime(sort_date, "%Y-%m-%d").date() >= today_date:
                            clean_title = re.sub(r'[^a-zA-Z0-9]', '', title).lower()
                            if clean_title not in events:
                                events[clean_title] = {
                                    "title": title, "organizer": "Institute Hub Crawler", "category": classify_event(text),
                                    "type": "School" if "school" in text.lower() else "Conference",
                                    "location": "See Official Link", "display_date": disp_date,
                                    "date": sort_date, "link": url, "description": text[:250] + "..."
                                }
                                print(f"Found deep link: {title}")
        except Exception:
            pass

    return list(events.values())

if __name__ == "__main__":
    new_events = fetch_events()
    final_events = sorted(new_events, key=lambda x: x['date'])

    output_data = {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "total_events": len(final_events),
        "events": final_events
    }

    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(final_events)} automated events to dashboard.")
