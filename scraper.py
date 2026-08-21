import json
import re
import requests
import feedparser
from bs4 import BeautifulSoup
import trafilatura
from urllib.parse import urljoin
from datetime import datetime
from dateutil import parser as date_parser

# The magic header to bypass bot-blockers on Society websites
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

KEYWORDS = [
    "attosecond", "atto", "high harmonic", "hhg", "sub-cycle", "strong field",
    "soft x-ray", "soft-x-ray", "water window", "xuv", "euv", "vuv", 
    "free electron laser", "fel", "xfel", "synchrotron", "linac",
    "ultrafast", "femtosecond", "picosecond", "nonlinear optics", "cpa",
    "fiber laser", "solid-state laser", "diode laser", "laser development",
    "optics", "photonics", "laser physics"
]

CATEGORIES = {
    "Soft X-Ray & Attosecond": ["attosecond", "atto", "hhg", "soft x-ray", "water window", "xuv", "euv", "vuv", "fel", "xfel", "synchrotron"],
    "Ultrafast Science & Non-Linear Optics": ["ultrafast", "femtosecond", "picosecond", "nonlinear", "cpa"],
    "Laser Sources & Development": ["fiber laser", "solid-state", "diode laser", "opcpa", "amplifier"]
}

# --- 1. DIRECT RSS FEEDS ---
RSS_FEEDS = [
    {"name": "Laserlab-Europe", "url": "https://laserlab-europe.eu/events/category/laserlab-europe/feed/"},
    {"name": "Laser4EU", "url": "https://laser4eu.eu/feed/"},
    {"name": "Lightsources.org", "url": "https://lightsources.org/for-users/events/feed/"},
    {"name": "European XFEL", "url": "https://www.xfel.eu/news_and_events/news/rss/index_eng.xml"},
    {"name": "CERN Indico", "url": "https://indico.cern.ch/export/feed/rss.xml"},
    {"name": "ELI Beams", "url": "https://www.eli-beams.eu/feed/"},
    {"name": "ELI ALPS", "url": "https://www.eli-alps.hu/en/rss"}
]

# --- 2. THE MASTER HTML HUBS (Societies + Institutes) ---
HTML_HUBS = [
    {"name": "Optica", "url": "https://www.optica.org/events/"},
    {"name": "SPIE", "url": "https://spie.org/conferences-and-exhibitions"},
    {"name": "EPS", "url": "https://www.eps.org/events/event_list.asp"},
    {"name": "APS", "url": "https://www.aps.org/meetings/"},
    {"name": "MBI Berlin", "url": "https://mbi-berlin.de/news-and-events"},
    {"name": "Lund Laser Centre", "url": "https://www.llc.lu.se/events"},
    {"name": "ARCNL", "url": "https://arcnl.nl/en/news-events"},
    {"name": "LLE Rochester", "url": "https://www.lle.rochester.edu/events/"},
    {"name": "ETH Zurich", "url": "https://phys.ethz.ch/news-and-events.html"},
    {"name": "EPFL", "url": "https://actu.epfl.ch/"},
    {"name": "PSI", "url": "https://www.psi.ch/en/media/events"},
    {"name": "GSI", "url": "https://www.gsi.de/en/news/events"},
    {"name": "Oxford Physics", "url": "https://www.physics.ox.ac.uk/events"},
    {"name": "Imperial College", "url": "https://www.imperial.ac.uk/physics/events/"},
    {"name": "Elettra Sincrotrone", "url": "https://www.elettra.eu/news.html"}
]

def parse_smart_date(month_str, day_str, year_str=None):
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
    months = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    
    p1 = rf'\b({months})\s+(\d{{1,2}})(?:\s*-\s*\d{{1,2}})?(?:st|nd|rd|th)?(?:(?:,\s*|\s+)(202[4-9]))?\b'
    p2 = rf'\b(\d{{1,2}})(?:\s*-\s*\d{{1,2}})?(?:st|nd|rd|th)?\s+({months})(?:(?:,\s*|\s+)(202[4-9]))?\b'
    
    for pattern in [p1, p2]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if pattern == p1:
                month, start_day, year = match.groups()
            else:
                start_day, month, year = match.groups()
                
            sort_date = parse_smart_date(month, start_day, year)
            if sort_date: return match.group(0).strip(), sort_date
    return None, None

