#!/usr/bin/env python3
"""
Kong Adversarial Validator
After expensive AI (Claude) produces analysis, Kong validates it for:
1. Completeness - Did the analyzer use all available data?
2. Consistency - Does the conclusion match the evidence?
3. Logic - Are there gaps in reasoning?
4. Adversarial Challenge - What questions weren't answered?

This implements the "cheap intelligence challenges expensive intelligence" pattern.
"""

import json
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ValidationResult:
    """Result of adversarial validation"""
    overall_confidence: float
    completeness_score: float
    consistency_score: float
    logic_score: float
    issues_found: List[str]
    adversarial_questions: List[str]
    recommended_actions: List[str]
    should_rerun: bool


class AdversarialValidator:
    """
    Kong as adversarial partner to expensive AI analysis.
    
    Pattern:
    1. Expensive AI (Claude/GPT-4) analyzes data → produces conclusion
    2. Cheap AI (Kong/local LLM) challenges the analysis
    3. Only low-confidence items go back to expensive AI
    
    This minimizes expensive API calls while maximizing quality.
    """
    
    def __init__(
        self,
        completeness_weight: float = 0.4,
        consistency_weight: float = 0.3,
        logic_weight: float = 0.3,
        confidence_threshold: float = 0.7,
        max_issues_before_rerun: int = 3
    ):
        self.completeness_weight = completeness_weight
        self.consistency_weight = consistency_weight
        self.logic_weight = logic_weight
        self.confidence_threshold = confidence_threshold
        self.max_issues_before_rerun = max_issues_before_rerun
    
    def validate(
        self,
        entity_id: str,
        analysis: Dict[str, Any],
        raw_data: Dict[str, Any],
        expected_fields: Optional[List[str]] = None
    ) -> ValidationResult:
        """
        Validate an analysis against the raw data it was based on.
        
        Args:
            entity_id: Identifier for the entity analyzed
            analysis: The AI-generated analysis to validate
            raw_data: The raw data that was provided for analysis
            expected_fields: Fields that should have been analyzed
            
        Returns:
            ValidationResult with scores and recommendations
        """
        issues = []
        adversarial_questions = []
        
        # 1. Completeness Check
        completeness_score, completeness_issues = self._check_completeness(
            analysis, raw_data, expected_fields
        )
        issues.extend(completeness_issues)
        
        # 2. Consistency Check
        consistency_score, consistency_issues = self._check_consistency(
            analysis, raw_data
        )
        issues.extend(consistency_issues)
        
        # 3. Logic Check
        logic_score, logic_issues = self._check_logic(analysis, raw_data)
        issues.extend(logic_issues)
        
        # 4. Generate Adversarial Questions
        adversarial_questions = self._generate_adversarial_questions(
            analysis, raw_data, issues
        )
        
        # Calculate overall confidence
        overall_confidence = (
            completeness_score * self.completeness_weight +
            consistency_score * self.consistency_weight +
            logic_score * self.logic_weight
        )
        
        # Apply issue penalty
        issue_penalty = min(len(issues) * 0.05, 0.3)
        overall_confidence = max(0, overall_confidence - issue_penalty)
        
        # Determine if rerun is needed
        should_rerun = (
            overall_confidence < self.confidence_threshold or
            len(issues) > self.max_issues_before_rerun
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            completeness_score,
            consistency_score,
            logic_score,
            issues,
            adversarial_questions
        )
        
        return ValidationResult(
            overall_confidence=round(overall_confidence, 3),
            completeness_score=round(completeness_score, 3),
            consistency_score=round(consistency_score, 3),
            logic_score=round(logic_score, 3),
            issues_found=issues,
            adversarial_questions=adversarial_questions,
            recommended_actions=recommendations,
            should_rerun=should_rerun
        )
    
    def _check_completeness(
        self,
        analysis: Dict,
        raw_data: Dict,
        expected_fields: Optional[List[str]]
    ) -> Tuple[float, List[str]]:
        """Check if all available data was analyzed.
        
        Uses multiple strategies to detect source usage:
        1. Direct key matching (source name appears in analysis)
        2. Semantic matching (related terms appear)
        3. Structural matching (analysis has corresponding sections)
        """
        issues = []
        
        # Strategy 1: Find all non-empty top-level keys in raw_data
        available_sources = set()
        for key, value in raw_data.items():
            if value and key not in ('data_quality_score', 'sources_failed', 
                                      'sources_successful', 'collection_timestamp',
                                      'ticker', 'entity_id'):
                # Check if source has actual data (not just metadata)
                if isinstance(value, dict):
                    if value.get('success', True) and any(v for k, v in value.items() 
                                                          if k != 'success'):
                        available_sources.add(key)
                elif value:
                    available_sources.add(key)
        
        # Strategy 2: Build semantic mappings for common sources
        semantic_mappings = {
            'earnings': ['earnings', 'eps', 'revenue', 'quarterly', 'q1', 'q2', 'q3', 'q4', 
                        'profit', 'income', 'financial'],
            'news': ['news', 'sentiment', 'media', 'coverage', 'article', 'press'],
            'analyst': ['analyst', 'rating', 'target', 'consensus', 'upgrade', 'downgrade',
                       'buy', 'sell', 'hold', 'overweight', 'underweight'],
            'insider': ['insider', 'transaction', 'executive', 'director', 'officer',
                       'purchase', 'sale', 'filing'],
            'sec': ['sec', 'filing', '10-k', '10-q', '8-k', 'proxy', 'edgar'],
            'filings': ['filing', 'regulatory', 'disclosure', 'sec', 'annual', 'quarterly']
        }
        
        # Convert analysis to searchable string (handles nested structures)
        def flatten_to_string(obj, depth=0) -> str:
            if depth > 10:  # Prevent infinite recursion
                return str(obj)
            if isinstance(obj, dict):
                parts = []
                for k, v in obj.items():
                    parts.append(str(k))
                    parts.append(flatten_to_string(v, depth + 1))
                return ' '.join(parts)
            elif isinstance(obj, list):
                return ' '.join(flatten_to_string(item, depth + 1) for item in obj)
            else:
                return str(obj) if obj else ''
        
        analysis_text = flatten_to_string(analysis).lower()
        
        # Strategy 3: Check which sources are referenced
        sources_referenced = set()
        for source in available_sources:
            source_lower = source.lower()
            
            # Direct match
            if source_lower in analysis_text:
                sources_referenced.add(source)
                continue
            
            # Semantic match - check if any related terms appear
            related_terms = semantic_mappings.get(source_lower, [source_lower])
            matches = sum(1 for term in related_terms if term in analysis_text)
            
            # Require at least 2 related terms for semantic match (reduces false positives)
            if matches >= 2:
                sources_referenced.add(source)
                continue
            
            # Structural match - check if analysis has a section for this source
            analysis_keys = set()
            def collect_keys(obj, depth=0):
                if depth > 5:
                    return
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        analysis_keys.add(str(k).lower())
                        collect_keys(v, depth + 1)
            collect_keys(analysis)
            
            if source_lower in analysis_keys or any(
                term in key for term in related_terms for key in analysis_keys
            ):
                sources_referenced.add(source)
        
        # Calculate completeness score
        if available_sources:
            completeness = len(sources_referenced) / len(available_sources)
        else:
            completeness = 1.0  # No sources to check = complete
        
        # Flag critical missing sources
        critical_sources = {'earnings', 'filings', 'analyst', 'news', 'insider', 'sec'}
        for source in available_sources:
            if source.lower() in critical_sources or any(
                crit in source.lower() for crit in critical_sources
            ):
                if source not in sources_referenced:
                    issues.append(
                        f"Critical data source '{source}' available but not clearly analyzed"
                    )
        
        # Check expected fields if provided
        if expected_fields:
            for field in expected_fields:
                field_lower = field.lower()
                # Use same semantic matching for expected fields
                related = semantic_mappings.get(field_lower, [field_lower])
                if not any(term in analysis_text for term in related):
                    issues.append(f"Expected field '{field}' not addressed in analysis")
        
        return completeness, issues
    
    def _check_consistency(
        self,
        analysis: Dict,
        raw_data: Dict
    ) -> Tuple[float, List[str]]:
        """Check if analysis conclusions are internally consistent"""
        issues = []
        consistency_score = 1.0
        
        # Extract key metrics from analysis
        confidence = analysis.get('confidence', 0)
        score = analysis.get('score') or analysis.get('quality_score', 0)
        findings = analysis.get('findings', []) or analysis.get('key_findings', [])
        
        # Extract metrics from raw data
        data_quality = raw_data.get('data_quality_score', 100)
        sources_failed = raw_data.get('sources_failed', [])
        
        # Consistency checks
        
        # High confidence with low data quality
        if confidence and confidence > 0.8 and data_quality < 50:
            issues.append(
                f"High confidence ({confidence:.0%}) despite low data quality ({data_quality}%)"
            )
            consistency_score *= 0.6
        
        # High score with many failed sources
        if score and score > 7 and len(sources_failed) > 2:
            issues.append(
                f"High score ({score}) but {len(sources_failed)} data sources failed"
            )
            consistency_score *= 0.7
        
        # Few findings but high confidence
        if confidence and confidence > 0.8 and len(findings) < 2:
            issues.append(
                f"High confidence ({confidence:.0%}) but only {len(findings)} findings"
            )
            consistency_score *= 0.8
        
        # Check for contradictions in findings
        findings_str = ' '.join(str(f) for f in findings).lower()
        contradiction_pairs = [
            ('positive', 'negative'),
            ('increasing', 'decreasing'),
            ('strong', 'weak'),
            ('improving', 'declining')
        ]
        
        for pos, neg in contradiction_pairs:
            if pos in findings_str and neg in findings_str:
                # This might be legitimate (describing different aspects)
                # but worth flagging for review
                issues.append(
                    f"Potentially contradictory terms in findings: '{pos}' and '{neg}'"
                )
                consistency_score *= 0.9
        
        return consistency_score, issues
    
    def _check_logic(
        self,
        analysis: Dict,
        raw_data: Dict
    ) -> Tuple[float, List[str]]:
        """Check if conclusions logically follow from evidence"""
        issues = []
        logic_score = 1.0
        
        # Get conclusion strength
        confidence = analysis.get('confidence', 0)
        score = analysis.get('score') or analysis.get('quality_score', 0)
        
        # Get evidence strength
        sources_successful = raw_data.get('sources_successful', [])
        data_quality = raw_data.get('data_quality_score', 0)
        
        # Logic check: Strong conclusions need strong evidence
        if confidence and confidence > 0.9:
            if len(sources_successful) < 4:
                issues.append(
                    f"Very high confidence ({confidence:.0%}) with limited data sources "
                    f"({len(sources_successful)} successful)"
                )
                logic_score *= 0.7
        
        # Logic check: Extreme scores need justification
        if score:
            if score > 9 or score < 1:
                findings = analysis.get('findings', []) or analysis.get('key_findings', [])
                if len(findings) < 3:
                    issues.append(
                        f"Extreme score ({score}) without sufficient supporting findings"
                    )
                    logic_score *= 0.6
        
        # Logic check: Recommendations should match findings
        recommendations = analysis.get('recommendations', [])
        findings = analysis.get('findings', []) or analysis.get('key_findings', [])
        
        if recommendations and not findings:
            issues.append("Recommendations provided without supporting findings")
            logic_score *= 0.7
        
        return logic_score, issues
    
    def _generate_adversarial_questions(
        self,
        analysis: Dict,
        raw_data: Dict,
        existing_issues: List[str]
    ) -> List[str]:
        """Generate challenging questions the analysis should address"""
        questions = []
        
        # Data completeness questions
        sources_failed = raw_data.get('sources_failed', [])
        if sources_failed:
            questions.append(
                f"How confident can we be with {len(sources_failed)} data sources unavailable?"
            )
        
        data_quality = raw_data.get('data_quality_score', 100)
        if data_quality < 80:
            questions.append(
                f"Data quality is only {data_quality}% - what are we potentially missing?"
            )
        
        # Temporal questions
        questions.append("Is this analysis based on current data or historical trends?")
        questions.append("How might this conclusion change in 3-6 months?")
        
        # Scope questions
        questions.append("What factors outside the available data could affect this conclusion?")
        questions.append("How does this compare to industry peers/benchmarks?")
        
        # Confidence questions
        confidence = analysis.get('confidence', 0)
        if confidence and confidence > 0.8:
            questions.append("What would cause you to lower your confidence in this analysis?")
        elif confidence and confidence < 0.5:
            questions.append("What additional data would increase confidence?")
        
        # Issue-specific questions
        if any('contradictory' in issue.lower() for issue in existing_issues):
            questions.append("Are the contradictions in findings a bug or a feature?")
        
        return questions
    
    def _generate_recommendations(
        self,
        completeness: float,
        consistency: float,
        logic: float,
        issues: List[str],
        questions: List[str]
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if completeness < 0.8:
            recommendations.append("ADD_DATA: Collect missing data sources before reanalysis")
        
        if consistency < 0.7:
            recommendations.append("REVIEW: Manual review needed for inconsistencies")
        
        if logic < 0.7:
            recommendations.append("RERUN: Conclusions may not follow from evidence")
        
        if len(issues) > 5:
            recommendations.append("ESCALATE: Too many issues for automated resolution")
        
        if len(questions) > 4:
            recommendations.append("DEEP_DIVE: Many unanswered questions require investigation")
        
        if not recommendations:
            recommendations.append("APPROVED: Analysis passes adversarial validation")
        
        return recommendations
    
    def batch_validate(
        self,
        analyses: List[Tuple[str, Dict, Dict]]
    ) -> Dict[str, Any]:
        """
        Validate multiple analyses and return summary.
        
        Args:
            analyses: List of (entity_id, analysis, raw_data) tuples
            
        Returns:
            Summary with overall stats and items needing rerun
        """
        results = []
        needs_rerun = []
        
        for entity_id, analysis, raw_data in analyses:
            result = self.validate(entity_id, analysis, raw_data)
            results.append((entity_id, result))
            
            if result.should_rerun:
                needs_rerun.append({
                    'entity_id': entity_id,
                    'confidence': result.overall_confidence,
                    'issues': result.issues_found,
                    'recommendations': result.recommended_actions
                })
        
        # Calculate summary stats
        confidences = [r.overall_confidence for _, r in results]
        
        return {
            'total_validated': len(results),
            'passed': sum(1 for _, r in results if not r.should_rerun),
            'needs_rerun': len(needs_rerun),
            'avg_confidence': sum(confidences) / len(confidences) if confidences else 0,
            'min_confidence': min(confidences) if confidences else 0,
            'max_confidence': max(confidences) if confidences else 0,
            'rerun_items': needs_rerun
        }


class OllamaAdversarialValidator(AdversarialValidator):
    """
    Adversarial validator that uses Ollama for deeper challenge generation.
    
    Combines rule-based validation with LLM-powered questioning.
    """
    
    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.model = model
        self.base_url = base_url
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            try:
                import ollama
                self._client = ollama.Client(host=self.base_url)
            except ImportError:
                raise ImportError("Install ollama: pip install ollama")
        return self._client
    
    def _generate_adversarial_questions(
        self,
        analysis: Dict,
        raw_data: Dict,
        existing_issues: List[str]
    ) -> List[str]:
        """Use LLM to generate deeper adversarial questions"""
        # Get base questions from parent
        base_questions = super()._generate_adversarial_questions(
            analysis, raw_data, existing_issues
        )
        
        try:
            # Ask LLM for additional challenges
            prompt = f"""You are an adversarial reviewer. Given this analysis and data, 
generate 3 challenging questions that poke holes in the analysis.

Analysis summary: {json.dumps(analysis, indent=2)[:1000]}

Data quality: {raw_data.get('data_quality_score', 'unknown')}%
Sources failed: {raw_data.get('sources_failed', [])}

Existing issues found: {existing_issues}

Generate exactly 3 adversarial questions, one per line.
Focus on what could be wrong, missing, or misleading."""

            response = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.7}
            )
            
            llm_questions = response['message']['content'].strip().split('\n')
            llm_questions = [q.strip() for q in llm_questions if q.strip()][:3]
            
            return base_questions + llm_questions
            
        except Exception:
            # Fall back to base questions if LLM fails
            return base_questions
