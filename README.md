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

- **Python 3.8.1+**
- **Windows** (app uses `taskkill` to close processes)
- **Poetry** (for dependency management)

## 📦 Installation

### Using Poetry (Recommended)

1. **Install Poetry** (if you haven't already):

   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

   Or on Windows:

   ```powershell
   (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
   ```

2. **Clone the repository**:

   ```bash
   git clone <repository-url>
   cd app-blocker
   ```

3. **Install dependencies**:

   ```bash
   poetry install
   ```

4. **Run the application**:

   ```bash
   # GUI version
   poetry run python gui.py

   # Command line monitoring
   poetry run python main.py
   ```

### Alternative Installation

If you prefer not to use Poetry, you can install dependencies manually:

```bash
pip install psutil
python gui.py  # For GUI
python main.py # For monitoring
```

## 🎯 Usage

1. **Start the GUI**: `poetry run python gui.py`
2. **Add applications** you want to monitor by clicking "Add App"
3. **Set time limits** for each application (in minutes)
4. **Enable monitoring** by checking the "Enable Monitoring" checkbox
5. **Start monitoring** by clicking "Start Monitoring"

The application will:

- Track time spent in monitored applications
- Automatically close applications when daily limits are exceeded
- Save usage history for each day

## 🔧 Configuration

Configuration is stored in `config.json`:

- `apps`: Dictionary of applications and their daily limits (in minutes)
- `check_interval`: How often to check processes (in seconds)
- `enabled`: Whether monitoring is active

## 📊 Dependencies

- `psutil` - for process monitoring
- `tkinter` - graphical interface (built into Python)
