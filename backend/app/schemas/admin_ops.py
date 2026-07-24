# -*- coding: utf-8 -*-
"""Admin ops Pydantic schemas (runtime logs, storage, payment, SMTP, maintenance)."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

class RuntimeLogFileOut(BaseModel):
    name: str
    size_bytes: int
    modified_at: str


class RuntimeLogViewOut(BaseModel):
    filename: str
    tail_lines: int
    size_bytes: int
    modified_at: str
    content: str


class AdminStorageUsageUserOut(BaseModel):
    user_id: int
    username: str
    email: Optional[str] = None
    file_count: int
    bytes: int

class AdminExpiredFileItem(BaseModel):
    user_id: int
    username: str
    email: Optional[str] = None
    filepath: str
    size: int
    modified_at: str

class AdminExpiredFilesOut(BaseModel):
    files: List[AdminExpiredFileItem]
    total_size: int
    total_count: int

class AdminExpiredRemindRequest(BaseModel):
    user_ids: Optional[List[int]] = None

class AdminExpiredDeleteRequest(BaseModel):
    user_ids: Optional[List[int]] = None

class GenericMessageOut(BaseModel):
    message: str

class AdminStorageUsageOut(BaseModel):
    upload_root: str
    total_bytes: int
    total_files: int
    users: List[AdminStorageUsageUserOut]


class PaymentConfig(BaseModel):
    mchid: Optional[str] = ""
    appid: Optional[str] = ""
    api_v3_key: Optional[str] = ""
    cert_serial_no: Optional[str] = ""
    private_key: Optional[str] = ""
    public_key: Optional[str] = ""
    public_key_id: Optional[str] = ""
    notify_url: Optional[str] = ""
    use_mock: bool = True


class SMTPConfig(BaseModel):
    host: Optional[str] = ""
    port: int = 587
    username: Optional[str] = ""
    password: Optional[str] = ""
    use_ssl: bool = False
    use_tls: bool = True
    from_email: Optional[str] = ""
    frontend_base_url: Optional[str] = ""


class SMTPTestRequest(BaseModel):
    to_email: str


class SMTPBroadcastRequest(BaseModel):
    subject: str
    content_html: Optional[str] = ""
    content_text: Optional[str] = ""
    confirm_phrase: str


class MaintenanceConfig(BaseModel):
    enabled: bool = False
    ends_at: Optional[str] = None
    message: Optional[str] = ""


class MaintenanceStatusOut(BaseModel):
    enabled: bool = False
    is_active: bool = False
    ends_at: Optional[str] = None
    message: Optional[str] = ""


