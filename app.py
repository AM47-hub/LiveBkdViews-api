from flask import Flask, request, jsonify
import re
from datetime import datetime, timedelta
import os

app = Flask(__name__)

def phonetic_repair(text):
    repairs = {
        r'\bone\b': '1', r'\btwo\b': '2', r'\bthree\b': '3', r'\bfour\b': '4',
        r'\bfive\b': '5', r'\bsix\b': '6', r'\bseven\b': '7', r'\beight\b': '8',
        r'\bnine\b': '9', r'\bten\b': '10', r'\btwenty\b': '20', r'\bthirty\b': '30',
        r'\bforty\b': '40', r'\bfifty\b': '50', r'\bto\b': '2', r'\bfor\b': '4',
        r'\bate\b': '8', r'\bat\b': '8'
    }
    for pattern, replacement in repairs.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def format_address(address):
    address = phonetic_repair(address)
    # CHANGE: Standardizing Unit/Flat/Flap/Suite/Block to UX/Y format
    unit_pattern = r'\b(flat|unit|u|suite|block|flap)\s*(\d+[a-z]?)\s*number\s*(\d+[a-z]?)'
    address = re.sub(unit_pattern, r'U\2/\3', address, flags=re.IGNORECASE)
    address = re.sub(r'\bnumber\s*(\d+[a-z]?)', r'\1', address, flags=re.IGNORECASE)
    
    st_types = {
        r'\bcrescent\b': 'Cres.', r'\bcresent\b': 'Cres.', r'\bway\b': 'Wy.',
        r'\broad\b': 'Rd.', r'\bstreet\b': 'St.', r'\bavenue\b': 'Ave.',
        r'\bparade\b': 'Pde.', r'\blane\b': 'Ln.', r'\bplace\b': 'Pl.'
    }
    for pattern, replacement in st_types.items():
        address = re.sub(pattern, replacement, address, flags=re.IGNORECASE)
    
    address = re.sub(r'\bsuburb\s+', '', address, flags=re.IGNORECASE)
    address = re.sub(r'\s+', ' ', address).strip()
    
    words = address.split()
    formatted = []
    for w in words:
        if '/' in w or w.upper().startswith('U'): formatted.append(w.upper())
        else: formatted.append(w.capitalize())
    return " ".join(formatted)

def calculate_date(text, anchor_str):
    days_map = {"mon":0, "tue":1, "wed":2, "thu":3, "fri":4, "sat":5, "sun":6}
    months_map = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
    
    try:
        anchor = datetime.strptime(anchor_str.strip(), '%Y-%m-%d')
    except:
        return None
    
    t_lower = text.lower()
    
    # 1. Absolute dates
    date_match = re.search(r'(\d+)(?:st|nd|rd|th)?\s*(?:of\s*)?([a-z]{3,})', t_lower)
    if date_match:
        try:
            m_idx = months_map[date_match.group(2)[:3]]
            return datetime(anchor.year, m_idx, int(date_match.group(1)))
        except: pass

    # 2. Relative dates (this/next)
    day_match = re.search(r'(this|next)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)', t_lower)
    if day_match:
        keyword = day_match.group(1)
        target_idx = days_map[day_match.group(2)[:3]]
        anchor_idx = anchor.weekday()
        
        days_ahead = (target_idx - anchor_idx) % 7
        if days_ahead == 0: days_ahead = 7
        
        res_date = anchor + timedelta(days=days_ahead)
        # CHANGE: Deterministic 'next' jump if within 2 days of anchor
        if keyword == 'next' and days_ahead <= 2:
            res_date += timedelta(days=7)
        return res_date
    return None

@app.route('/process', methods=['POST'])
def process():
    data = request.get_json(force=True)
    raw_payload = data.get('text', '')
    chunks = raw_payload.split('###NEWNOTE###')
    results = []
    
    for chunk in chunks:
        if not chunk.strip(): continue
        content_block = chunk.split('###ENDNOTE###')[0].strip()
        lines = content_block.split('\n')
        
        note_text, anchor_val, status_val = "", "", ""
        for line in lines:
            l = line.strip()
            if 'anchor:' in l.lower(): anchor_val = l.split(':', 1)[1].strip()
            elif 'status:' in l.lower(): status_val = l.split(':', 1)[1].strip()
            elif 'content:' in l.lower(): note_text = l.split(':', 1)[1].strip()
            else: note_text += " " + l

        if not anchor_val or not status_val: continue
        res_date = calculate_date(note_text, anchor_val)
        if not res_date: continue

        # CHANGE: DayFlag logic (LIVE vs PAST) based on status date
        status_dt = datetime.strptime(status_val, '%Y-%m-%d')
        day_flag = "LIVE"
        if res_date.date() < status_dt.date():
            day_flag = "PAST"

        address_raw = note_text.split("viewing")[0].strip()
        address_raw = re.sub(r'^booked,.*?,.*?,', '', address_raw, flags=re.IGNORECASE).strip()
        
        results.append({
            "viewing_date": res_date.strftime('%d/%m/%Y'),
            "status": day_flag, # This is the DayFlag
            "address": format_address(address_raw)
        })

    return jsonify(results)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
