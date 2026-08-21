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

ALL_EVENT_HUBS = [
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

def get_today_split():
    day_of_month = datetime.now().day
    is_even_day = (day_of_month % 2 == 0)
    
    feeds = [f for i, f in enumerate(ALL_DIRECT_FEEDS) if (i % 2 == 0) == is_even_day]
    hubs = [h for i, h in enumerate(ALL_EVENT_HUBS) if (i % 2 == 0) == is_even_day]
    
    batch_name = "Even" if is_even_day else "Odd"
    print(f"--- Running {batch_name} Batch (Day {day_of_month}) ---")
    return feeds, hubs

def parse_smart_date(month_str, day_str, year_str=None):
    """If the year is missing from the website text, intelligently calculate if it's this year or next year."""
    today = datetime.now().date()
    try:
        if year_str:
            year = int(year_str)
        else:
            # Test with current year
            tmp_date = date_parser.parse(f"{month_str} {day_str} {today.year}").date()
            year = today.year + 1 if tmp_date < today else today.year
            
        final_date = date_parser.parse(f"{month_str} {day_str} {year}").strftime("%Y-%m-%d")
        return final_date
    except:
        return None

def extract_dates(text):
    months_regex = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    
    # Notice the year (202X) is now OPTIONAL (the trailing ? block)
    p1 = rf'\b({months_regex})\s+(\d{{1,2}})(?:\s*-\s*\d{{1,2}})?(?:st|nd|rd|th)?(?:(?:,\s*|\s+)(202[4-9]))?\b'
    p2 = rf'\b(\d{{1,2}})(?:\s*-\s*\d{{1,2}})?(?:st|nd|rd|th)?\s+({months_regex})(?:(?:,\s*|\s+)(202[4-9]))?\b'
    
    match1 = re.search(p1, text, re.IGNORECASE)
    if match1:
        month, start_day, year = match1.groups()
        sort_date = parse_smart_date(month, start_day, year)
        if sort_date: return match1.group(0).strip(), sort_date
        
    match2 = re.search(p2, text, re.IGNORECASE)
    if match2:
        start_day, month, year = match2.groups()
        sort_date = parse_smart_date(month, start_day, year)
        if sort_date: return match2.group(0).strip(), sort_date

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

    print("\n--- Scanning RSS Feeds ---")
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
                                "title": title, "organizer": feed["name"], "category": classify_event(combined),
                                "type": "School" if "school" in combined.lower() else "Conference",
                                "location": "See Official Link", "display_date": disp_date,
                                "date": sort_date, "link": entry.get("link", "#"), "description": summary[:250] + "..."
                            }
                            print(f"[SUCCESS] Added: {title} ({sort_date})")
                        else:
                            print(f"[SKIPPED - PAST EVENT] {title}")
                    else:
                        print(f"[SKIPPED - NO EXACT DATE] {title}")
        except Exception as e:
            print(f"[ERROR] Failed to read {feed['name']}: {e}")

    print("\n--- Scanning Deep Hubs ---")
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
                                print(f"[SUCCESS] Added deep link: {title}")
                        else:
                            print(f"[SKIPPED - PAST EVENT] {title}")
                    else:
                        print(f"[SKIPPED - NO EXACT DATE] {title}")
        except Exception as e:
            print(f"[ERROR] Deep scrape failed for {hub}: {e}")

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
    print(f"\nSuccessfully saved {len(final_events)} total combined events.")
