import os
import time
from abc import ABC, abstractmethod
import pdfplumber  # <--- เปลี่ยนจาก pypdf เป็นตัวนี้
from functools import wraps
import json
from typing import Any

# --- Decorator (เหมือนเดิม) ---
def time_logger(func: callable) -> callable:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"Function {func.__name__} took {end - start:.4f} seconds")
        return result
    return wrapper

# --- Base Class (เหมือนเดิม) ---
class DocumentReader(ABC):
    @abstractmethod
    def extract_text(self) -> bool:
        pass

# --- PDFProcessor (แก้ใหม่ใช้ pdfplumber) ---
class PDFProcessor(DocumentReader):
    def __init__(self, file_path) -> None:
        self.file_path = file_path
        self._content = []

    def __enter__(self) -> 'PDFProcessor':
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    @time_logger
    def extract_text(self) -> bool:
        try:
            full_text = ""
            # ใช้ pdfplumber เปิดไฟล์
            with pdfplumber.open(self.file_path) as pdf:
                # ถ้ามีรหัสผ่าน ให้ใส่ตรงนี้: pdfplumber.open(path, password='รหัส')
                
                for page in pdf.pages:
                    # extract_text ของตัวนี้เก่งกว่า pypdf มาก
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"
            
            # Cleaning Data: ตัดบรรทัดว่าง และตัดประโยคสั้นๆ (เช่น เลขหน้า) ทิ้ง
            self._content = []
            for line in full_text.split('\n'):
                line = line.strip()
                # กรอง: ต้องไม่ว่าง และยาวกว่า 5 ตัวอักษร (กันพวกเลขหน้าหลุดมา)
                if line and len(line) > 5:
                    self._content.append(line)
                    
            return True
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return False

    def get_lines(self) -> list[str]:
        return self._content

# --- ส่วนอื่นๆ (เหมือนเดิม) ---
def calculate_accuracy(original: str, typed: str) -> float:
    if not original: return 0
    matches = sum([1 for o, t in zip(original, typed) if o == t])
    return (matches / len(original)) * 100

class DataManager:
    # ... (โค้ด DataManager ส่วนเดิม ไม่ต้องแก้) ...
    def __init__(self, db_file: str ='db.json') -> None:
        self.db_file = db_file
        self.data = self._load_data()

    def _load_data(self) -> dict:
        if not os.path.exists(self.db_file):
            return {}
        try:
            with open(self.db_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def save_data(self) -> None:
        with open(self.db_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    def add_file(self, filename: str, total_lines: int) -> None:
        if filename not in self.data:
            self.data[filename] = {
                'current_index': 0,
                'total_lines': total_lines,
                'score': 0,
                'mistakes': []
            }
            self.save_data()

    def update_progress(
        self, 
        filename: str, 
        index: int, 
        score: float, 
        mistakes: list[str]
        ) -> None:
        if filename in self.data:
            self.data[filename]['current_index'] = index
            self.data[filename]['score'] = score
            self.data[filename]['mistakes'] = mistakes
            self.save_data()
            
    def get_file_info(self, filename: str) -> dict:
        return self.data.get(filename, {})
        
    def get_all_files(self) -> dict:
        return self.data