def classify_event(text):
    for cat, kw_list in CATEGORIES.items():
        if any(kw in text.lower() for kw in kw_list): return cat
    return "Ultrafast Science & Non-Linear Optics"

def run_scraper():
    events = {}
    today_date = datetime.now().date()

    print("--- 1. Scanning RSS Feeds ---")
    for feed in RSS_FEEDS:
        try:
            parsed = feedparser.parse(feed["url"])
            for entry in parsed.entries:
                title = entry.get("title", "")
                summary = BeautifulSoup(entry.get("summary", "") or entry.get("description", ""), "html.parser").get_text()
                combined_text = f"{title} {summary}"
                
                if any(kw in combined_text.lower() for kw in KEYWORDS):
                    disp_date, sort_date = extract_dates(combined_text)
                    if sort_date and datetime.strptime(sort_date, "%Y-%m-%d").date() >= today_date:
                        clean_title = re.sub(r'[^a-zA-Z0-9]', '', title).lower()
                        events[clean_title] = {
                            "title": title, "organizer": feed["name"], "category": classify_event(combined_text),
                            "type": "School" if "school" in combined_text.lower() else "Conference",
                            "location": "See Link", "display_date": disp_date,
                            "date": sort_date, "link": entry.get("link", "#"), "description": summary[:250] + "..."
                        }
                        print(f"[RSS] Found: {title[:50]}...")
        except Exception as e:
            print(f"[Error] RSS {feed['name']} failed.")

    print("\n--- 2. Deep-Crawling Master Hubs ---")
    for hub in HTML_HUBS:
        print(f"Checking {hub['name']}...")
        try:
            # 1. Fetch the Hub Directory
            response = requests.get(hub["url"], headers=HEADERS, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 2. Find all links that look like individual events
            event_links = set()
            for a_tag in soup.find_all('a', href=True):
                url = urljoin(hub["url"], a_tag['href'])
                if any(w in url.lower() for w in ['event', 'conf', 'school', 'workshop', 'meeting']):
                    event_links.add(url)
            
            # 3. Visit each event link directly (limit to 15 per site to avoid timeouts)
            for link in list(event_links)[:15]:
                try:
                    # Using requests to bypass bot blockers, then trafilatura to clean the text
                    page_resp = requests.get(link, headers=HEADERS, timeout=7)
                    text = trafilatura.extract(page_resp.text)
                    
                    if not text or not any(kw in text.lower() for kw in KEYWORDS): 
                        continue
                    
                    disp_date, sort_date = extract_dates(text)
                    if sort_date and datetime.strptime(sort_date, "%Y-%m-%d").date() >= today_date:
                        # Find a good title
                        page_soup = BeautifulSoup(page_resp.text, 'html.parser')
                        title = page_soup.title.string if page_soup.title else text[:50]
                        clean_title = re.sub(r'[^a-zA-Z0-9]', '', title).lower()
                        
                        if clean_title not in events:
                            events[clean_title] = {
                                "title": title.strip(), "organizer": hub["name"], "category": classify_event(text),
                                "type": "School" if "school" in text.lower() else "Conference",
                                "location": "See Link", "display_date": disp_date,
                                "date": sort_date, "link": link, "description": text[:250].replace('\n', ' ') + "..."
                            }
                            print(f"  -> [Deep Link] Found: {title[:50]}...")
                except:
                    pass
        except Exception as e:
            print(f"[Error] Hub {hub['name']} failed.")

    # Return sorted events
    return sorted(list(events.values()), key=lambda x: x['date'])

if __name__ == "__main__":
    final_events = run_scraper()

    output_data = {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "total_events": len(final_events),
        "events": final_events
    }

    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nSUCCESS: Saved {len(final_events)} total deeply-crawled events.")
