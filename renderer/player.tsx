import * as React from "react"
import { createRoot } from "react-dom/client"
import { Pause, Play, Plus, Square, X } from "lucide-react"
import { Button } from "./components/button"

type PlayerState = { active: boolean; paused: boolean; speed: number; speedValue: string; ready: boolean; error: string }
declare global {
  interface Window {
    readAloud: {
      onState: (listener: (state: PlayerState) => void) => void
      action: (name: "pause" | "stop" | "faster" | "hide") => void
    }
  }
}

function Player() {
  const [state, setState] = React.useState<PlayerState>({ active: false, paused: false, speed: 0, speedValue: "1.0", ready: false, error: "" })
  React.useEffect(() => window.readAloud.onState(setState), [])

  return (
    <main className="player flex h-full items-center gap-2 rounded-lg border bg-background px-3 text-foreground">
      <span className="logo h-6 w-6 shrink-0 bg-primary" aria-hidden="true" />
      {!state.active ? <>
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="text-sm font-medium">Read Aloud</span>
          <span className="text-xs opacity-80">Select text, then press Windows+R</span>
        </div>
        <Button variant="ghost" size="icon" aria-label="Close" onClick={() => window.readAloud.action("hide")}>
          <X aria-hidden="true" />
        </Button>
      </> : <>
        <Button variant="ghost" size="icon" aria-label={state.paused ? "Play" : "Pause"} onClick={() => window.readAloud.action("pause")}>
          {state.paused ? <Play aria-hidden="true" /> : <Pause aria-hidden="true" />}
        </Button>
        <Button variant="ghost" size="icon" aria-label="Stop" onClick={() => window.readAloud.action("stop")}>
          <Square aria-hidden="true" />
        </Button>
        <output className="ml-auto text-sm tabular-nums" aria-live="polite">{state.speedValue}×</output>
        <Button variant="outline" size="sm" aria-label="Increase speed" disabled={state.speed >= 4}
          onClick={() => window.readAloud.action("faster")}>
          <Plus aria-hidden="true" /> Faster
        </Button>
      </>}
    </main>
  )
}

createRoot(document.getElementById("root")!).render(<Player />)
