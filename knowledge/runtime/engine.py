"""TrustLens Phase 3 P3-WP8 — the authoritative runtime engine version.

``ENGINE_VERSION`` is the single source of truth for ``provenance.engine_version`` in every assembled
``DetectionResult`` (result assembly, DET-001 §16 / pipeline stage 19). It identifies the DETERMINISTIC
ENGINE CODE (WP2 loader → WP3 evaluator → WP4 suppression → WP5 aggregation → WP6 explanation → WP8
assembly), NOT the knowledge bundle — the knowledge content is pinned separately by ``bundle_content_digest``
and ``component_versions`` (ADR-0004). The two provenance axes are kept deliberately distinct.

Governance (ratified P3-WP8):
  * engine_version belongs to executable runtime code and lives ONLY here — never duplicated, never a bundle
    member, never a caller argument. WP8 pins it into provenance; a caller cannot override it.
  * It is SemVer (``result-contract`` regex ``^\\d+\\.\\d+\\.\\d+(-[0-9A-Za-z.-]+)?$``).
  * A future change to deterministic runtime semantics or the integration/result contract requires a
    deliberate, governed bump of this constant (recorded in DET-001).
"""

from __future__ import annotations

import re

# The deterministic-engine version for Phase-3 GA. Bump ONLY under governance when WP3–WP8 semantics change.
ENGINE_VERSION = "1.0.0"

# detection-result.schema.json provenance.engine_version pattern. Enforcement is AUTHORITATIVE at result
# assembly (the schema validates provenance.engine_version), so a malformed constant is caught there and only
# by P3-WP8 — it deliberately does NOT raise at import, which would break every runtime importer instead of
# the one integration gate that owns the constant. Exposed for the WP8 validator's explicit format check.
ENGINE_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")
