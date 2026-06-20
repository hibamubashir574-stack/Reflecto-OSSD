import os, json, re
from datetime import datetime
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
def _default_data(theme: str = "light") -> dict:
    return {"journal": [], "notes": [], "tasks": [], "moods": [], "theme": theme}
def _user_file(user: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", user)
    return os.path.join(DATA_DIR, f"{safe}.json")
def load_user(user: str) -> dict:
    f = _user_file(user)
    if not os.path.exists(f):
        return _default_data()
    try:
        with open(f, "r", encoding="utf-8") as fp:
            return json.load(fp) or _default_data()
    except (json.JSONDecodeError, OSError):
        return _default_data()
def save_user(user: str, data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_user_file(user), "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2, ensure_ascii=False)
def delete_user(user: str) -> bool:
    f = _user_file(user)
    if os.path.exists(f):
        os.unlink(f)
        return True
    return False
def reset_user(user: str) -> None:
    theme = load_user(user).get("theme", "light")
    fresh = _default_data(theme)
    fresh["lastLogin"] = datetime.now().isoformat()
    save_user(user, fresh)
def list_users() -> list:
    if not os.path.isdir(DATA_DIR):
        return []
    users = []
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"):
            continue
        name = filename[:-5]
        try:
            with open(os.path.join(DATA_DIR, filename), "r", encoding="utf-8") as fp:
                d = json.load(fp) or {}
        except (json.JSONDecodeError, OSError):
            d = {}
        users.append({"name": name, "lastLogin": d.get("lastLogin", "")})
    users.sort(key=lambda u: u["lastLogin"], reverse=True)
    return users
