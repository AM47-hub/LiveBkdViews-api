from flask import Flask, request, make_response
import re
import json
from datetime import datetime, timedelta
import os

app = Flask(__name__)

@app.route('/ping', methods=['GET', 'HEAD'])
def health_check():
    """Lightweight endpoint to wake the server from sleep."""
    return make_response("Ready", 200)

def parse_content(body):
    """
    Closing Keyword Logic: Extracts values by finding the text between 
    a keyword and the next occurring keyword.
    """

    keywords = [
        "flat", "number", "beside", "suburb", "type", "rent", "rooms", 
        "available", "viewing", "from", "until", "agency", 
        "person", "mobile", "comments"
    ]

    # Find start position of every keyword found
    found_tokens = []
    for kw in keywords:
        # Match word boundaries to avoid partial matches (e.g., 'type' in 'prototype')
        for match in re.finditer(rf'\b{kw}\b', body, re.IGNORECASE):
            found_tokens.append({'key': kw.lower(), 'start': match.start(), 'end': match.end()})

    # Sort tokens by start position
    found_tokens.sort(key=lambda x: x['start'])

    # Extract values between keywords
    data = {kw: "" for kw in keywords}
    for i in range(len(found_tokens)):
        current = found_tokens[i]
        val_start = current['end']
        val_end = found_tokens[i+1]['start'] if i + 1 < len(found_tokens) else len(body)
        data[current['key']] = body[val_start:val_end].strip()

    return data

def format_address(tokens):
    # Pass tokens directly Pass 1 results
    # 1. Handle Unit/Number formatting
    unit = tokens.get('flat', '')
    street_num = tokens.get('number', '')

    # Mapping word-to-digit
    rep = {r'\bone\b':'1', r'\btwo\b':'2', r'\bthree\b':'3', r'\bfour\b':'4', r'\bfive\b':'5', r'\bsix\b':'6', r'\bseven\b':'7', r'\beight\b':'8', r'\bnine\b':'9', r'\bzero\b':'0', r'\bnone\b':'0', r'\bnill\b':'0', r'\bto\b':'2', r'\bfor\b':'4', r'\bate\b':'8'}
    for p, r in rep.items():
        unit = re.sub(p, r, unit, flags=re.I)
        street_num = re.sub(p, r, street_num, flags=re.I)

    # Remove spaces and Uppercase
    unit = unit.replace(" ", "").upper()
    street_num = street_num.replace(" ", "").upper()
    
    # Convert "dash" to "-" in street number
    street_num = re.sub(r'\s+dash\s+', '-', street_num, flags=re.I)

    # Assemble Unit/Number
    if unit:
        addr_prefix = f"U{unit}/{street_num}"
    else:
        addr_prefix = street_num

    # 2. Handle Street and Suburb
    beside = tokens.get('beside', '')
    # Standardise: "The" from "The Kingsway"
    beside = re.sub(r'^the\s+kingsway', 'Kingsway', beside, flags=re.I)

    suburb = tokens.get('suburb', '')

    # Build address key
    full_addr = f"{addr_prefix} {beside} {suburb}"

    # 3. Apply abbreviations
    subs = {r'\broad\b':'Rd.', r'\bstreet\b':'St.', r'\bcrescent\b':'Cres.', r'\bplace\b':'Pl.', r'\bclose\b':'Cl.', r'\bavenue\b':'Ave.', r'\blane\b':'Ln.', r'\bhighway\b':'Hwy.', r'\bway\b':'Wy.', r'\brow\b':'Rw.', r'\bterrace\b':'Tce.', r'\bdrive\b':'Dr.'}
    
    for p, r in subs.items(): full_addr = re.sub(p, r, full_addr, flags=re.I)

    return re.sub(r'\s+', ' ', full_addr).strip().title()

