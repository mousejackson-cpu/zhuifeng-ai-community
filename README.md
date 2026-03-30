# ZhuiFeng AI Community Edition

Self-hosted community edition for image generation, prompt extraction, gallery inspiration, and lightweight video generation.

> Want the hosted version with no deployment, cloud history, membership, batch workflows, and more polished operations?
> Visit the Pro version: https://www.zhuifengai.hk/

## What this repo includes
- Image upload
- Prompt extraction endpoint
- Image generation endpoint
- Inspiration gallery
- Local history
- Batch download
- Bilingual UI
- Optional lightweight video entry

## What was removed from the commercial version
- User auth
- MySQL / cloud database dependency
- JWT
- Payment and billing
- Orders
- Credits / membership
- Referral system
- Admin panel
- WeChat login / payment flows

## Community vs Pro
| Capability | Community Edition | Pro Version |
|---|---|---|
| Local self-hosted deployment | Yes | No setup needed |
| Image generation | Yes | Yes |
| Prompt extraction | Yes | Yes |
| Inspiration gallery | Yes | Yes |
| Local history | Yes | Cloud sync |
| Batch workflows | Basic | Advanced |
| Membership / credits | No | Yes |
| Orders / billing | No | Yes |
| Referral system | No | Yes |
| Team collaboration | No | Yes |
| Hosted stability and operations | Self-managed | Official hosted |

## Quick start (local)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open http://127.0.0.1:5000

## Quick start (Docker)
```bash
cp .env.example .env
# fill in your own model keys

docker compose up --build
```

Open http://127.0.0.1:5000

## Environment variables
Copy `.env.example` to `.env` and fill your own keys.

Important variables:
- `ARK_API_KEY`
- `ARK_IMAGE_MODEL_ID`
- `ARK_ANALYSIS_MODEL_ID`
- `QWEN_API_KEY`
- `QWEN_IMAGE_MODEL_ID`
- `VIDEO_API_KEY`
- `VIDEO_MODEL_ID`
- `PRO_BASE_URL`
- `GITHUB_URL`

## Suggested repo structure
```text
zhuifeng-ai-community/
├── app.py
├── templates/
├── static/
├── data/
├── uploads/
├── generated/
├── temp/
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Publish checklist
Before uploading to GitHub, confirm:
1. No production API keys are committed.
2. No payment certificates or private keys are present.
3. No internal domains or webhook callbacks are present.
4. `.env` is excluded.
5. Upload, generated, temp, and data files are ignored except `.gitkeep`.

## License recommendation
See `LICENSE-CHOICE.md`.
Recommended default for this project: **AGPL-3.0**.

## Notes
- Video is optional and can stay disabled if you do not fill video credentials.
- This repo is designed to stay useful for developers while still leaving obvious reasons to use the hosted Pro version.
