from fastapi import APIRouter, status

from ..schemas.assessment import InitialAssessmentRequest, InitialAssessmentResponse
from ..utils.assessment_service import create_initial_assessment, get_initial_assessment


router = APIRouter(prefix="/api/v1/assessments", tags=["assessments"])


@router.post(
    "/initial",
    response_model=InitialAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_assessment(payload: InitialAssessmentRequest) -> InitialAssessmentResponse:
    return create_initial_assessment(payload)


@router.get("/{assessment_id}", response_model=InitialAssessmentResponse)
def get_assessment(assessment_id: str) -> InitialAssessmentResponse:
    return get_initial_assessment(assessment_id)
