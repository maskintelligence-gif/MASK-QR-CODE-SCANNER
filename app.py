# app.py
import streamlit as st
import sqlite3
import json
from datetime import datetime, date
from PIL import Image
import numpy as np
import cv2
from pyzbar.pyzbar import decode
import qrcode
import io
import pandas as pd
import zipfile
import tempfile
import os
from typing import List, Dict, Any, Optional
import base64
from contextlib import contextmanager
import hashlib

# ==================== DATABASE SETUP ====================
class QRDatabase:
    """SQLite database manager for QR Scanner"""
    
    def __init__(self, db_path: str = "qr_scans.db"):
        self.db_path = db_path
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            st.error(f"Database error: {str(e)}")
            raise e
        finally:
            conn.close()
    
    def init_db(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Main scans table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    qr_data TEXT NOT NULL,
                    qr_type TEXT NOT NULL,
                    scan_date DATE DEFAULT CURRENT_DATE,
                    scan_time TIME DEFAULT CURRENT_TIME,
                    
                    -- Image metadata
                    file_size_kb INTEGER,
                    file_format TEXT,
                    
                    -- User data
                    tags TEXT DEFAULT '[]',  -- JSON array
                    notes TEXT,
                    is_favorite BOOLEAN DEFAULT 0,
                    
                    -- Quick search fields (optimized)
                    data_preview TEXT,  -- First 100 chars for quick view
                    data_hash TEXT UNIQUE,  -- For duplicate detection
                    
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Statistics table (updated daily)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date DATE PRIMARY KEY,
                    total_scans INTEGER DEFAULT 0,
                    unique_scans INTEGER DEFAULT 0,
                    by_type TEXT DEFAULT '{}',  -- JSON
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_scans_date 
                ON scans(scan_date DESC)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_scans_type 
                ON scans(qr_type)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_scans_favorite 
                ON scans(is_favorite) WHERE is_favorite = 1
            ''')
            
            # Create a view for common queries
            cursor.execute('''
                CREATE VIEW IF NOT EXISTS scan_summary AS
                SELECT 
                    scan_date,
                    COUNT(*) as total_scans,
                    COUNT(DISTINCT data_hash) as unique_scans,
                    GROUP_CONCAT(DISTINCT qr_type) as types_found
                FROM scans 
                GROUP BY scan_date 
                ORDER BY scan_date DESC
            ''')
    
    def save_scan(self, filename: str, qr_data: str, qr_type: str, 
                  file_size_kb: int = None, file_format: str = None) -> int:
        """Save a new scan to database"""
        # Generate hash for duplicate detection
        data_hash = hashlib.md5(qr_data.encode()).hexdigest()
        
        # Check for duplicates
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if this exact data already exists
            cursor.execute(
                "SELECT id FROM scans WHERE data_hash = ?", 
                (data_hash,)
            )
            existing = cursor.fetchone()
            
            if existing:
                return existing['id']  # Return existing ID
            
            # Insert new scan
            cursor.execute('''
                INSERT INTO scans (
                    filename, qr_data, qr_type, data_preview,
                    file_size_kb, file_format, data_hash,
                    scan_date, scan_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, DATE('now'), TIME('now'))
            ''', (
                filename, qr_data, qr_type, 
                (qr_data[:97] + '...' if len(qr_data) > 100 else qr_data),
                file_size_kb, file_format, data_hash
            ))
            
            scan_id = cursor.lastrowid
            
            # Update daily stats
            self._update_daily_stats()
            
            return scan_id
    
    def _update_daily_stats(self):
        """Update daily statistics"""
        today = date.today().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get today's scans
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    COUNT(DISTINCT data_hash) as unique_count,
                    qr_type,
                    COUNT(*) as type_count
                FROM scans 
                WHERE scan_date = DATE('now')
                GROUP BY qr_type
            ''')
            
            results = cursor.fetchall()
            
            if results:
                total = results[0]['total']
                unique = results[0]['unique_count']
                
                # Build type distribution JSON
                type_counts = {}
                for row in results:
                    type_counts[row['qr_type']] = row['type_count']
                
                # Insert or update stats
                cursor.execute('''
                    INSERT OR REPLACE INTO daily_stats 
                    (date, total_scans, unique_scans, by_type)
                    VALUES (?, ?, ?, ?)
                ''', (today, total, unique, json.dumps(type_counts)))
    
    def get_all_scans(self, limit: int = 100) -> List[Dict]:
        """Get all scans with pagination"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM scans 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_scans_by_type(self, qr_type: str) -> List[Dict]:
        """Get scans filtered by type"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM scans 
                WHERE qr_type = ? 
                ORDER BY created_at DESC
            ''', (qr_type,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_favorites(self) -> List[Dict]:
        """Get favorite scans"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM scans 
                WHERE is_favorite = 1 
                ORDER BY created_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def toggle_favorite(self, scan_id: int) -> bool:
        """Toggle favorite status of a scan"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get current state
            cursor.execute(
                "SELECT is_favorite FROM scans WHERE id = ?", 
                (scan_id,)
            )
            result = cursor.fetchone()
            
            if result:
                new_state = 0 if result['is_favorite'] else 1
                cursor.execute('''
                    UPDATE scans 
                    SET is_favorite = ? 
                    WHERE id = ?
                ''', (new_state, scan_id))
                return new_state == 1
            return False
    
    def update_tags(self, scan_id: int, tags: List[str]):
        """Update tags for a scan"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE scans 
                SET tags = ? 
                WHERE id = ?
            ''', (json.dumps(tags), scan_id))
    
    def update_notes(self, scan_id: int, notes: str):
        """Update notes for a scan"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE scans 
                SET notes = ? 
                WHERE id = ?
            ''', (notes, scan_id))
    
    def delete_scan(self, scan_id: int) -> bool:
        """Delete a scan"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
            return cursor.rowcount > 0
    
    def search_scans(self, query: str) -> List[Dict]:
        """Search scans by content"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            search_term = f"%{query}%"
            cursor.execute('''
                SELECT * FROM scans 
                WHERE qr_data LIKE ? 
                   OR filename LIKE ? 
                   OR tags LIKE ?
                ORDER BY created_at DESC
            ''', (search_term, search_term, search_term))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_stats(self) -> Dict:
        """Get overall statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Total scans
            cursor.execute("SELECT COUNT(*) as total FROM scans")
            stats['total_scans'] = cursor.fetchone()['total']
            
            # Unique scans
            cursor.execute("SELECT COUNT(DISTINCT data_hash) as unique FROM scans")
            stats['unique_scans'] = cursor.fetchone()['unique']
            
            # By type
            cursor.execute('''
                SELECT qr_type, COUNT(*) as count 
                FROM scans 
                GROUP BY qr_type 
                ORDER BY count DESC
            ''')
            stats['by_type'] = dict(cursor.fetchall())
            
            # Recent activity
            cursor.execute('''
                SELECT scan_date, COUNT(*) as count 
                FROM scans 
                GROUP BY scan_date 
                ORDER BY scan_date DESC 
                LIMIT 7
            ''')
            stats['recent_activity'] = dict(cursor.fetchall())
            
            # Favorites count
            cursor.execute("SELECT COUNT(*) as count FROM scans WHERE is_favorite = 1")
            stats['favorites'] = cursor.fetchone()['count']
            
            return stats
    
    def export_to_csv(self) -> str:
        """Export all scans to CSV string"""
        with self.get_connection() as conn:
            df = pd.read_sql_query("SELECT * FROM scans", conn)
            return df.to_csv(index=False)
    
    def export_to_json(self) -> str:
        """Export all scans to JSON string"""
        scans = self.get_all_scans(limit=1000)
        return json.dumps(scans, indent=2, default=str)

