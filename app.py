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
        r'\bate\b': '8', r'\bat\b': '8', r'\btoo\b': '2'
    }
    for pattern, replacement in repairs.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def format_address(address):
    address = phonetic_repair(address)
    # Remove "beside" and "suburb"
    address = re.sub(r'\bbeside\b', '', address, flags=re.IGNORECASE)
    address = re.sub(r'\bsuburb\s+', '', address, flags=re.IGNORECASE)
    
    # Standardize Unit/Flat/Flap/Suite
    unit_pattern = r'\b(flat|unit|u|suite|block|flap|flaps)\s*(\d+[a-z]?)\s*number\s*(\d+[a-z]?)'
    address = re.sub(unit_pattern, r'U\2/\3', address, flags=re.IGNORECASE)
    
    # Abbreviate Street Types
    st_types = {
        r'\bcrescent\b': 'Cres.', r'\bcresent\b': 'Cres.', r'\bway\b': 'Wy.',
        r'\broad\b': 'Rd.', r'\bstreet\b': 'St.', r'\bavenue\b': 'Ave.',
        r'\bparade\b': 'Pde.', r'\blane\b': 'Ln.', r'\bplace\b': 'Pl.'
    }
    for pattern, replacement in st_types.items():
        address = re.sub(pattern, replacement, address, flags=re.IGNORECASE)
    
    address = re.sub(r'\s+', ' ', address).strip()
    # Force Uppercase for Unit parts, Capitalize others
    words = address.split()
    return " ".join([w.upper() if ('/' in w or w.upper().startswith('U')) else w.capitalize() for w in words])

def calculate_date(text, anchor_str):
    days_map = {"mon":0, "tue":1, "wed":2, "thu":3, "fri":4, "sat":5, "sun":6}
    months_map = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
    
    anchor = datetime.strptime(anchor_str.strip(), '%Y-%m-%d')
    t_lower = text.lower()
    
    # Absolute Date (e.g. 7th of April)
    date_match = re.search(r'(\d+)(?:st|nd|rd|th)?\s*(?:of\s*)?([a-z]{3,})', t_lower)
    if date_match:
        m_idx = months_map[date_match.group(2)[:3]]
        return datetime(anchor.year, m_idx, int(date_match.group(1)))

    # Day of Week (e.g. next Thursday)
    day_match = re.search(r'(this|next)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)', t_lower)
    if day_match:
        keyword = day_match.group(1)
        target_idx = days_map[day_match.group(2)[:3]]
        days_ahead = (target_idx - anchor.weekday()) % 7
        if days_ahead == 0: days_ahead = 7
        
        res_date = anchor + timedelta(days=days_ahead)
        if keyword == 'next' and days_ahead <= 2:
            res_date += timedelta(days=7)
        return res_date
    return None

@app.route('/process', methods=['POST'])
def process():
    data = request.get_json(force=True)
    raw_payload = data.get('text', '')
    chunks = re.split(r'###NEWNOTE###', raw_payload)
    results = [] # Initialized once
    
    for chunk in chunks:
        if '###ENDNOTE###' not in chunk: continue
        content_block = chunk.split('###ENDNOTE###')[0].strip()
        
        # Explicit extraction of metadata
        a_match = re.search(r'Anchor:\s*([\d-]+)', content_block, re.I)
        s_match = re.search(r'Status:\s*([\d-]+)', content_block, re.I)
        
        if not a_match or not s_match: continue
        
        anchor_val = a_match.group(1)
        status_val = s_match.group(1)
        
        # Extract address and date context
        note_body = re.sub(r'(Anchor|Status|Content):.*', '', content_block, flags=re.I).strip()
        res_date = calculate_date(note_body, anchor_val)
        
        if res_date:
            status_dt = datetime.strptime(status_val, '%Y-%m-%d')
            day_flag = "LIVE" if res_date.date() >= status_dt.date() else "PAST"
            
            # Clean address
            addr_raw = re.split(r'\bviewing\b', note_body, flags=re.I)[0].strip()
            addr_raw = re.sub(r'^booked,.*?,.*?,', '', addr_raw, flags=re.I).strip()
            
            results.append({
                "viewing_date": res_date.strftime('%d/%m/%Y'),
                "status": day_flag,
                "address": format_address(addr_raw)
            })

    return jsonify(results) # Returns valid array [...]

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
