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

# --- ALL SOURCES SPLIT INTO EVEN AND ODD LISTS ---
ALL_DIRECT_FEEDS = [
    {"name": "Laserlab-Europe", "url": "https://laserlab-europe.eu/events/category/laserlab-europe/feed/"}, # 0 (Even)
    {"name": "Laser4EU", "url": "https://laser4eu.eu/feed/"}, # 1 (Odd)
    {"name": "Lightsources.org", "url": "https://lightsources.org/for-users/events/feed/"}, # 2 (Even)
    {"name": "Optica Events", "url": "https://www.optica.org/events/rss"}, # 3 (Odd)
    {"name": "SPIE Conferences", "url": "https://spie.org/conferences-and-exhibitions/rss"}, # 4 (Even)
    {"name": "APS Physics", "url": "https://physics.aps.org/feeds/all"}, # 5 (Odd)
    {"name": "EPS", "url": "https://www.eps.org/events/event_list.asp?show=&rss=1"}, # 6 (Even)
    {"name": "European XFEL", "url": "https://www.xfel.eu/news_and_events/news/rss/index_eng.xml"}, # 7 (Odd)
    {"name": "CERN Indico", "url": "https://indico.cern.ch/export/feed/rss.xml"}, # 8 (Even)
    {"name": "ELI Beams", "url": "https://www.eli-beams.eu/feed/"}, # 9 (Odd)
    {"name": "ELI ALPS", "url": "https://www.eli-alps.hu/en/rss"} # 10 (Even)
]

ALL_EVENT_HUBS = [
    "https://mbi-berlin.de/news-and-events", # 0 (Even)
    "https://www.llc.lu.se/events", # 1 (Odd)
    "https://arcnl.nl/en/news-events", # 2 (Even)
    "https://www.lle.rochester.edu/events/", # 3 (Odd)
    "https://phys.ethz.ch/news-and-events.html", # 4 (Even)
    "https://actu.epfl.ch/", # 5 (Odd)
    "https://www.psi.ch/en/media/events", # 6 (Even)
    "https://www.gsi.de/en/news/events", # 7 (Odd)
    "https://www.elettra.eu/news.html", # 8 (Even)
    "https://www.physics.ox.ac.uk/events", # 9 (Odd)
    "https://www.imperial.ac.uk/physics/events/", # 10 (Even)
    "https://www.kcl.ac.uk/news", # 11 (Odd)
    "https://www.qub.ac.uk/News/" # 12 (Even)
]

def get_today_split():
    """Determines whether to check Even or Odd sources based on the day of the month."""
    day_of_month = datetime.now().day
    is_even_day = (day_of_month % 2 == 0)
    
    # Split direct feeds
    feeds = [f for i, f in enumerate(ALL_DIRECT_FEEDS) if (i % 2 == 0) == is_even_day]
    # Split event hubs
    hubs = [h for i, h in enumerate(ALL_EVENT_HUBS) if (i % 2 == 0) == is_even_day]
    
    batch_name = "Even" if is_even_day else "Odd"
    print(f"Today is day {day_of_month} ({batch_name} batch). Scraping {len(feeds)} feeds and {len(hubs)} hubs.")
    return feeds, hubs

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

def fetch_current_batch_events():
    events = {}
    today_date = datetime.now().date()
    feeds, hubs = get_today_split()

    # --- ENGINE 1: Current Batch Direct Feeds ---
    for feed in feeds:
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

    # --- ENGINE 2: Current Batch Deep Hub Crawler ---
    for hub in hubs:
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

    return list(events.values())

if __name__ == "__main__":
    existing_events = []
    try:
        with open("events.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            existing_events = data.get("events", [])
    except:
        pass

    today_date = datetime.now().date()
    valid_existing = {re.sub(r'[^a-zA-Z0-9]', '', e['title']).lower(): e for e in existing_events if datetime.strptime(e['date'], "%Y-%m-%d").date() >= today_date}

    new_batch = fetch_current_batch_events()

    for ev in new_batch:
        key = re.sub(r'[^a-zA-Z0-9]', '', ev['title']).lower()
        valid_existing[key] = ev

    final_events = sorted(list(valid_existing.values()), key=lambda x: x['date'])

    output_data = {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "total_events": len(final_events),
        "events": final_events
    }

    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"Successfully saved {len(final_events)} total combined events.")
