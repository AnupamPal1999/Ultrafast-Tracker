import json
import re
from datetime import datetime
import feedparser
import requests
from bs4 import BeautifulSoup

# Comprehensive keywords tailored for Soft X-ray, Water Window, Attosecond, and Laser Dev
KEYWORDS = [
    # Attosecond, High-Field & HHG
    "attosecond", "atto", "high harmonic", "hhg", "sub-cycle", "strong field",
    "tunnel ionization", "recombination", "isolated attosecond",
    
    # Soft X-Ray, EUV, XUV & Water Window
    "soft x-ray", "soft x ray", "soft-x-ray", "soft x", "water window", "water-window",
    "xuv", "euv", "extreme ultraviolet", "vuv", "vacuum ultraviolet",
    "x-ray transient absorption", "transient absorption", "nexafs", "xanes",
    "free electron laser", "fel", "xfel",
    
    # Ultrafast Science & Drivers
    "ultrafast", "femtosecond", "picosecond", "nonlinear optics", "cpa", "opcpa",
    "mid-ir", "mid-infrared", "optical parametric",
    
    # Laser Sources & Engineering
    "fiber laser", "solid-state laser", "solid state laser", "diode laser",
    "thin disk", "laser development", "chirped pulse", "power amplifier"
]

CATEGORIES = {
    "Soft X-Ray & Attosecond": [
        "attosecond", "atto", "hhg", "high harmonic", "soft x-ray", "soft x ray",
        "soft-x-ray", "soft x", "water window", "water-window", "xuv", "euv",
        "extreme ultraviolet", "vuv", "vacuum ultraviolet", "sub-cycle", "strong field",
        "transient absorption", "nexafs", "xanes", "fel", "xfel"
    ],
    "Ultrafast Science & Non-Linear Optics": [
        "ultrafast", "femtosecond", "picosecond", "nonlinear optics", "cpa", "mid-ir", "mid-infrared"
    ],
    "Laser Sources & Development": [
        "fiber laser", "solid-state", "solid state", "diode laser", "opcpa",
        "thin disk", "laser development", "amplifier"
    ]
}

FEEDS = [
    # General & Optics RSS Feeds
    {"name": "Optica Events", "url": "https://www.optica.org/events/rss"},
    {"name": "SPIE Conferences", "url": "https://spie.org/conferences-and-exhibitions/rss"},
    {"name": "Laserlab-Europe", "url": "https://www.laserlab-europe.eu/events/events-rss"},
    {"name": "Gordon Research Conferences", "url": "https://www.grc.org/rss/conferences.xml"},
    {"name": "Physics Today Events", "url": "https://physicstoday.scitation.org/action/showFeed?type=etoc&feed=rss&jc=pto"},
    {"name": "Lightsources.org News & Events", "url": "https://lightsources.org/feed/"}
]

