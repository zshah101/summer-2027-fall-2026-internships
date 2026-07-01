"""The single normalized job record every connector produces.

Keeping one shape means the pipeline, store, and renderer never care which ATS a
role came from — adding a source touches only its connector.
"""

from __future__ import annotations

from dataclasses import dataclass

# Fields that exist only during a run and must never be written to the store
# (descriptions are multi-KB blobs; we persist the classification, not the text).
TRANSIENT_FIELDS = ("description",)


@dataclass
class Job:
    id: str               # stable: "<source>:<company_slug>:<external_id>"
    source: str
    company: str
    company_slug: str
    title: str
    location: str
    url: str
    posted_at: str | None = None   # real publish date, or None when unknown
    season: str = "Unspecified"    # cycle label, assigned by the pipeline
    category: str = "Other"
    sponsorship: str = "unknown"   # citizens-only | no-sponsorship | offers | unknown
    salary: str | None = None      # pay text when the ATS exposes it (Ashby/Lever/Breezy)
    description: str | None = None  # transient: raw posting text, used for classification