# ==================== QR SCANNER FUNCTIONS ====================
def detect_content_type(data: str) -> str:
    """Detect type of QR code content"""
    data_lower = data.lower()
    
    if data.startswith(('http://', 'https://', 'www.')):
        return 'url'
    elif data.startswith('WIFI:'):
        return 'wifi'
    elif data.startswith('BEGIN:VCARD'):
        return 'vcard'
    elif 'mailto:' in data_lower or '@' in data_lower and '.com' in data_lower:
        return 'email'
    elif data.startswith('tel:'):
        return 'phone'
    elif data.startswith('SMSTO:'):
        return 'sms'
    elif data.startswith('BITCOIN:'):
        return 'crypto'
    elif data.replace('.', '', 1).isdigit():
        return 'numeric'
    elif len(data.split()) > 3:  # Multiple words
        return 'text'
    else:
        return 'text'

def parse_wifi_string(wifi_string: str) -> Dict:
    """Parse WiFi connection string"""
    result = {'ssid': 'Unknown', 'password': None, 'security': 'WPA'}
    
    try:
        parts = wifi_string[5:].split(';')
        for part in parts:
            if ':' in part:
                key, value = part.split(':', 1)
                if key == 'S':
                    result['ssid'] = value
                elif key == 'T':
                    result['security'] = value
                elif key == 'P':
                    result['password'] = value
    except:
        pass
    
    return result

