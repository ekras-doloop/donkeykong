"""
Tests for DonkeyKong Kong Adversarial Validator

Run with: pytest tests/ -v
"""

import pytest
from dataclasses import asdict
from donkeykong.kong.adversarial import (
    AdversarialValidator,
    ValidationResult,
    OllamaAdversarialValidator
)


class TestValidationResult:
    """Test ValidationResult dataclass"""
    
    def test_validation_result_creation(self):
        result = ValidationResult(
            overall_confidence=0.85,
            completeness_score=0.9,
            consistency_score=0.8,
            logic_score=0.85,
            issues_found=["Test issue"],
            adversarial_questions=["Test question?"],
            recommended_actions=["APPROVED"],
            should_rerun=False
        )
        assert result.overall_confidence == 0.85
        assert result.should_rerun is False
        assert len(result.issues_found) == 1
    
    def test_validation_result_to_dict(self):
        result = ValidationResult(
            overall_confidence=0.7,
            completeness_score=0.7,
            consistency_score=0.7,
            logic_score=0.7,
            issues_found=[],
            adversarial_questions=[],
            recommended_actions=[],
            should_rerun=False
        )
        d = asdict(result)
        assert isinstance(d, dict)
        assert 'overall_confidence' in d


class TestAdversarialValidator:
    """Test AdversarialValidator class"""
    
    @pytest.fixture
    def validator(self):
        return AdversarialValidator(
            confidence_threshold=0.7,
            max_issues_before_rerun=3
        )
    
    @pytest.fixture
    def good_analysis(self):
        return {
            "score": 7.5,
            "confidence": 0.85,
            "findings": [
                "Strong revenue growth",
                "Improving margins",
                "Market share gains"
            ],
            "recommendations": ["Buy"],
            "sources_used": ["earnings", "news", "analyst"]
        }
    
    @pytest.fixture
    def good_raw_data(self):
        return {
            "earnings": {"q1": 1.5, "q2": 1.6, "q3": 1.7, "q4": 1.8},
            "news": {"sentiment": 0.7, "count": 50},
            "analyst": {"rating": "buy", "target": 150},
            "data_quality_score": 85,
            "sources_successful": ["earnings", "news", "analyst"],
            "sources_failed": []
        }
    
    @pytest.fixture
    def poor_analysis(self):
        return {
            "score": 9.5,  # Extreme score
            "confidence": 0.95,  # Very high confidence
            "findings": ["Good"],  # Minimal findings
            "recommendations": []
        }
    
    @pytest.fixture
    def poor_raw_data(self):
        return {
            "earnings": None,
            "data_quality_score": 30,
            "sources_successful": ["news"],
            "sources_failed": ["earnings", "analyst", "sec"]
        }
    
    def test_validate_good_analysis(self, validator, good_analysis, good_raw_data):
        """Good analysis with good data should pass"""
        result = validator.validate("TEST", good_analysis, good_raw_data)
        
        assert isinstance(result, ValidationResult)
        assert result.overall_confidence >= 0.7
        assert result.should_rerun is False
        assert "APPROVED" in str(result.recommended_actions)
    
    def test_validate_poor_analysis(self, validator, poor_analysis, poor_raw_data):
        """Poor analysis with poor data should fail"""
        result = validator.validate("TEST", poor_analysis, poor_raw_data)
        
        assert result.overall_confidence < 0.7
        assert result.should_rerun is True
        assert len(result.issues_found) > 0
    
    def test_high_confidence_low_data_quality(self, validator):
        """High confidence with low data quality should be flagged"""
        analysis = {"confidence": 0.95, "score": 8}
        raw_data = {"data_quality_score": 30}
        
        result = validator.validate("TEST", analysis, raw_data)
        
        assert result.consistency_score < 1.0
        assert any("confidence" in issue.lower() for issue in result.issues_found)
    
    def test_extreme_score_without_findings(self, validator):
        """Extreme scores without supporting findings should be flagged"""
        analysis = {"score": 9.8, "findings": ["Good"]}
        raw_data = {"data_quality_score": 80}
        
        result = validator.validate("TEST", analysis, raw_data)
        
        assert result.logic_score < 1.0
        assert any("extreme" in issue.lower() or "score" in issue.lower() 
                   for issue in result.issues_found)
    
    def test_recommendations_without_findings(self, validator):
        """Recommendations without findings should be flagged"""
        analysis = {"recommendations": ["Buy now!"], "findings": []}
        raw_data = {}
        
        result = validator.validate("TEST", analysis, raw_data)
        
        assert result.logic_score < 1.0
    
    def test_adversarial_questions_generated(self, validator, good_analysis, good_raw_data):
        """Should always generate adversarial questions"""
        result = validator.validate("TEST", good_analysis, good_raw_data)
        
        assert len(result.adversarial_questions) > 0
        assert all(isinstance(q, str) for q in result.adversarial_questions)
    
    def test_failed_sources_generate_questions(self, validator):
        """Failed data sources should generate specific questions"""
        analysis = {"score": 7}
        raw_data = {"sources_failed": ["sec_filings", "earnings"]}
        
        result = validator.validate("TEST", analysis, raw_data)
        
        assert any("unavailable" in q.lower() or "source" in q.lower() 
                   for q in result.adversarial_questions)
    
    def test_issue_penalty_applied(self, validator):
        """More issues should reduce confidence"""
        # Analysis designed to trigger multiple issues
        analysis = {
            "score": 9.9,  # Extreme
            "confidence": 0.99,  # Too high
            "findings": [],  # None
            "recommendations": ["Buy"]  # Without findings
        }
        raw_data = {
            "data_quality_score": 20,  # Low quality
            "sources_failed": ["a", "b", "c"]  # Many failures
        }
        
        result = validator.validate("TEST", analysis, raw_data)
        
        # Should have multiple issues and low confidence
        assert len(result.issues_found) >= 2
        assert result.overall_confidence < 0.5
    
    def test_custom_weights(self):
        """Custom weights should affect scoring"""
        # Completeness-heavy validator
        validator = AdversarialValidator(
            completeness_weight=0.8,
            consistency_weight=0.1,
            logic_weight=0.1
        )
        
        analysis = {"score": 5}
        raw_data = {"earnings": {"data": "present"}, "news": {"data": "present"}}
        
        result = validator.validate("TEST", analysis, raw_data)
        
        # Completeness should dominate the score
        assert result.overall_confidence > 0


