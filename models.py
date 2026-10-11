"""Strict research contracts: a finding without evidence is never displayed as fact."""
import ipaddress
import json
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field, field_validator, model_validator


def public_url(value: str) -> str:
    value = value.strip()
    if '://' not in value:
        value = 'https://' + value
    try:
        parts = urlsplit(value)
        host = (parts.hostname or '').lower().rstrip('.')
        port = parts.port
    except ValueError as exc:
        raise ValueError('Enter a valid public website URL.') from exc
    if parts.scheme not in ('https', 'http') or not host or parts.username or parts.password:
        raise ValueError('Use a public HTTP or HTTPS website without credentials.')
    if port not in (None, 80, 443) or '.' not in host or host.endswith(('.local', '.localhost', '.internal', '.test', '.invalid', '.example')):
        raise ValueError('Use a public website, not a local or internal address.')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if any(c.isspace() for c in host) or '%' in host or '\\' in value:
            raise ValueError('Enter a valid public website URL.')
    else:
        if not address.is_global:
            raise ValueError('Private and reserved IP addresses are not allowed.')
    if host in ('localhost', 'metadata.google.internal'):
        raise ValueError('Local addresses are not allowed.')
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or '/', parts.query, ''))


class ResearchRequest(BaseModel):
    url: str = Field(min_length=3, max_length=2048)
    competitor_limit: int = Field(default=3, ge=1, le=3)
    use_vault: bool = False
    credential_item_ids: list[str] = Field(default_factory=list, max_length=5)
    authorize_portal: bool = False

    @model_validator(mode='after')
    def vault_gate(self):
        if self.use_vault and (not self.authorize_portal or not self.credential_item_ids):
            raise ValueError('Vault research requires a selected credential and explicit portal authorization.')
        if not self.use_vault and (self.credential_item_ids or self.authorize_portal):
            raise ValueError('Portal credentials and authorization require Vault mode.')
        if self.use_vault and urlsplit(self.url).scheme != 'https':
            raise ValueError('Authenticated research requires HTTPS.')
        if any(not value.startswith('cred:') or len(value) > 1024 for value in self.credential_item_ids):
            raise ValueError('Invalid Vault credential reference.')
        return self

    @field_validator('url')
    @classmethod
    def valid_url(cls, value: str) -> str:
        return public_url(value)


class Finding(BaseModel):
    text: str | None = Field(default=None, max_length=3000)
    sources: list[str] = Field(default_factory=list, max_length=32)

    @field_validator('sources')
    @classmethod
    def valid_sources(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(public_url(value) for value in values))

    @model_validator(mode='after')
    def require_evidence(self):
        if not self.sources or not self.text or not self.text.strip():
            self.text = None
            self.sources = []
        return self


class Company(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    website: str
    positioning: Finding = Field(default_factory=Finding)
    products: Finding = Field(default_factory=Finding)
    pricing: Finding = Field(default_factory=Finding)
    customers: Finding = Field(default_factory=Finding)
    differentiation: Finding = Field(default_factory=Finding)
    limitations: list[str] = Field(default_factory=list, max_length=12)

    @field_validator('website')
    @classmethod
    def valid_website(cls, value: str) -> str:
        return public_url(value)

    @model_validator(mode='after')
    def has_research(self):
        if not any(getattr(self, key).text for key in ('positioning', 'products', 'pricing', 'customers', 'differentiation')):
            raise ValueError('No source-backed findings were returned for this company.')
        return self


class Candidate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    website: str
    reason: Finding

    @field_validator('website')
    @classmethod
    def valid_website(cls, value: str) -> str:
        return public_url(value)


class Discovery(BaseModel):
    company: Company
    competitors: list[Candidate] = Field(default_factory=list, max_length=12)


def decode_result(raw):
    """Accept documented result/result.result and legacy resultJson envelopes."""
    for _ in range(5):
        if isinstance(raw, str):
            raw = raw.strip()
            if raw.startswith('```'):
                raw = raw.split('\n', 1)[1].rsplit('```', 1)[0].strip()
            raw = json.loads(raw)
        elif isinstance(raw, dict) and set(raw) == {'result'}:
            raw = raw['result']
        else:
            break
    if not isinstance(raw, dict):
        raise ValueError('TinyFish returned no structured research object.')
    return raw
