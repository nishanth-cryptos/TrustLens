"""S4 deterministic scam-indicator extraction (PLAN-001 S4; KB-002 extraction contracts).

Turns the exact bytes of one FINALIZED synthetic text evidence item into governed, immutable inputs for the existing
Phase-3 engine: an input envelope (input-envelope.schema.json), normalized observations (observation.schema.json) and
indicator observations (indicator-observation.schema.json), plus the input-support state the engine decides on first.

- S4.1 The envelope is derived from the original bytes read through the protected evidence store, after the caller's
  case access is authorized, the item is FINALIZED and its digest and length re-verify. The read is audited.
- S4.2 Normalization is NFKC per character cluster, invisible-format removal and whitespace collapse. Every normalized
  character keeps its raw origin, so offsets index normalized_text and raw_span is the exact submitted text.
- S4.3 Each occurrence carries polarity (negation), attribution (first party, reported, quoted, hypothetical), mood,
  actor/action/target, and payment direction where one is stated.
- S4.4 Every indicator id is checked against the ACTIVE bundle (registry polarity, family partition, negative-library
  status), every artefact is schema-validated, and the set passes the engine's own governed validation boundary
  (build_validated_context) before it is returned.

The extractor never emits a verdict, risk, score or result. Only occurrences that are affirmed and first party
project positive indicators; negated, reported, quoted and hypothetical occurrences are kept as observations (and as
the negative indicators they evidence). Unsupported language, insufficient information, malformed input and unavailable
extraction are explicit states; none of them is benign. Fixtures may test this module but never replace it.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

import psycopg
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from knowledge.ai.governance import canonical_json
from knowledge.runtime.observations import build_validated_context
from knowledge.runtime.runtime_knowledge import freeze

from .audit import AuditEvent, AuditUnavailable, append as audit_append
from .content_store import ContentStoreUnavailable, IntegrityFailure
from .principals import SCHEMA

EXTRACTOR_ID = "trustlens-deterministic-extractor"
EXTRACTOR_VERSION = "1.0.0"
NORMALIZER = {"id": "trustlens-text-normalizer", "version": "1.0.0"}
ENVELOPE_VERSION = "1.0.0"
MAX_TEXT_BYTES = 64 * 1024                     # the S2 evidence bound; extraction never reads more
MIN_WORDS = 3                                  # below this, and with nothing extracted: INSUFFICIENT_INFORMATION
EVALUATION_ROLES = ("USER", "ANALYST")          # createEvaluations (api-v1.json): CASE_ACCESS, the content stays server-side
CHANNELS = {"SMS": "CH-01", "CHAT_MESSAGE": "CH-02", "EMAIL": "CH-03", "URL": "CH-07"}
INPUT_TYPES = ("TEXT", "SMS", "CHAT_MESSAGE", "EMAIL", "URL", "OCR_TEXT", "SCREENSHOT_DERIVED_TEXT", "DOCUMENT_TEXT",
               "USER_NARRATIVE")
SUPPORTED_TEXT_MEDIA = "text/plain; charset=utf-8"

_ROOT = Path(__file__).resolve().parents[3]
_SCHEMAS = _ROOT / "knowledge" / "schemas"
_FORBIDDEN_KEYS = {"verdict", "risk", "risk_score", "risk_level", "severity", "is_scam", "scam", "scam_verdict",
                   "finding", "decision", "label", "classification", "malicious", "outcome"}


class ExtractionRefused(Exception):
    """The caller may not extract this item (masked NOT_FOUND / FORBIDDEN) or the item is not extractable."""

    def __init__(self, category: str):
        super().__init__(category)
        self.category = category


class ExtractionUnavailable(Exception):
    """Extraction cannot run now (knowledge not ready, store or audit unavailable, integrity failure). Never benign."""

    def __init__(self, category: str):
        super().__init__(category)
        self.category = category


class ExtractionContractError(RuntimeError):
    """The extractor produced something the governed contracts reject. A defect; nothing is returned."""


# ================================================================ the pattern pack (versioned, digest-pinned)
_D = r"(?:(?:the|your|ur|this|that|my|an?|our)\s+)"
_AMOUNT = r"(?:rs\.?|inr|₹)\s*(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
_CRED_VERB = (r"(?:ask\s+you\s+to\s+(?:share|send|give|tell|provide|confirm|forward|disclose|reveal)|ask\s+(?:you\s+)?for"
              r"|share|send|give|tell|provide|confirm|forward|disclose|reveal|read\s+out|submit|reply\s+with|enter|type"
              r"|update|re-?enter|re-?submit"
              r"|request)")
_OTP = (r"(?:otp(?:\s+code)?|one[\s-]time\s+(?:password|passcode|pin|code)|verification\s+code|security\s+code"
        r"|login\s+code|\d[\s-]?digit\s+code|(?:four|six|4|6)[\s-]digit\s+code|code\s+(?:you|we)\s+(?:just\s+)?(?:received|got|sent))")
_CVV = r"(?:cvv\d?|cvc|card\s+verification\s+(?:value|code))"
_CARD = r"(?:(?:full\s+|complete\s+|16[\s-]digit\s+)?(?:debit\s+|credit\s+|atm\s+)?card\s+(?:number|no\.?|details))"
_PASSWORD = (r"(?:net[\s-]?banking\s+(?:password|credentials|login)|login\s+(?:credentials|details)|password|passcode"
             r"|credentials|atm\s+pin)")
_REMOTE_APPS = (r"(anydesk|any\s+desk|teamviewer|team\s+viewer|airdroid|quick\s*support|rustdesk|ultraviewer|ammyy"
                r"|supremo|splashtop)")

PATTERNS: dict[str, str] = {
    # credentials (FAM-CREDENTIAL-REQUEST, FAM-VERIFICATION-CAPTURE); the noun decides the credential kind
    "credential_request": rf"\b{_CRED_VERB}\s+(?:(?:me|us)\s+)?{_D}?(?:[\w-]+\s+){{0,2}}?"
                          rf"(?:(?P<otp>{_OTP})|(?P<cvv>{_CVV})|(?P<card>{_CARD})|(?P<pwd>{_PASSWORD}))\b"
                          r"(?:\s+(?:you|we)\s+(?:just\s+)?(?:received|got|sent(?:\s+you)?))?",
    "credential_pronoun": rf"\b{_CRED_VERB}\s+(?:it|this|these|them)\b",
    "otp_delivered": r"\b(?:your|the)\s+(?:otp|one[\s-]time\s+password|verification\s+code|code)\s*(?:is|:)\s*:?\s*\d{4,8}\b"
                     r"|\b\d{4,8}\s+is\s+your\s+(?:otp|one[\s-]time\s+password|verification\s+code)\b",
    "otp_mention": r"\b(?:otp|one[\s-]time\s+password|verification\s+code)\b",
    # UPI PIN (FAM-UPI-PIN-CONTEXT) and the stated payment direction (FAM-PAYMENT-DIRECTION)
    "upi_pin": r"\b(?:enter|type|input|put\s+in|provide|share|give|tell|send)\s+(?:in\s+)?(?:your\s+|the\s+|ur\s+)?(?:upi\s+(?:m?pin)|mpin)\b",
    "direction_receive": rf"\bto\s+(?:receive|get|claim|collect|accept)\b(?:\s+(?:the\s+|your\s+)?(?:money|amount|refund|payment|cashback|prize))?(?:\s+{_AMOUNT})?",
    "direction_pay": rf"\bto\s+(?:pay|send|transfer|make\s+(?:the\s+)?payment)\b(?:\s+(?:the\s+)?(?P<merchant>merchant|shop|store|seller|shopkeeper|biller))?(?:\s+{_AMOUNT})?",
    # payment requests (FAM-PAYMENT-REQUEST) and task monetisation (FAM-TASK-MONETISATION)
    "immediate_payment": r"\b(?:pay|make\s+(?:the\s+)?payment|clear\s+(?:the\s+|your\s+)?(?:dues|bill)|transfer\s+(?:the\s+)?(?:amount|money|funds))"
                         rf"(?:\s+{_AMOUNT})?\s+(?:now|immediately|right\s+now|right\s+away|urgently|asap|at\s+once)\b",
    "payment_demand": rf"\b(?:pay|transfer|send)\s+(?:{_AMOUNT}|the\s+(?:amount|fee|charges?|dues|fine|penalty|balance)|money|funds)",
    "upfront_fee": r"\b(?:pay|deposit|transfer|send)\s+(?:a\s+|the\s+)?(?:(?:rs\.?|inr|₹)\s*[\d,]+(?:\.\d+)?\s+(?:as\s+)?)?(?:registration|processing|activation"
                   r"|joining|clearance|customs|release|refundable|advance|upfront|delivery|redelivery|re-delivery|shipping|placement|training"
                   r"|application|verification|onboarding|kit|security)\s+(?:fee|charges?|deposit|amount)",
    "explicit_no_fee": r"\bno\s+(?:registration\s+|joining\s+|placement\s+|hidden\s+)?(?:fee|fees|charges?)\s+(?:at\s+any\s+stage|is\s+required|are\s+required|required)\b"
                       r"|\bfree\s+of\s+(?:cost|charge)\b",
    "job_context": r"\b(?:job|jobs|vacancy|vacancies|hiring|recruitment|recruiter|placement|offer\s+letter|interview|employment"
                   r"|selected\s+for\s+(?:the\s+)?(?:job|role|post|position))\b",
    "job_guarantee": r"\b(?:job|placement|employment|selection|salary|income)\s+(?:is\s+)?(?:guaranteed|assured)\b"
                     r"|\b(?:guaranteed|assured|100%)\s+(?:job|placement|selection|salary|income)\b",
    "unsolicited_offer": r"\b(?:congratulations|congrats)\b[^.!?\n]{0,40}?\b(?:won|selected|winner|eligible|chosen|shortlisted)\b"
                         r"|\byou\s+have\s+been\s+(?:selected|chosen|shortlisted)\b|\b(?:exclusive|special)\s+offer\s+for\s+you\b",
    "claimed_relative": r"\b(?:mum|mom|mummy|mama|dad|daddy|papa|mother|father)\s*,?\s+(?:it'?s|its)\s+me\b"
                        r"|\bthis\s+is\s+your\s+(?:son|daughter|nephew|niece|brother|sister|uncle|aunt|cousin|grandson|granddaughter)\b",
    "scarcity": r"\bonly\s+\d+\s+(?:seats?|slots?|spots?|places?)\s+(?:left|remaining)\b|\blimited\s+(?:seats|slots|spots)\b",
    "payment_context": r"\b(?:complete|finish|finali[sz]e|process|approve|authori[sz]e)\s+(?:the\s+|your\s+|this\s+)?(?:payment|transaction|transfer)\b",
    "deposit_for_earnings": rf"\b(?:deposit|recharge|top[\s-]?up|invest)\s+{_AMOUNT}(?=(?:\s+\w+){{0,4}}?\s+(?:to\s+)?(?:unlock|release|withdraw|activate|claim))",
    "withdrawal_blocked": r"\b(?:to\s+)?(?:unlock|release|enable|allow)\s+(?:the\s+|your\s+)?withdrawals?\b(?:\s+of\s+(?:your\s+)?(?:balance|earnings|funds|money|commission|profits?))?"
                          r"|\bwithdrawals?\s+(?:is|are|has\s+been|will\s+be)\s+(?:blocked|frozen|locked|on\s+hold)\b",
    "task_earning": r"\b(?:like|subscribe\s+to|follow|rate|review|watch)\s+(?:\w+\s+){0,3}?(?:videos?|posts?|pages?|channels?|products?|hotels?|reviews?)\b"
                    rf"[^.!?\n]{{0,40}}?\b(?:earn|get\s+paid|make)\b(?:\s+{_AMOUNT})?"
                    r"|\b(?:part[\s-]?time|work\s+from\s+home|simple\s+tasks?|daily\s+tasks?)\b[^.!?\n]{0,40}?\b(?:earn|income|commission)\b"
                    rf"|\bearn\s+{_AMOUNT}\s+(?:daily|per\s+day|a\s+day|per\s+task|every\s+day|from\s+home)\b",
    "off_platform": r"\b(?:contact|message|join|chat\s+with|add|text|ping)\s+(?:us\s+|me\s+)?(?:on|via|in)\s+(?:telegram|whatsapp|signal)\b",
    "investment": rf"\b(?:invest|investment\s+of)\s+(?:{_AMOUNT}|now|today|in\s+(?:our|this|the)\s+(?:scheme|plan|fund|platform))",
    "parcel": r"\b(?:parcel|package|courier|shipment|consignment)\b",
    "new_number": r"\b(?:this\s+is\s+my\s+new\s+number|my\s+new\s+number|changed\s+my\s+number|lost\s+my\s+phone)\b",
    # threats and pressure (FAM-THREAT-CONSEQUENCE, FAM-URGENCY-PRESSURE, FAM-COERCION-ISOLATION)
    "account_block": r"\baccount\s+(?:will\s+be|would\s+be|is\s+being|being|to\s+be|is\s+going\s+to\s+be|gets?|has\s+been)\s+"
                     r"(?:permanently\s+|temporarily\s+)?(?:blocked|frozen|suspended|locked|deactivated|closed|disabled|restricted)\b"
                     r"|\b(?:block|freeze|suspend|lock|deactivate)\s+your\s+account\b",
    "suspension": r"\b(?:will\s+be|would\s+be|is\s+being|being|to\s+be|gets?)\s+(?:permanently\s+|temporarily\s+)?"
                  r"(?:disconnected|suspended|deactivated|cut\s+off|terminated|discontinued)\b"
                  r"|\bavoid\s+(?:the\s+)?(?:disconnection|suspension|deactivation)\b",
    "service_subject": r"\b(?:electricity|power|connection|service|sim|number|gas|water|internet|broadband|mobile|line|subscription|meter)\b",
    "arrest": r"\b(?:will\s+be|would\s+be|to\s+be|being|get)\s+(?:arrested|detained|jailed)\b|\barrest\s+warrant\b|\bdigital\s+arrest\b|\bunder\s+arrest\b",
    "legal_accusation": r"\b(?:money\s+laundering|drug\s+trafficking|illegal\s+(?:parcel|transactions?|activity)|case\s+(?:has\s+been\s+)?(?:registered|filed)\s+against\s+you"
                        r"|fir\s+(?:has\s+been\s+)?(?:registered|filed|lodged))\b",
    "secrecy": r"\b(?:do\s+not|don't|dont|never)\s+(?:tell|inform|discuss\s+(?:this\s+|it\s+)?with)\s+(?:anyone|anybody|your\s+(?:bank|friends|colleagues))\b"
               r"(?!\s+(?:your\s+|the\s+)?(?:otp|pin|password|cvv|code))|\bkeep\s+(?:this|it)\s+(?:a\s+)?(?:secret|confidential)\b",
    "isolation": r"\b(?:do\s+not|don't|dont)\s+(?:tell|inform|involve|contact|call)\s+(?:your\s+)?(?:family|parents|relatives|lawyer|advocate)\b",
    "discourages_verification": r"\b(?:do\s+not|don't|dont)\s+(?:call|contact|visit)\s+(?:the\s+|your\s+)?(?:bank|branch|customer\s+care|helpline)\b",
    "urgency": r"\b(?:immediately|urgently|urgent|asap|right\s+away|without\s+delay|last\s+chance|act\s+now|hurry)\b",
    "urgency_contextual": r"\b(?:tonight|today\s+itself|within\s+the\s+hour)\b",
    "deadline": r"\b(?:expires?|expiring|valid|due|deadline|ends?)\s+(?:today|tonight|tomorrow|in\s+\d+\s*(?:minutes?|mins?|hours?|hrs?|days?)"
                r"|by\s+(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)?|today|tonight|midnight))\b"
                r"|\bwithin\s+\d+\s*(?:minutes?|mins?|hours?|hrs?)\b|\bbefore\s+(?:midnight|\d{1,2}\s*(?:am|pm))\b",
    # pretexts (FAM-PRETEXT-ACCOUNT-KYC, FAM-PRETEXT-BENIGN-COVER, FAM-PRETEXT-INVESTMENT-JOB)
    "kyc": r"\b(?:e-?kyc|re-?kyc|kyc|know\s+your\s+customer)\b",
    "verification_pretext": r"\b(?:verify|re-?verify|validate|confirm)\s+(?:your\s+|the\s+)?(?:holdings|account|identity|wallet|details|kyc|pan|aadhaar"
                            r"|ownership|profile|sim|assets|funds)\b",
    "verify_at_link": r"\b(?:verify|validate|confirm|authenticate)\s+(?:your\s+|the\s+)?(?:\w+\s+){0,2}?(?:at|on|via|through|using)\s+$",
    "verification_context": r"\b(?:verify|verification|validate|kyc|log\s*in|sign\s*in|link|site|page|portal)\b",
    "benign_cue": r"\bto\s+(?:process|help|assist|guide|fix|resolve|speed\s+up)\s+(?:you|your\s+\w+)\b|\b(?:i|we)\s+(?:need|want|will|can)\s+(?:to\s+)?(?:guide|help|assist)\s+you\b"
                  r"|\bfor\s+(?:your\s+)?(?:refund|troubleshooting|support|assistance)\b|\b(?:laptop|computer|device|system|technical)\s+troubleshooting\b",
    "it_support": r"\b(?:corporate|company|office|employer|internal)\s+IT\b|\bIT\s+(?:help\s*desk|helpdesk|support|department|team)\b",
    "it_support_task": r"\b(?:troubleshoot(?:ing)?|laptop|computer|workstation|ticket)\b",
    # remote access, device and wallet actions
    "screen_share": rf"\b(?:install|download|open|start|run|launch|use|get|set\s+up|setup)\s+(?:the\s+|an?\s+)?(?:app\s+)?(?:called\s+)?{_REMOTE_APPS}"
                    r"(?:\s+(?:app|session|application))?\b(?:\s+and\s+(?:give|share|send|tell)\s+(?:me|us)\s+the\s+(?:code|id|number|pin))?",
    "apk_install": r"\b(?:install|download)\s+(?:the\s+|this\s+|our\s+)?(?:[\w-]+\s+){0,2}?(?:apk|app\s+from\s+(?:this|the|below)\s+link)\b",
    "accessibility": r"\b(?:enable|allow|grant|turn\s+on|give)\s+(?:the\s+)?accessibility(?:\s+(?:permission|service|access|settings))?\b",
    "ussd_dial": r"\b(?:dial|call|press)\s+(?:\*\d{2,4}(?:\*\d+)*#?|\*\*\d{2,3}\*\d+#?)",
    "device_linking": r"\b(?:share|send|give|tell)\s+(?:me\s+|us\s+)?(?:the\s+|your\s+)?(?:\d[\s-]digit\s+)?(?:whatsapp\s+|telegram\s+)?(?:linking|pairing)\s+code\b",
    "wallet_connect": r"\b(?:connect|link|sync|attach)\s+(?:your\s+|the\s+|ur\s+)?(?:crypto\s+|web3\s+|metamask\s+|trust\s+)?wallet\b",
    # QR (FAM-QR-ARTIFACT, FAM-QR-PAYMENT)
    "qr_mention": r"\bqr(?:\s+code)?\b",
    "qr_scan": r"\bscan\s+(?:this\s+|the\s+|below\s+|attached\s+)?qr(?:\s+code)?\b",
    "attachment": r"\[(?:image|photo|picture|attachment|file|qr)(?:\s+attached)?\]|<(?:image|attachment)>|\bsee\s+(?:the\s+)?attached\s+(?:image|qr)\b",
    # investment claims (FAM-INVESTMENT-RETURNS)
    "return_guarantee": r"\bguaranteed?\s+(?:(?P<pct>\d+(?:\.\d+)?)\s*%\s+)?(?:\w+\s+){0,2}?(?:returns?|profits?|income|gains?|payouts?)\b"
                        r"|\bassured\s+(?:returns?|profits?)\b|\b(?:double|triple)\s+your\s+(?:money|investment)\b",
    # identity claims (FAM-IDENTITY-IMPERSONATION)
    "bank_claim": r"\b(?:[A-Z][\w&'-]*\s+){1,3}Bank\b|\bbank\s+(?:officer|manager|executive|official|representative)\b|\bcalling\s+from\s+(?:the\s+)?bank\b",
    "authority_claim": r"\b(?:cyber\s*crime\s+(?:cell|department|branch|police)|police\s+(?:officer|station|department|inspector)|enforcement\s+directorate"
                       r"|customs\s+(?:officer|department)|income\s+tax\s+department|narcotics\s+(?:bureau|department))\b",
    # safety and context language (negative indicators)
    "educational": r"\b(?:scam|fraud)\s+(?:alert|awareness|warning)\b|\bbeware\s+of\s+(?:scams?|frauds?|fraudsters|scammers)\b"
                   r"|\b(?:fraudsters|scammers|criminals|imposters|impostors)\s+(?:may|might|can|could|often|usually|will|pretend)\b",
    "official_channel": r"\b(?:report|call|contact|visit)\s+(?:it\s+)?(?:on|to|at|via)?\s*(?:our|the)\s+official\s+(?:helpline|app|website|number|branch|channel)\b",
    "url": r"(?:https?://|www\.)[^\s<>\"'\]\[]+",
    "bare_domain": r"(?<![@\w.-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?P<tld>[a-z]{2,24})\b(?:/[^\s<>\"'\]\[]*)?",
    # clause structure
    "negation": r"\b(?:never|not|don't|dont|do\s+not|does\s+not|doesn't|won't|will\s+not|wouldn't|shouldn't|should\s+not|cannot|can't|no\s+one|nobody)\b",
    "contrast": r"\b(?:but|however|yet|whereas|although|though|that\s+said)\b",
    "negation_exempt": r"\bnever\s+mind\b|\bnot\s+only\b|\bno\s+matter\b|\bnot\s+just\b",
    "conditional_coercion": r"\bif\s+you\s+(?:do\s+not|don't|dont|fail\s+to|refuse\s+to)\s+$",
    "reported_frame": r"\b(?:asked|told|instructed|wanted|pressured|forced|requested|kept\s+asking)\s+(?:me|us|him|her|them|my\s+\w+)\b"
                      r"|\b(?:he|she|they|someone|somebody|a\s+(?:man|woman|person|caller|guy)|the\s+(?:caller|scammer|fraudster|agent|person|man|woman|sender))\s+"
                      r"(?:said|says|asked|told|wanted|messaged|texted)\b"
                      r"|\b(?:i|we|my\s+\w+|he|she|they)\s+(?:got|received|was\s+sent|were\s+sent)\s+(?:a\s+|an\s+|this|that)",
    "hypothetical_frame": r"\b(?:fraudsters|scammers|criminals|cheats|imposters|impostors|someone|anyone|people)\s+(?:may|might|could|can|will|often|usually|sometimes|try\s+to|pretend)\b"
                          r"|\bif\s+(?:someone|anyone|somebody|a\s+caller|they)\b|\b(?:will|would|does|do|shall)\s+(?:never|not)\s+(?:ask|request|call)\b"
                          r"|\b(?:should|can|do|must|shall)\s+i\b|\bis\s+it\s+(?:safe|ok|okay)\s+to\b",
    "first_person_plural": r"^\s*(?:we|us|our\s+(?:team|staff|bank|executives|employees|officers|representatives|agents))\b",
    "directive_prefix": r"^\s*(?:(?:please|kindly|pls|plz|now|so|then|and|also|just|immediately|urgently|quickly)[\s,]+)*"
                        r"(?:(?:never|do\s+not|don't|dont)\s+)?(?:(?:you|u)\s+(?:must|need\s+to|have\s+to|should|will|are\s+required\s+to|are\s+requested\s+to)\s+)?"
                        r"(?:(?:i|we)\s+need\s+you\s+to\s+)?(?:(?:please|kindly)\s+)?$",
    "discourse_marker": r"^\s*(?:that\s+said|however|but|also|now|and|so|ok|okay|dear\s+(?:customer|user|sir|madam))\s*,?\s*",
    "scam_lexicon": r"\b(?:scam|scams|scammer|scammers|fraud|frauds|fraudster|fraudsters|fake|cheat|cheated|suspicious)\b",
    # A contrastive conjunction always starts a new clause: negation never crosses "but" (Codex S4/S5 MEDIUM-1).
    "clause_split": r"\s*[;:]\s+|\s+[-–—]\s+|,?\s+(?:but|however|yet|whereas|although|though)\b,?\s+"
                    r"|(?:,?\s+(?:and|then)|,)\s+(?=(?:(?:please|kindly)\s+)?(?:share|send|give|tell|provide|confirm"
                    r"|forward|enter|install|download|open|click|tap|visit|connect|scan|pay|transfer|deposit|verify|update|call|dial|reply"
                    r"|complete|log\s*in|sign\s*in|keep|do\s+not|don't|never)\b)",
    "sentence_split": r"(?<=[.!?])\s+|\n+",
}
_CASE_SENSITIVE = {"it_support", "bank_claim"}
TLDS = frozenset("com net org in co io info biz xyz top online site app link me ly gl to cc tk ml ga cf gq ru cn uk us example "
                 "invalid test shop club live vip pro ai gov edu ws su icu win bid loan work click".split())
SHORTENERS = frozenset("bit.ly tinyurl.com t.co goo.gl is.gd cutt.ly ow.ly rb.gy shorturl.at tiny.cc rebrand.ly buff.ly".split())
SECOND_LEVEL = frozenset("co.in org.in gov.in net.in ac.in co.uk org.uk ac.uk com.au".split())

# Latin-script language heuristics: English function and service vocabulary versus transliterated Hindi and common
# European function words (ADR-0014: only English is detected; everything else is flagged, never scored).
EN_WORDS = frozenset("""a about above account after again all also am an and any anyone app are as asap at avoid
balance bank be been before being below blocked by call can cancel card case click code complete confirm connect could
customer day dear deposit details did do does done due earn email enter expires for from get give go has have he hello
help her here hi his holdings how i if immediately in install is it its just kindly know let like link login make may me
message money more my need never new no not now number of on once one only open or order other otp our out over own
paid parcel pay payment pending phone pin please process receive received refund reply report request requested right
safe scam scan screen secure send service session share she should sms so some soon start still such support sure team
than thank thanks that the their them then there these they this those through to today tomorrow tonight transaction
transfer under unlock until up update upi us use verify very via video videos wallet want was we well were what when
where which while who why will with within withdrawal won would yes you your yours
able across activate active address after afternoon ago agent alert already always amount another answer anything apply
apps april around ask asked attached august available away back bad bill birthday book boss both bring brother bonus
business but buy calling came cannot cash cashback change changed charge charges check child children city claim close
closed come coming company contact counter course credit credited cvv daily data date daughter days debit debited delay
delivered delivery dinner direct does doing door down download during each early easy either else end enough even evening
ever every everything expected expire expiry family fast father fee few file final find fine first follow food forget form
found free friday friend friends front full fund funds getting given going good great group had happy hard has having
head hear held help here high hold holiday home hope hour hours house however id important inform information inside
instead into issue item job join keep kids kyc last late later least leave left less life limit line little live load
local log long look lost lot made mail main many market meeting member messages minutes miss mobile monday month monthly
months morning most mother move much must name near need needed net next nice night nothing notice off offer office
officer official often old online open order others owner page parcel part party password past people per period person
phone photo photos pick place plan play point police policy possible post power price prize problem profile project
provide put quick quickly rate rather read ready real really reason receipt register registered remember rent request
reset rest return returns review reward room run said same saturday saw say says school second see seen sell sent set
shop shopping short show sign since sir site small someone something son sorry speak special staff stop store sunday
system take talk tax telegram tell test text thing things think thursday time times told too top total town trust try
tuesday turn two type unable unusual upload urgent usual value verified visit wait waiting walk weekend wednesday week
weeks whatsapp whole win without work working world write wrong year years yesterday young youtube""".split())
HI_WORDS = frozenset("""hai hain kya aap aapka aapke aapki apna apne apni nahi nahin karo kare karein kijiye bhejo bhej
mein mujhe ko ka ki ke se ho hoga hogi jaldi abhi paisa paise yeh woh tum tumhara mera meri bhai ji warna band jayega
batao bataye diya diye liye""".split())
EU_WORDS = frozenset("""el la los las que por para usted su sus favor ahora codigo cuenta und der die das nicht ist ihr
ihre bitte jetzt le les vous est pour avec votre une des sie conta seu sua voce agora""".split())
CONFUSABLES = {
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T", "Х": "X",
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s", "ԁ": "d",
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O", "Ρ": "P",
    "Τ": "T", "Υ": "Y", "Χ": "X", "ο": "o", "ν": "v",
}
_SCRIPT_PREFIXES = (("LATIN", "Latn"), ("CYRILLIC", "Cyrl"), ("GREEK", "Grek"), ("DEVANAGARI", "Deva"), ("TAMIL", "Taml"),
                    ("BENGALI", "Beng"), ("TELUGU", "Telu"), ("KANNADA", "Knda"), ("MALAYALAM", "Mlym"),
                    ("GUJARATI", "Gujr"), ("GURMUKHI", "Guru"), ("ORIYA", "Orya"), ("ARABIC", "Arab"), ("HEBREW", "Hebr"),
                    ("THAI", "Thai"), ("HANGUL", "Hang"), ("HIRAGANA", "Hira"), ("KATAKANA", "Kana"), ("CJK", "Hani"))


def _pattern_pack() -> dict:
    return {"pack_version": EXTRACTOR_VERSION, "patterns": PATTERNS, "case_sensitive": sorted(_CASE_SENSITIVE),
            "tlds": sorted(TLDS), "shorteners": sorted(SHORTENERS), "second_level": sorted(SECOND_LEVEL),
            "en": sorted(EN_WORDS), "hi_latn": sorted(HI_WORDS), "eu": sorted(EU_WORDS), "confusables": CONFUSABLES,
            "min_words": MIN_WORDS, "normalizer": NORMALIZER}


CONFIG_REF = "TL-XPACK-" + EXTRACTOR_VERSION + ":sha256:" + hashlib.sha256(canonical_json(_pattern_pack()).encode("utf-8")).hexdigest()
PROVENANCE = MappingProxyType({"extractor_id": EXTRACTOR_ID, "extractor_type": "DETERMINISTIC_PATTERN",
                               "extractor_version": EXTRACTOR_VERSION, "config_ref": CONFIG_REF})
_RX = {name: re.compile(p, 0 if name in _CASE_SENSITIVE else re.IGNORECASE) for name, p in PATTERNS.items()}


# ================================================================ normalization (offset-preserving)
def _invisible(ch: str) -> bool:
    return unicodedata.category(ch) == "Cf"            # zero-width, bidi controls, soft hyphen, BOM, word joiner


def _malformed_control(ch: str) -> bool:
    return unicodedata.category(ch) == "Cc" and not ch.isspace()


def normalize(raw: str) -> tuple[str, tuple[tuple[int, int], ...]]:
    """(normalized_text, origin): NFKC per base+combining cluster, invisible format characters removed, whitespace
    runs collapsed (to one newline if the run contained a line break, else one space), ends trimmed. origin[i] is the
    [start, end) range of raw text that produced normalized character i, so every span maps back to the exact input."""
    out: list[str] = []
    origin: list[tuple[int, int]] = []
    pending: tuple[str, int, int] | None = None
    i, n = 0, len(raw)
    while i < n:
        ch = raw[i]
        if ch.isspace():
            j, newline = i, False
            while j < n and (raw[j].isspace() or _invisible(raw[j])):
                newline = newline or raw[j] in "\n\r  \x0b\x0c\x85"
                j += 1
            if out:
                pending = ("\n" if newline else " ", i, j)
            i = j
            continue
        if _invisible(ch):
            i += 1
            continue
        j = i + 1
        while j < n and unicodedata.category(raw[j]).startswith("M"):
            j += 1
        piece = unicodedata.normalize("NFKC", raw[i:j])
        if pending is not None:
            out.append(pending[0])
            origin.append((pending[1], pending[2]))
            pending = None
        for c in piece:
            out.append(c)
            origin.append((i, j))
        i = j
    return "".join(out), tuple(origin)


def _script_of(ch: str) -> str | None:
    if not ch.isalpha():
        return None
    name = unicodedata.name(ch, "")
    for prefix, code in _SCRIPT_PREFIXES:
        if name.startswith(prefix):
            return code
    return "Zzzz"


@dataclass(frozen=True)
class LanguageAssessment:
    language: tuple[str, ...]
    script: tuple[str, ...]
    confidence: str
    supported: bool
    words: int
    confusables_folded: bool
    match_text: str
    too_short: bool = False          # too few words to determine any language                  # same length as normalized_text; confusables folded only when folding applies


def assess_language(normalized: str) -> LanguageAssessment:
    """Script by Unicode character name; language by function-word evidence. English in Latin script is the only
    supported language (ADR-0014). Latin-dominant text whose only other-script letters are confusable look-alikes is
    folded for matching (an evasion artefact, recorded), never reported as a different language."""
    counts: dict[str, int] = {}
    confusable = 0
    for ch in normalized:
        if ch in CONFUSABLES:
            confusable += 1
            continue
        code = _script_of(ch)
        if code:
            counts[code] = counts.get(code, 0) + 1
    latin = counts.get("Latn", 0)
    others = {k: v for k, v in counts.items() if k != "Latn"}
    fold = bool(confusable) and not others and latin > 0 and confusable <= 0.3 * (latin + confusable)
    match_text = "".join(CONFUSABLES.get(c, c) for c in normalized) if fold else normalized
    if not fold and confusable:
        for ch in normalized:
            if ch in CONFUSABLES:
                code = _script_of(ch)
                counts[code] = counts.get(code, 0) + 1
        others = {k: v for k, v in counts.items() if k != "Latn"}
    tokens = re.findall(r"[a-z]+(?:'[a-z]+)?", match_text.lower())
    scripts = tuple(sorted(counts, key=lambda k: (-counts[k], k))) or ("Zyyy",)
    if others or not latin:
        return LanguageAssessment(("und",), scripts, "LOW", False, len(tokens), False, match_text)
    en = sum(t in EN_WORDS for t in tokens)
    hi = sum(t in HI_WORDS for t in tokens)
    eu = sum(t in EU_WORDS for t in tokens)
    if hi >= 2 and hi * 2 >= en:
        return LanguageAssessment(("hi",), ("Latn",), "LOW", False, len(tokens), fold, match_text)
    if eu >= 2 and eu > en:
        return LanguageAssessment(("und",), ("Latn",), "LOW", False, len(tokens), fold, match_text)
    if tokens and (en >= 3 or en / len(tokens) >= 0.25):
        confidence = "HIGH" if en / len(tokens) >= 0.4 and not fold else "MEDIUM"
        return LanguageAssessment(("en",), ("Latn",), confidence, True, len(tokens), fold, match_text)
    return LanguageAssessment(("und",), ("Latn",), "LOW", False, len(tokens), fold, match_text,
                              too_short=len(tokens) < MIN_WORDS and hi < 2 and eu < 2)


# ================================================================ clause structure
@dataclass(frozen=True)
class Clause:
    start: int
    end: int
    sentence_start: int
    sentence_end: int
    interrogative: bool


@dataclass(frozen=True)
class Structure:
    polarity: str
    attribution: str
    mood: str


class Message:
    """One normalized message: the matching view, quotes, sentences and clauses, and structural analysis."""

    def __init__(self, normalized: str, match_text: str, input_type: str, relationship: str | None):
        self.text = normalized
        self.view = match_text
        self.lower = match_text.lower()
        self.narrative = input_type == "USER_NARRATIVE" or relationship == "REPORTING_ON_BEHALF"
        self.quotes = self._quotes()
        self.clauses = self._clauses()
        self.url_spans = self._url_spans()

    def _url_spans(self) -> tuple[tuple[int, int], ...]:
        candidates = [(m.start(), m.end()) for m in _RX["url"].finditer(self.view)]
        for m in _RX["bare_domain"].finditer(self.view):
            if m.group("tld").lower() in TLDS and not any(a <= m.start() < b for a, b in candidates):
                candidates.append((m.start(), m.end()))
        spans: list[tuple[int, int]] = []
        for start, end in sorted(candidates):
            while end > start and self.view[end - 1] in ".,;:!?)'\"":
                end -= 1
            if end > start and not any(a <= start < b for a, b in spans):
                spans.append((start, end))
        return tuple(spans)

    def in_url(self, pos: int) -> bool:
        return any(s <= pos < e for s, e in self.url_spans)

    def _quotes(self) -> tuple[tuple[int, int], ...]:
        spans = []
        for m in re.finditer(r"\"([^\"\n]{1,2000})\"|“([^”\n]{1,2000})”|«([^»\n]{1,2000})»", self.view):
            inner = next(g for g in range(1, 4) if m.group(g) is not None)
            outside = (self.view[:m.start()] + self.view[m.end():]).strip(" .!?,;:-\n")
            if outside:                       # a message that is entirely one quotation is the message itself
                spans.append((m.start(inner), m.end(inner)))
        return tuple(spans)

    def in_quote(self, pos: int) -> bool:
        return any(s <= pos < e for s, e in self.quotes)

    def _clauses(self) -> tuple[Clause, ...]:
        clauses = []
        for s_start, s_end in self._split(0, len(self.view), _RX["sentence_split"]):
            sentence = self.view[s_start:s_end].rstrip()
            interrogative = sentence.rstrip("\"'”)] ").endswith("?")
            for c_start, c_end in self._split(s_start, s_end, _RX["clause_split"]):
                clauses.append(Clause(c_start, c_end, s_start, s_end, interrogative))
        return tuple(clauses)

    def _split(self, start: int, end: int, rx: re.Pattern) -> list[tuple[int, int]]:
        cuts, pos = [], start
        for m in rx.finditer(self.view, start, end):
            if self.in_quote(m.start()) or m.start() == start:
                continue
            cuts.append((pos, m.start()))
            pos = m.end()
        cuts.append((pos, end))
        return [(a, b) for a, b in cuts if self.view[a:b].strip()]

    def clause_at(self, pos: int) -> Clause:
        for c in self.clauses:
            if c.start <= pos < c.end:
                return c
        return self.clauses[-1] if self.clauses else Clause(0, len(self.view), 0, len(self.view), False)

    def prefix(self, pos: int) -> str:
        """The clause text before `pos`, with leading discourse markers removed."""
        clause = self.clause_at(pos)
        start = clause.start
        for q_start, q_end in self.quotes:
            if q_start <= pos < q_end:
                start = max(start, q_start)
        text = self.lower[start:pos]
        return _RX["discourse_marker"].sub("", text, count=1)

    def sentence_before(self, pos: int) -> str:
        return self.lower[self.clause_at(pos).sentence_start:pos]

    def structure(self, pos: int, *, request: bool) -> Structure:
        """Polarity, attribution and mood of the occurrence starting at `pos` (KB-002 STEP 6)."""
        prefix = self.prefix(pos)
        negation = None
        for m in _RX["negation"].finditer(prefix):
            negation = m
        exempt = bool(_RX["negation_exempt"].search(prefix))
        coerced = bool(_RX["conditional_coercion"].search(prefix))
        conditional = negation is not None and re.search(r"\bif\s+you\s+$", prefix[:negation.start()]) is not None
        window = 6 if request else 2
        contrasted = negation is not None and _RX["contrast"].search(prefix[negation.end():]) is not None
        negated = (negation is not None and not exempt and not coerced and not conditional and not contrasted
                   and len(prefix[negation.end():].split()) <= window)
        polarity = "NEGATED" if negated else "AFFIRMED"
        if self.in_quote(pos):
            attribution = "QUOTED"
        elif _RX["hypothetical_frame"].search(prefix + self.lower[pos:pos + 24]):
            attribution = "HYPOTHETICAL"
        elif _RX["reported_frame"].search(self.sentence_before(pos)) or self.narrative:
            attribution = "REPORTED"
        else:
            attribution = "FIRST_PARTY"
        if attribution != "FIRST_PARTY":
            mood = "DESCRIPTIVE"
        elif self.clause_at(pos).interrogative:
            mood = "INTERROGATIVE"
        elif not request or _RX["directive_prefix"].match(prefix) or coerced:
            mood = "DIRECTIVE"
        else:
            mood = "DESCRIPTIVE"
        return Structure(polarity, attribution, mood)


# ================================================================ findings
# Extraction confidence (KB-002 §8) is "how sure are we the text says this", never indicator strength: HIGH for an
# explicit pattern or a parsed fact, MEDIUM for a contextual or interpretive reading (identity claims, cover stories,
# descriptive or interrogative requests, referenced-but-unseen artefacts), LOW only for an ambiguous reading. Weak
# indicators stay weak through the governed rules and strengths, not through confidence.
@dataclass
class Finding:
    obs_type: str
    canonical: str
    start: int
    end: int
    structure: Structure | None = None      # None: a claim/fact, schema defaults apply unless non-default below
    fields: dict = field(default_factory=dict)
    status: str = "OBSERVED"
    indicators: list = field(default_factory=list)   # (indicator_id, confidence, review_required)
    risky: bool = False                      # would project a positive if it were a live first-party occurrence
    url_ref: str | None = None

    def live_first_party(self) -> bool:
        s = self.structure
        return s is None or (s.polarity == "AFFIRMED" and s.attribution == "FIRST_PARTY")

    def emit(self, indicator_id: str, confidence: str, review: bool = False) -> None:
        if all(i[0] != indicator_id for i in self.indicators):
            self.indicators.append((indicator_id, confidence, review))


def _amount(match_text: str) -> dict:
    m = re.search(_AMOUNT, match_text, re.IGNORECASE)
    if not m:
        return {}
    value = float(m.group(1).replace(",", ""))
    return {"amount": int(value) if value.is_integer() else value, "currency": "INR"}


def _claim_structure(msg: Message, pos: int) -> Structure | None:
    """Claims and facts carry structure only when it departs from the schema defaults (negated / not first party)."""
    s = msg.structure(pos, request=False)
    if s.polarity == "AFFIRMED" and s.attribution == "FIRST_PARTY":
        return None
    return Structure(s.polarity, s.attribution, "DESCRIPTIVE")


def _find(name: str, msg: Message):
    return [m for m in _RX[name].finditer(msg.view) if not msg.in_url(m.start())]


def _credential_findings(msg: Message, out: list[Finding]) -> None:
    taken: list[tuple[int, int]] = []
    otp_context = bool(_RX["otp_mention"].search(msg.view))
    verification_context = bool(_RX["verification_context"].search(msg.view))
    for m in _find("credential_request", msg):
        kind = ("OTP" if m.group("otp") else "CVV" if m.group("cvv") else "CARD_NUMBER" if m.group("card") else "PASSWORD")
        if kind == "OTP" and re.search(r"\bcode\b", m.group(0), re.I) and not re.search(r"otp|one[\s-]time|verification|security|login|digit|received|got|sent", m.group(0), re.I):
            continue
        taken.append((m.start(), m.end()))
        out.append(_credential(msg, m.start(), m.end(), kind, verification_context))
    for m in _find("credential_pronoun", msg):
        if any(s <= m.start() < e for s, e in taken):
            continue
        s = msg.structure(m.start(), request=True)
        if s.polarity != "NEGATED" or not otp_context:
            continue                              # a bare pronoun object is only read in a negated safety statement
        out.append(_credential(msg, m.start(), m.end(), "OTP", verification_context))


def _credential(msg: Message, start: int, end: int, kind: str, verification_context: bool) -> Finding:
    s = msg.structure(start, request=True)
    password = kind == "PASSWORD"
    f = Finding("AUTHENTICATION_ACTION", "VERIFICATION_CAPTURE" if password else
                {"OTP": "REQUEST_DISCLOSE_OTP", "CVV": "REQUEST_DISCLOSE_CVV", "CARD_NUMBER": "REQUEST_DISCLOSE_CARD"}[kind],
                start, end, s, {"action": {"type": "DISCLOSE_CREDENTIAL", "dimension_ref": "UA-01"},
                                "target": {"credential_kind": kind}}, risky=True)
    if s.polarity == "NEGATED":
        f.risky = False
        f.emit("NEGATED_CREDENTIAL_REQUEST", "HIGH")
        if _RX["first_person_plural"].search(msg.prefix(start)):
            f.emit("EDUCATIONAL_CONTENT", "HIGH")
            f.emit("SUPPORT_NEVER_ASKS", "HIGH")
        else:
            f.emit("SELF_PROTECTIVE_WARNING", "HIGH")
    elif s.attribution == "FIRST_PARTY":
        confidence = "HIGH" if s.mood == "DIRECTIVE" else "MEDIUM"
        if password:
            if verification_context:
                f.emit("VERIFICATION_PROMPT", confidence)
        else:
            f.emit({"OTP": "CREDENTIAL_REQUEST_OTP", "CVV": "CREDENTIAL_REQUEST_CVV",
                    "CARD_NUMBER": "CREDENTIAL_REQUEST_CARD"}[kind], confidence)
    return f


def _sentence_after(msg: Message, end: int) -> tuple[int, int]:
    return end, msg.clause_at(max(end - 1, 0)).sentence_end


def _payment_findings(msg: Message, out: list[Finding], qr_present: bool, threat_present: bool) -> None:
    for m in _find("upi_pin", msg):
        s = msg.structure(m.start(), request=True)
        f = Finding("AUTHENTICATION_ACTION", "ENTER_UPI_PIN", m.start(), m.end(), s,
                    {"action": {"type": "ENTER_UPI_PIN", "dimension_ref": "UA-02"}, "target": {"credential_kind": "UPI_PIN"}},
                    risky=True)
        live = s.polarity == "AFFIRMED" and s.attribution == "FIRST_PARTY"
        a, b = _sentence_after(msg, m.end())
        receive, pay = _RX["direction_receive"].search(msg.view, a, b), _RX["direction_pay"].search(msg.view, a, b)
        direction = "USER_RECEIVES" if receive and (not pay or receive.start() < pay.start()) else "USER_PAYS" if pay else "UNKNOWN_DIRECTION"
        f.fields["payment_direction"] = direction
        if live:
            f.emit("UPI_PIN_PROMPT", "HIGH" if s.mood != "DESCRIPTIVE" else "MEDIUM")
        out.append(f)
        if direction == "USER_RECEIVES":
            d = Finding("PAYMENT_CONTEXT", "RECEIVE_MONEY", receive.start(), receive.end(), s,
                        {"payment_direction": "USER_RECEIVES", "target": _amount(receive.group(0))}, risky=True)
            if re.search(r"\brefund\b", msg.view, re.I):
                d.fields["pretext"] = {"kind": "REFUND"}
            if live:
                d.emit("RECEIVE_FRAMING", "HIGH")
            out.append(d)
        elif direction == "USER_PAYS":
            target = _amount(pay.group(0))
            if pay.group("merchant"):
                target["recipient_label"] = "MERCHANT"
                f.fields["target"]["recipient_label"] = "MERCHANT"
            d = Finding("PAYMENT_CONTEXT", "PAY_MERCHANT" if pay.group("merchant") else "PAY_OUTBOUND", pay.start(), pay.end(), s,
                        {"payment_direction": "USER_PAYS", "target": target})
            if pay.group("merchant") and live:
                d.emit("PAY_MERCHANT_DIRECTION", "HIGH")
            out.append(d)
    for m in _find("immediate_payment", msg):
        s = msg.structure(m.start(), request=True)
        f = Finding("PAYMENT_CONTEXT", "IMMEDIATE_PAYMENT", m.start(), m.end(), s,
                    {"action": {"type": "MAKE_PAYMENT", "dimension_ref": "UA-03"}, "target": _amount(m.group(0))}, risky=True)
        if s.polarity == "AFFIRMED" and s.attribution == "FIRST_PARTY":
            f.emit("IMMEDIATE_PAYMENT_DEMAND" if threat_present else "PAYMENT_DEMAND", "HIGH" if s.mood != "DESCRIPTIVE" else "MEDIUM")
        out.append(f)
    covered = [(f.start, f.end) for f in out if f.canonical == "IMMEDIATE_PAYMENT"]
    for name, canonical, indicator in (("upfront_fee", "UPFRONT_FEE", "UPFRONT_FEE_DEMAND"),
                                       ("payment_demand", "PAYMENT_DEMAND", "PAYMENT_DEMAND")):
        for m in _find(name, msg):
            if any(a <= m.start() < b for a, b in covered):
                continue
            covered.append((m.start(), m.end()))
            s = msg.structure(m.start(), request=True)
            f = Finding("PAYMENT_CONTEXT", canonical, m.start(), m.end(), s,
                        {"action": {"type": "MAKE_PAYMENT", "dimension_ref": "UA-03"}, "payment_direction": "USER_PAYS",
                         "target": _amount(m.group(0))}, risky=True)
            if s.polarity == "AFFIRMED" and s.attribution == "FIRST_PARTY" and s.mood != "DESCRIPTIVE":
                f.emit(indicator, "MEDIUM")
            out.append(f)
    for m in _find("payment_context", msg):
        st = _claim_structure(msg, m.start())
        ambiguous = qr_present
        f = Finding("PAYMENT_CONTEXT", "PAYMENT_CONTEXT", m.start(), m.end(), st, {}, risky=True,
                    status="AMBIGUOUS" if ambiguous else "OBSERVED")
        if ambiguous:
            f.fields["payment_direction"] = "UNKNOWN_DIRECTION"
        if f.live_first_party():
            f.emit("PAYMENT_CONTEXT", "LOW" if ambiguous else "MEDIUM", review=ambiguous)
        out.append(f)
    for m in _find("deposit_for_earnings", msg):
        s = msg.structure(m.start(), request=True)
        f = Finding("PAYMENT_CONTEXT", "DEPOSIT_FOR_EARNINGS", m.start(), m.end(), s,
                    {"payment_direction": "USER_PAYS", "target": _amount(m.group(0))}, risky=True)
        if s.polarity == "AFFIRMED" and s.attribution == "FIRST_PARTY":
            f.emit("DEPOSIT_FOR_EARNINGS", "MEDIUM")
        out.append(f)


def _simple(msg: Message, out: list[Finding], name: str, obs_type: str, canonical: str, indicator: str | None,
            confidence: str, fields: dict | None = None, request: bool = False, risky: bool = True,
            skip: Iterable[tuple[int, int]] = ()) -> list[Finding]:
    made = []
    skip = list(skip)
    for m in _find(name, msg):
        if any(a <= m.start() < b for a, b in skip):
            continue
        st = msg.structure(m.start(), request=True) if request else _claim_structure(msg, m.start())
        f = Finding(obs_type, canonical, m.start(), m.end(), st, json.loads(json.dumps(fields or {})), risky=risky)
        if indicator and f.live_first_party() and (not request or st.mood != "DESCRIPTIVE"):
            f.emit(indicator, confidence if (not request or st.mood == "DIRECTIVE") else "MEDIUM")
        out.append(f)
        made.append(f)
    return made


def _url_findings(msg: Message, input_id: str, raw_of, out: list[Finding]) -> list[dict]:
    urls = []
    for start, end in msg.url_spans:
        url_id = f"{input_id}:u{len(urls) + 1}"
        urls.append(_url_observation(url_id, msg.text[start:end], raw_of(start, end), start, end))
        st = _claim_structure(msg, start)
        verify_at = bool(_RX["verify_at_link"].search(msg.lower[msg.clause_at(start).start:start]))
        f = Finding("LINK_ACTION", "FAKE_VERIFICATION_SITE" if verify_at else "LINK_PRESENT", start, end, st,
                    {"pretext": {"kind": "VERIFICATION"}} if verify_at else {}, risky=True, url_ref=url_id)
        if f.live_first_party():
            if verify_at:
                f.emit("FAKE_VERIFICATION_SITE", "HIGH")
            f.emit("LINK_PRESENT", "HIGH")                   # a parsed URL is a fact
            if urls[-1]["structural"]["flags"].get("shortened"):
                f.emit("SHORTENED_URL", "HIGH")
        out.append(f)
    return urls


def _url_observation(url_id: str, text: str, raw: str, start: int, end: int) -> dict:
    scheme_match = re.match(r"(?i)^(https?)://", text)
    rest = text[scheme_match.end():] if scheme_match else text
    authority, _, path = rest.partition("/")
    obfuscated = "@" in authority or "%" in authority
    host = authority.split("@")[-1].split(":")[0].lower().rstrip(".")
    labels = [label for label in host.split(".") if label]
    two = ".".join(labels[-2:])
    registered = ".".join(labels[-3:]) if two in SECOND_LEVEL and len(labels) >= 3 else two
    subdomain = host[: -len(registered) - 1] if registered and host.endswith("." + registered) else ""
    ip_literal = bool(re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host))
    structural = {"hostname": host, "registered_domain": registered,
                  "flags": {"shortened": registered in SHORTENERS or host in SHORTENERS, "obfuscated": obfuscated or len(labels) > 5,
                            "punycode": "xn--" in host, "ip_literal": ip_literal}}
    if scheme_match:
        structural["scheme"] = scheme_match.group(1).lower()
    if subdomain:
        structural["subdomain"] = subdomain
    if path:
        structural["path"] = "/" + path
    tail = re.sub(r"(?i)([?&])utm_[^&#]*&?", r"\1", ("/" + path) if path else "").rstrip("?&")
    normalized = (scheme_match.group(1).lower() + "://" if scheme_match else "") + authority.lower() + tail
    return {"url_id": url_id, "raw_url": raw, "normalized_url": normalized, "span": {"start": start, "end": end},
            "structural": structural}


def _find_all(msg: Message, input_id: str, raw_of) -> tuple[list[Finding], list[dict], list[str]]:
    out: list[Finding] = []
    gaps: list[str] = []
    attachment = _find("attachment", msg)
    qr_present = bool(_find("qr_mention", msg)) and (bool(attachment) or bool(_find("qr_scan", msg)))
    if attachment:
        gaps.append("REFERENCED_ATTACHMENT_NOT_EVALUATED")
    _credential_findings(msg, out)
    for m in _find("otp_delivered", msg):
        st = _claim_structure(msg, m.start())
        f = Finding("AUTHENTICATION_ACTION", "OTP_DELIVERED", m.start(), m.end(),
                    st or Structure("AFFIRMED", "FIRST_PARTY", "DESCRIPTIVE"),
                    {"target": {"credential_kind": "OTP"}, "payment_direction": "UNKNOWN_DIRECTION"})
        if f.live_first_party():
            f.emit("OTP_DELIVERED_NOT_REQUESTED", "HIGH")
        out.append(f)
    # threats first: an immediate payment demand is one framed as avoiding a stated consequence
    threats = []
    threats += _simple(msg, out, "account_block", "THREAT", "ACCOUNT_BLOCK", "ACCOUNT_BLOCK_THREAT", "HIGH",
                       {"pressure": {"kind": "THREAT", "threat_of": "ACCOUNT_BLOCK"}})
    service = bool(_RX["service_subject"].search(msg.view))
    if service:
        threats += _simple(msg, out, "suspension", "THREAT", "THREAT_SERVICE_SUSPENSION", "SUSPENSION_THREAT", "HIGH",
                           {"pressure": {"kind": "THREAT", "threat_of": "SERVICE_SUSPENSION", "dimension_ref": "SE-03"}},
                           skip=[(f.start, f.end) for f in threats])
    threats += _simple(msg, out, "arrest", "THREAT", "THREAT_ARREST", "ARREST_THREAT", "HIGH",
                       {"pressure": {"kind": "THREAT", "threat_of": "ARREST"}})
    threats += _simple(msg, out, "legal_accusation", "THREAT", "LEGAL_ACCUSATION", "LEGAL_ACCUSATION", "HIGH",
                       {"pressure": {"kind": "THREAT", "threat_of": "LEGAL_ACTION"}})
    threats += _simple(msg, out, "withdrawal_blocked", "THREAT", "WITHDRAWAL_BLOCKED", "WITHDRAWAL_BLOCKED_PRETEXT", "HIGH",
                       {"pressure": {"kind": "THREAT", "threat_of": "FINANCIAL_LOSS"}})
    threat_present = any(f.live_first_party() for f in threats)
    _payment_findings(msg, out, qr_present, threat_present)
    deadlines = _simple(msg, out, "deadline", "TEMPORAL_PRESSURE", "URGENCY_DEADLINE", "URGENCY_DEADLINE", "HIGH",
                        {"pressure": {"kind": "DEADLINE", "dimension_ref": "SE-02"}})
    _simple(msg, out, "urgency", "TEMPORAL_PRESSURE", "URGENCY", "URGENCY", "HIGH",
            {"pressure": {"kind": "URGENCY", "dimension_ref": "SE-02"}}, skip=[(f.start, f.end) for f in deadlines])
    pressured = {msg.clause_at(f.start).sentence_start for f in out if f.risky and f.indicators}
    for f in _simple(msg, out, "urgency_contextual", "TEMPORAL_PRESSURE", "URGENCY", "URGENCY", "MEDIUM",
                     {"pressure": {"kind": "URGENCY", "dimension_ref": "SE-02"}}, skip=[(f.start, f.end) for f in deadlines]):
        if msg.clause_at(f.start).sentence_start not in pressured:
            f.indicators.clear()               # a time word is pressure only beside a live threat or request
    _simple(msg, out, "secrecy", "TEMPORAL_PRESSURE", "SECRECY_REQUEST", "SECRECY_REQUEST", "HIGH",
            {"pressure": {"kind": "SECRECY"}})
    _simple(msg, out, "isolation", "TEMPORAL_PRESSURE", "ISOLATION", "ISOLATION_FROM_FAMILY_OR_LAWYER", "HIGH",
            {"pressure": {"kind": "ISOLATION"}})
    _simple(msg, out, "discourages_verification", "CLAIM", "DISCOURAGES_VERIFICATION", "DISCOURAGES_VERIFICATION", "HIGH")
    for f in out:                                                         # negation-shaped coercion stays affirmed
        if f.canonical in ("SECRECY_REQUEST", "ISOLATION", "DISCOURAGES_VERIFICATION") and f.structure and f.structure.polarity == "NEGATED":
            f.structure = None if f.structure.attribution == "FIRST_PARTY" else Structure("AFFIRMED", f.structure.attribution, "DESCRIPTIVE")
            if f.live_first_party():
                f.emit({"SECRECY_REQUEST": "SECRECY_REQUEST", "ISOLATION": "ISOLATION_FROM_FAMILY_OR_LAWYER",
                        "DISCOURAGES_VERIFICATION": "DISCOURAGES_VERIFICATION"}[f.canonical], "HIGH")
    for m in _find("kyc", msg):
        clause = msg.clause_at(m.start())
        start = clause.start + (len(msg.view[clause.start:clause.end]) - len(msg.view[clause.start:clause.end].lstrip()))
        end = clause.end
        while end > start and msg.view[end - 1] in ".!?, ":
            end -= 1
        f = Finding("CLAIM", "KYC_PRETEXT", start, end, _claim_structure(msg, m.start()), {"pretext": {"kind": "KYC_UPDATE"}}, risky=True)
        if f.live_first_party():
            f.emit("KYC_PRETEXT", "HIGH")
        out.append(f)
        break
    _simple(msg, out, "verification_pretext", "CLAIM", "VERIFICATION_PRETEXT", "VERIFICATION_PRETEXT", "HIGH",
            {"pretext": {"kind": "VERIFICATION"}})
    _simple(msg, out, "task_earning", "CLAIM", "TASK_EARNING_LURE", "TASK_EARNING_LURE", "HIGH", {"pretext": {"kind": "JOB_OFFER"}})
    _simple(msg, out, "off_platform", "LINK_ACTION", "OFF_PLATFORM_HANDOFF", "OFF_PLATFORM_HANDOFF", "MEDIUM", request=True)
    _simple(msg, out, "job_guarantee", "CLAIM", "JOB_GUARANTEE", "JOB_GUARANTEE", "HIGH", {"pretext": {"kind": "JOB_OFFER"}})
    _simple(msg, out, "unsolicited_offer", "CLAIM", "UNSOLICITED_OFFER", "UNSOLICITED_OFFER", "MEDIUM", {"pretext": {"kind": "PRIZE"}})
    _simple(msg, out, "scarcity", "TEMPORAL_PRESSURE", "SCARCITY", "SCARCITY_PRESSURE", "HIGH", {"pressure": {"kind": "SCARCITY"}})
    for m in _find("job_context", msg)[:1]:                # one job pretext per message
        f = Finding("CLAIM", "JOB_CONTEXT", m.start(), m.end(), _claim_structure(msg, m.start()), {"pretext": {"kind": "JOB_OFFER"}},
                    risky=True)
        if f.live_first_party():
            f.emit("JOB_CONTEXT", "MEDIUM")               # a job is mentioned; that it is the pretext is read
        out.append(f)
    for m in _find("explicit_no_fee", msg):
        f = Finding("CLAIM", "EXPLICIT_NO_FEE", m.start(), m.end(), _claim_structure(msg, m.start()))
        if f.live_first_party():
            f.emit("EXPLICIT_NO_FEE", "HIGH")
        out.append(f)
    _simple(msg, out, "investment", "CLAIM", "INVESTMENT_SOLICITATION", "INVESTMENT_SOLICITATION", "MEDIUM", {"pretext": {"kind": "INVESTMENT"}})
    for m in _find("parcel", msg)[:1]:
        f = Finding("CLAIM", "PARCEL_PRETEXT", m.start(), m.end(), _claim_structure(msg, m.start()), {"pretext": {"kind": "PARCEL_DELIVERY"}},
                    risky=True)
        if f.live_first_party():
            f.emit("PARCEL_PRETEXT", "MEDIUM")             # a parcel is mentioned; that it is the pretext is read
        out.append(f)
    for m in _find("return_guarantee", msg):
        f = Finding("CLAIM", "RETURN_GUARANTEE", m.start(), m.end(), _claim_structure(msg, m.start()),
                    {"pretext": {"kind": "INVESTMENT"}}, risky=True)
        if f.live_first_party():
            f.emit("RETURN_GUARANTEE", "HIGH")
            if m.group("pct") and float(m.group("pct")) >= 20:
                f.emit("HIGH_RETURN_MENTION", "MEDIUM")
        out.append(f)
    # device, remote-access and wallet actions
    technical = []
    for m in _find("screen_share", msg):
        s = msg.structure(m.start(), request=True)
        app = re.sub(r"\s+", "", m.group(1)).lower()
        instrument = {"anydesk": "AnyDesk", "teamviewer": "TeamViewer", "airdroid": "AirDroid", "quicksupport": "QuickSupport",
                      "rustdesk": "RustDesk", "ultraviewer": "UltraViewer", "ammyy": "Ammyy", "supremo": "Supremo",
                      "splashtop": "Splashtop"}.get(app, m.group(1))
        f = Finding("DEVICE_ACTION", "INSTALL_SCREEN_SHARE_APP", m.start(), m.end(), s,
                    {"action": {"type": "INSTALL_APP", "dimension_ref": "UA-05"}, "target": {"instrument": instrument}}, risky=True)
        if s.polarity == "AFFIRMED" and s.attribution == "FIRST_PARTY":
            f.emit("SCREEN_SHARE_APP_REQUEST", "HIGH" if s.mood != "DESCRIPTIVE" else "MEDIUM")
        out.append(f)
        technical.append(f)
    technical += _simple(msg, out, "apk_install", "DEVICE_ACTION", "INSTALL_APK", "APK_INSTALL_REQUEST", "HIGH",
                         {"action": {"type": "INSTALL_APP"}}, request=True)
    technical += _simple(msg, out, "accessibility", "DEVICE_ACTION", "GRANT_ACCESSIBILITY", "ACCESSIBILITY_PERMISSION_REQUEST", "HIGH",
                         {"action": {"type": "GRANT_PERMISSION"}, "target": {"instrument": "Accessibility"}}, request=True)
    technical += _simple(msg, out, "device_linking", "DEVICE_ACTION", "SHARE_LINKING_CODE", "DEVICE_LINKING_CODE_REQUEST", "HIGH",
                         {"action": {"type": "LINK_DEVICE"}, "target": {"credential_kind": "LINKING_CODE"}}, request=True)
    technical += _simple(msg, out, "wallet_connect", "DEVICE_ACTION", "CONNECT_WALLET", "WALLET_CONNECT_REQUEST", "HIGH",
                         {"action": {"type": "CONNECT_WALLET", "dimension_ref": "UA-08"}}, request=True)
    _simple(msg, out, "ussd_dial", "DEVICE_ACTION", "DIAL_CODE", "USSD_CODE_DIAL_REQUEST", "HIGH", {"action": {"type": "DIAL_CODE"}},
            request=True)
    live_technical = [f for f in technical if f.indicators]
    # IT-support context and benign cover for a technical action
    sensitive_request = any(f.indicators and f.obs_type in ("AUTHENTICATION_ACTION", "PAYMENT_CONTEXT") and f.risky for f in out)
    it = _find("it_support", msg) if _RX["it_support_task"].search(msg.view) else []
    if it and technical:
        clause = msg.clause_at(it[0].start())
        start, end = clause.sentence_start, clause.sentence_end
        while end > start and msg.view[end - 1] in ".!? ":
            end -= 1
        f = Finding("RELATIONSHIP_CONTEXT", "IT_SUPPORT", start, end, _claim_structure(msg, it[0].start()),
                    {"pretext": {"kind": "TECHNICAL_SUPPORT"}})
        if f.live_first_party():
            f.emit("BENIGN_PRETEXT_FOR_TECHNICAL_ACTION", "MEDIUM")
            if not sensitive_request:
                f.emit("IT_SUPPORT_CONTEXT", "HIGH")
        out.append(f)
    elif technical:
        cue = _find("benign_cue", msg)
        if cue:
            clause = msg.clause_at(cue[0].start())
            start, end = clause.start, clause.end
            while end > start and msg.view[end - 1] in ".!?, ":
                end -= 1
            f = Finding("CLAIM", "BENIGN_COVER", start, end, _claim_structure(msg, cue[0].start()),
                        {"pretext": {"kind": "TECHNICAL_SUPPORT"}}, risky=True)
            if f.live_first_party() and live_technical:
                f.emit("BENIGN_PRETEXT_FOR_TECHNICAL_ACTION", "MEDIUM")
            out.append(f)
    # QR artefact
    if qr_present:
        marker = attachment[0] if attachment else _find("qr_mention", msg)[0]
        out.append(Finding("ENTITY", "QR_PRESENT", marker.start(), marker.end(), None, {}, indicators=[("QR_PRESENT", "MEDIUM", False)]))   # referenced, not seen
        for m in _find("qr_scan", msg):
            s = msg.structure(m.start(), request=True)
            a, b = _sentence_after(msg, m.end())
            receive, pay = _RX["direction_receive"].search(msg.view, a, b), _RX["direction_pay"].search(msg.view, a, b)
            if not (receive or pay):
                continue                       # direction not stated: the payment context is AMBIGUOUS, not a scan request
            f = Finding("PAYMENT_CONTEXT", "SCAN_QR", m.start(), m.end(), s,
                        {"action": {"type": "SCAN_QR"}, "payment_direction": "USER_RECEIVES" if receive else "USER_PAYS"}, risky=True)
            if s.polarity == "AFFIRMED" and s.attribution == "FIRST_PARTY":
                f.emit("QR_SCAN_REQUEST", "MEDIUM")
                if receive:
                    f.emit("RECEIVE_FRAMING", "HIGH")
                elif pay.group("merchant"):
                    f.fields["target"] = {**_amount(pay.group(0)), "recipient_label": "MERCHANT"}
                    f.emit("PAY_MERCHANT_DIRECTION", "HIGH")
            out.append(f)
    urls = _url_findings(msg, input_id, raw_of, out)
    # identity claims: projected only alongside a live sensitive directive in the same message
    live_directive = any(f.indicators and f.risky and f.obs_type in ("AUTHENTICATION_ACTION", "PAYMENT_CONTEXT", "DEVICE_ACTION", "LINK_ACTION")
                         and f.structure is not None and f.structure.mood != "DESCRIPTIVE" for f in out)
    for m in _find("claimed_relative", msg):
        f = Finding("IDENTITY_ASSERTION", "CLAIMED_RELATIVE", m.start(), m.end(), _claim_structure(msg, m.start()),
                    {"actor": {"claimed_identity": "RELATIVE", "verified": "UNKNOWN"}}, risky=True)
        if f.live_first_party():
            f.emit("CLAIMED_RELATIVE", "MEDIUM")
        out.append(f)
    for m in _find("new_number", msg):
        f = Finding("IDENTITY_ASSERTION", "NEW_NUMBER", m.start(), m.end(), _claim_structure(msg, m.start()),
                    {"actor": {"claimed_identity": "KNOWN_CONTACT", "verified": "UNKNOWN"}}, risky=True)
        if f.live_first_party():
            f.emit("NEW_NUMBER_CLAIM", "MEDIUM")
        out.append(f)
    for name, canonical, identity, indicator in (("bank_claim", "CLAIM_BANK", "AUTHORITY_BANK", "AUTHORITY_IMPERSONATION_BANK"),
                                                 ("authority_claim", "CLAIM_AUTHORITY", "AUTHORITY_LAW_ENFORCEMENT", "AUTHORITY_IMPERSONATION")):
        for m in _find(name, msg):
            f = Finding("IDENTITY_ASSERTION", canonical, m.start(), m.end(), _claim_structure(msg, m.start()),
                        {"actor": {"claimed_identity": identity, "verified": "UNKNOWN"}})
            if f.live_first_party() and (live_directive or (indicator == "AUTHORITY_IMPERSONATION" and threat_present)):
                f.emit(indicator, "MEDIUM")
            out.append(f)
    # safety language
    edu = _find("educational", msg)
    if edu:
        f = Finding("CLAIM", "EDUCATIONAL_WARNING", edu[0].start(), edu[0].end(), Structure("AFFIRMED", "HYPOTHETICAL", "DESCRIPTIVE"))
        f.emit("EDUCATIONAL_CONTENT", "HIGH")
        out.append(f)
    for m in _find("official_channel", msg):     # recorded; projection deferred, as in golden fixture XF-12
        out.append(Finding("CLAIM", "OFFICIAL_CHANNEL_REDIRECT", m.start(), m.end(), _claim_structure(msg, m.start())))
    # a reported or quoted risky occurrence is preserved as REPORTED_SCAM_NARRATIVE, never as a live positive
    reported = [f for f in out if f.risky and f.structure is not None and f.structure.attribution in ("REPORTED", "QUOTED")
                and f.structure.polarity == "AFFIRMED"]
    if reported:
        reported[0].indicators.append(("REPORTED_SCAM_NARRATIVE", "HIGH", False, tuple(id(f) for f in reported)))
    return out, urls, gaps


# ================================================================ governed artefacts
@lru_cache(maxsize=1)
def _validators() -> dict[str, Draft202012Validator]:
    names = {"envelope": "input-envelope", "observation": "observation", "url": "url-observation",
             "indicator_observation": "indicator-observation"}
    schemas = {k: json.loads((_SCHEMAS / f"{v}.schema.json").read_text()) for k, v in names.items()}
    registry = Registry().with_resources([(s["$id"], Resource.from_contents(s)) for s in schemas.values()])
    return {k: Draft202012Validator(s, registry=registry) for k, s in schemas.items()}


def _forbidden(node, path="$") -> list[str]:
    found = []
    if isinstance(node, Mapping):
        for k, v in node.items():
            if k in _FORBIDDEN_KEYS:
                found.append(f"{path}.{k}")
            if k != "confidence":
                found += _forbidden(v, f"{path}.{k}")
    elif isinstance(node, (list, tuple)):
        for i, v in enumerate(node):
            found += _forbidden(v, f"{path}[{i}]")
    return found


def _family_of(knowledge) -> dict[str, str]:
    families = knowledge.index("indicator_families_by_id")
    return {i: fid for fid in families for i in knowledge.indicators_for_family(fid)}


def _thaw(value):
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


@dataclass(frozen=True)
class GovernedInput:
    """The immutable, validated S4 output for ONE input; what S5 hands to the engine. Never carries a verdict."""

    input_id: str
    envelope: Mapping[str, Any]
    observations: tuple[Mapping[str, Any], ...]
    indicator_observations: tuple[Mapping[str, Any], ...]
    input_support_status: str
    language: tuple[str, ...]
    script: tuple[str, ...]
    whole_evaluation_errors: tuple[Mapping[str, Any], ...]
    support_gaps: tuple[str, ...]
    normalization_notes: tuple[str, ...]
    knowledge_content_digest: str
    extractor: Mapping[str, str]
    source: Mapping[str, Any] | None = None

    def __repr__(self) -> str:                  # never the evidence text
        return (f"GovernedInput(input_id={self.input_id!r}, support={self.input_support_status!r}, "
                f"observations={len(self.observations)}, indicators={len(self.indicator_observations)})")

    def engine_inputs(self) -> dict:
        """Keyword arguments for knowledge.runtime.result.evaluate_detection_from_governed (S5 adds evaluation_id and
        evaluation_timestamp). Plain JSON copies; the frozen originals stay untouched."""
        return {"indicator_observations": _thaw(self.indicator_observations), "observations": _thaw(self.observations),
                "input_id": self.input_id, "language": list(self.language), "script": list(self.script),
                "input_support_status": self.input_support_status,
                "whole_evaluation_errors": _thaw(self.whole_evaluation_errors)}

    def positive_signals(self) -> tuple[str, ...]:
        return tuple(sorted({i["indicator_id"] for i in self.indicator_observations if i["polarity"] == "POSITIVE"}))

    def negative_signals(self) -> tuple[str, ...]:
        return tuple(sorted({i["indicator_id"] for i in self.indicator_observations if i["polarity"] == "NEGATIVE"}))


def _require_compatible(knowledge) -> None:
    if knowledge is None:
        raise ExtractionUnavailable("KNOWLEDGE_NOT_READY")
    if knowledge.component_versions.get("extraction_schemas") != ENVELOPE_VERSION:
        raise ExtractionUnavailable("EXTRACTION_SCHEMA_INCOMPATIBLE")


def _error_input(input_id: str, input_type: str, knowledge, code: str, message: str, *, synthetic: bool,
                 received_via: str, relationship: str | None, source: Mapping | None) -> GovernedInput:
    envelope = {"envelope_version": ENVELOPE_VERSION, "input_id": input_id, "input_type": input_type,
                "source_channel": {"value": CHANNELS.get(input_type, "UNKNOWN")},
                "content": {"language": ["und"], "script": ["Zzzz"], "language_detection": {"method": "UNKNOWN", "confidence": "UNKNOWN"}},
                "provenance": {"received_via": received_via, "pipeline_stage": "INGESTED", "normalizer": dict(NORMALIZER),
                               "synthetic": synthetic}}
    if relationship:
        envelope["user_supplied_context"] = {"relationship_to_content": relationship}
    _validate_envelope(envelope)
    error = {"scope": "WHOLE_EVALUATION", "stage": "EXTRACTION_MALFORMED", "code": code, "message": message}
    return GovernedInput(input_id, freeze(envelope), (), (), "ERROR", ("und",), ("Zzzz",), freeze([error]), (), (),
                         knowledge.content_digest, PROVENANCE, freeze(dict(source)) if source else None)


def _where(error) -> str:
    """Path and keyword only: a schema message can quote the instance, and the instance may be evidence text."""
    return "/".join(str(p) for p in error.absolute_path) + f" ({error.validator})"


def _validate_envelope(envelope: dict) -> None:
    errors = sorted(_validators()["envelope"].iter_errors(envelope), key=lambda e: list(e.absolute_path))
    if errors:
        raise ExtractionContractError(f"input envelope rejected by input-envelope.schema.json at {_where(errors[0])}")


def extract_text(data: bytes, *, input_id: str, input_type: str, knowledge, relationship_to_content: str | None = None,
                 synthetic: bool = True, received_via: str = "USER_SUBMISSION", source: Mapping | None = None) -> GovernedInput:
    """Deterministically extract governed inputs from the exact submitted bytes. Same bytes, input id, type, context and
    knowledge always give the same result. `knowledge` is the ACTIVE, verified RuntimeKnowledge (S3 readiness)."""
    _require_compatible(knowledge)
    if input_type not in INPUT_TYPES:
        raise ExtractionRefused("UNSUPPORTED_INPUT_TYPE")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{1,100}", input_id or ""):
        raise ExtractionRefused("INVALID_INPUT_ID")
    common = dict(synthetic=synthetic, received_via=received_via, relationship=relationship_to_content, source=source)
    if len(data) > MAX_TEXT_BYTES:
        return _error_input(input_id, input_type, knowledge, "INPUT_TOO_LARGE", "Input exceeds the 64 KiB text bound.", **common)
    try:
        raw = data.decode("utf-8")
    except UnicodeDecodeError:
        return _error_input(input_id, input_type, knowledge, "INVALID_UTF8", "Input is not valid UTF-8 text.", **common)
    if raw.startswith("﻿"):
        raw = raw[1:]
    if any(_malformed_control(ch) for ch in raw):
        return _error_input(input_id, input_type, knowledge, "CONTROL_CHARACTERS", "Input contains control characters.", **common)

    normalized, origin = normalize(raw)
    assessment = assess_language(normalized)

    def raw_of(start: int, end: int) -> str:
        return raw[origin[start][0]:origin[end - 1][1]]

    notes = []
    if normalized != raw:
        notes.append("UNICODE_NORMALIZED_OR_WHITESPACE_COLLAPSED")
    if any(_invisible(ch) for ch in raw):
        notes.append("INVISIBLE_FORMAT_CHARACTERS_REMOVED")
    if assessment.confusables_folded:
        notes.append("MIXED_SCRIPT_CONFUSABLES_FOLDED_FOR_MATCHING")

    findings, urls, gaps = [], [], []
    if assessment.supported:
        msg = Message(normalized, assessment.match_text, input_type, relationship_to_content)
        findings, urls, gaps = _find_all(msg, input_id, raw_of)
    observations, indicator_observations = _materialize(findings, input_id, normalized, raw_of, knowledge, assessment)

    if not any(ch.isalpha() for ch in normalized):
        status = "INSUFFICIENT_INFORMATION"            # nothing linguistic to evaluate (empty, digits or symbols only)
    elif assessment.too_short:
        status = "INSUFFICIENT_INFORMATION"
    elif not assessment.supported:
        status = "UNSUPPORTED"
    elif assessment.words < MIN_WORDS and not indicator_observations:
        status = "INSUFFICIENT_INFORMATION"
    elif gaps:
        status = "PARTIALLY_SUPPORTED"
    else:
        status = "SUPPORTED"

    envelope = {"envelope_version": ENVELOPE_VERSION, "input_id": input_id, "input_type": input_type,
                "source_channel": {"value": CHANNELS.get(input_type, "UNKNOWN")},
                "content": {"raw_text": raw, "normalized_text": normalized, "language": list(assessment.language),
                            "script": list(assessment.script),
                            "language_detection": {"method": "HEURISTIC", "confidence": assessment.confidence}},
                "provenance": {"received_via": received_via, "pipeline_stage": "INGESTED", "normalizer": dict(NORMALIZER),
                               "synthetic": synthetic}}
    primitives = _primitives(normalized, urls)
    if primitives:
        envelope["extracted_primitives"] = primitives
    if relationship_to_content:
        envelope["user_supplied_context"] = {"relationship_to_content": relationship_to_content}
    _validate_envelope(envelope)
    _validate_artifacts(observations, indicator_observations, urls, normalized, raw_of, knowledge)
    problems = _forbidden(envelope) + _forbidden(observations) + _forbidden(indicator_observations)
    if problems:
        raise ExtractionContractError(f"an extraction artefact carries a verdict-shaped key at {problems[0]}")
    if status in ("SUPPORTED", "PARTIALLY_SUPPORTED"):
        try:                                     # the engine's own governed validation boundary (S4.4)
            build_validated_context(indicator_observations, observations, language=assessment.language[0],
                                    script=assessment.script[0])
        except ValueError:
            raise ExtractionContractError("governed validation (build_validated_context) rejected the extraction") from None
    return GovernedInput(input_id, freeze(envelope), freeze(observations), freeze(indicator_observations), status,
                         assessment.language, assessment.script, (), tuple(gaps), tuple(notes), knowledge.content_digest,
                         PROVENANCE, freeze(dict(source)) if source else None)


def _primitives(normalized: str, urls: list[dict]) -> dict:
    out: dict[str, list] = {}
    if urls:
        out["urls"] = urls
    amounts = []
    for m in re.finditer(_AMOUNT, normalized, re.IGNORECASE):
        value = float(m.group(1).replace(",", ""))
        amounts.append({"value": int(value) if value.is_integer() else value, "currency": "INR",
                        "span": {"start": m.start(), "end": m.end()}})
    if amounts:
        out["amounts"] = amounts
    codes = [{"value": "#" * (m.end() - m.start()), "span": {"start": m.start(), "end": m.end()}}   # masked: never the code
             for m in re.finditer(r"(?<![\w,.])\d{4,8}(?![\w,])", normalized)
             if not re.search(_AMOUNT + r"$", normalized[max(0, m.start() - 8):m.end()], re.IGNORECASE)]
    if codes:
        out["codes"] = codes
    phones = [{"value": m.group(0), "span": {"start": m.start(), "end": m.end()}}
              for m in re.finditer(r"(?<![\w])(?:\+91[\s-]?)?[6-9]\d{9}(?![\w])", normalized)]
    if phones:
        out["phone_numbers"] = phones
    upi = [{"value": m.group(0), "span": {"start": m.start(), "end": m.end()}}
           for m in re.finditer(r"\b[\w.-]{2,64}@(?:ok\w+|ybl|paytm|upi|ibl|axl|apl|icici|sbi|hdfcbank)\b", normalized, re.IGNORECASE)]
    if upi:
        out["upi_ids"] = upi
    return out


def _materialize(findings: list[Finding], input_id: str, normalized: str, raw_of, knowledge, assessment) -> tuple[list, list]:
    """Assign deterministic ids in text order and build the governed observation / indicator-observation objects."""
    family = _family_of(knowledge)
    ordered = sorted(findings, key=lambda f: (f.start, f.end, f.obs_type, f.canonical))
    ids = {id(f): f"{input_id}:o{n}" for n, f in enumerate(ordered, 1)}
    observations, indicators = [], []
    for f in ordered:
        oid = ids[id(f)]
        o = {"observation_id": oid, "observation_type": f.obs_type, "source_input_id": input_id, "status": f.status,
             "provenance": dict(PROVENANCE), "canonical_value": f.canonical, "raw_span": raw_of(f.start, f.end),
             "offsets": {"start": f.start, "end": f.end},
             "confidence": {"level": "MEDIUM" if f.status == "AMBIGUOUS" else "HIGH", "method": "CATEGORICAL"}}
        if f.structure is not None:
            o.update(polarity=f.structure.polarity, attribution=f.structure.attribution, mood=f.structure.mood)
        for key in ("actor", "action", "target", "pressure", "pretext", "payment_direction"):
            value = f.fields.get(key)
            if value:
                o[key] = value
        if f.url_ref:
            o["url_ref"] = f.url_ref
        observations.append(o)
        for entry in f.indicators:
            indicator_id, confidence, review = entry[:3]
            refs = [ids[r] for r in entry[3]] if len(entry) > 3 else [oid]
            spans = sorted({(fx.start, fx.end) for fx in ordered if ids[id(fx)] in refs})
            positive = knowledge.indicator(indicator_id) is not None
            io = {"indicator_id": indicator_id, "polarity": "POSITIVE" if positive else "NEGATIVE", "matched": "OBSERVED",
                  "input_id": input_id, "confidence": {"level": confidence, "method": "CATEGORICAL"},
                  "observation_refs": refs, "supporting_spans": [{"start": a, "end": b} for a, b in spans],
                  "language": assessment.language[0], "script": assessment.script[0],
                  "extraction_method": "COMPOSED" if len(refs) > 1 else "DETERMINISTIC_PATTERN",
                  "provenance": dict(PROVENANCE), "review_required": bool(review)}
            if positive:
                io["family_ref"] = family.get(indicator_id)
            indicators.append(io)
    indicators.sort(key=lambda i: (i["observation_refs"][0], i["indicator_id"]))
    return observations, indicators


def _validate_artifacts(observations, indicator_observations, urls, normalized, raw_of, knowledge) -> None:
    v = _validators()
    for kind, items in (("observation", observations), ("indicator_observation", indicator_observations), ("url", urls)):
        for item in items:
            errors = list(v[kind].iter_errors(item))
            if errors:
                raise ExtractionContractError(f"{kind} rejected by its governed schema at {_where(errors[0])}")
    for o in observations:
        start, end = o["offsets"]["start"], o["offsets"]["end"]
        if not (0 <= start < end <= len(normalized)) or o["raw_span"] != raw_of(start, end):
            raise ExtractionContractError(f"observation {o['observation_id']} is not grounded in the submitted text")
    for io in indicator_observations:
        iid = io["indicator_id"]
        if io["polarity"] == "POSITIVE":
            record = knowledge.indicator(iid)
            if record is None or record.get("polarity", "POSITIVE") != "POSITIVE" or not io.get("family_ref"):
                raise ExtractionContractError(f"positive indicator {iid} is not in the active registry partition")
            if iid not in knowledge.indicators_for_family(io["family_ref"]):
                raise ExtractionContractError(f"indicator {iid} is not an output of {io['family_ref']}")
        else:
            record = knowledge.negative_indicator(iid)
            if record is None or record.get("status", "ACTIVE") != "ACTIVE":
                raise ExtractionContractError(f"negative indicator {iid} is not ACTIVE in the active library")


# ================================================================ the protected evidence boundary (S4.1)
@dataclass(frozen=True)
class _Item:
    case_id: str
    submission_id: str
    input_type: str
    relationship: str | None
    synthetic: bool
    artifact_kind: str
    content_state: str
    locator: str | None
    sha256: str
    length: int
    media: str | None


def _load_item(cur, evidence_id: str) -> _Item | None:
    cur.execute(f"SELECT s.case_record_id::text, s.submission_id::text, s.declared_input_type, s.relationship_to_content,"
                f" s.is_synthetic, e.artifact_kind, e.content_state, e.ecs_locator, e.content_sha256, e.byte_length,"
                f" e.verified_media_type FROM {SCHEMA}.evidence_item e JOIN {SCHEMA}.submission s"
                " ON s.submission_id = e.submission_id WHERE e.evidence_item_id = %s", (evidence_id,))
    row = cur.fetchone()
    return _Item(*row) if row else None


def _audit(cur, principal, item: _Item, evidence_id: str, correlation_id: str, event_type: str, stage: str, outcome: str):
    audit_append(cur, AuditEvent(event_type=event_type, outcome=outcome, actor_kind="HUMAN",
                                 actor_principal_id=principal.principal_reference_id, target_kind="EVIDENCE_ITEM",
                                 target_id=evidence_id, case_record_id=item.case_id, evidence_item_id=evidence_id,
                                 correlation_id=correlation_id, safe_metadata={"stage": stage}))


def extract_finalized_evidence(runtime, principal, evidence_id: str, *, correlation_id: str) -> GovernedInput:
    """S4 live path: authorize, read the FINALIZED original bytes through the encrypted store, re-verify digest and
    length, audit the access, and extract against the deployment's ACTIVE, verified knowledge bundle.

    Authorization follows createEvaluations (api-v1.json: USER/ANALYST with CASE_ACCESS); the content never leaves the
    server. Raises ExtractionRefused (NOT_FOUND masked, FORBIDDEN, EVIDENCE_NOT_FINALIZED, UNSUPPORTED_ARTIFACT,
    NON_SYNTHETIC_INPUT) or ExtractionUnavailable (KNOWLEDGE_*, CONTENT_STORE_UNAVAILABLE, INTEGRITY_FAILURE,
    AUDIT_UNAVAILABLE, DATABASE_UNAVAILABLE). Nothing here ever yields a benign default."""
    from .cases import _Unavailable, _audit_denial, _connect, _uuid, _visible_case
    from .capabilities import evidence_schema_active
    from .evidence import get_store, supported_media
    from .knowledge_seam import evaluation_readiness

    if _uuid(correlation_id) is None:
        raise ValueError("correlation_id must be the request or run UUID")     # checked before any content is read
    if _uuid(evidence_id) is None:
        raise ExtractionRefused("NOT_FOUND")
    try:
        connection = _connect(runtime)
    except _Unavailable:
        raise ExtractionUnavailable("DATABASE_UNAVAILABLE") from None
    with connection:
        try:
            if not evidence_schema_active(connection):
                raise ExtractionUnavailable("DATABASE_UNAVAILABLE")
            with connection.cursor() as cur:
                item = _load_item(cur, evidence_id)
                case = _visible_case(cur, item.case_id, principal.principal_reference_id) if item else None
                if case is None:
                    raise ExtractionRefused("NOT_FOUND")             # masked: existence is not disclosed
                if not set(principal.roles) & set(EVALUATION_ROLES):
                    _audit_denial(runtime, _Correlated(correlation_id), principal, item.case_id,
                                  "ROLE_OWNERSHIP_OR_CONTENT_PERMISSION_REQUIRED", "createEvaluations")
                    raise ExtractionRefused("FORBIDDEN")
                if item.content_state != "FINALIZED" or not item.locator:
                    raise ExtractionRefused("EVIDENCE_NOT_FINALIZED")
                if item.artifact_kind != "TEXT_BODY" or not supported_media(item.media or ""):
                    raise ExtractionRefused("UNSUPPORTED_ARTIFACT")
                if not item.synthetic:
                    raise ExtractionRefused("NON_SYNTHETIC_INPUT")
                readiness = evaluation_readiness(cur, runtime.knowledge_verifier, runtime.deployment_ref)
                if not readiness.ready:
                    raise ExtractionUnavailable(readiness.reason)
                store = get_store(runtime)
                if store is None:
                    raise ExtractionUnavailable("CONTENT_STORE_UNAVAILABLE")
                try:
                    data = store.get(item.locator)
                    if len(data) != item.length or hashlib.sha256(data).hexdigest() != item.sha256:
                        raise IntegrityFailure("digest or length mismatch")
                except IntegrityFailure:
                    with connection.transaction():
                        _audit(cur, principal, item, evidence_id, correlation_id, "INTEGRITY_FAILURE", "EXTRACTION_READ", "FAILED")
                    raise ExtractionUnavailable("INTEGRITY_FAILURE") from None
                except ContentStoreUnavailable:
                    raise ExtractionUnavailable("CONTENT_STORE_UNAVAILABLE") from None
                try:
                    with connection.transaction():
                        _audit(cur, principal, item, evidence_id, correlation_id, "EVIDENCE_ACCESSED",
                               "DETERMINISTIC_EXTRACTION", "SUCCEEDED")
                except (AuditUnavailable, psycopg.Error, ValueError):
                    raise ExtractionUnavailable("AUDIT_UNAVAILABLE") from None      # no audited read, no content
        except psycopg.Error:
            raise ExtractionUnavailable("DATABASE_UNAVAILABLE") from None
    source = {"evidence_id": evidence_id, "submission_id": item.submission_id, "content_sha256": item.sha256,
              "byte_length": item.length}
    return extract_text(data, input_id=f"TL-INPUT:{evidence_id}", input_type=item.input_type, knowledge=readiness.knowledge,
                        relationship_to_content=item.relationship, synthetic=True, source=source)


class _Correlated:
    """Minimal request stand-in for the shared denial-audit helper (it reads only request.state.request_id)."""

    def __init__(self, correlation_id: str):
        self.state = type("State", (), {"request_id": correlation_id})()
