from flask import Flask, request, jsonify
import re
from datetime import datetime, timedelta
import os

app = Flask(__name__)

def calculate_date(text, anchor_str, status_str):
    days_map = {"mon":0, "tue":1, "wed":2, "thu":3, "fri":4, "sat":5, "sun":6}
    try:
        anchor = datetime.strptime(anchor_str, '%Y-%m-%d')
        status = datetime.strptime(status_str, '%Y-%m-%d')
    except:
        return None
    
    # Matches: Monday, Tuesday, etc. (and optional "this" or "next")
    match = re.search(r'(this|next|last)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', text.lower())
    if not match: return None
    
    keyword = match.group(1)
    target_day = match.group(2)[:3]
    target_idx = days_map[target_day]
    anchor_idx = anchor.weekday()

    days_ahead = (target_idx - anchor_idx) % 7
    # If it's today, we usually mean next week in these logs
    if days_ahead == 0: days_ahead = 7
    
    viewing_date = anchor + timedelta(days=days_ahead)
    
    # Logic for "next" usually implies jumping a week if the day is very close
    if keyword == "next" and days_ahead <= 3:
        viewing_date += timedelta(days=7)

    return viewing_date

@app.route('/process', methods=['POST'])
def process():
    data = request.json
    raw_payload = data.get('text', '')
    
    # 1. Split the bulk text into individual note chunks
    chunks = [c.strip() for c in raw_payload.split('###ENDNOTE###') if c.strip()]
    results = []

    for chunk in chunks:
        # Clean the chunk and split into lines
        lines = chunk.replace('###NEWNOTE###', '').strip().split('\n')
        
        note_text = ""
        anchor_val = ""
        status_val = ""
        
        # 2. Extract internal variables from the text block
        for line in lines:
            if line.startswith('Anchor:'):
                anchor_val = line.replace('Anchor:', '').strip()
            elif line.startswith('Status:'):
                status_val = line.replace('Status:', '').strip()
            elif line.startswith('Content:'):
                note_text = line.replace('Content:', '').strip()
            else:
                # Catch multi-line address/description
                note_text += " " + line.strip()

        # 3. Calculate date for this specific note
        res_date = calculate_date(note_text, anchor_val, status_val)
        
        if not res_date:
            continue # Skip notes where no date is found

        # 4. Determine Status (LIVE/DELETE)
        status_dt = datetime.strptime(status_val, '%Y-%m-%d')
        current_status = "LIVE"
        if res_date.date() < status_dt.date():
            current_status = "DELETE"

        # 5. Extract Address (very basic extraction)
        # Assuming address follows the 'suburb' keyword or similar
        address = note_text.split("viewing")[0].strip()

        results.append({
            "viewing_date": res_date.strftime('%d/%m/%Y'),
            "status": current_status,
            "address": address
        })

    # 6. Return the list of dictionaries back to Shortcuts
    return jsonify(results)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
