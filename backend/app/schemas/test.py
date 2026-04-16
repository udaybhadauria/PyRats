"""
Pydantic schemas for test operations
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class TestStatus(str, Enum):
    """Test status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class TestPriority(str, Enum):
    """Test priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TestBase(BaseModel):
    """Base test information"""
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    test_group: str = Field(..., description="Test category/group")
    timeout: int = Field(default=300, ge=1, description="Timeout in seconds")
    priority: TestPriority = Field(default=TestPriority.MEDIUM)
    parameters: Optional[Dict[str, Any]] = None


class TestCreate(TestBase):
    """Schema for creating a test"""
    pass


class TestCase(BaseModel):
    """Individual test case"""
    id: str
    name: str
    description: Optional[str]
    test_group: str
    timeout: int
    priority: TestPriority
    parameters: Optional[Dict[str, Any]]


class TestRequest(BaseModel):
    """Request to execute tests"""
    device_id: str = Field(..., description="Target device ID")
    test_cases: List[str] = Field(..., min_items=1, description="Test case IDs")
    parameters: Optional[Dict[str, Any]] = None
    priority: TestPriority = Field(default=TestPriority.MEDIUM)


class TestExecution(BaseModel):
    """Test execution record"""
    id: str
    device_id: str
    test_case: str
    status: TestStatus = Field(default=TestStatus.PENDING)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None  # seconds
    parameters: Optional[Dict[str, Any]] = None


class TestResult(BaseModel):
    """Test result data"""
    id: str
    execution_id: str
    test_case: str
    status: TestStatus
    passed: bool
    output: Optional[str] = None
    errors: Optional[List[str]] = None
    metrics: Optional[Dict[str, Any]] = None
    timestamp: datetime


class TestBatch(BaseModel):
    """Batch of test executions"""
    id: str
    device_id: str
    status: TestStatus
    total_tests: int
    completed_tests: int
    passed_tests: int
    failed_tests: int
    created_at: datetime
    completed_at: Optional[datetime] = None
