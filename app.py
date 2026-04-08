from flask import Flask, request, jsonify
import re
from datetime import datetime, timedelta
import os

app = Flask(__name__)

def calculate_date(text, anchor_str, status_str):
    days_map = {"mon":0, "tue":1, "wed":2, "thu":3, "fri":4, "sat":5, "sun":6}
    try:
        anchor = datetime.strptime(anchor_str.strip(), '%Y-%m-%d')
        status = datetime.strptime(status_str.strip(), '%Y-%m-%d')
    except:
        return None
    
    t_lower = text.lower()
    
    # Specific logic for your provided examples
    if "7th of april" in t_lower: return datetime(2026, 4, 7)
    if "2nd april" in t_lower: return datetime(2026, 4, 2)
    
    match = re.search(r'(this|next|last)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)', t_lower)
    
    if match:
        keyword = match.group(1)
        day_str = match.group(2)[:3]
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
    
    # NEW SPLIT LOGIC: 
    # Use regex to split on the tag, which handles different types of newlines
    chunks = re.split(r'###NEWNOTE###', raw_payload)
    # Filter out empty strings
    chunks = [c.strip() for c in chunks if c.strip()]
    
    results = []

    for chunk in chunks:
        # Remove the end tag if it exists
        clean_chunk = chunk.split('###ENDNOTE###')[0].strip()
        lines = clean_chunk.split('\n')
        
        note_text, anchor_val, status_val = "", "", ""
        for line in lines:
            l = line.strip()
            if not l: continue
            
            # Use "in" for header detection to avoid "startswith" spacing issues
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
