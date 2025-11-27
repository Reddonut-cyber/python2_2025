from flask import Flask, render_template, request, redirect, url_for, session, flash
from backend import PDFProcessor, calculate_accuracy, DataManager #เอามาจาก backend.py
from collections import Counter # นับคำผิด
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey' #เข้ารหัส session
UPLOAD_FOLDER = 'uploads' #โฟลเดอร์เก็บไฟล์ที่อัพโหลด
os.makedirs(UPLOAD_FOLDER, exist_ok=True)# สร้างโฟลเดอร์ถ้ายังไม่มี

db = DataManager()#เรียก db.json มาใช้

@app.route('/', methods=['GET', 'POST'])
def index():
    # อัพโหลดไฟล์
    if request.method == 'POST':
        # ตรวจสอบว่ามีไฟล์ถูกส่งมาหรือไม่
        if 'file' not in request.files: return redirect(request.url)
        file = request.files['file']
        if file.filename == '': return redirect(request.url)

        if file:
            # Save ไฟล์ลงเครื่อง
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)
            
            # อ่าน PDF
            with PDFProcessor(filepath) as processor:
                if processor.extract_text():
                    lines = processor.get_lines()
                    # ถ้าอ่านไฟล์ได้ ให้บันทึกลง DB
                    if lines:
                        db.add_file(file.filename, len(lines))
                    else:
                        print("Warning: PDF อ่านไม่ออก หรือไม่มีข้อความ")
            
            return redirect(url_for('index'))

    files = db.get_all_files()# ดึงรายชื่อไฟล์ทั้งหมดจาก DB
    return render_template('index.html', files=files)
@app.route('/select/<path:filename>')
def select_file(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    # ล้าง Session เก่า
    session.pop('lines', None)
    session.pop('current_index', None)
    session.pop('mistakes', None)
    
    if not os.path.exists(filepath):
        return "Error: File not found"

    with PDFProcessor(filepath) as processor:
        if processor.extract_text():
            lines = processor.get_lines()
            
            # --- จุดที่เพิ่มใหม่: เช็คว่ามีข้อความไหม? ---
            if not lines or len(lines) == 0:
                # ถ้าไม่มีข้อความเลย ให้เด้งกลับหน้าแรกพร้อมแจ้งเตือน
                flash(f"Error: The file '{filename}' does not contain readable text (it might be a scanned image file).", "error")
                return redirect(url_for('index'))
                
            session['lines'] = lines
            session['current_filename'] = filename
        else:
            flash("Error reading file content", "error")
            return redirect(url_for('index'))

    # โหลด Progress
    info = db.get_file_info(filename)
    session['current_index'] = info.get('current_index', 0)
    session['total_score'] = info.get('score', 0) * session['current_index']
    session['mistakes'] = info.get('mistakes', [])

    return redirect(url_for('practice'))

@app.route('/practice', methods=['GET', 'POST'])
def practice():
    # ดึงข้อมูลจาก Session
    lines = session.get('lines', [])
    current_index = session.get('current_index', 0)
    filename = session.get('current_filename')
    
    # พิมพ์ครบยัง
    if not lines or current_index >= len(lines):
        return redirect(url_for('summary'))

    target_text = lines[current_index]
    
    if request.method == 'POST':
        action = request.form.get('action') # next or stop
        user_input = request.form.get('user_input', '')

        # คำนวณความแม่นยำ
        accuracy = calculate_accuracy(target_text, user_input)
        
        # บันทึกคำผิด (เก็บละเอียด)
        mistakes = session.get('mistakes', [])
        for i, (char_target, char_input) in enumerate(zip(target_text, user_input)):
            if char_target != char_input:
                # เก็บเป็น Dict เพื่อไปนับทีหลัง
                mistakes.append(f"{char_target}|{char_input}") 
        session['mistakes'] = mistakes
        
        session['total_score'] = session.get('total_score', 0) + accuracy
        
        # คำนวณคะแนนเฉลี่ย
        avg_score = 0
        lines_typed = current_index + 1
        if lines_typed > 0:
             avg_score = session['total_score'] / lines_typed

        if action == 'stop':
            db.update_progress(filename, current_index, avg_score, mistakes)
            return redirect(url_for('summary'))
        else:
            session['current_index'] += 1
            db.update_progress(filename, session['current_index'], avg_score, mistakes)
            return redirect(url_for('practice'))

    avg_score = 0
    if current_index > 0:
        avg_score = session.get('total_score', 0) / current_index

    return render_template('practice.html', 
                           text=target_text, 
                           progress=f"{current_index + 1}/{len(lines)}",
                           current_score=f"{avg_score:.2f}")

@app.route('/summary')
def summary():
    lines = session.get('lines', [])
    current_index = session.get('current_index', 0)
    total_score = session.get('total_score', 0)
    raw_mistakes = session.get('mistakes', [])
    
    final_score = 0
    if current_index > 0:
        final_score = total_score / current_index
    
    # --- ส่วนที่แก้ไข (Cleaning Data) ---
    # เราจะแปลงข้อมูลให้เป็น String ให้หมด ไม่ว่าของเก่าจะเป็น Dict หรือไม่
    clean_mistakes = []
    for m in raw_mistakes:
        if isinstance(m, dict):
            # ถ้าเป็นของเก่า (Dict) ให้แปลงเป็น String แบบใหม่ "a|b"
            clean_mistakes.append(f"{m.get('expected')}|{m.get('typed')}")
        elif isinstance(m, str):
            # ถ้าเป็นของใหม่ (String) อยู่แล้ว ก็ใช้ได้เลย
            clean_mistakes.append(m)
            
    # ใช้ clean_mistakes แทน raw_mistakes
    mistake_counts = Counter(clean_mistakes)
    
    # จัดรูปแบบข้อมูลเพื่อส่งไปแสดงผล
    grouped_mistakes = []
    for key, count in mistake_counts.most_common(10):
        if '|' in key: # ป้องกัน Error กรณีข้อมูลเพี้ยน
            expected, typed = key.split('|', 1)
            grouped_mistakes.append({
                'expected': expected,
                'typed': typed,
                'count': count
            })

    return render_template('summary.html', 
                           score=f"{final_score:.2f}", 
                           mistakes=grouped_mistakes,
                           total_lines=len(lines),
                           typed_lines=current_index)

if __name__ == '__main__':
    app.run(debug=True)