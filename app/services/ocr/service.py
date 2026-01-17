"""OCR Service."""

import logging
import os
import tempfile
from pathlib import Path
from typing import List

from app.core.models import OCRResult
from app.core.retry import with_retry
from app.core.config import get_settings
from app.services.ocr.providers import OCRProviderChain

logger = logging.getLogger(__name__)


def _convert_pdf_to_images(pdf_path: str) -> List[str]:
    from pdf2image import convert_from_path

    images = convert_from_path(pdf_path, dpi=200)
    image_paths = []

    for i, image in enumerate(images):
        temp_path = tempfile.mktemp(suffix=f"_page_{i}.png")
        image.save(temp_path, "PNG")
        image_paths.append(temp_path)

    return image_paths


class OCRService:
    def __init__(self):
        self.settings = get_settings()
        self.chain = OCRProviderChain(min_confidence=self.settings.min_confidence_threshold)

    def _is_pdf(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() == ".pdf"

    @with_retry(max_attempts=3, delay=1.0, backoff=2.0)
    def extract(self, image_path: str) -> OCRResult:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {image_path}")

        if self._is_pdf(image_path):
            return self._extract_from_pdf(image_path)

        return self.chain.extract(str(path), lang=self.settings.ocr_lang)

    def _extract_from_pdf(self, pdf_path: str) -> OCRResult:
        image_paths = _convert_pdf_to_images(pdf_path)

        if not image_paths:
            return OCRResult(text="", confidence=0.0, language="unknown", provider="pdf")

        all_texts = []
        total_confidence = 0.0
        provider_used = "unknown"

        try:
            for img_path in image_paths:
                result = self.chain.extract(img_path, lang=self.settings.ocr_lang)
                all_texts.append(result.text)
                total_confidence += result.confidence
                provider_used = result.provider
        finally:
            for img_path in image_paths:
                try:
                    os.unlink(img_path)
                except OSError:
                    pass

        avg_confidence = total_confidence / len(image_paths) if image_paths else 0.0

        return OCRResult(
            text="\n\n--- Page Break ---\n\n".join(all_texts),
            confidence=avg_confidence,
            language=self.settings.ocr_lang,
            provider=f"{provider_used}+pdf",
        )

    def extract_with_fallback(self, file_path: str) -> OCRResult:
        result = self.extract(file_path)

        if result.confidence >= self.settings.min_confidence_threshold:
            return result

        try:
            if self._is_pdf(file_path):
                image_paths = _convert_pdf_to_images(file_path)
                all_texts = []
                total_conf = 0.0
                try:
                    for img_path in image_paths:
                        tr_result = self.chain.extract(img_path, lang="tr")
                        all_texts.append(tr_result.text)
                        total_conf += tr_result.confidence
                finally:
                    for img_path in image_paths:
                        try:
                            os.unlink(img_path)
                        except OSError:
                            pass

                if image_paths:
                    avg_conf = total_conf / len(image_paths)
                    if avg_conf > result.confidence:
                        return OCRResult(
                            text="\n\n--- Page Break ---\n\n".join(all_texts),
                            confidence=avg_conf,
                            language="tr",
                            provider=f"{result.provider}",
                            retry_count=1,
                        )
            else:
                tr_result = self.chain.extract(file_path, lang="tr")
                if tr_result.confidence > result.confidence:
                    tr_result.retry_count = 1
                    return tr_result
        except Exception:
            pass

        return result

    def extract_with_specific_provider(
        self, file_path: str, provider_name: str, lang: str = "en"
    ) -> OCRResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if self._is_pdf(file_path):
            image_paths = _convert_pdf_to_images(file_path)
            all_texts = []
            total_conf = 0.0
            try:
                for img_path in image_paths:
                    result = self.chain.extract_with_provider(img_path, provider_name, lang=lang)
                    all_texts.append(result.text)
                    total_conf += result.confidence
            finally:
                for img_path in image_paths:
                    try:
                        os.unlink(img_path)
                    except OSError:
                        pass

            avg_conf = total_conf / len(image_paths) if image_paths else 0.0
            return OCRResult(
                text="\n\n--- Page Break ---\n\n".join(all_texts),
                confidence=avg_conf,
                language=lang,
                provider=f"{provider_name}+pdf",
            )

        return self.chain.extract_with_provider(str(path), provider_name, lang=lang)
