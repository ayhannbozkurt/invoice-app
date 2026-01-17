"""Extraction Agent."""

import logging
from typing import Optional

from pydantic_ai import Agent

from app.core.config import get_settings
from app.core.models import InvoiceGeneral, InvoiceExtraction
from app.prompts.extraction_prompts import EXTRACTION_SYSTEM_PROMPT, EXTRACTION_USER_PROMPT

logger = logging.getLogger(__name__)


class ExtractionAgent:
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.settings = get_settings()
        self.provider = provider or self.settings.llm_provider
        self.model = model or self._get_default_model()
        self._agent = self._create_agent()

    def _get_default_model(self) -> str:
        if self.provider == "ollama":
            return self.settings.ollama_model
        return self.settings.openai_model

    def _get_model_string(self) -> str:
        if self.provider == "ollama":
            return f"ollama:{self.model}"
        return f"openai:{self.model}"

    def _create_agent(self) -> Agent:
        return Agent(
            self._get_model_string(),
            output_type=InvoiceExtraction,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
        )

    @property
    def source_name(self) -> str:
        return f"{self.provider}:{self.model}"

    def extract(self, ocr_text: str) -> InvoiceExtraction:
        if not ocr_text.strip():
            logger.warning("Empty OCR text provided to extraction agent")
            return InvoiceExtraction(general_fields=InvoiceGeneral(), items=[])

        prompt = EXTRACTION_USER_PROMPT.format(ocr_text=ocr_text)
        logger.info(f"Extracting invoice data using {self.source_name}")

        try:
            result = self._agent.run_sync(prompt)
            extraction = result.output
            
            logger.info(f"Extracted {len(extraction.items)} items using {self.source_name}")
            return extraction
            
        except Exception as e:
            logger.error(f"Extraction failed with {self.source_name}: {e}")
            raise


def create_parallel_extractors() -> list[ExtractionAgent]:
    settings = get_settings()
    agents = []
    
    agents.append(ExtractionAgent(provider="openai", model=settings.openai_model))
    
    if settings.parallel_llm_enabled:
        try:
            agents.append(ExtractionAgent(provider="ollama", model=settings.ollama_model))
            logger.info("Parallel LLM enabled with OpenAI + Ollama")
        except Exception as e:
            logger.warning(f"Ollama not available for parallel extraction: {e}")
    
    return agents
