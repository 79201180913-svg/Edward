from edward.services.opportunity_analysis_pipeline_v0821 import (
    OpportunityAnalysisPipelineV0821,
    UnifiedOpportunityEngineV0821,
)
from edward.services.opportunity_search_service import OpportunitySearchService


def test_opportunity_search_defaults_to_canonical_v0821_pipeline():
    service = OpportunitySearchService(object())

    assert isinstance(service.analysis, OpportunityAnalysisPipelineV0821)
    assert isinstance(service.opportunity_engine, UnifiedOpportunityEngineV0821)


def test_opportunity_search_keeps_explicit_analysis_dependency_injection():
    analysis = object()

    service = OpportunitySearchService(object(), analysis_service=analysis)

    assert service.analysis is analysis
    assert isinstance(service.opportunity_engine, UnifiedOpportunityEngineV0821)
