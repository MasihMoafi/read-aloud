import * as React from "react"
import { createRoot } from "react-dom/client"
import { Pause, Play, Square } from "lucide-react"
import { Button } from "./components/button"
import { Slider } from "./components/slider"

type PlayerState = { active: boolean; paused: boolean; speed: number; speedValue: string; ready: boolean; error: string }
declare global {
  interface Window {
    readAloud: {
      onState: (listener: (state: PlayerState) => void) => void
      action: (name: "pause" | "stop" | "speed", value?: number) => void
    }
  }
}

function Player() {
  const [state, setState] = React.useState<PlayerState>({ active: false, paused: false, speed: 0, speedValue: "1.0", ready: false, error: "" })
  React.useEffect(() => window.readAloud.onState(setState), [])

  return (
    <main className="player flex h-full items-center gap-2 rounded-lg border bg-background px-3 text-foreground">
      <span className="logo size-6 shrink-0 bg-primary" role="img" aria-label="Read Aloud" />
      <Button variant="ghost" size="icon" aria-label={state.paused ? "Play" : "Pause"} onClick={() => window.readAloud.action("pause")}>
        {state.paused ? <Play aria-hidden="true" /> : <Pause aria-hidden="true" />}
      </Button>
      <Button variant="ghost" size="icon" aria-label="Stop" onClick={() => window.readAloud.action("stop")}>
        <Square aria-hidden="true" />
      </Button>
      <Slider className="min-w-12 flex-1" min={0} max={4} step={1} value={[state.speed]}
        aria-label="Playback speed" aria-valuetext={`${state.speedValue} times`}
        onValueChange={([speed]) => window.readAloud.action("speed", speed)} />
      <output className="w-12 text-right text-sm tabular-nums" aria-live="polite">{state.speedValue}×</output>
    </main>
  )
}

createRoot(document.getElementById("root")!).render(<Player />)