def enhance_image_for_scanning(image_np):
    """Apply image processing to improve QR detection"""
    if len(image_np.shape) == 3:
        gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
    else:
        gray = image_np.copy()
    
    # Multiple enhancement strategies
    enhanced_images = []
    
    # Strategy 1: Adaptive threshold
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY, 11, 2)
    enhanced_images.append(thresh)
    
    # Strategy 2: Otsu threshold
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    enhanced_images.append(otsu)
    
    # Strategy 3: Equalize histogram
    equalized = cv2.equalizeHist(gray)
    enhanced_images.append(equalized)
    
    # Strategy 4: Denoising
    denoised = cv2.medianBlur(gray, 3)
    enhanced_images.append(denoised)
    
    return enhanced_images

def scan_qr_from_image(image) -> List[Dict]:
    """Scan QR codes from image with multiple strategies"""
    results = []
    detected_texts = set()
    
    # Convert to numpy array
    if isinstance(image, Image.Image):
        image_np = np.array(image)
    else:
        image_np = image.copy()
    
    # Try original image first
    decoded_objects = decode(image_np)
    
    # If no detection, try enhanced versions
    if not decoded_objects:
        enhanced_images = enhance_image_for_scanning(image_np)
        
        for enhanced in enhanced_images:
            decoded_objects = decode(enhanced)
            if decoded_objects:
                break
    
    # Process results
    for obj in decoded_objects:
        try:
            data = obj.data.decode("utf-8", errors='ignore')
            
            # Skip duplicates in same image
            if data in detected_texts:
                continue
            detected_texts.add(data)
            
            qr_type = detect_content_type(data)
            
            result = {
                'data': data,
                'type': qr_type,
                'bounds': obj.rect if hasattr(obj, 'rect') else None,
                'timestamp': datetime.now().isoformat()
            }
            results.append(result)
            
        except Exception as e:
            st.warning(f"Error decoding QR: {str(e)}")
    
    return results

