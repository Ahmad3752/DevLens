from app.services.llm_client import invoke_json, provider_status


print(provider_status())
print(invoke_json("Return only valid JSON with exactly these fields: ok=true, provider=\"llm\"."))