def extract_viewing_date(v_str, anchor_date):
    # Confirm viewing date value

    if not v_str: return None
    v_str = v_str.lower()
    
    # Specific date
    d_m = re.search(r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?', v_str)
    if d_m:
        day, month = int(d_m.group(1)), int(d_m.group(2))
        year = int(d_m.group(3)) if d_m.group(3) else anchor_date.year
        if year < 100: year += 2000
        return datetime(year, month, day)

    # Natural Language / Relative
    months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
    words_to_num = {"first":1,"second":2,"third":3,"fourth":4,"fifth":5,"sixth":6,"seventh":7,"eighth":8,"ninth":9,"tenth":10}
    for word, val in words_to_num.items():
        if word in v_str: v_str = v_str.replace(word, str(val))

    abs_m = re.search(r'(\d+)(?:st|nd|rd|th)?\s*(?:of\s*)?([a-z]{3,})', v_str)
    if abs_m:
        m_prefix = abs_m.group(2)[:3]
        if m_prefix in months:
            return datetime(anchor_date.year, months[m_prefix], int(abs_m.group(1)))
    
    # Relative Terms
    if any(word in v_str for word in ["today", "this morning", "this afternoon"]):
        return datetime.combine(anchor_date, datetime.min.time())

    if "tomorrow" in v_str:
        return datetime.combine(anchor_date + timedelta(days=1), datetime.min.time())

    days_map = {"mon":0, "tue":1, "wed":2, "thu":3, "fri":4, "sat":5, "sun":6}
    rel_m = re.search(r'(this|next)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)', v_str)
    if rel_m:
        kw, day = rel_m.groups()
        target_weekday = days_map[day[:3]]
        days_ahead = (target_weekday - anchor_date.weekday()) % 7
        if days_ahead == 0: days_ahead = 7
        res = anchor_date + timedelta(days=days_ahead)
        if kw == 'next' and days_ahead <= 2: res += timedelta(days=7)
        return datetime.combine(res, datetime.min.time())
    return None

@app.route('/process', methods=['POST'])
def process():
    data = request.get_json(force=True)
    raw = data.get('text', '').replace('\xa0', ' ').strip()
    notes = [c for c in raw.split('|') if c.strip()]

    parsed_notes = []

    for block in notes:

        a_m = re.search(r'Anchor:\s*([^\n\r]+)', block, re.I)
        s_m = re.search(r'Status:\s*(\d{4}-\d{2}-\d{2})', block, re.I)
        c_m = re.search(r'Content:\s*(.*)', block, re.I | re.S)

        if a_m and s_m and c_m:
            parsed_notes.append({
                "ts": datetime.fromisoformat(a_m.group(1).strip()),
                "status": s_m.group(1).strip(),
                "body": c_m.group(1).strip()
            })

    # Sort by date ascending
    parsed_notes.sort(key=lambda x: x["ts"])

    # Pass 1: Build comprehensive records
    unique_listings = {} 

    for item in parsed_notes:
        current_tokens = parse_content(item["body"])
        addr_key = format_address(current_tokens)

        if addr_key not in unique_listings:
            unique_listings[addr_key] = {
                "tokens": current_tokens,
                "anchor_date": item["ts"].date(),
                "status_date": datetime.strptime(item["status"], '%Y-%m-%d').date()

            }
        else:
            # Waterfall Coalesce
            for k, v in current_tokens.items():
                if v.strip():
                    unique_listings[addr_key]["tokens"][k] = v

            # Update meta-data to newest
            unique_listings[addr_key]["anchor_date"] = item["ts"].date()
            unique_listings[addr_key]["status_date"] = datetime.strptime(item["status"], '%Y-%m-%d').date()

    # PASS 2: Assembly from coalesced tokens
    final_results = []
    for addr_key, record in unique_listings.items():
        v_token = record["tokens"].get("viewing", "")
        
        # Check for specific date
        target_dt_obj = extract_viewing_date(v_token, record["anchor_date"])
        if target_dt_obj:
            target_dt = target_dt_obj.date()
            final_results.append({
                "sortDate": target_dt.strftime('%Y/%m/%d'),
                "DayFlag": "LIVE" if target_dt >= record["status_date"] else "PAST",
                "viewDate": target_dt.strftime('%d/%m/%Y'),
                "address": addr_key
            })

    return make_response(json.dumps(final_results), 200, {"Content-Type": "application/json"})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