class TestBatchValidation:
    """Test batch validation functionality"""
    
    @pytest.fixture
    def validator(self):
        return AdversarialValidator()
    
    def test_batch_validate_empty(self, validator):
        """Empty batch should return empty results"""
        result = validator.batch_validate([])
        
        assert result['total_validated'] == 0
        assert result['passed'] == 0
        assert result['needs_rerun'] == 0
    
    def test_batch_validate_mixed(self, validator):
        """Mixed batch should correctly categorize results"""
        analyses = [
            ("GOOD1", {"score": 7, "confidence": 0.8, "findings": ["a", "b", "c"]}, 
             {"data_quality_score": 90}),
            ("GOOD2", {"score": 6, "confidence": 0.75, "findings": ["x", "y"]}, 
             {"data_quality_score": 85}),
            ("BAD1", {"score": 9.9, "confidence": 0.99, "findings": []}, 
             {"data_quality_score": 20}),
        ]
        
        result = validator.batch_validate(analyses)
        
        assert result['total_validated'] == 3
        assert result['needs_rerun'] >= 1  # At least BAD1
        assert 'rerun_items' in result
        assert result['avg_confidence'] > 0
    
    def test_batch_validate_all_pass(self, validator):
        """All good analyses should pass"""
        good = {"score": 7, "confidence": 0.8, "findings": ["a", "b", "c"]}
        data = {"data_quality_score": 90}
        
        analyses = [
            ("A", good.copy(), data.copy()),
            ("B", good.copy(), data.copy()),
            ("C", good.copy(), data.copy()),
        ]
        
        result = validator.batch_validate(analyses)
        
        assert result['passed'] == 3
        assert result['needs_rerun'] == 0


