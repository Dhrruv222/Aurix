"""
app/api/v1/ai/credit.py
────────────────────────
POST /v1/ai/credit-score  — credit scoring + loan eligibility
POST /v1/ai/snbl-check    — Save Now, Buy Later affordability + instalment plan

Runs credit scoring, loan eligibility, and SNBL assessment via credit_ai service.
"""

import asyncio

from fastapi import APIRouter, HTTPException, Request
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.schemas import CreditScoreRequest, CreditScoreResponse, SNBLRequest, SNBLResponse
from app.services.ai_modules.credit_ai.service import (
    compute_credit_score,
    assess_loan_eligibility,
    compute_snbl_approval,
)

router = APIRouter()
logger = get_logger(__name__)

_MODULE = "credit_ai"


@router.post(
    "/credit-score",
    response_model=CreditScoreResponse,
    summary="Credit Score + Loan Eligibility Assessment",
    tags=["Credit AI"],
)
async def credit_score(payload: CreditScoreRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    logger.info(
        f"[{_MODULE.upper()}] REQUEST | request_id={request_id} "
        f"user_id={payload.user_id} module={_MODULE} "
        f"gold_value={payload.gold_value_usd} tenure={payload.tenure_months}mo"
    )

    user_data = {
        "savings_rate": payload.savings_rate,
        "gold_value_usd": payload.gold_value_usd,
        "repayment_rate": payload.repayment_rate,
        "tenure_months": payload.tenure_months,
    }

    try:
        score_result = await asyncio.wait_for(
            asyncio.to_thread(compute_credit_score, payload.user_id, user_data),
            timeout=settings.SCORING_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.error(
            f"[{_MODULE.upper()}] TIMEOUT | request_id={request_id} user_id={payload.user_id}"
        )
        raise HTTPException(status_code=504, detail="Credit scoring timed out.")
    except Exception:
        logger.exception(
            f"[{_MODULE.upper()}] ERROR | request_id={request_id} user_id={payload.user_id}"
        )
        raise HTTPException(status_code=500, detail="Internal error during credit scoring.")

    # Run loan eligibility only if a loan amount was requested
    loan_result = None
    if payload.requested_loan_amount is not None:
        loan_request = {
            "credit_score": score_result["credit_score"],
            "gold_value_usd": payload.gold_value_usd,
            "requested_amount": payload.requested_loan_amount,
        }
        try:
            loan_result = await asyncio.wait_for(
                asyncio.to_thread(assess_loan_eligibility, payload.user_id, loan_request),
                timeout=settings.SCORING_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error(
                f"[{_MODULE.upper()}] LOAN TIMEOUT | request_id={request_id} user_id={payload.user_id}"
            )
            raise HTTPException(status_code=504, detail="Loan eligibility check timed out.")
        except Exception:
            logger.exception(
                f"[{_MODULE.upper()}] LOAN ERROR | request_id={request_id} user_id={payload.user_id}"
            )
            raise HTTPException(status_code=500, detail="Internal error during loan eligibility check.")

    logger.info(
        f"[{_MODULE.upper()}] RESULT | request_id={request_id} user_id={payload.user_id} "
        f"module={_MODULE} decision_type=credit_score "
        f"score={score_result['credit_score']} grade={score_result['grade']} "
        f"loan_decision={loan_result['decision'] if loan_result else 'N/A'}"
    )

    data: dict = {"credit": score_result}
    if loan_result:
        data["loan_eligibility"] = loan_result

    return CreditScoreResponse(
        status="success",
        data=data,
        metadata={
            "request_id": request_id,
            "user_id": payload.user_id,
            "module": _MODULE,
            "loan_requested": payload.requested_loan_amount is not None,
        },
    )


# ─── SNBL Endpoint ────────────────────────────────────────────────────────────

@router.post(
    "/snbl-check",
    response_model=SNBLResponse,
    summary="Save Now, Buy Later — Affordability & Instalment Plan",
    tags=["Credit AI"],
)
async def snbl_check(payload: SNBLRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    logger.info(
        f"[{_MODULE.upper()}] REQUEST | request_id={request_id} "
        f"user_id={payload.user_id} action=snbl "
        f"item_price={payload.item_price_usd} instalments={payload.num_instalments}"
    )

    snbl_data = payload.model_dump(exclude={"user_id"})

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(compute_snbl_approval, payload.user_id, snbl_data),
            timeout=settings.SCORING_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.error(
            f"[{_MODULE.upper()}] SNBL TIMEOUT | request_id={request_id} user_id={payload.user_id}"
        )
        raise HTTPException(status_code=504, detail="SNBL check timed out.")
    except Exception:
        logger.exception(
            f"[{_MODULE.upper()}] SNBL ERROR | request_id={request_id} user_id={payload.user_id}"
        )
        raise HTTPException(status_code=500, detail="Internal error during SNBL check.")

    logger.info(
        f"[{_MODULE.upper()}] RESULT | request_id={request_id} user_id={payload.user_id} "
        f"decision={result['decision']} credit_score={result['credit_score']} "
        f"monthly_instalment={result['monthly_instalment']}"
    )

    return SNBLResponse(
        status="success",
        data=result,
        metadata={
            "request_id": request_id,
            "user_id": payload.user_id,
            "module": _MODULE,
            "item_price_usd": payload.item_price_usd,
            "num_instalments": payload.num_instalments,
        },
    )
