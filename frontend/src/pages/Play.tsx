import { useEffect, useRef, useState } from "react";
import * as api from "../api";
import type { ClassInfo, GameDetail, SessionState } from "../types";

const LAST_KEY = "rpg:lastGame";

const CLASS_CN: Record<string, string> = {
  warrior: "战士",
  mage: "法师",
  rogue: "盗贼",
};

const DIR_CN: Record<string, string> = {
  north: "北 ↑",
  south: "南 ↓",
  east: "东 →",
  west: "西 ←",
};

function splitLabel(label: string): [string, string] {
  const i = label.indexOf("（");
  return i > 0 ? [label.slice(0, i), label.slice(i)] : [label, ""];
}

export default function Play() {
  const [classes, setClasses] = useState<ClassInfo[]>([]);
  const [name, setName] = useState("冒险者");
  const [picked, setPicked] = useState("warrior");
  const [detail, setDetail] = useState<GameDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [saves, setSaves] = useState<string[]>([]);
  const [slot, setSlot] = useState("s1");
  const [cmd, setCmd] = useState("");
  const logRef = useRef<HTMLDivElement>(null);

  // 启动：载职业表 + 尝试恢复上次会话（重启即清的服务端会话可能已不在）
  useEffect(() => {
    api.listClasses().then(setClasses).catch((e: Error) => setError(e.message));
    let last: string | null = null;
    try {
      last = localStorage.getItem(LAST_KEY);
    } catch {
      /* 无 localStorage（隐私模式），跳过恢复 */
    }
    if (last) {
      api
        .getGame(last)
        .then((d) => setDetail(d))
        .catch(() => {
          try {
            localStorage.removeItem(LAST_KEY);
          } catch {
            /* ignore */
          }
        });
    }
  }, []);

  useEffect(() => {
    if (detail) {
      api.listSaves().then(setSaves).catch(() => setSaves([]));
    }
  }, [detail]);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [detail?.state.log.length]);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const d = await api.createGame(picked, name.trim() || "冒险者");
      setDetail(d);
      try {
        localStorage.setItem(LAST_KEY, d.id);
      } catch {
        /* ignore */
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function act(fn: () => Promise<unknown>) {
    if (!detail || busy) return;
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      await fn();
      const fresh = await api.getGame(detail.id);
      setDetail(fresh);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const run = (input: string) => {
    const cleaned = input.trim();
    if (!cleaned || !detail) return;
    setCmd("");
    act(() => api.runCommand(detail.id, cleaned));
  };

  async function doSave() {
    if (!detail) return;
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const r = await api.saveGame(detail.id, slot.trim());
      setInfo(r.message);
      api.listSaves().then(setSaves).catch(() => setSaves([]));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function quit() {
    setDetail(null);
    setError(null);
    setInfo(null);
    try {
      localStorage.removeItem(LAST_KEY);
    } catch {
      /* ignore */
    }
  }

  // ---- 建局态 ----
  if (!detail) {
    const maxHp = Math.max(...classes.map((c) => c.stats.max_hp), 1);
    const maxMp = Math.max(...classes.map((c) => c.stats.max_mp), 1);
    const maxAtk = Math.max(...classes.map((c) => c.stats.atk), 1);
    const maxDef = Math.max(...classes.map((c) => c.stats.def_), 1);
    return (
      <section className="setup">
        <p className="lead">
          选择你的职业，踏入幽暗森林。三职业数值差异显著：战士耐打、法师技能凶猛、盗贼爆发高。
          打赢挡路的敌人才能继续前进；每一步都可以存档。
        </p>
        <div className="field">
          <label htmlFor="hero-name">角色名</label>
          <input
            id="hero-name"
            value={name}
            maxLength={12}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="class-grid">
          {classes.map((c) => {
            const [head, tail] = splitLabel(c.label);
            return (
              <button
                type="button"
                key={c.class}
                className={`class-card${picked === c.class ? " picked" : ""}`}
                onClick={() => setPicked(c.class)}
              >
                <strong>{head}</strong>
                <small>{tail}</small>
                <StatBar k="HP" v={c.stats.max_hp} max={maxHp} tone="hp" />
                <StatBar k="MP" v={c.stats.max_mp} max={maxMp} tone="mp" />
                <StatBar k="ATK" v={c.stats.atk} max={maxAtk} tone="amber" />
                <StatBar k="DEF" v={c.stats.def_} max={maxDef} tone="dim" />
              </button>
            );
          })}
        </div>
        <ErrorLine error={error} />
        <button
          type="button"
          className="primary"
          disabled={busy || classes.length === 0}
          onClick={start}
        >
          ▶ 开始冒险
        </button>
      </section>
    );
  }

  // ---- 游玩态 ----
  const state: SessionState = detail.state;
  const hero = state.hero;
  const inBattle = state.battle !== null && !state.battle.over;
  const battle = state.battle;

  return (
    <section className="play">
      <section className="panel hud">
        <div className="hud-name">
          <strong>{hero.name}</strong>
          <span className="cls">{CLASS_CN[hero.class] ?? hero.class}</span>
          <span className="lv">Lv {hero.level}</span>
        </div>
        <div className="statline">
          <span className="stat-key">HP</span>
          <div className="bar hp">
            <i style={{ width: `${(hero.hp / hero.max_hp) * 100}%` }} />
          </div>
          <span className="stat-val">
            {hero.hp}/{hero.max_hp}
          </span>
        </div>
        <div className="statline">
          <span className="stat-key">MP</span>
          <div className="bar mp">
            <i style={{ width: `${(hero.mp / hero.max_mp) * 100}%` }} />
          </div>
          <span className="stat-val">
            {hero.mp}/{hero.max_mp}
          </span>
        </div>
        <div className="hud-combat">
          ATK {hero.atk} · DEF {hero.def_}
        </div>
      </section>

      <section className="panel scene">
        <h2>{state.scene.name}</h2>
        {state.narration && <p className="narration">{state.narration}</p>}
        <p className="desc">{state.scene.description}</p>
        {state.scene.items.length > 0 && (
          <p className="chips-line">
            地上：<Chips items={state.scene.items} tone="amber" />
          </p>
        )}
        {state.pending_enemy && !inBattle && (
          <p className="warn">
            ⚠ {state.pending_enemy.name} 在此徘徊——不解决它就无法移动。
          </p>
        )}
        <div className="exits">
          {Object.entries(state.scene.exits).map(([dir, target]) => (
            <button
              type="button"
              key={dir}
              disabled={busy || inBattle}
              onClick={() => run(`go ${dir}`)}
              title={`前往 ${target}`}
            >
              {DIR_CN[dir] ?? dir}
            </button>
          ))}
        </div>
      </section>

      {battle && !battle.over && (
        <section className="panel battle">
          <h2>⚔ 战斗 · {battle.enemy.name}</h2>
          <div className="statline">
            <span className="stat-key foe">敌</span>
            <div className="bar hp">
              <i style={{ width: `${(battle.enemy.hp / battle.enemy.max_hp) * 100}%` }} />
            </div>
            <span className="stat-val">
              {battle.enemy.hp}/{battle.enemy.max_hp}
            </span>
          </div>
          <div className="battle-actions">
            <button type="button" className="amber" disabled={busy} onClick={() => run("attack")}>
              攻击
            </button>
            <button type="button" className="blue" disabled={busy} onClick={() => run("skill")}>
              技能（10 MP）
            </button>
          </div>
          <div className="battle-log">
            {battle.log.slice(-3).map((line, i) => (
              <p key={i}>{line}</p>
            ))}
          </div>
        </section>
      )}

      {battle && battle.over && (
        <section className={`panel settle ${battle.result === "win" ? "win" : "lose"}`}>
          {battle.result === "win" ? (
            <h2>== 战斗胜利 ==</h2>
          ) : (
            <>
              <h2>== 你倒下了 ==</h2>
              <p className="warn">冒险已结束。读一个存档继续，或重新选职业开新局。</p>
            </>
          )}
        </section>
      )}

      <section className="panel actions">
        <div className="cmdline">
          <input
            aria-label="指令输入"
            placeholder="输入指令：go north / look / status / fight / attack / skill"
            value={cmd}
            disabled={busy || state.game_over}
            onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") run(cmd);
            }}
          />
          <button type="button" disabled={busy || state.game_over} onClick={() => run(cmd)}>
            执行
          </button>
        </div>
        <div className="quick">
          <button type="button" disabled={busy || inBattle || state.game_over} onClick={() => run("look")}>
            环视
          </button>
          <button type="button" disabled={busy || inBattle || state.game_over} onClick={() => run("status")}>
            状态
          </button>
          <button
            type="button"
            className="amber"
            disabled={busy || inBattle || state.game_over || !state.pending_enemy}
            onClick={() => run("fight")}
          >
            战斗
          </button>
        </div>
        <ErrorLine error={error} />
        {info && <p className="info">{info}</p>}
        <div className="saves">
          <span className="saves-label">存档</span>
          <input
            aria-label="存档槽位"
            value={slot}
            onChange={(e) => setSlot(e.target.value)}
            placeholder="槽位名"
          />
          <button type="button" disabled={busy || state.game_over} onClick={doSave}>
            存档
          </button>
          <button
            type="button"
            disabled={busy || !slot.trim()}
            onClick={() => {
              const s = slot.trim();
              if (s) act(() => api.loadGame(detail.id, s));
            }}
          >
            读档
          </button>
          {saves.map((s) => (
            <button
              type="button"
              key={s}
              className="chip"
              disabled={busy}
              onClick={() => {
                setSlot(s);
                act(() => api.loadGame(detail.id, s));
              }}
              title={`读取槽位 ${s}`}
            >
              {s}
            </button>
          ))}
        </div>
      </section>

      <section className="panel terminal">
        <h2>冒险日志</h2>
        <div className="log" ref={logRef}>
          {state.log.map((line, i) => (
            <p key={i}>{line}</p>
          ))}
        </div>
        <div className="foot-row">
          <button type="button" className="ghost" onClick={quit}>
            ← 重选职业
          </button>
        </div>
      </section>
    </section>
  );
}

function StatBar(props: { k: string; v: number; max: number; tone: string }) {
  return (
    <div className="statline mini">
      <span className="stat-key">{props.k}</span>
      <div className={`bar ${props.tone}`}>
        <i style={{ width: `${(props.v / props.max) * 100}%` }} />
      </div>
      <span className="stat-val">{props.v}</span>
    </div>
  );
}

function Chips(props: { items: string[]; tone?: string }) {
  return (
    <>
      {props.items.map((it) => (
        <span key={it} className={`chip static ${props.tone ?? ""}`}>
          {it}
        </span>
      ))}
    </>
  );
}

function ErrorLine(props: { error: string | null }) {
  if (!props.error) return null;
  return <p className="error">✕ {props.error}</p>;
}