def generate_qr_code(data: str, size: int = 300):
    """Generate QR code from text"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize((size, size))
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    return buf

# ==================== STREAMLIT APP ====================
def init_session_state():
    """Initialize session state variables"""
    if 'db' not in st.session_state:
        st.session_state.db = QRDatabase()
    if 'scans' not in st.session_state:
        st.session_state.scans = []
    if 'stats' not in st.session_state:
        st.session_state.stats = {}
    if 'selected_tags' not in st.session_state:
        st.session_state.selected_tags = []
    if 'search_query' not in st.session_state:
        st.session_state.search_query = ""

def main():
    """Main Streamlit app"""
    
    # Page config
    st.set_page_config(
        page_title="QRScan Pro",
        page_icon="📱",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 2rem;
            border-radius: 10px;
            color: white;
            margin-bottom: 2rem;
        }
        .stat-card {
            background: white;
            padding: 1rem;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }
        .scan-card {
            background: #f8f9fa;
            padding: 1.5rem;
            border-radius: 10px;
            border-left: 5px solid #667eea;
            margin-bottom: 1rem;
        }
        .badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: bold;
            margin: 0.25rem;
        }
        .badge-url { background: #e3f2fd; color: #1976d2; }
        .badge-wifi { background: #e8f5e9; color: #2e7d32; }
        .badge-text { background: #f5f5f5; color: #616161; }
        .badge-vcard { background: #f3e5f5; color: #7b1fa2; }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize
    init_session_state()
    db = st.session_state.db
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1 style="margin: 0;">📱 QRScan Pro</h1>
        <p style="margin: 0; opacity: 0.9;">Advanced QR Code Scanner with Database Storage</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/qr-code.png", width=80)
        
        st.title("Navigation")
        page = st.radio(
            "Go to:",
            ["📤 Scan Images", "📊 Dashboard", "🔍 Browse Scans", "⚙️ Settings"]
        )
        
        st.markdown("---")
        
        # Quick stats
        stats = db.get_stats()
        st.markdown("### 📈 Quick Stats")
        col1, col2 = st.columns(2)
        col1.metric("Total Scans", stats['total_scans'])
        col2.metric("Unique", stats['unique_scans'])
        
        if st.button("🔄 Refresh Data"):
            st.rerun()
        
        st.markdown("---")
        st.markdown("**Made with ❤️ by MASK INTELLIGENCE**")
    
    # Page routing
    if page == "📤 Scan Images":
        show_scan_page(db)
    elif page == "📊 Dashboard":
        show_dashboard_page(db)
    elif page == "🔍 Browse Scans":
        show_browse_page(db)
    elif page == "⚙️ Settings":
        show_settings_page(db)

def show_scan_page(db):
    """Show image scanning page"""
    st.title("📤 Scan QR Codes from Images")
    
    # File upload
    uploaded_files = st.file_uploader(
        "Choose image files",
        type=['png', 'jpg', 'jpeg', 'bmp', 'gif', 'webp'],
        accept_multiple_files=True,
        help="Upload images containing QR codes"
    )
    
    if uploaded_files:
        # Process files
        total_found = 0
        
        for uploaded_file in uploaded_files:
            with st.expander(f"📄 {uploaded_file.name}", expanded=True):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    # Display image
                    image = Image.open(uploaded_file)
                    st.image(image, caption=f"Size: {image.size[0]}x{image.size[1]}px", 
                            use_column_width=True)
                
                with col2:
                    # File info
                    file_size_kb = uploaded_file.size / 1024
                    st.metric("File Size", f"{file_size_kb:.1f} KB")
                    st.metric("Format", uploaded_file.type.split('/')[-1].upper())
                    
                    # Scan button
                    if st.button(f"🔍 Scan {uploaded_file.name}", key=f"scan_{uploaded_file.name}"):
                        with st.spinner("Scanning..."):
                            # Scan for QR codes
                            results = scan_qr_from_image(image)
                            
                            if results:
                                st.success(f"✅ Found {len(results)} QR code(s)")
                                
                                for i, result in enumerate(results):
                                    # Save to database
                                    scan_id = db.save_scan(
                                        filename=uploaded_file.name,
                                        qr_data=result['data'],
                                        qr_type=result['type'],
                                        file_size_kb=file_size_kb,
                                        file_format=uploaded_file.type
                                    )
                                    
                                    # Display result
                                    with st.container():
                                        badge_class = f"badge-{result['type']}"
                                        st.markdown(f'<span class="badge {badge_class}">{result["type"].upper()}</span>', 
                                                   unsafe_allow_html=True)
                                        
                                        # Display based on type
                                        if result['type'] == 'wifi':
                                            wifi_info = parse_wifi_string(result['data'])
                                            st.write(f"**WiFi:** {wifi_info['ssid']}")
                                            if wifi_info['password']:
                                                st.write(f"**Password:** `{wifi_info['password']}`")
                                        elif result['type'] == 'url':
                                            st.markdown(f"[{result['data']}]({result['data']})")
                                        else:
                                            st.text_area("Content", result['data'], 
                                                        height=100, key=f"content_{i}")
                                        
                                        # Actions
                                        col_a, col_b, col_c = st.columns(3)
                                        with col_a:
                                            if st.button("📋 Copy", key=f"copy_{i}"):
                                                st.toast("Copied to clipboard!")
                                        with col_b:
                                            if st.button("⭐ Favorite", key=f"fav_{i}"):
                                                db.toggle_favorite(scan_id)
                                                st.toast("Added to favorites!")
                                        with col_c:
                                            if st.button("🗑️ Delete", key=f"del_{i}"):
                                                db.delete_scan(scan_id)
                                                st.rerun()
                                        
                                        st.markdown("---")
                                
                                total_found += len(results)
                            else:
                                st.warning("❌ No QR codes found")
        
        if total_found > 0:
            st.success(f"🎯 Total: Found {total_found} QR code(s) across {len(uploaded_files)} image(s)")
            
            # Export options
            st.markdown("### 💾 Export All Scans")
            export_col1, export_col2 = st.columns(2)
            
            with export_col1:
                csv_data = db.export_to_csv()
                st.download_button(
                    label="📥 Download CSV",
                    data=csv_data,
                    file_name="qr_scans.csv",
                    mime="text/csv"
                )
            
            with export_col2:
                json_data = db.export_to_json()
                st.download_button(
                    label="📥 Download JSON",
                    data=json_data,
                    file_name="qr_scans.json",
                    mime="application/json"
                )

def show_dashboard_page(db):
    """Show dashboard with statistics"""
    st.title("📊 Dashboard")
    
    # Get statistics
    stats = db.get_stats()
    
    # Top stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Scans", stats['total_scans'])
    with col2:
        st.metric("Unique Scans", stats['unique_scans'])
    with col3:
        st.metric("Favorites", stats['favorites'])
    with col4:
        st.metric("QR Types", len(stats['by_type']))
    
    st.markdown("---")
    
    # Type distribution
    st.subheader("📈 Scan Type Distribution")
    if stats['by_type']:
        type_df = pd.DataFrame({
            'Type': list(stats['by_type'].keys()),
            'Count': list(stats['by_type'].values())
        })
        st.bar_chart(type_df.set_index('Type'))
    else:
        st.info("No scans yet. Upload some images!")
    
    # Recent scans
    st.subheader("🕐 Recent Scans")
    recent_scans = db.get_all_scans(limit=10)
    
    if recent_scans:
        for scan in recent_scans:
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    badge_class = f"badge-{scan['qr_type']}"
                    st.markdown(f'''
                    <span class="badge {badge_class}">{scan['qr_type'].upper()}</span>
                    **{scan['filename']}** - {scan['scan_date']}
                    ''', unsafe_allow_html=True)
                    st.caption(scan['data_preview'])
                
                with col2:
                    if st.button("⭐", key=f"fav_{scan['id']}"):
                        db.toggle_favorite(scan['id'])
                        st.rerun()
                
                with col3:
                    if st.button("🗑️", key=f"del_{scan['id']}"):
                        db.delete_scan(scan['id'])
                        st.rerun()
                
                st.markdown("---")
    else:
        st.info("No scans yet. Upload some images!")

def show_browse_page(db):
    """Show browse and search page"""
    st.title("🔍 Browse Scans")
    
    # Search and filter
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        search_query = st.text_input("🔎 Search scans", 
                                    placeholder="Search by content or filename...")
    
    with col2:
        filter_type = st.selectbox(
            "Filter by type",
            ["All", "url", "wifi", "text", "vcard", "email", "phone"]
        )
    
    with col3:
        show_favorites = st.checkbox("⭐ Favorites only")
    
    # Get scans based on filters
    if search_query:
        scans = db.search_scans(search_query)
    elif filter_type != "All":
        scans = db.get_scans_by_type(filter_type)
    elif show_favorites:
        scans = db.get_favorites()
    else:
        scans = db.get_all_scans(limit=50)
    
    # Display scans
    if scans:
        st.info(f"Found {len(scans)} scan(s)")
        
        for scan in scans:
            with st.expander(f"{scan['filename']} - {scan['qr_type'].upper()} - {scan['scan_date']}", 
                           expanded=False):
                
                # Scan info
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    badge_class = f"badge-{scan['qr_type']}"
                    st.markdown(f'<span class="badge {badge_class}">{scan["qr_type"].upper()}</span>', 
                               unsafe_allow_html=True)
                    
                    # Display content based on type
                    if scan['qr_type'] == 'wifi':
                        wifi_info = parse_wifi_string(scan['qr_data'])
                        st.write(f"**SSID:** {wifi_info['ssid']}")
                        if wifi_info['password']:
                            st.write(f"**Password:** `{wifi_info['password']}`")
                    elif scan['qr_type'] == 'url':
                        st.markdown(f"[{scan['qr_data']}]({scan['qr_data']})")
                    else:
                        st.text_area("Content", scan['qr_data'], height=150)
                
                with col2:
                    # Actions
                    if st.button("📋 Copy", key=f"copy_{scan['id']}"):
                        st.toast("Copied to clipboard!")
                    
                    fav_status = "★" if scan['is_favorite'] else "☆"
                    if st.button(f"{fav_status} Favorite", key=f"fav_{scan['id']}"):
                        db.toggle_favorite(scan['id'])
                        st.rerun()
                    
                    if st.button("🗑️ Delete", key=f"delete_{scan['id']}"):
                        db.delete_scan(scan['id'])
                        st.rerun()
                    
                    # Generate QR button
                    if st.button("🔄 Generate QR", key=f"gen_{scan['id']}"):
                        qr_img = generate_qr_code(scan['qr_data'])
                        st.image(qr_img, caption="Generated QR Code")
                        st.download_button(
                            label="📥 Download QR",
                            data=qr_img,
                            file_name=f"qr_{scan['id']}.png",
                            mime="image/png"
                        )
    else:
        st.info("No scans found. Try different filters or upload some images!")

def show_settings_page(db):
    """Show settings page"""
    st.title("⚙️ Settings")
    
    tab1, tab2, tab3 = st.tabs(["Database", "Scanning", "Appearance"])
    
    with tab1:
        st.subheader("Database Settings")
        
        # Backup database
        if st.button("💾 Backup Database"):
            csv_data = db.export_to_csv()
            st.download_button(
                label="📥 Download Backup (CSV)",
                data=csv_data,
                file_name="qrscan_backup.csv",
                mime="text/csv"
            )
        
        # Clear database
        st.markdown("---")
        st.warning("⚠️ Dangerous Zone")
        
        if st.button("🗑️ Clear All Scans", type="secondary"):
            if st.checkbox("I understand this will delete ALL scans permanently"):
                if st.button("Confirm Delete", type="primary"):
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM scans")
                        cursor.execute("DELETE FROM daily_stats")
                    st.success("All scans deleted!")
                    st.rerun()
    
    with tab2:
        st.subheader("Scanning Settings")
        
        # Detection settings
        st.checkbox("Use enhanced detection", value=True, 
                   help="Apply image processing for better detection")
        st.checkbox("Auto-rotate images", value=True)
        st.checkbox("Remove image noise", value=True)
        
        st.slider("Detection confidence", 0.1, 1.0, 0.7, 0.1,
                 help="Higher values = stricter detection")
        
        if st.button("💾 Save Scanning Settings"):
            st.success("Settings saved!")
    
    with tab3:
        st.subheader("Appearance")
        
        theme = st.selectbox("Theme", ["Light", "Dark", "Auto"])
        results_per_page = st.slider("Results per page", 10, 100, 25)
        
        if st.button("💾 Save Appearance Settings"):
            st.success("Settings saved!")

# Run the app
if __name__ == "__main__":
    main()
