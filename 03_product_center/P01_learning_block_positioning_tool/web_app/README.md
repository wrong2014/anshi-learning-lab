# P01 Web Prototype

This is the first usable frontend entrance for the P01 science learning block positioning agent.

Run:

```powershell
cd D:\wbh\social-media\anshi-learning-lab\03_product_center\P01_learning_block_positioning_tool
.\run_p01_web.ps1
```

Then open:

```text
http://127.0.0.1:8765
```

The browser only receives UI blocks and results. The factor scoring rules stay in the Python backend.

LLM keys are optional. Without keys the app runs in rules mode. With keys, copy
`agent_engine/.env.example` to `agent_engine/.env` and fill the provider config.
