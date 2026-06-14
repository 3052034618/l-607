import uuid
from datetime import datetime


def generate_permit_number(site_code: str) -> str:
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"ZY-{site_code}-{date_str}-{short_uuid}"


def generate_ticket_number() -> str:
    now = datetime.now()
    date_str = now.strftime("%Y%m%d%H%M%S")
    short_uuid = uuid.uuid4().hex[:4].upper()
    return f"CF-{date_str}-{short_uuid}"


def generate_work_order_number(level: str) -> str:
    level_map = {"minor": "1", "medium": "2", "major": "3", "critical": "4"}
    level_code = level_map.get(level, "0")
    now = datetime.now()
    date_str = now.strftime("%Y%m%d%H%M%S")
    short_uuid = uuid.uuid4().hex[:4].upper()
    return f"GD-{level_code}-{date_str}-{short_uuid}"


def generate_settlement_number(project_code: str) -> str:
    now = datetime.now()
    month_str = now.strftime("%Y%m")
    short_uuid = uuid.uuid4().hex[:4].upper()
    return f"JS-{project_code}-{month_str}-{short_uuid}"


def generate_report_id() -> str:
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    return f"RPT-{date_str}"
