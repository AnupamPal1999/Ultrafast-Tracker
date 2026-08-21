import json
import re
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser as date_parser

# The magic header to bypass Optica and SPIE bot-blockers
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
    "optics", "photonics", "laser"
]

CATEGORIES = {
    "Soft X-Ray & Attosecond": ["attosecond", "atto", "hhg", "soft x-ray", "water window", "xuv", "euv", "vuv", "fel", "xfel", "synchrotron"],
    "Ultrafast Science & Non-Linear Optics": ["ultrafast", "femtosecond", "picosecond", "nonlinear", "cpa"],
    "Laser Sources & Development": ["fiber laser", "solid-state", "diode laser", "opcpa", "amplifier"]
}

def classify_event(text):
    for cat, kw_list in CATEGORIES.items():
        if any(kw in text.lower() for kw in kw_list): return cat
    return "Ultrafast Science & Non-Linear Optics"

def extract_dates_from_text(text):
    months = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    p1 = rf'\b(\d{{1,2}})(?:\s*-\s*\d{{1,2}})?\s+({months})\s+(202[4-9])\b'
    p2 = rf'\b({months})\s+(\d{{1,2}})(?:\s*-\s*\d{{1,2}})?(?:,\s*)?\s+(202[4-9])\b'
    
    try:
        m1 = re.search(p1, text, re.IGNORECASE)
        if m1:
            sort_date = date_parser.parse(f"{m1.group(2)} {m1.group(1)} {m1.group(3)}").strftime("%Y-%m-%d")
            return m1.group(0), sort_date
        m2 = re.search(p2, text, re.IGNORECASE)
        if m2:
            sort_date = date_parser.parse(f"{m2.group(1)} {m2.group(2)} {m2.group(3)}").strftime("%Y-%m-%d")
            return m2.group(0), sort_date
    except:
        pass
    return None, None

def scrape_optica_spie_laserlab():
    """Specifically targets the HTML structure of the Big 4"""
    events_found = {}
    today_date = datetime.now().date()
    
    # 1. Optica Events
    print("Scanning Optica Events...")
    try:
        req = requests.get("https://www.optica.org/events/", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(req.text, 'html.parser')
        # Optica lists events in standard block elements
        for block in soup.find_all(['div', 'li']):
            text = block.get_text(separator=" ", strip=True)
            if any(kw in text.lower() for kw in KEYWORDS) and ('202' in text):
                disp_date, sort_date = extract_dates_from_text(text)
                if sort_date and datetime.strptime(sort_date, "%Y-%m-%d").date() >= today_date:
                    title_elem = block.find('a')
                    title = title_elem.text.strip() if title_elem else text[:60] + "..."
                    clean_title = re.sub(r'[^a-zA-Z0-9]', '', title).lower()
                    
                    if len(title) > 10 and clean_title not in events_found:
                        events_found[clean_title] = {
                            "title": title, "organizer": "Optica", "category": classify_event(text),
                            "type": "School" if "school" in text.lower() else "Conference",
                            "location": "See Optica Site", "display_date": disp_date,
                            "date": sort_date, "link": "https://www.optica.org" + (title_elem['href'] if title_elem and title_elem.has_attr('href') else "/events/"),
                            "description": text[:200] + "..."
                        }
    except Exception as e: print(f"Optica failed: {e}")

    # 2. SPIE Events
    print("Scanning SPIE Events...")
    try:
        req = requests.get("https://spie.org/conferences-and-exhibitions", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(req.text, 'html.parser')
        for block in soup.find_all('div', class_=re.compile('event|conf', re.I)):
            text = block.get_text(separator=" ", strip=True)
            if any(kw in text.lower() for kw in KEYWORDS):
                disp_date, sort_date = extract_dates_from_text(text)
                if sort_date and datetime.strptime(sort_date, "%Y-%m-%d").date() >= today_date:
                    title = text.split('202')[0].strip()
                    clean_title = re.sub(r'[^a-zA-Z0-9]', '', title).lower()
                    if clean_title not in events_found:
                        events_found[clean_title] = {
                            "title": title[:60], "organizer": "SPIE", "category": classify_event(text),
                            "type": "Conference", "location": "See SPIE Site", "display_date": disp_date,
                            "date": sort_date, "link": "https://spie.org/conferences-and-exhibitions",
                            "description": text[:200] + "..."
                        }
    except Exception as e: print(f"SPIE failed: {e}")

    # 3. Laserlab-Europe & Laser4EU
    print("Scanning Laserlab/Laser4EU...")
    try:
        req = requests.get("https://laserlab-europe.eu/events/conferences.html", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(req.text, 'html.parser')
        for block in soup.find_all('p'):
            text = block.get_text(separator=" ", strip=True)
            if any(kw in text.lower() for kw in KEYWORDS):
                disp_date, sort_date = extract_dates_from_text(text)
                if sort_date and datetime.strptime(sort_date, "%Y-%m-%d").date() >= today_date:
                    clean_title = re.sub(r'[^a-zA-Z0-9]', '', text[:30]).lower()
                    if clean_title not in events_found:
                        events_found[clean_title] = {
                            "title": text.split(',')[1].strip() if ',' in text else text[:60], 
                            "organizer": "Laserlab-Europe / Laser4EU", "category": classify_event(text),
                            "type": "Workshop", "location": "Europe", "display_date": disp_date,
                            "date": sort_date, "link": "https://laserlab-europe.eu/events/conferences.html",
                            "description": text[:200] + "..."
                        }
    except Exception as e: print(f"Laserlab failed: {e}")

    return list(events_found.values())

def fetch_rss_feeds():
    """Keeps the standard RSS catcher active for the accelerators/institutes"""
    feeds = [
        {"name": "European XFEL", "url": "https://www.xfel.eu/news_and_events/news/rss/index_eng.xml"},
        {"name": "CERN Indico", "url": "https://indico.cern.ch/export/feed/rss.xml"},
        {"name": "ELI Beams", "url": "https://www.eli-beams.eu/feed/"},
        {"name": "Lightsources.org", "url": "https://lightsources.org/for-users/events/feed/"}
    ]
    events = []
    today_date = datetime.now().date()
    
    print("Scanning Standard RSS Feeds...")
    for feed in feeds:
        try:
            parsed = feedparser.parse(feed["url"])
            for entry in parsed.entries:
                text = entry.get("title", "") + " " + BeautifulSoup(entry.get("summary", ""), "html.parser").get_text()
                if any(kw in text.lower() for kw in KEYWORDS):
                    disp_date, sort_date = extract_dates_from_text(text)
                    if sort_date and datetime.strptime(sort_date, "%Y-%m-%d").date() >= today_date:
                        events.append({
                            "title": entry.get("title", ""), "organizer": feed["name"], "category": classify_event(text),
                            "type": "Conference", "location": "See Link", "display_date": disp_date,
                            "date": sort_date, "link": entry.get("link", "#"), "description": text[:200] + "..."
                        })
        except: pass
    return events

if __name__ == "__main__":
    print("Starting targeted scrape...")
    target_events = scrape_optica_spie_laserlab()
    rss_events = fetch_rss_feeds()
    
    all_events = target_events + rss_events
    
    # Deduplicate and Sort
    final_events = {}
    for ev in all_events:
        key = re.sub(r'[^a-zA-Z0-9]', '', ev['title']).lower()
        final_events[key] = ev
        
    sorted_events = sorted(list(final_events.values()), key=lambda x: x['date'])

    output_data = {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "total_events": len(sorted_events),
        "events": sorted_events
    }

    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nTargeted Scrape Complete. Saved {len(sorted_events)} events.")
