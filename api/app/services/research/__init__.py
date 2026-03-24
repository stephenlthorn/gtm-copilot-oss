from __future__ import annotations

from app.services.research.company_verify import CompanyVerifyService
from app.services.research.sources import ResearchSourceRunner

try:
    from app.services.research.precall_report import PreCallReportGenerator
except ImportError:
    PreCallReportGenerator = None  # type: ignore[assignment,misc]

try:
    from app.services.research.postcall_pipeline import PostCallPipeline
except ImportError:
    PostCallPipeline = None  # type: ignore[assignment,misc]

try:
    from app.services.research.refinement_service import RefinementService
except ImportError:
    RefinementService = None  # type: ignore[assignment,misc]

try:
    from app.services.research.calendar_scanner import CalendarScannerService
except ImportError:
    CalendarScannerService = None  # type: ignore[assignment,misc]

try:
    from app.services.research.orchestrator import ResearchOrchestrator
except ImportError:
    ResearchOrchestrator = None  # type: ignore[assignment,misc]

__all__ = [
    "CompanyVerifyService",
    "ResearchSourceRunner",
    "PreCallReportGenerator",
    "PostCallPipeline",
    "RefinementService",
    "CalendarScannerService",
    "ResearchOrchestrator",
]
