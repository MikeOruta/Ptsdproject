# Deployment — PythonAnywhere

Live URL: **https://mikeoruta.pythonanywhere.com**

## How deployment works

```
Laptop (write code) --git push--> GitHub --git pull--> PythonAnywhere --> public URL
```

PythonAnywhere was chosen because it hosts Flask for free and keeps files between
restarts, so the SQLite database is not wiped (many free hosts use temporary disks).
Free-tier limit: log in and click "Run until 1 month from today" on the Web tab
every month to keep the site running (PythonAnywhere emails a reminder a week before).

## First-time setup

### 1. Copy the code from GitHub (Bash console)
Dashboard → **Consoles** → **Bash**, then run:

```bash
git clone https://github.com/MikeOruta/Ptsdproject.git ~/ptsd-system
cd ~/ptsd-system
python3.12 -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
```

`--system-site-packages` reuses PythonAnywhere's pre-installed scientific
packages (pandas, scikit-learn), which saves the free account's limited disk space.

### 2. Settings and database

```bash
cp .env.example .env
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')/" .env
sed -i "s/^SECURE_COOKIES=.*/SECURE_COOKIES=1/" .env
python db/init_db.py
python -m ml.generate_synthetic_data
python -m ml.train_model
```

This creates a server-only `.env` with its own random secret key (never copied
from the laptop), turns on HTTPS-only cookies, creates the 10 database tables,
and trains the model **on the server**. Training on the server guarantees that
the model matches the server's scikit-learn version; it takes a few seconds.

Then create your administrator account (you type the password privately):

```bash
python -m db.create_user --role administrator --email you@example.org --name "Your Name"
```

Optional, for demonstrations: load fictional demo accounts. First set a demo
password (10+ characters, letters and numbers) in `.env`, then run the seed script:

```bash
nano .env        # set DEMO_PASSWORD=..., then Ctrl+O, Enter, Ctrl+X
python -m db.seed_demo
```

### 3. Create the web app (Web tab)
1. **Web** → **Add a new web app** → **Next**.
2. Choose **Manual configuration** (not "Flask") → **Python 3.12** → **Next**.
3. **Virtualenv** section: enter `/home/mikeoruta/ptsd-system/venv`
4. **Code** section → **Source code**: `/home/mikeoruta/ptsd-system`
5. **Code** section → click the **WSGI configuration file** link, delete everything
   in it, paste the following, then **Save**:

```python
import sys

path = "/home/mikeoruta/ptsd-system"
if path not in sys.path:
    sys.path.insert(0, path)

from run import app as application  # PythonAnywhere looks for "application"
```

6. **Web** tab → **Security** → turn **Force HTTPS** on.
7. Click the green **Reload** button, then open https://mikeoruta.pythonanywhere.com

## Updating the live site after new work

After pushing from the laptop, in a PythonAnywhere Bash console:

```bash
cd ~/ptsd-system
git pull
source venv/bin/activate
pip install -r requirements.txt
```

Then **Web** tab → **Reload**. Re-run `python -m ml.train_model` if the ML code
changed. Only re-run `python db/init_db.py` if the schema changed: it wipes all
data, after which you must run `train_model`, `create_user` (and `seed_demo`) again.

## Troubleshooting
- **Error page / "Something went wrong"**: Web tab → **Error log** (bottom of the
  log files list). The last lines show the Python error.
- **`python3.12: command not found`**: use `python3.11` instead, and pick 3.11 in step 3.
