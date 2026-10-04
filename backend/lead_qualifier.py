"""
Live Lead Qualification Agent – Python client
Endpoint: https://live-lead-qualifier-agent.vercel.app/api/qualify
"""

import httpx
from typing import Any, Dict

ENDPOINT = "https://live-lead-qualifier-agent.vercel.app/api/qualify"

async def qualify_lead(lead: Dict[str, Any]) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(ENDPOINT, json=lead)
            response.raise_for_status()
            return response.json()
    except Exception as err:
        print(f"[LeadQualifier] Failed to qualify lead: {err}")
        return {
            "success": False,
            "score": 0,
            "recommended_action": "nurture",
            "reason": "API unavailable – defaulting to nurture",
            "summary": "Lead scoring service temporarily unavailable",
            "error": str(err),
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "agent": "Live Lead Qualification Agent v1.0 (fallback)",
        }
