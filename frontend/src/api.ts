// 请求层：同源相对 /api（dev 由 vite 代理，prod 由 nginx 承接，代码不写绝对地址）
import type {
  ClassInfo,
  CommandResult,
  GameDetail,
  Health,
  SaveResult,
} from "./types";

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (body && body.detail !== undefined) detail = String(body.detail);
    } catch {
      /* 非 JSON 错误体，保留状态行 */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export function getHealth(): Promise<Health> {
  return fetch("/api/health").then((r) => asJson<Health>(r));
}

export function listClasses(): Promise<ClassInfo[]> {
  return fetch("/api/classes").then((r) => asJson<ClassInfo[]>(r));
}

export function createGame(
  cls: string,
  name: string,
  sceneId = "forest"
): Promise<GameDetail> {
  return fetch("/api/games", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ class: cls, name, scene_id: sceneId }),
  }).then((r) => asJson<GameDetail>(r));
}

export function getGame(id: string): Promise<GameDetail> {
  return fetch(`/api/games/${encodeURIComponent(id)}`).then((r) =>
    asJson<GameDetail>(r)
  );
}

export function runCommand(id: string, input: string): Promise<CommandResult> {
  return fetch(`/api/games/${encodeURIComponent(id)}/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input }),
  }).then((r) => asJson<CommandResult>(r));
}

export function saveGame(id: string, slot: string): Promise<SaveResult> {
  return fetch(`/api/games/${encodeURIComponent(id)}/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slot }),
  }).then((r) => asJson<SaveResult>(r));
}

export function loadGame(id: string, slot: string): Promise<CommandResult> {
  return fetch(`/api/games/${encodeURIComponent(id)}/load`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slot }),
  }).then((r) => asJson<CommandResult>(r));
}

export function listSaves(): Promise<string[]> {
  return fetch("/api/saves").then((r) => asJson<string[]>(r));
}
