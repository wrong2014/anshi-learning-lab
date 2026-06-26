# P01 Diagnostic Agent Engine

This is the local V1 skeleton for the science learning block positioning agent.

Current scope:

- Pydantic schemas.
- Rule-based factor scoring.
- Natural conversation UI block planning.
- Empty provider config for DeepSeek and Doubao.
- Runnable local demo without LLM keys.

Not included yet:

- Real PydanticAI calls.
- DeepSeek API calls.
- Doubao multimodal / speech calls.
- LangGraph workflow persistence.

Run local demo:

```powershell
cd D:\wbh\social-media\anshi-learning-lab\03_product_center\P01_learning_block_positioning_tool\agent_engine
python .\scripts\demo_rule_engine.py
```

