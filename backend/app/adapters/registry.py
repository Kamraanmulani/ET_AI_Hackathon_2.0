"""
app/adapters/registry.py — Registry for DocumentAdapters.
"""
from typing import Optional, Dict, Type

from app.adapters.base import DocumentAdapter
from app.adapters.spreadsheet import SpreadsheetAdapter
from app.adapters.pdf import PDFTextAdapter
from app.adapters.email import EmailAdapter

# Add more adapters as they are built
ADAPTERS: list[Type[DocumentAdapter]] = [
    SpreadsheetAdapter,
    PDFTextAdapter,
    EmailAdapter,
]

def get_adapter_for_extension(extension: str) -> Optional[DocumentAdapter]:
    ext = extension.lower()
    for adapter_class in ADAPTERS:
        if ext in adapter_class.supported_extensions:
            return adapter_class()
    return None