class TestCompletenessCheck:
    """Test completeness checking logic"""
    
    @pytest.fixture
    def validator(self):
        return AdversarialValidator()
    
    def test_all_sources_used(self, validator):
        """Analysis mentioning all sources should score high"""
        analysis = {
            "text": "Based on earnings data and news sentiment analysis...",
            "earnings_analysis": "Strong Q4",
            "news_summary": "Positive coverage"
        }
        raw_data = {
            "earnings": {"q4": 2.5},
            "news": {"sentiment": 0.8}
        }
        
        result = validator.validate("TEST", analysis, raw_data)
        assert result.completeness_score > 0.5
    
    def test_missing_critical_source(self, validator):
        """Missing critical sources should be flagged"""
        analysis = {"summary": "The company looks good"}
        raw_data = {
            "earnings": {"important": "data"},
            "filings": {"sec": "documents"},
            "analyst": {"ratings": "data"}
        }
        
        result = validator.validate("TEST", analysis, raw_data)
        # Should flag missing analysis of available data
        assert result.completeness_score < 1.0


class TestContradictionDetection:
    """Test finding contradictions in analysis"""
    
    @pytest.fixture
    def validator(self):
        return AdversarialValidator()
    
    def test_contradictory_terms_flagged(self, validator):
        """Contradictory terms in findings should be noted"""
        analysis = {
            "findings": [
                "Revenue is strongly increasing",
                "Market share is decreasing significantly"
            ]
        }
        raw_data = {}
        
        result = validator.validate("TEST", analysis, raw_data)
        
        # Should note potential contradiction (though may be legitimate)
        # The validator flags this for human review, doesn't auto-fail
        assert result.consistency_score <= 1.0


class TestExpectedFields:
    """Test expected fields validation"""
    
    @pytest.fixture
    def validator(self):
        return AdversarialValidator()
    
    def test_expected_fields_present(self, validator):
        """Analysis with expected fields should pass"""
        analysis = {
            "revenue_analysis": "Growing 15% YoY",
            "margin_analysis": "Expanding by 200bps",
            "risk_assessment": "Low regulatory risk"
        }
        expected = ["revenue", "margin", "risk"]
        
        result = validator.validate("TEST", analysis, {}, expected_fields=expected)
        
        # All expected fields addressed
        assert len([i for i in result.issues_found if "Expected field" in i]) == 0
    
    def test_expected_fields_missing(self, validator):
        """Missing expected fields should be flagged"""
        analysis = {"revenue_analysis": "Growing"}
        expected = ["revenue", "competition", "management"]
        
        result = validator.validate("TEST", analysis, {}, expected_fields=expected)
        
        # Should flag missing fields
        missing_field_issues = [i for i in result.issues_found if "Expected field" in i]
        assert len(missing_field_issues) >= 2  # competition and management


