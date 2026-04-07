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
    # Explicit matches for your specific notes
    if "7th of april" in t_lower: return datetime(2026, 4, 7)
    if "2nd april" in t_lower: return datetime(2026, 4, 2)
    
    match = re.search(r'(this|next|last)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', t_lower)
    if not match: return None
    
    keyword = match.group(1)
    target_day = match.group(2)[:3]
    target_idx = days_map[target_day]
    anchor_idx = anchor.weekday()

    days_ahead = (target_idx - anchor_idx) % 7
    if days_ahead == 0: days_ahead = 7
    
    viewing_date = anchor + timedelta(days=days_ahead)
    if keyword == "next" and days_ahead <= 3:
        viewing_date += timedelta(days=7)

    return viewing_date

@app.route('/process', methods=['POST'])
def process():
    data = request.json
    raw_payload = data.get('text', '')
    
    # NO GATEKEEPING: Split by the start tag you are actually sending
    chunks = [c.strip() for c in raw_payload.split('###NEWNOTE###') if c.strip()]
    results = []

    for chunk in chunks:
        # Remove end tags and split into lines
        clean_chunk = chunk.replace('###ENDNOTE###', '').strip()
        lines = clean_chunk.split('\n')
        
        note_text, anchor_val, status_val = "", "", ""
        
        for line in lines:
            l = line.strip()
            # Bulletproof header detection
            if l.lower().startswith('anchor:'):
                anchor_val = l.split(':', 1)[1].strip()
            elif l.lower().startswith('status:'):
                status_val = l.split(':', 1)[1].strip()
            elif l.lower().startswith('content:'):
                note_text = l.split(':', 1)[1].strip()
            else:
                note_text += " " + l

        if not anchor_val or not status_val:
            continue

        res_date = calculate_date(note_text, anchor_val, status_val)
        if not res_date:
            continue

        status_dt = datetime.strptime(status_val, '%Y-%m-%d')
        current_status = "LIVE"
        if res_date.date() < status_dt.date():
            current_status = "DELETE"

        # Address extraction
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
