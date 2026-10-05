// 与后端 api/routes.py + game_service.GameService.view 的响应形状一一对应
export interface Health {
  ok: boolean;
  mode: string;
}

export interface ClassInfo {
  class: string;
  label: string;
  stats: {
    max_hp: number;
    max_mp: number;
    atk: number;
    def_: number;
  };
}

export interface HeroView {
  name: string;
  class: string;
  hp: number;
  max_hp: number;
  mp: number;
  max_mp: number;
  atk: number;
  def_: number;
  level: number;
}

export interface SceneView {
  id: string;
  name: string;
  description: string;
  exits: Record<string, string>;
  items: string[];
  npcs: string[];
}

export interface PendingEnemy {
  id: string;
  name: string;
}

export interface BattleView {
  enemy: {
    id: string | null;
    name: string;
    hp: number;
    max_hp: number;
  };
  log: string[];
  over: boolean;
  result: "win" | "lose" | null;
}

export interface SessionState {
  hero: HeroView;
  scene: SceneView;
  pending_enemy: PendingEnemy | null;
  battle: BattleView | null;
  narration: string;
  log: string[];
  game_over: boolean;
}

export interface GameDetail {
  id: string;
  created_at: string;
  state: SessionState;
}

export interface CommandResult {
  messages: string[];
  state: SessionState;
  game_over: boolean;
}

export interface SaveResult {
  slot: string;
  message: string;
}
