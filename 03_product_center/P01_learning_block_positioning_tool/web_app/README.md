# P01 Web Prototype

This is the first usable frontend entrance for the P01 science learning block positioning agent.

The current user-facing entrance is the Vite frontend on port `5173`.
The Python backend on port `8765` only serves APIs.

Backend:

```powershell
cd D:\wbh\social-media\anshi-learning-lab\03_product_center\P01_learning_block_positioning_tool
python .\web_app\server.py
```

Frontend:

```powershell
cd D:\wbh\social-media\anshi-learning-lab\03_product_center\P01_learning_block_positioning_tool\web_app\frontend
npm install
npm run dev
```

Then open the app:

```text
http://localhost:5173/
```

The browser only receives UI blocks and results. The factor scoring rules stay in the Python backend.

LLM keys are optional. Without keys the app runs in rules mode. With keys, copy
`agent_engine/.env.example` to `agent_engine/.env` and fill the provider config.

For the full AI-readable startup flow, see:

```text
03_product_center/P01_learning_block_positioning_tool/STARTUP_RUNBOOK_FOR_AI.md
```