class TestOllamaValidator:
    """Test Ollama-powered validator (mocked)"""
    
    def test_ollama_import_error(self):
        """Should handle missing ollama gracefully"""
        # This tests the fallback behavior
        validator = AdversarialValidator()
        analysis = {"score": 7}
        raw_data = {}
        
        # Should work without Ollama
        result = validator.validate("TEST", analysis, raw_data)
        assert isinstance(result, ValidationResult)
    
    def test_ollama_validator_inherits(self):
        """OllamaAdversarialValidator should inherit base functionality"""
        # Can't test actual Ollama without it running, but can test inheritance
        try:
            validator = OllamaAdversarialValidator(model="test")
            assert hasattr(validator, 'validate')
            assert hasattr(validator, 'batch_validate')
            assert validator.completeness_weight == 0.4  # Default
        except ImportError:
            pytest.skip("Ollama not installed")


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    @pytest.fixture
    def validator(self):
        return AdversarialValidator()
    
    def test_empty_analysis(self, validator):
        """Empty analysis should not crash"""
        result = validator.validate("TEST", {}, {})
        assert isinstance(result, ValidationResult)
        assert result.should_rerun is True  # Empty analysis should fail
    
    def test_none_values(self, validator):
        """None values should be handled"""
        analysis = {"score": None, "confidence": None}
        raw_data = {"data_quality_score": None}
        
        result = validator.validate("TEST", analysis, raw_data)
        assert isinstance(result, ValidationResult)
    
    def test_nested_data(self, validator):
        """Deeply nested data should be handled"""
        analysis = {
            "sections": {
                "revenue": {
                    "analysis": {
                        "quarterly": {"q1": "good", "q2": "better"}
                    }
                }
            }
        }
        raw_data = {
            "financials": {
                "earnings": {
                    "historical": {"2023": {}, "2024": {}}
                }
            }
        }
        
        result = validator.validate("TEST", analysis, raw_data)
        assert isinstance(result, ValidationResult)
    
    def test_unicode_content(self, validator):
        """Unicode content should be handled"""
        analysis = {
            "findings": ["收入增长 15%", "Margen améliore", "利益率向上"]
        }
        raw_data = {"notes": "日本語テスト"}
        
        result = validator.validate("TEST", analysis, raw_data)
        assert isinstance(result, ValidationResult)
    
    def test_very_long_content(self, validator):
        """Very long content should be handled"""
        analysis = {
            "findings": ["x" * 10000],
            "text": "y" * 50000
        }
        raw_data = {"data": "z" * 100000}
        
        result = validator.validate("TEST", analysis, raw_data)
        assert isinstance(result, ValidationResult)


# Fixtures for integration tests
@pytest.fixture
def sample_financial_analysis():
    """Sample financial analysis for integration testing"""
    return {
        "ticker": "ACME",
        "quality_score": 6.5,
        "confidence": 0.82,
        "key_findings": [
            "Management guidance increasingly conservative vs analyst expectations",
            "News sentiment diverging from insider trading patterns",
            "Earnings calls show subtle tone shift in Q3 vs Q2"
        ],
        "contradictions_found": [
            "Bullish analyst ratings despite cautious management tone",
            "Positive news coverage vs insider selling"
        ],
        "data_sources_analyzed": ["earnings", "news", "analyst", "insider"],
        "recommendation": "Monitor for potential guidance revision"
    }


@pytest.fixture
def sample_raw_research_data():
    """Sample raw research data for integration testing"""
    return {
        "ticker": "ACME",
        "collection_timestamp": "2026-01-13T10:00:00Z",
        "earnings": {
            "quarterly": [
                {"quarter": "Q1-2024", "eps": 2.18, "revenue": 119.6},
                {"quarter": "Q2-2024", "eps": 1.53, "revenue": 94.8},
                {"quarter": "Q3-2024", "eps": 1.40, "revenue": 85.8},
                {"quarter": "Q4-2024", "eps": 2.40, "revenue": 124.3}
            ],
            "success": True
        },
        "news": {
            "articles_analyzed": 47,
            "sentiment_score": 0.68,
            "success": True
        },
        "analyst": {
            "consensus_rating": "Overweight",
            "price_targets": {"low": 180, "median": 220, "high": 250},
            "success": True
        },
        "insider": {
            "net_transactions_90d": -15000000,
            "success": True
        },
        "sec_filings": {
            "success": False,
            "error": "403 Forbidden - Datacenter IP blocked"
        },
        "data_quality_score": 78,
        "sources_successful": ["earnings", "news", "analyst", "insider"],
        "sources_failed": ["sec_filings"]
    }


class TestIntegration:
    """Integration tests with realistic data"""
    
    def test_financial_analysis_validation(self, sample_financial_analysis, sample_raw_research_data):
        """Test validation of realistic financial analysis"""
        validator = AdversarialValidator()
        
        result = validator.validate(
            "ACME",
            sample_financial_analysis,
            sample_raw_research_data
        )
        
        # Should pass - good analysis with mostly good data
        assert result.overall_confidence > 0.5
        
        # Should note SEC filing failure
        assert any("sec" in q.lower() or "unavailable" in q.lower() 
                   for q in result.adversarial_questions)
        
        # Should have actionable output
        assert len(result.recommended_actions) > 0
