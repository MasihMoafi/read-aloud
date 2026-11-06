import * as React from "react"
import { createRoot } from "react-dom/client"
import { Check, ChevronUp, Pause, Play, Square, X } from "lucide-react"
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
const card = "rounded-xl border border-border/40 bg-background text-foreground"
const icon = "size-7 rounded-lg [&_svg:not([class*='size-'])]:size-4"

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
      <ul role="menu" aria-label="Speed" className={`${card} fixed inset-x-0 top-0 flex flex-col p-1`}>
        {SPEEDS.map((value, index) => (
          <li key={value} role="none">
            <button role="menuitemradio" aria-checked={index === state.speed}
              className="flex h-7 w-full items-center gap-2 rounded-lg px-2 text-xs tabular-nums outline-none hover:bg-accent focus-visible:bg-accent aria-checked:font-semibold"
              onClick={() => { window.readAloud.setSpeed(index); toggle(false) }}>
              <Check aria-hidden="true" className={`size-3.5 text-primary ${index === state.speed ? "" : "invisible"}`} />
              {value === "1.0" ? "Normal" : `${value}×`}
            </button>
          </li>
        ))}
      </ul>
    )}
    <Button variant="ghost" aria-label="Speed" aria-haspopup="menu" aria-expanded={open}
      className="ml-auto h-7 gap-0.5 rounded-lg px-2 text-xs tabular-nums has-[>svg]:px-2" onClick={() => toggle(!open)}>
      <span>{state.speedValue}×</span>
      <ChevronUp aria-hidden="true" className={`size-3 opacity-60 transition-transform ${open ? "rotate-180" : ""}`} />
    </Button>
  </>
}

function Player() {
  const [state, setState] = React.useState<PlayerState>({ active: false, paused: false, speed: 0, speedValue: "1.0", ready: false, error: "" })
  React.useEffect(() => window.readAloud.onState(setState), [])

  return (
    <main className={`player ${card} fixed inset-x-0 bottom-0 flex h-10 items-center gap-0.5 px-1.5`}>
      <span className="flex size-7 shrink-0 items-center justify-center">
        <span className="logo size-[18px] bg-primary" role="img" aria-label="Read Aloud" />
      </span>
      {!state.active ? <>
        <span className="min-w-0 flex-1 truncate px-1 text-xs text-foreground/70">Super+R to read</span>
        <Button variant="ghost" aria-label="Close" className={icon} onClick={() => window.readAloud.action("hide")}>
          <X aria-hidden="true" />
        </Button>
      </> : <>
        <Button variant="ghost" aria-label={state.paused ? "Play" : "Pause"} className={icon} onClick={() => window.readAloud.action("pause")}>
          {state.paused ? <Play aria-hidden="true" className="fill-current" /> : <Pause aria-hidden="true" className="fill-current" />}
        </Button>
        <Button variant="ghost" aria-label="Stop" className={icon} onClick={() => window.readAloud.action("stop")}>
          <Square aria-hidden="true" className="size-3.5 fill-current" />
        </Button>
        <SpeedMenu state={state} />
      </>}
    </main>
  )
}

createRoot(document.getElementById("root")!).render(<Player />)
