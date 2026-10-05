# text-adventure-rpg — API 容器（agent 家族 api 段 5405，host=container）
#
# 家族 deploy 链同款（kids/ai-tutoring 先例）：
#   VPS nginx 终结 TLS → /api/ proxy_pass http://127.0.0.1:5405 → 容器 uvicorn。
#   CI deploy job build & push（latest + tag 双份）→ VPS deploy/text-adventure-rpg.sh
#   拉镜像起容器。
#
# 端口是家族契约（docs/families/agent.md，2026-10-06 起 5305/5405），
# 钉死在 CMD 里不走 env 兜底；env-file APP_PORT=5405 与 CMD 双写一致。
# CMD 用 --factory main:create_app（settings 从 env 读），webserver.py 的
# 127.0.0.1 dev 姿态不动——容器侧 host 由这里覆盖。
# hatchling build backend：pyproject 声明 readme = "README.md"，必须 COPY 进来
# （ai-tutoring 首航指纹 hatchling-readme-metadata-dockerfile-copy）。
# 存档持久化：deploy 脚本挂 /home/deploy/<repo>/data/saves:/data/saves
# + APP_SAVES_DIR=/data/saves（文件存档，同三兄弟 SQLite 卷姿态）。
# 无 HEALTHCHECK（debian slim 无 wget）：探活由 deploy 脚本 host 侧 /api/health 完成。
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

EXPOSE 5405
CMD ["uvicorn", "--factory", "text_adventure_rpg.main:create_app", "--host", "0.0.0.0", "--port", "5405"]
