import { useEffect, useState } from "react";
import Play from "./pages/Play";
import { getHealth } from "./api";

export default function App() {
  const [mode, setMode] = useState<string>("");

  useEffect(() => {
    getHealth()
      .then((h) => setMode(h.mode))
      .catch(() => setMode("offline"));
  }, []);

  return (
    <>
      <header className="site-head">
        <h1>
          <span className="sigil">▚</span> 文字冒险 RPG
          <span className="sub">战斗集成版 · character / combat / formulas / narrative</span>
        </h1>
        {mode && <span className={`pill pill-${mode}`}>{mode.toUpperCase()}</span>}
      </header>
      <main>
        <Play />
      </main>
      <footer className="site-foot">
        <span>《Harness 工程》卷三配套案例 · text-full-rpg Web 化</span>
      </footer>
    </>
  );
}
