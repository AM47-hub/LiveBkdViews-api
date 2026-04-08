from flask import Flask, request, jsonify
import re
import json
from datetime import datetime, timedelta
import os

app = Flask(__name__)

def format_address(address):
    rep = {r'\bone\b':'1', r'\btwo\b':'2', r'\bthree\b':'3', r'\bfour\b':'4', r'\bfive\b':'5', r'\bsix\b':'6', r'\bseven\b':'7', r'\beight\b':'8', r'\bnine\b':'9', r'\bto\b':'2', r'\bfor\b':'4'}
    for p, r in rep.items(): address = re.sub(p, r, address, flags=re.I)
    address = re.sub(r'\bbeside\b', '', address, flags=re.I)
    u_p = r'\b(flat|unit|u|suite|block)\s*(\d+[a-z]?)\s*number\s*(\d+[a-z]?)'
    address = re.sub(u_p, r'U\2/\3', address, flags=re.I)
    address = re.sub(r'\bnumber\s*(\d+[a-z]?)', r'\1', address, flags=re.I)
    subs = {r'\bcrescent\b':'Cres.', r'\bcresent\b':'Cres.', r'\bway\b':'Wy.', r'\broad\b':'Rd.', r'\bstreet\b':'St.'}
    for p, r in subs.items(): address = re.sub(p, r, address, flags=re.I)
    address = re.sub(r'\bsuburb\s+', '', address, flags=re.I)
    return re.sub(r'\s+', ' ', address).strip().title().replace('U', 'U')

def extract_viewing_date(body, anchor_date):
    match = re.search(r'\bviewing\s+(.*)', body, re.I)
    if not match: return None
    v_str = match.group(1).lower()
    
    # Check for direct date (e.g., 7/4/2026)
    d_m = re.search(r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?', v_str)
    if d_m:
        day, month = int(d_m.group(1)), int(d_m.group(2))
        year = int(d_m.group(3)) if d_m.group(3) else anchor_date.year
        if year < 100: year += 2000
        return datetime(year, month, day)
    
    # Check for relative dates
    days_map = {"mon":0, "tue":1, "wed":2, "thu":3, "fri":4, "sat":5, "sun":6}
    rel_m = re.search(r'(this|next)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)', v_str)
    if rel_m:
        kw, day = rel_m.groups()
        days_ahead = (days_map[day[:3]] - anchor_date.weekday()) % 7
        if days_ahead == 0: days_ahead = 7
        res = anchor_date + timedelta(days=days_ahead)
        if kw == 'next' and days_ahead <= 2: res += timedelta(days=7)
        return datetime.combine(res, datetime.min.time())
    return None

@app.route('/process', methods=['POST'])
def process():
    data = request.get_json(force=True)
    raw = data.get('text', '').replace('\xa0', ' ').strip()
    chunks = [c for c in raw.split('|') if c.strip()]
    
    # Initialize list outside the loop
    results = []
    
    for block in chunks:
        a_m = re.search(r'Anchor:\s*(\d{4}-\d{2}-\d{2})', block, re.I)
        s_m = re.search(r'Status:\s*(\d{4}-\d{2}-\d{2})', block, re.I)
        c_m = re.search(r'Content:\s*(.*)', block, re.I | re.S)
        
        if not a_m or not s_m or not c_m: continue
        
        anchor_dt = datetime.strptime(a_m.group(1), '%Y-%m-%d').date()
        status_dt = datetime.strptime(s_m.group(1), '%Y-%m-%d').date()
        body = c_m.group(1).strip()
        
        target_dt_obj = extract_viewing_date(body, anchor_dt)
        if target_dt_obj:
            target_dt = target_dt_obj.date()
            # Flag logic: Compare Target (Viewing) to Status (Today)
            day_flag = "LIVE" if target_dt >= status_dt else "PAST"
            
            pre_viewing = re.split(r'\bviewing\b', body, flags=re.I)[0]
            parts = [p.strip() for p in pre_viewing.split(',')]
            addr = ", ".join(parts[3:]) if len(parts) >= 4 else pre_viewing
            
            results.append({
                "viewing_date": target_dt.strftime('%d/%m/%Y'),
                "DayFlag": day_flag,
                "address": format_address(addr)
            })

    # Single return outside the loop ensures proper JSON array formatting
    return jsonify(results)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
