# File: app/utils/time.py
from datetime import datetime
import pytz

def get_pakistan_time():
    """Get current time in Pakistan Standard Time (UTC+5)"""
    pakistan_tz = pytz.timezone('Asia/Karachi')
    return datetime.now(pakistan_tz)

def convert_to_pakistan_time(dt: datetime) -> datetime:
    """Convert a datetime to Pakistan Standard Time"""
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    pakistan_tz = pytz.timezone('Asia/Karachi')
    return dt.astimezone(pakistan_tz) 

def format_pakistan_time(dt: datetime) -> str:
    """Format datetime in Pakistan timezone with timezone info"""
    pakistan_time = convert_to_pakistan_time(dt)
    return pakistan_time.strftime('%Y-%m-%d %H:%M:%S %Z')   