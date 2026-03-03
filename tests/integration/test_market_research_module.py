from __future__ import annotations


def test_market_research_generates_strategy_from_csv_inputs(client):
    payload = {
        "mode": "sales_rep",
        "user": "user.one@example.com",
        "regions": ["East", "Central"],
        "strategic_goal": "Prioritize East and Central accounts for this quarter.",
        "current_customers_csv": (
            "account,region,industry,current_platform,use_case,arr\n"
            "Account Alpha Health,East,Healthcare,Aurora MySQL,Claims analytics,$1.2M\n"
            "Account Gamma,Central,Retail,Sharded MySQL,Checkout scaling,$640K\n"
        ),
        "pipeline_csv": (
            "account,region,stage,industry,workload,est_arr,close_quarter,competing_vendor\n"
            "Account Delta,East,POC,Financial Services,Fraud scoring,$900K,Q2 FY26,CompetitorY\n"
            "Account Epsilon,Central,Technical Validation,Logistics,Fleet telemetry,$550K,Q3 FY26,CompetitorX\n"
        ),
        "additional_context": "Team has 2 AEs and 1 SE.",
        "top_n": 5,
    }

    res = client.post("/rep/market-research", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert isinstance(data.get("summary"), str)
    assert isinstance(data.get("required_inputs"), list)
    assert isinstance(data.get("priority_accounts"), list)
    assert len(data["priority_accounts"]) > 0
    assert isinstance(data.get("execution_plan"), list)
