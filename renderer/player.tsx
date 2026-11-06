import * as React from "react"
import { createRoot } from "react-dom/client"
import { Check, Pause, Play, Square, X } from "lucide-react"
import { Button } from "./components/button"

type PlayerState = { active: boolean; paused: boolean; speed: number; speedValue: string; ready: boolean; error: string }
declare global {
  interface Window {
    readAloud: {
      onState: (listener: (state: PlayerState) => void) => void
      action: (name: "pause" | "stop" | "hide") => void
      setSpeed: (index: number) => void
      menu: (open: boolean) => void
    }
  }
}

// Same steps as SPEEDS in core/main.rs; the daemon accepts their index.
const SPEEDS = ["1.0", "1.25", "1.5", "1.75", "2.0"]

function SpeedMenu({ state }: { state: PlayerState }) {
  const [open, setOpen] = React.useState(false)
  const toggle = (next: boolean) => { setOpen(next); window.readAloud.menu(next) }
  React.useEffect(() => {
    if (!open) return
    const close = () => toggle(false)
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") close() }
    window.addEventListener("blur", close)
    window.addEventListener("keydown", onKey)
    return () => { window.removeEventListener("blur", close); window.removeEventListener("keydown", onKey) }
  }, [open])
  React.useEffect(() => { if (!state.active && open) toggle(false) }, [state.active])

  return <>
    {open && (
      <ul role="menu" aria-label="Speed" className="fixed inset-x-1 top-1 flex flex-col">
        {SPEEDS.map((value, index) => (
          <li key={value} role="none">
            <button role="menuitemradio" aria-checked={index === state.speed}
              className="flex h-7 w-full items-center gap-2 rounded px-2 text-xs tabular-nums hover:bg-accent focus-visible:bg-accent outline-none"
              onClick={() => { window.readAloud.setSpeed(index); toggle(false) }}>
              <Check aria-hidden="true" className={`size-3.5 ${index === state.speed ? "" : "invisible"}`} />
              {value === "1.0" ? "Normal" : `${value}×`}
            </button>
          </li>
        ))}
      </ul>
    )}
    <Button variant="ghost" aria-label="Speed" aria-haspopup="menu" aria-expanded={open}
      className="h-7 w-12 px-0 text-xs tabular-nums" onClick={() => toggle(!open)}>
      {state.speedValue}×
    </Button>
  </>
}

function Player() {
  const [state, setState] = React.useState<PlayerState>({ active: false, paused: false, speed: 0, speedValue: "1.0", ready: false, error: "" })
  React.useEffect(() => window.readAloud.onState(setState), [])

  return (
    <main className="player relative h-full rounded-lg border bg-background text-foreground">
      <div className="absolute inset-x-0 bottom-0 flex h-[38px] items-center gap-0.5 px-2">
        <span className="logo mr-1 size-5 shrink-0 bg-primary" role="img" aria-label="Read Aloud" />
        {!state.active ? <>
          <span className="min-w-0 flex-1 truncate text-xs opacity-80">Super+R to read</span>
          <Button variant="ghost" aria-label="Close" className="size-7" onClick={() => window.readAloud.action("hide")}>
            <X aria-hidden="true" />
          </Button>
        </> : <>
          <Button variant="ghost" aria-label={state.paused ? "Play" : "Pause"} className="size-7" onClick={() => window.readAloud.action("pause")}>
            {state.paused ? <Play aria-hidden="true" /> : <Pause aria-hidden="true" />}
          </Button>
          <Button variant="ghost" aria-label="Stop" className="size-7" onClick={() => window.readAloud.action("stop")}>
            <Square aria-hidden="true" className="size-3.5" />
          </Button>
          <SpeedMenu state={state} />
        </>}
      </div>
    </main>
  )
}

createRoot(document.getElementById("root")!).render(<Player />)