# Static curated list of recurring gold-standard conferences
CURATED_CONFERENCES = [
    {
        "title": "International Conference on Attosecond Science and Technology (ATTO)",
        "organizer": "ATTO Committee",
        "category": "Soft X-Ray & Attosecond",
        "type": "Conference",
        "location": "Biennial International",
        "date": "Summer Series",
        "link": "https://atto-conference.org",
        "description": "The flagship conference for attosecond physics, soft X-ray HHG in gases and solids, and core-level electron dynamics."
    },
    {
        "title": "VUVX (International Conference on Vacuum Ultraviolet and X-ray Physics)",
        "organizer": "VUVX Steering Committee",
        "category": "Soft X-Ray & Attosecond",
        "type": "Conference",
        "location": "Triennial International",
        "date": "Triennial Series",
        "link": "https://lightsources.org",
        "description": "Major international forum covering fundamental advances in VUV, EUV, and soft X-ray science using synchrotrons, FELs, and HHG."
    },
    {
        "title": "Optica High-Brightness Sources and Light-Driven Interactions Congress",
        "organizer": "Optica",
        "category": "Soft X-Ray & Attosecond",
        "type": "Conference",
        "location": "Biennial (Spring)",
        "date": "Spring Series",
        "link": "https://www.optica.org",
        "description": "Features dedicated topical meetings on Compact EUV & X-Ray Light Sources, Mid-IR Drivers, and High-Intensity Lasers."
    },
    {
        "title": "Ultrafast Phenomena (UP)",
        "organizer": "Optica",
        "category": "Ultrafast Science & Non-Linear Optics",
        "type": "Conference",
        "location": "Biennial International",
        "date": "Summer Series",
        "link": "https://www.optica.org",
        "description": "Primary international gathering for ultrafast laser development, attosecond spectroscopy, and quantum dynamics."
    },
    {
        "title": "Gordon Research Conference: X-Ray Science / Ultrafast Phenomena",
        "organizer": "GRC",
        "category": "Soft X-Ray & Attosecond",
        "type": "Workshop",
        "location": "Rotational (US / Europe)",
        "date": "Biennial",
        "link": "https://www.grc.org",
        "description": "Frontier research in ultrafast soft X-ray science, water-window spectroscopy, and coherent diffraction."
    },
    {
        "title": "Europhoton (Solid-State and Fibre Coherent Light Sources)",
        "organizer": "European Physical Society (EPS)",
        "category": "Laser Sources & Development",
        "type": "Conference",
        "location": "Europe (Rotational)",
        "date": "Biennial (Late Summer)",
        "link": "https://www.europhoton.net",
        "description": "Cutting-edge solid-state, fiber, waveguide, and high-power laser development essential as pump sources."
    },
    {
        "title": "International Summer School on Ultrafast Laser Science",
        "organizer": "European Facilities / ELI",
        "category": "Soft X-Ray & Attosecond",
        "type": "Summer School",
        "location": "Europe (e.g., ELI-Beamlines / Lund)",
        "date": "Annual (July - Sept)",
        "link": "https://www.eli-laser.eu",
        "description": "Hands-on training school for PhD students covering high-power driver laser technology, HHG optimization, and EUV/soft X-ray metrology."
    }
]

def classify_event(text):
    text_lower = text.lower()
    for cat, kw_list in CATEGORIES.items():
        if any(kw in text_lower for kw in kw_list):
            return cat
    return "Ultrafast Science & Non-Linear Optics"

def matches_keywords(text):
    text_lower = text.lower()
    return any(re.search(r'\b' + re.escape(kw) + r'\b', text_lower) for kw in KEYWORDS)

def fetch_feed_events():
    events = list(CURATED_CONFERENCES)
    
    for feed_info in FEEDS:
        try:
            parsed = feedparser.parse(feed_info["url"])
            for entry in parsed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                combined = f"{title} {summary}"
                
                if matches_keywords(combined):
                    category = classify_event(combined)
                    event_type = "Conference"
                    lower_combined = combined.lower()
                    if "school" in lower_combined:
                        event_type = "Summer School"
                    elif "workshop" in lower_combined or "symposium" in lower_combined:
                        event_type = "Workshop"
                        
                    events.append({
                        "title": title,
                        "organizer": feed_info["name"],
                        "category": category,
                        "type": event_type,
                        "location": "See Event Link",
                        "date": entry.get("published", datetime.now().strftime("%B %Y")),
                        "link": entry.get("link", "#"),
                        "description": BeautifulSoup(summary, "html.parser").get_text()[:260] + "..."
                    })
        except Exception as e:
            print(f"Error parsing {feed_info['name']}: {e}")

    # Deduplicate entries by normalized title
    unique_events = {}
    for ev in events:
        clean_title = re.sub(r'[^a-zA-Z0-9]', '', ev['title']).lower()
        if clean_title not in unique_events:
            unique_events[clean_title] = ev

    return list(unique_events.values())

if __name__ == "__main__":
    collected = fetch_feed_events()
    output_data = {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "total_events": len(collected),
        "events": collected
    }
    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"Successfully saved {len(collected)} events to events.json")
