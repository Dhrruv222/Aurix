"""
app/api/v1/ai/risk.py
─────────────────────
POST /v1/ai/analyze-risk       — anomaly detection + AML check (single transaction)
POST /v1/ai/compliance-report  — batch compliance screening + regulatory report

Runs anomaly detection, AML pattern checking, and compliance reporting via risk_ai.
"""

import asyncio

from fastapi import APIRouter, HTTPException, Request
from app.core.config import settings
from app.core.logging import get_logger
from uuid import uuid4

from app.schemas.schemas import (
    AnalyzeRiskRequest,
    AnalyzeRiskResponse,
    ComplianceReportRequest,
    ComplianceReportResponse,
)
from app.services.ai_modules.risk_ai.service import (
    detect_anomaly,
    check_aml_patterns,
    generate_compliance_report,
)

router = APIRouter()
logger = get_logger(__name__)

_MODULE = "risk_ai"


@router.post(
    "/analyze-risk",
    response_model=AnalyzeRiskResponse,
    summary="Anomaly Detection + AML Pattern Check",
    tags=["Risk AI"],
)
async def analyze_risk(payload: AnalyzeRiskRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)
    tx = payload.transaction

    logger.info(
        f"[{_MODULE.upper()}] REQUEST | request_id={request_id} "
        f"user_id={payload.user_id} module={_MODULE} "
        f"amount={tx.amount} location={tx.location} hour={tx.hour_of_day}"
    )

    tx_data = tx.model_dump()

    try:
        anomaly_result, aml_result = await asyncio.gather(
            asyncio.to_thread(detect_anomaly, payload.user_id, tx_data),
            asyncio.to_thread(check_aml_patterns, payload.user_id, tx_data),
        )
    except asyncio.TimeoutError:
        logger.error(
            f"[{_MODULE.upper()}] TIMEOUT | request_id={request_id} user_id={payload.user_id}"
        )
        raise HTTPException(status_code=504, detail="Risk analysis timed out. Please retry.")
    except Exception:
        logger.exception(
            f"[{_MODULE.upper()}] ERROR | request_id={request_id} user_id={payload.user_id}"
        )
        raise HTTPException(status_code=500, detail="Internal error during risk analysis.")

    overall_flag = anomaly_result["anomaly_detected"] or aml_result["aml_flag"]

    logger.info(
        f"[{_MODULE.upper()}] RESULT | request_id={request_id} user_id={payload.user_id} "
        f"module={_MODULE} decision_type=risk_analysis "
        f"anomaly={anomaly_result['anomaly_detected']} aml_flag={aml_result['aml_flag']} "
        f"aml_risk_level={aml_result['risk_level']}"
    )

    return AnalyzeRiskResponse(
        status="success",
        data={
            "anomaly": anomaly_result,
            "aml": aml_result,
            "overall_flagged": overall_flag,
        },
        metadata={
            "request_id": request_id,
            "user_id": payload.user_id,
            "module": _MODULE,
        },
    )


# ─── Compliance Report Endpoint ───────────────────────────────────────────────

@router.post(
    "/compliance-report",
    response_model=ComplianceReportResponse,
    summary="Batch Compliance Screening + Regulatory Report",
    tags=["Risk AI"],
)
async def compliance_report(payload: ComplianceReportRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    report_id = payload.report_id or f"RPT-{str(uuid4())[:8].upper()}"

    logger.info(
        f"[{_MODULE.upper()}] REQUEST | request_id={request_id} "
        f"report_id={report_id} transactions={len(payload.transactions)} "
        f"period={payload.reporting_period}"
    )

    tx_dicts = [tx.model_dump() for tx in payload.transactions]

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                generate_compliance_report,
                report_id,
                tx_dicts,
                payload.reporting_period or "",
            ),
            timeout=max(settings.SCORING_TIMEOUT, len(tx_dicts) * 0.05),
        )
    except asyncio.TimeoutError:
        logger.error(
            f"[{_MODULE.upper()}] COMPLIANCE TIMEOUT | request_id={request_id}"
        )
        raise HTTPException(status_code=504, detail="Compliance report generation timed out.")
    except Exception:
        logger.exception(
            f"[{_MODULE.upper()}] COMPLIANCE ERROR | request_id={request_id}"
        )
        raise HTTPException(status_code=500, detail="Internal error during compliance report.")

    logger.info(
        f"[{_MODULE.upper()}] RESULT | request_id={request_id} report_id={report_id} "
        f"total={result['total_transactions']} flagged={result['flagged_count']} "
        f"high={result['high_risk_count']}"
    )

    return ComplianceReportResponse(
        status="success",
        data=result,
        metadata={
            "request_id": request_id,
            "report_id": report_id,
            "module": _MODULE,
        },
    )
