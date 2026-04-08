from flask import Flask, request, jsonify
import re
from datetime import datetime, timedelta
import os

app = Flask(__name__)

def calculate_date(text, anchor_str, status_str):
    days_map = {"mon":0, "tue":1, "wed":2, "thu":3, "fri":4, "sat":5, "sun":6}
    months_map = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
    
    try:
        anchor = datetime.strptime(anchor_str.strip(), '%Y-%m-%d')
    except:
        return None
    
    t_lower = text.lower()
    
    # CHANGE: Generalized regex to catch "7th of April", "2nd April", or "Friday"
    # This avoids hardcoding specific dates while capturing the patterns in your text.
    date_match = re.search(r'(\d+)(?:st|nd|rd|th)?\s*(?:of\s*)?([a-z]+)', t_lower)
    day_match = re.search(r'(this|next|last)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)', t_lower)
    
    # CHANGE: Logic to handle "7th of April" style dates dynamically
    if date_match:
        day_num = int(date_match.group(1))
        month_str = date_match.group(2)[:3]
        if month_str in months_map:
            # Assumes the year of the anchor date
            return datetime(anchor.year, months_map[month_str], day_num)

    # CHANGE: Standard day-of-week logic (remains as base logic)
    if day_match:
        keyword = day_match.group(1)
        day_str = day_match.group(2)[:3]
        target_idx = days_map[day_str]
        anchor_idx = anchor.weekday()
        days_ahead = (target_idx - anchor_idx) % 7
        if days_ahead == 0: days_ahead = 7
        viewing_date = anchor + timedelta(days=days_ahead)
        if keyword == "next" and days_ahead <= 3:
            viewing_date += timedelta(days=7)
        return viewing_date
        
    return None

@app.route('/process', methods=['POST'])
def process():
    data = request.get_json(force=True)
    raw_payload = data.get('text', '')
    
    # # CHANGE: Standard split logic (No regex overhead)
    chunks = raw_payload.split('###NEWNOTE###')
    
    results = []
    for chunk in chunks:
        if not chunk.strip(): 
            continue
            
        content_block = chunk.split('###ENDNOTE###')[0].strip()
        lines = content_block.split('\n')
        
        note_text, anchor_val, status_val = "", "", ""
        for line in lines:
            l = line.strip()
            # # CHANGE: 'in' operator to ensure leading spaces don't break header detection
            if 'anchor:' in l.lower(): anchor_val = l.split(':', 1)[1].strip()
            elif 'status:' in l.lower(): status_val = l.split(':', 1)[1].strip()
            elif 'content:' in l.lower(): note_text = l.split(':', 1)[1].strip()
            else: note_text += " " + l

        if not anchor_val or not status_val:
            continue

        res_date = calculate_date(note_text, anchor_val, status_val)
        if not res_date:
            continue

        status_dt = datetime.strptime(status_val, '%Y-%m-%d')
        current_status = "LIVE"
        if res_date.date() < status_dt.date():
            current_status = "DELETE"

        address = note_text.split("viewing")[0].strip()
        # # CHANGE: Strip metadata prefix from address
        address = re.sub(r'^booked,.*?,.*?,', '', address, flags=re.IGNORECASE).strip()

        results.append({
            "viewing_date": res_date.strftime('%d/%m/%Y'),
            "status": current_status,
            "address": address
        })

    return jsonify(results)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
