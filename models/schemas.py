"""
Pydantic models cho toan bo he thong Zertdoo.
Moi nguon du lieu (Sheet, Notion, Tasks, Calendar, Postgres)
deu co model rieng de chuan hoa va validate.
"""

from datetime import date, datetime, time
from typing import Optional
from pydantic import BaseModel, Field


# ============================================================
# TU GOOGLE SHEET
# ============================================================

class TaskItem(BaseModel):
    """
    Mot nhiem vu doc tu Google Sheet.
    Moi hang hop le trong sheet = 1 TaskItem.
    """
    sheet_name: str = Field(description="Ten worksheet (VD: In_class, Self-study)")
    category: str = Field(default="", description="Category/Domain tu cot A (da forward-fill)")
    task: str = Field(description="Ten cong viec chinh (cot B)")
    priority: str = Field(default="", description="Muc do uu tien: High/Medium/Low (cot C)")
    start_date: Optional[str] = Field(default=None, description="Ngay bat dau (cot D)")
    due_date: Optional[str] = Field(default=None, description="Han chot (cot E)")
    status: str = Field(default="", description="Trang thai: Done/Pending/Reschedule (cot F)")
    notes: str = Field(default="", description="Ghi chu gop tu cot G + H")


# ============================================================
# TU NOTION
# ============================================================

class NotionNote(BaseModel):
    """
    Mot trang (page) doc tu Notion database.
    """
    page_id: str = Field(description="ID cua page trong Notion")
    database_id: str = Field(description="ID cua database chua page nay")
    database_name: str = Field(default="", description="Ten cua database")
    title: str = Field(description="Tieu de cua page")
    content: str = Field(default="", description="Noi dung plain text cua page")
    properties: dict = Field(default_factory=dict, description="Cac properties khac cua page")
    last_edited: Optional[datetime] = Field(default=None, description="Lan chinh sua cuoi")
    url: str = Field(default="", description="URL cua page tren Notion")


# ============================================================
# TU GOOGLE TASKS
# ============================================================

class GoogleTask(BaseModel):
    """
    Mot task doc tu Google Tasks.
    """
    task_id: str = Field(description="ID cua task trong Google Tasks")
    task_list_id: str = Field(description="ID cua task list chua task nay")
    task_list_title: str = Field(default="", description="Ten cua task list")
    title: str = Field(description="Tieu de cua task")
    notes: str = Field(default="", description="Ghi chu")
    status: str = Field(description="Trang thai: needsAction hoac completed")
    due: Optional[str] = Field(default=None, description="Han chot (RFC 3339)")
    completed: Optional[str] = Field(default=None, description="Thoi diem hoan thanh")
    position: str = Field(default="", description="Vi tri trong list (de sap xep)")
    updated: Optional[str] = Field(default=None, description="Lan cap nhat cuoi")


# ============================================================
# TU GOOGLE CALENDAR
# ============================================================

class CalendarEvent(BaseModel):
    """
    Mot su kien doc tu Google Calendar.
    """
    event_id: str = Field(description="ID cua event")
    summary: str = Field(description="Tieu de su kien")
    description: str = Field(default="", description="Mo ta chi tiet")
    start: str = Field(description="Thoi gian bat dau (ISO format)")
    end: str = Field(description="Thoi gian ket thuc (ISO format)")
    location: str = Field(default="", description="Dia diem")
    is_all_day: bool = Field(default=False, description="La su kien ca ngay?")
    status: str = Field(default="confirmed", description="confirmed/tentative/cancelled")


# ============================================================
# TU POSTGRESQL (thong ke hanh vi)
# ============================================================

class BehaviorStats(BaseModel):
    """
    Thong ke hanh vi nguoi dung tu PostgreSQL.
    Dung de cung cap context cho LLM.
    """
    total_tasks_30d: int = Field(default=0, description="Tong so task trong 30 ngay")
    completed_tasks_30d: int = Field(default=0, description="So task hoan thanh")
    skipped_tasks_30d: int = Field(default=0, description="So task bo qua")
    rescheduled_tasks_30d: int = Field(default=0, description="So task bi doi lich")
    completion_rate: float = Field(default=0.0, description="Ti le hoan thanh (0-1)")
    avg_tasks_per_day: float = Field(default=0.0, description="Trung binh tasks/ngay")
    most_productive_hours: list[str] = Field(
        default_factory=list,
        description="Khung gio hoan thanh nhieu nhat"
    )
    common_skip_patterns: list[str] = Field(
        default_factory=list,
        description="Pattern thuong bo qua task"
    )


class TaskLog(BaseModel):
    """
    Mot ban ghi trong bang task_logs.
    """
    id: Optional[int] = None
    task_name: str
    source: str
    sheet_name: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    status: str = "pending"
    scheduled_date: Optional[date] = None
    scheduled_time_slot: Optional[str] = None
    duration_minutes: Optional[int] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class AgentLog(BaseModel):
    """
    Mot ban ghi trong bang agent_logs.
    """
    id: Optional[int] = None
    agent_name: str
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    reasoning: Optional[str] = None
    llm_model: Optional[str] = None
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None


class DailyPlan(BaseModel):
    """
    Ke hoach hang ngay tu bang daily_plans.
    """
    id: Optional[int] = None
    plan_date: date
    plan_json: dict
    confirmed: bool = False
    confirmed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


# ============================================================
# OUTPUT CUA LLM (SchedulerAgent)
# ============================================================

class ScheduledTask(BaseModel):
    """Mot task trong lich trinh ngay, do LLM tao."""
    title: str
    source: str = Field(description="VD: 'In_class/Toan roi rac'")
    priority_rank: int = Field(description="Thu tu uu tien (1 = cao nhat)")
    time_slot: str = Field(description="VD: '08:00 - 09:30'")
    duration_minutes: int
    reasoning: str = Field(description="Tai sao task nay o vi tri nay")


class EventToCreate(BaseModel):
    """Su kien can tao tren Google Calendar."""
    title: str
    start: str = Field(description="ISO datetime")
    end: str = Field(description="ISO datetime")
    description: str = ""


class DailyPlanOutput(BaseModel):
    """Output day du cua SchedulerAgent."""
    daily_tasks: list[ScheduledTask] = []
    events_to_create: list[EventToCreate] = []
    risks: list[str] = []
    questions_for_user: list[str] = []
    overall_reasoning: str = ""
