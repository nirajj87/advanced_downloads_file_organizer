# 📦 Advanced Downloads Organizer
A powerful Python tool to automatically organize your Downloads folder by **file type**, **date**, and **custom rules**.  
Supports both **GUI** and **CLI** modes with real-time monitoring.

---

## 🚀 Features

- **Multiple Organization Modes:**  
  - Type → Date  
  - Date → Type  
  - Type Only (Flat)

- **Dual Interface:**  
  ✔ GUI for easy use  
  ✔ CLI for automation  

- **Real-time Watch Mode** (auto-organize newly added files)

- **Custom Rules (JSON config)**  
  Define your own file types & categories

- **Smart Cleanup**  
  Automatically deletes empty folders

- **Detailed Logging**  
  Logs every activity in `/logs/organizer.log`

- **Config Persistence**  
  Saves your settings across sessions

---

## 📁 Example — Before & After Organization

### **Before**

Downloads/
├── photo1.jpg
├── document.pdf
├── video.mp4
├── script.py
├── music.mp3
├── archive.zip
└── random_file.txt

### **After (Type → Date mode)**
Downloads/
├── Images/
│ └── 2024/Jan/photo1.jpg
├── Documents/
│ └── 2024/Jan/document.pdf
├── Videos/
│ └── 2024/Jan/video.mp4
├── Code/
│ └── 2024/Jan/script.py
├── Audio/
│ └── 2024/Jan/music.mp3
├── Archives/
│ └── 2024/Jan/archive.zip
└── Others/
└── 2024/Jan/random_file.txt


---

## 🧰 Organization Methods Explained

| Method | Structure |
|--------|-----------|
| **type_date** | Type → Year → Month → File |
| **date_type** | Year → Month → Type → File |
| **type** | Type → File |

---

## 🖥 GUI Mode
Run GUI (default):

```bash
python organizer_downloads_advanced.py

💻 CLI Usage
Run Once
python organizer_downloads_advanced.py --run

Watch Mode (Real-time)
python organizer_downloads_advanced.py --watch

With Options
python organizer_downloads_advanced.py --run --method type --delete-empty true

⚙ CLI Arguments
Argument	Description
--run	Run organization once
--watch	Continuous watch mode
--target <path>	Override target directory
--method <type>	type_date / date_type / type
--recursive	Enable recursive scanning
--delete-empty	Remove empty folders
🧩 Config File (Auto-generated)

organizer_config.json

{
  "target_folder": "C:/Users/User/Downloads",
  "method": "type_date",
  "recursive": false,
  "delete_empty": true,
  "watch_mode": false,
  "custom_rules": {}
}

📦 Installation
Install Dependencies
pip install watchdog colorama


Tkinter comes preinstalled on Windows & most Linux systems.

📜 Logging

Logs are saved here:

logs/organizer.log


Each move + error is recorded.

📂 Project Structure
advanced_downloads_file_organizer/
├── organizer_downloads_advanced.py
├── organizer_config.json
├── logs/
│   └── organizer.log
└── README.md

📝 Summary Report Example
📦 DOWNLOAD ORGANIZER - TASK SUMMARY
✔ Total Files Scanned       : 124
📁 Folders Created           : 32
📂 Files Moved               : 118
🗑 Folders Deleted (empty)   : 9
🎉 Task Completed Successfully!

🏁 Future Enhancements

Multithreaded file moving

Duplicate file detector

GUI: Live stats + pie charts

Light/Dark themes

File preview panel

⭐ Contribute

Pull requests & suggestions are welcome!

❤️ Support

If you like this tool, please ⭐ the repo!
