from pydantic import BaseModel, Field
from typing import List

class TermGroup(BaseModel):
    main_terms: List[str] = Field(default_factory=list)
    synonyms: List[str] = Field(default_factory=list)
    excluded_terms: List[str] = Field(default_factory=list)

class SearchTerms(BaseModel):
    brand: TermGroup = Field(default_factory=TermGroup)
    competitors: TermGroup = Field(default_factory=TermGroup)

class SearchResultItem(BaseModel):
    link: str
    htmlSnippet: str

class PreviewResult(BaseModel):
    brand_results: List[SearchResultItem]
    competitor_results: List[SearchResultItem]
