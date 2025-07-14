# 🚫 App Blocker

**App Blocker** is an application for monitoring and limiting time spent on specific programs on your computer. It allows you to set daily time limits for applications and automatically closes them when the limit is exceeded.

## 📋 Features

- ⏰ **Time Limits** - set daily limits for applications (in minutes)
- 🎯 **Automatic Closing** - applications are closed when limit is exceeded
- 📊 **Real-time Monitoring** - track current usage time
- 🖥️ **Graphical Interface** - easy management through GUI
- 📈 **Usage History** - data is saved day by day
- ⚙️ **Configurable Interval** - set how often the app checks processes

## 🚀 Requirements

- **Python 3.7+**
- **Windows** (app uses `taskkill` to close processes)
- Python libraries:
  - `psutil` - for process monitoring
  - `tkinter` - graphical interface (usually built into Python)
