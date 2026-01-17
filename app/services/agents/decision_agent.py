"""Decision Agent."""

import logging
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic_ai import Agent

from app.core.config import get_settings
from app.prompts.decision_prompts import DECISION_SYSTEM_PROMPT, DECISION_USER_PROMPT
from app.core.models import InvoiceExtraction, AgentDecision
from app.core.validators import validate_invoice
from .extraction_agent import ExtractionAgent, create_parallel_extractors

logger = logging.getLogger(__name__)


class DecisionAgent:
    def __init__(self):
        self.settings = get_settings()
        self._comparison_agent = self._create_comparison_agent()

    def _create_comparison_agent(self) -> Agent:
        return Agent(
            f"openai:{self.settings.openai_model}",
            output_type=AgentDecision,
            system_prompt=DECISION_SYSTEM_PROMPT,
        )

    def _run_parallel_extractions(
        self, ocr_text: str, extractors: List[ExtractionAgent]
    ) -> List[Tuple[str, InvoiceExtraction]]:
        results = []
        with ThreadPoolExecutor(max_workers=len(extractors)) as executor:
            future_to_source = {
                executor.submit(extractor.extract, ocr_text): extractor.source_name
                for extractor in extractors
            }

            for future in as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    extraction = future.result()
                    results.append((source, extraction))
                    logger.info(f"Extraction completed from {source}")
                except Exception as e:
                    logger.error(f"Extraction failed from {source}: {e}")
        return results

    def _calculate_score(self, extraction: InvoiceExtraction) -> float:
        score = 0.0
        
        # Field completeness (30%)
        general = extraction.general_fields
        general_fields = [
            general.invoice_number,
            general.date,
            general.supplier_name,
            general.total_amount,
            general.currency,
        ]
        completeness = sum(1 for f in general_fields if f is not None) / 5
        score += completeness * 0.3
        
        # Items present (20%)
        if extraction.items:
            score += 0.2
            item_completeness = sum(
                sum(1 for v in [i.product_name, i.quantity, i.unit_price, i.total_price] if v is not None)
                for i in extraction.items
            ) / (len(extraction.items) * 4)
            score += item_completeness * 0.1
        
        # Validation score (40%)
        validations = validate_invoice(extraction)
        if validations.get("all_valid"):
            score += 0.4
        else:
            item_calcs = validations.get("item_calculations", [])
            if item_calcs:
                valid_items = sum(1 for c in item_calcs if c.get("valid"))
                score += (valid_items / len(item_calcs)) * 0.2
            
            if validations.get("tax_validation", {}).get("valid"):
                score += 0.2
        
        return min(score, 1.0)

    def _select_best_heuristic(
        self, results: List[Tuple[str, InvoiceExtraction]]
    ) -> AgentDecision:
        scored_results = [
            (source, extraction, self._calculate_score(extraction))
            for source, extraction in results
        ]
        
        scored_results.sort(key=lambda x: x[2], reverse=True)
        best_source, best_extraction, best_score = scored_results[0]
        
        reasoning = f"Selected based on quality score: {best_score:.2f}"
        if len(scored_results) > 1:
            second_source, _, second_score = scored_results[1]
            reasoning += f" (vs {second_source}: {second_score:.2f})"
        
        return AgentDecision(
            selected_source=best_source,
            confidence=best_score,
            reasoning=reasoning,
            result=best_extraction,
        )

    def _select_best_llm(
        self, 
        results: List[Tuple[str, InvoiceExtraction]], 
        ocr_text: str
    ) -> AgentDecision:
        if len(results) < 2:
            source, extraction = results[0]
            return AgentDecision(
                selected_source=source,
                confidence=0.8,
                reasoning="Only one result available",
                result=extraction,
            )
        
        source_a, result_a = results[0]
        source_b, result_b = results[1]
        
        prompt = DECISION_USER_PROMPT.format(
            source_a=source_a,
            result_a=result_a.model_dump_json(indent=2),
            source_b=source_b,
            result_b=result_b.model_dump_json(indent=2),
            ocr_text=ocr_text[:1500],
        )
        
        try:
            result = self._comparison_agent.run_sync(prompt)
            return result.output
        except Exception as e:
            logger.warning(f"LLM comparison failed, falling back to heuristic: {e}")
            return self._select_best_heuristic(results)

    def decide(self, ocr_text: str) -> AgentDecision:
        extractors = create_parallel_extractors()
        
        if len(extractors) == 1:
            extraction = extractors[0].extract(ocr_text)
            return AgentDecision(
                selected_source=extractors[0].source_name,
                confidence=self._calculate_score(extraction),
                reasoning="Single extractor mode",
                result=extraction,
            )
        
        results = self._run_parallel_extractions(ocr_text, extractors)
        
        if not results:
            raise RuntimeError("All extraction attempts failed")
        
        if len(results) == 1:
            source, extraction = results[0]
            return AgentDecision(
                selected_source=source,
                confidence=self._calculate_score(extraction),
                reasoning="Only one extraction succeeded",
                result=extraction,
            )
        
        scores = [(s, e, self._calculate_score(e)) for s, e in results]
        scores.sort(key=lambda x: x[2], reverse=True)
        
        best_score = scores[0][2]
        second_score = scores[1][2]
        
        if abs(best_score - second_score) < 0.15:
            logger.info("Scores are close, using LLM for decision")
            return self._select_best_llm(results, ocr_text)
        
        logger.info("Clear score difference, using heuristic selection")
        return self._select_best_heuristic(results)
