"""OCR Provider implementations with fallback support."""

import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List

from app.core.models import OCRResult

logger = logging.getLogger(__name__)


class OCRProvider(ABC):
    """Base class for OCR providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        pass

    @abstractmethod
    def extract(self, image_path: str, lang: str = "en") -> OCRResult:
        """Extract text from image."""
        pass


class PaddleOCRProvider(OCRProvider):
    """PaddleOCR - primary OCR engine."""

    _instances: Dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "paddleocr"

    def extract(self, image_path: str, lang: str = "en") -> OCRResult:
        os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"
        
        # Cache PaddleOCR instance to avoid reloading model
        if lang not in self._instances:
            from paddleocr import PaddleOCR
            logger.info(f"Initializing PaddleOCR for language: {lang}")
            self._instances[lang] = PaddleOCR(lang=lang, show_log=False)
            
        ocr = self._instances[lang]
        result = ocr.predict(image_path)

        if not result or not result[0]:
            return OCRResult(text="", confidence=0.0, language=lang, provider=self.name)

        page = result[0]
        texts = page.get("rec_texts", [])
        scores = page.get("rec_scores", [])

        return OCRResult(
            text="\n".join(t for t in texts if t),
            confidence=sum(scores) / len(scores) if scores else 0.0,
            language=lang,
            provider=self.name,
        )


class EasyOCRProvider(OCRProvider):
    """EasyOCR - fallback OCR engine."""

    _readers: Dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "easyocr"

    def extract(self, image_path: str, lang: str = "en") -> OCRResult:
        import easyocr

        if lang not in self._readers:
            logger.info(f"Initializing EasyOCR for language: {lang}")
            self._readers[lang] = easyocr.Reader([lang], gpu=False)

        result = self._readers[lang].readtext(image_path)

        if not result:
            return OCRResult(text="", confidence=0.0, language=lang, provider=self.name)

        texts = [r[1] for r in result]
        scores = [r[2] for r in result]

        return OCRResult(
            text="\n".join(texts),
            confidence=sum(scores) / len(scores) if scores else 0.0,
            language=lang,
            provider=self.name,
        )


class OCRProviderChain:
    """Runs OCR providers in sequence until one succeeds with good confidence."""

    def __init__(self, min_confidence: float = 0.5):
        self.providers: List[OCRProvider] = [PaddleOCRProvider(), EasyOCRProvider()]
        self.min_confidence = min_confidence

    def extract(self, image_path: str, lang: str = "en") -> OCRResult:
        """Try each provider, return best result."""
        results: List[OCRResult] = []

        for provider in self.providers:
            try:
                result = provider.extract(image_path, lang)
                results.append(result)

                if result.confidence >= self.min_confidence:
                    logger.info(f"{provider.name}: success (conf={result.confidence:.2f})")
                    return result

                logger.warning(f"{provider.name}: low confidence ({result.confidence:.2f})")
            except Exception as e:
                logger.error(f"{provider.name}: failed - {e}")
                # Log usage of fallback implicitly if this was the first provider
                if provider != self.providers[-1]:
                     logger.info(f"Falling back to next provider...")

        if results:
            return max(results, key=lambda r: r.confidence)

        raise RuntimeError("All OCR providers failed")

    def extract_with_provider(
        self, image_path: str, provider_name: str, lang: str = "en"
    ) -> OCRResult:
        """Run a specific provider by name."""
        provider = next(
            (p for p in self.providers if p.name == provider_name), None
        )
        if not provider:
            raise ValueError(f"Unknown OCR provider: {provider_name}")
        return provider.extract(image_path, lang)
