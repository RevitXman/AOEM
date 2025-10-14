from icalendar import Calendar, Event
from datetime import datetime, timedelta, timezone

def generate_ics(events: list[dict]) -> bytes:
    cal = Calendar()
    cal.add('prodid', '-//S77 Buffs//server-77.com//')
    cal.add('version', '2.0')
    for e in events:
        ev = Event()
        ev.add('summary', f"{e['title']} | {e['region']} | {e['aoe_name']}")
        ev.add('dtstart', e['start_utc'])
        ev.add('dtend', e['start_utc'] + timedelta(hours=1))
        ev.add('dtstamp', datetime.now(timezone.utc))
        cal.add_component(ev)
    return cal.to_ical()
