"""Curated flood-safety guidance for the emergency assistant fallback."""
import logging

from .gemini_emergency import (
    GeminiConfigurationError,
    GeminiInvalidResponseError,
    GeminiProviderError,
    GeminiTimeoutError,
    generate_gemini_response,
)

MODE = "curated_fallback"
logger = logging.getLogger(__name__)

_URGENT_GUIDANCE = (
    "If you or someone else is in immediate danger, contact your local emergency "
    "services now and follow official local authority instructions. Do not wait for "
    "this assistant.\n\n"
    "• Move to higher ground or an upper level only if you can do so safely.\n"
    "• Do not walk, swim, or drive through floodwater, and do not attempt a water rescue.\n"
    "• If trapped, move to the highest safe level, avoid enclosed areas where water "
    "can rise, and signal for help from a safe place.\n"
    "• Stay away from downed power lines and electrical equipment in or near water."
)

_GUIDANCE = (
    (
        ("trapped", "stranded", "rescue", "water entering", "water entered",
         "water enters my house", "water enters my home", "water enters the house",
         "water in my house", "water inside", "flooded house", "immediate danger"),
        _URGENT_GUIDANCE,
    ),
    (
        ("after the flood", "after a flood", "post-flood", "flood is over",
         "return home", "clean up", "cleanup", "floodwater recede"),
        "After a flood:\n"
        "• Return home only when local authorities say it is safe.\n"
        "• Avoid floodwater, damaged buildings, downed power lines, and anything "
        "electrical that is wet or near water.\n"
        "• Wear sturdy shoes and gloves during cleanup. Do not use food or drinking "
        "water that may have been contaminated; follow local water-safety advisories.\n"
        "• Photograph damage only when it is safe to do so, and seek medical help "
        "for injuries or possible exposure to contaminated water.",
    ),
    (
        ("emergency kit", "pack", "prepare", "prepared", "family", "protect my family",
         "supplies", "go bag"),
        "Prepare your household before flooding:\n"
        "• Make a family communication and evacuation plan, including a meeting place "
        "and arrangements for children, older adults, people with disabilities, and pets.\n"
        "• Pack drinking water, non-perishable food, needed medicines, a first-aid kit, "
        "flashlight and batteries, phone charger or power bank, hygiene items, and copies "
        "of important documents in a waterproof bag.\n"
        "• Keep up with official local alerts and know where you can move to higher "
        "ground. Leave when authorities instruct you to evacuate.",
    ),
    (
        ("water enters my home", "water enters the house", "water in my home",
         "flood in my house", "house is flooding", "home is flooding"),
        _URGENT_GUIDANCE,
    ),
    (
        ("during a flood", "flood safety", "what should i do", "flooding now",
         "water is rising", "evacuate", "flood"),
        "During a flood:\n"
        "• Follow official local alerts and evacuation instructions; move to higher "
        "ground when safe.\n"
        "• Do not walk, swim, or drive through floodwater. Turn around and use only a "
        "route authorities identify as open.\n"
        "• Keep away from downed power lines and electrical equipment near water.\n"
        "• If you face immediate danger, contact your local emergency services. This "
        "assistant cannot see live conditions or request a rescue.",
    ),
)

_DEFAULT_GUIDANCE = (
    "I can share general flood-safety guidance, but I cannot assess live conditions "
    "or your exact level of danger. Follow official local authority instructions. "
    "If anyone is in immediate danger, contact your local emergency services now. "
    "Do not walk, swim, or drive through floodwater. You can ask about what to do "
    "during a flood, household preparedness, emergency kits, or safety after a flood."
)


def generate_emergency_guidance(message):
    """Return a response from curated guidance without claiming to use a live AI."""
    normalized_message = message.casefold()
    for keywords, guidance in _GUIDANCE:
        if any(keyword in normalized_message for keyword in keywords):
            return {"answer": guidance, "mode": MODE}
    return {"answer": _DEFAULT_GUIDANCE, "mode": MODE}


def generate_assistant_response(message, history=None):
    """Prefer Gemini and explicitly identify a safe curated fallback when unavailable."""
    try:
        answer = generate_gemini_response(message, history=history)
    except GeminiConfigurationError:
        logger.info("Gemini is not configured; using curated emergency guidance.")
        fallback_reason = "missing_api_key"
    except GeminiTimeoutError:
        logger.warning("Gemini request timed out; using curated emergency guidance.")
        fallback_reason = "timeout"
    except GeminiInvalidResponseError:
        logger.warning("Gemini returned an invalid response; using curated emergency guidance.")
        fallback_reason = "invalid_response"
    except GeminiProviderError as exc:
        logger.warning(
            "Gemini provider request failed (sdk_error=%s, status_code=%s, "
            "fallback_reason=%s); using curated emergency guidance.",
            exc.sdk_error_type,
            exc.status_code,
            exc.fallback_reason,
        )
        fallback_reason = exc.fallback_reason
    else:
        return {"answer": answer, "mode": "gemini", "fallback_reason": None}

    fallback = generate_emergency_guidance(message)
    return {
        **fallback,
        "fallback_reason": fallback_reason,
    }
