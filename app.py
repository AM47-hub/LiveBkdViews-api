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
    u_p = r'\b(flat|unit|u|suite|block|flap|flaps)\s*(\d+[a-z]?)\s*number\s*(\d+[a-z]?)'
    address = re.sub(u_p, r'U\2/\3', address, flags=re.I)
    address = re.sub(r'\bnumber\s*(\d+[a-z]?)', r'\1', address, flags=re.I)
    subs = {r'\bcrescent\b':'Cres.', r'\bcresent\b':'Cres.', r'\bway\b':'Wy.', r'\broad\b':'Rd.', r'\bstreet\b':'St.'}
    for p, r in subs.items(): address = re.sub(p, r, address, flags=re.I)
    address = re.sub(r'\bsuburb\s+', '', address, flags=re.I)
    return re.sub(r'\s+', ' ', address).strip().title().replace('U', 'U')

def calculate_date(text, anchor_str):
    try:
        days_map = {"mon":0, "tue":1, "wed":2, "thu":3, "fri":4, "sat":5, "sun":6}
        months_map = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
        anchor = datetime.strptime(anchor_str.strip(), '%Y-%m-%d')
        t_lower = text.lower()
        
        # Priority: dd/mm/yyyy
        digit_m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', t_lower)
        if digit_m:
            return datetime(int(digit_m.group(3)), int(digit_m.group(2)), int(digit_m.group(1)))

        # Ordinals: 7th of April
        abs_m = re.search(r'(\d+)(?:st|nd|rd|th)?\s*(?:of\s*)?([a-z]{3,})', t_lower)
        if abs_m:
            m_str = abs_m.group(2)[:3]
            if m_str in months_map: return datetime(anchor.year, months_map[m_str], int(abs_m.group(1)))

        # Relative: next Thursday
        rel_m = re.search(r'(this|next)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)', t_lower)
        if rel_m:
            kw, day = rel_m.groups()
            days_ahead = (days_map[day[:3]] - anchor.weekday()) % 7
            if days_ahead == 0: days_ahead = 7
            res = anchor + timedelta(days=days_ahead)
            if kw == 'next' and days_ahead <= 2: res += timedelta(days=7)
            return res
    except: return None
    return None

@app.route('/process', methods=['POST'])
def process():
    data = request.get_json(force=True)
    raw = data.get('text', '').replace('\xa0', ' ')
    
    # RESTORED: This is the split logic that returned 5 items
    chunks = raw.split('###NEWNOTE###')
    results = []
    
    for chunk in chunks:
        if '###ENDNOTE###' not in chunk: continue
        block = chunk.split('###ENDNOTE###')[0].strip()
        
        a_m = re.search(r'Anchor:\s*(\d{4}-\d{2}-\d{2})', block, re.I)
        s_m = re.search(r'Status:\s*(\d{4}-\d{2}-\d{2})', block, re.I)
        if not a_m or not s_m: continue
        
        anchor_val, status_val = a_m.group(1), s_m.group(1)
        body = re.sub(r'(Anchor|Status|Content):.*', '', block, flags=re.I).strip()
        
        target_date = calculate_date(body, anchor_val)
        if target_date:
            status_dt = datetime.strptime(status_val, '%Y-%m-%d')
            day_flag_val = "LIVE" if target_date.date() >= status_dt.date() else "PAST"
            addr = re.split(r'\bviewing\b', body, flags=re.I)[0]
            addr = re.sub(r'^booked,.*?,.*?,', '', addr, flags=re.I).strip()
            
            results.append({
                "viewing_date": target_date.strftime('%d/%m/%Y'),
                "DayFlag": day_flag_val,
                "address": format_address(addr)
            })

    return jsonify(results)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
