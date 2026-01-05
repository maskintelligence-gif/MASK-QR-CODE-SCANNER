#MASK QR CODE SCANNER

https://img.shields.io/badge/QRScan-Pro-blue?style=for-the-badge&logo=qrcode&logoColor=white
https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white
https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white
https://img.shields.io/badge/License-MIT-green?style=for-the-badge

Mask Qr Code Scanner is a professional-grade QR code scanning application, SUPPORTS IMAGE UPLOADS ONLY built with Streamlit, featuring advanced image processing, database storage, and comprehensive analytics—all in a single file!

✨ Features

🎯 Core Scanning

· Advanced Image Processing - Multiple scanning strategies for difficult QR codes
· Batch Processing - Scan multiple images simultaneously
· Duplicate Detection - Smart duplicate prevention using content hashing
· Type Recognition - Auto-detects URLs, WiFi, vCards, emails, SMS, and more

📊 Data Management

· SQLite Database - Local storage with no backend setup needed
· Search & Filter - Full-text search with type and favorite filters
· Export Options - CSV, JSON, and ZIP exports
· Tagging System - Automatic and manual content tagging

📈 Analytics Dashboard

· Real-time Statistics - Scan counts, success rates, type distribution
· Visual Charts - Interactive charts and graphs
· Activity Timeline - Heatmaps of scanning activity
· Content Analysis - Word clouds and domain analysis

🛠️ Advanced Features

· QR Code Generation - Generate QR codes from any text
· Enhanced Detection - Image preprocessing for difficult scans
· Favorites System - Bookmark important scans
· Dark/Light Mode - Theme customization

🚀 Quick Start

1. Local Installation

```bash
# Clone the repository
git clone https://github.com/maskintelligence-gif/qrscan-pro.git
cd maskqrcodescanner

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

2. Streamlit Cloud Deployment

1. Fork this repository
2. Go to share.streamlit.io
3. Connect your GitHub repository
4. Select app.py as the main file
5. Deploy! 🎉

📦 Requirements

Create a requirements.txt file:

```txt
streamlit>=1.28.0
Pillow>=10.0.0
opencv-python>=4.8.0
pyzbar>=0.1.9
qrcode[pil]>=7.4.2
pandas>=2.0.0
numpy>=1.24.0
```

🗂️ Project Structure

```
maskqrcodescanner/
├── app.py                 # Main application (single file!)
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── LICENSE               # MIT License
├── .streamlit/           # Streamlit config
│   └── config.toml       # Theme and settings
├── assets/               # Screenshots and logos
│   ├── screenshot1.png
│   ├── screenshot2.png
│   └── logo.png
└── tests/                # Optional test files
    └── test_scanner.py
```

🎮 Usage Guide

1. Scanning QR Codes

1. Navigate to the "Scan Images" page
2. Upload one or multiple image files (PNG, JPG, JPEG, BMP, GIF, WEBP)
3. Click "Scan All Images" to process
4. View results with detailed information
5. Save, tag, or favorite important scans

2. Managing Scans

· Browse: Search and filter through all scans
· Favorites: Star important scans for quick access
· Export: Download scans as CSV, JSON, or ZIP
· Delete: Remove unwanted scans

3. Analytics

· View scan statistics and trends
· Analyze scan types and frequencies
· Monitor daily activity patterns
· Generate reports

4. Settings

· Configure scanning preferences
· Manage database (backup/clear)
· Customize appearance

🔧 Advanced Configuration

Environment Variables

Create a .streamlit/secrets.toml for production:

```toml
# For AI features (optional)
OPENAI_API_KEY = "your-api-key-here"

# For API integrations (optional)
IFRAMELY_API_KEY = "your-api-key"
VIRUSTOTAL_API_KEY = "your-api-key"
```

Custom Themes

Edit .streamlit/config.toml:

```toml
[theme]
primaryColor = "#667eea"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
font = "sans serif"
```

📱 Screenshots

Scan Page Dashboard Browse Scans
assets/screenshot1.png assets/screenshot2.png assets/screenshot3.png

🏗️ Architecture

Database Schema

```sql
-- Main scans table
CREATE TABLE scans (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    qr_data TEXT,
    qr_type TEXT,
    scan_date DATE,
    data_hash TEXT UNIQUE,
    is_favorite BOOLEAN,
    tags TEXT,          -- JSON array
    created_at DATETIME
);

-- Daily statistics
CREATE TABLE daily_stats (
    date DATE PRIMARY KEY,
    total_scans INTEGER,
    by_type TEXT        -- JSON object
);
```

Scanning Algorithm

1. Original Image → Try direct decoding
2. Enhanced Processing → Apply image preprocessing
3. Channel Separation → Try individual color channels
4. Multiple Thresholds → Try different binarization methods
5. Results Aggregation → Combine all findings

🤝 Contributing

We welcome contributions! Here's how:

1. Fork the repository
2. Create a feature branch (git checkout -b feature/AmazingFeature)
3. Commit your changes (git commit -m 'Add AmazingFeature')
4. Push to the branch (git push origin feature/AmazingFeature)
5. Open a Pull Request

Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Format code
black app.py
```

🧪 Testing

```python
# Sample test
def test_qr_detection():
    """Test QR code detection functionality"""
    test_image = create_test_qr("https://example.com")
    results = scan_qr_from_image(test_image)
    assert len(results) > 0
    assert results[0]['type'] == 'url'
```

📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

🙏 Acknowledgements

· Streamlit - For the amazing framework
· Pyzbar - For QR code decoding
· OpenCV - For image processing
· PIL/Pillow - For image handling
· SQLite - For lightweight database

📞 Support

· Issues: GitHub Issues
· Email: maskintelligence@gmail.com


---

Built with ❤️ by MASK INTELLIGENCE

Ready to scan? Deploy now and start scanning like a pro! 🚀
