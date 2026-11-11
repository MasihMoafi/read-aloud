import * as React from "react"
import { createRoot } from "react-dom/client"
import { AudioLines, Check, Pause, Play, Square, X, Zap } from "lucide-react"
import { Button } from "./components/button"

type PlayerState = { active: boolean; paused: boolean; speed: number; speedValue: string; ready: boolean; error: string; download: { phase: "checking" | "downloading" | "failed" | "ready"; percent: number; error: string } }
type Voices = { voices: string[]; selected: string }
type Menu = "speed" | "voice" | null
declare global {
  interface Window {
    readAloud: {
      onState: (listener: (state: PlayerState) => void) => void
      action: (name: "pause" | "stop" | "hide" | "retry") => void
      setSpeed: (index: number) => void
      voiceStatus: () => Promise<Voices>
      selectVoice: (name: string) => Promise<Voices>
      menu: (name: Menu) => void
      barWidth: (width: number) => void
    }
  }
}

// Same steps as SPEEDS in core/main.rs; the daemon accepts their index.
const SPEEDS = ["1.0", "1.25", "1.3", "1.4", "1.5", "1.75", "2.0"]
const card = "rounded-xl border border-border/40 bg-background text-foreground"
// One height and corner for every control in the bar and its menus; change it here and they all follow.
const control = "h-7 rounded-lg"
const icon = `${control} w-7 [&_svg:not([class*='size-'])]:size-4`

function SpeedMenu({ state, open, toggle }: { state: PlayerState; open: boolean; toggle: () => void }) {
  return <>
    {open && (
      <ul role="menu" aria-label="Speed" className={`${card} fixed inset-x-0 top-0 flex flex-col p-1`}>
        {SPEEDS.map((value, index) => (
          <li key={value} role="none">
            <button role="menuitemradio" aria-checked={index === state.speed}
              className={`flex ${control} w-full items-center gap-2 px-2 text-xs tabular-nums outline-none hover:bg-accent focus-visible:bg-accent aria-checked:font-semibold`}
              onClick={() => { window.readAloud.setSpeed(index); toggle() }}>
              <Check aria-hidden="true" className={`size-3.5 text-primary ${index === state.speed ? "" : "invisible"}`} />
              {value === "1.0" ? "Normal" : `${value}×`}
            </button>
          </li>
        ))}
      </ul>
    )}
    <Button variant="ghost" aria-label="Speed" aria-haspopup="menu" aria-expanded={open}
      className={`${control} gap-0.5 px-2 text-xs tabular-nums has-[>svg]:px-2`} onClick={toggle}>
      <Zap aria-hidden="true" className="size-4" />
      <span>{state.speedValue}×</span>
    </Button>
  </>
}

function voiceLabel(id: string) {
  const [prefix, name] = id.split("_")
  return `${name[0].toUpperCase()}${name.slice(1)} · ${prefix.startsWith("a") ? "US" : "UK"}`
}

function VoiceMenu({ data, open, saving, toggle, onSelect }: {
  data: Voices | null; open: boolean; saving: boolean; toggle: () => void; onSelect: (name: string) => void
}) {
  return <>
    {open && data && (
      <ul role="menu" aria-label="Voices" className={`${card} fixed inset-x-0 top-0 flex h-[280px] flex-col overflow-y-auto p-1`}>
        {data.voices.map((name) => (
          <li key={name} role="none">
            <button role="menuitemradio" aria-checked={name === data.selected} disabled={saving}
              className={`flex ${control} w-full items-center gap-2 px-2 text-xs outline-none hover:bg-accent focus-visible:bg-accent aria-checked:font-semibold`}
              onClick={() => onSelect(name)}>
              <Check aria-hidden="true" className={`size-3.5 text-primary ${name === data.selected ? "" : "invisible"}`} />
              {voiceLabel(name)}
            </button>
          </li>
        ))}
      </ul>
    )}
    <Button variant="ghost" aria-label="Voice" aria-haspopup="menu" aria-expanded={open}
      title={data ? `Voice: ${voiceLabel(data.selected)}. New speech uses this voice.` : "Local voices unavailable"}
      disabled={!data || saving} className={icon} onClick={toggle}>
      <AudioLines aria-hidden="true" />
    </Button>
  </>
}

function Player() {
  const [state, setState] = React.useState<PlayerState>({ active: false, paused: false, speed: 0, speedValue: "1.0", ready: false, error: "", download: { phase: "checking", percent: 0, error: "" } })
  const [voices, setVoices] = React.useState<Voices | null>(null)
  const [menu, setMenu] = React.useState<Menu>(null)
  const [savingVoice, setSavingVoice] = React.useState(false)
  const savingVoiceRef = React.useRef(false)
  const wasActive = React.useRef(false)
  const bar = React.useRef<HTMLElement>(null)
  // The window is exactly as wide as the controls: no empty space at the end of the bar.
  React.useEffect(() => {
    const el = bar.current
    if (!el) return
    const report = () => window.readAloud.barWidth(el.getBoundingClientRect().width)
    const observer = new ResizeObserver(report)
    observer.observe(el)
    report()
    return () => observer.disconnect()
  }, [])
  React.useEffect(() => window.readAloud.onState(setState), [])
  React.useEffect(() => {
    if (state.download.phase === "ready") window.readAloud.voiceStatus().then(setVoices).catch(() => {})
  }, [state.download.phase])
  React.useEffect(() => { window.readAloud.menu(menu) }, [menu])
  React.useEffect(() => {
    if (!menu) return
    const close = () => setMenu(null)
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") close() }
    window.addEventListener("blur", close)
    window.addEventListener("keydown", onKey)
    return () => { window.removeEventListener("blur", close); window.removeEventListener("keydown", onKey) }
  }, [menu])
  React.useEffect(() => { if (!state.active && menu === "speed") setMenu(null) }, [state.active, menu])
  React.useEffect(() => {
    if (wasActive.current && !state.active) setMenu(null)
    wasActive.current = state.active
  }, [state.active])
  React.useEffect(() => {
    if (menu === "voice") document.querySelector('[role="menuitemradio"][aria-checked="true"]')?.scrollIntoView({ block: "nearest" })
  }, [menu])
  const toggle = (name: Exclude<Menu, null>) => setMenu((current) => current === name ? null : name)
  const selectVoice = (name: string) => {
    if (savingVoiceRef.current) return
    savingVoiceRef.current = true
    setSavingVoice(true)
    window.readAloud.selectVoice(name).then((data) => { setVoices(data); setMenu(null) }).catch(() => {}).finally(() => {
      savingVoiceRef.current = false
      setSavingVoice(false)
    })
  }

  return (
    <main ref={bar} className={`player ${card} fixed bottom-0 right-0 flex h-10 w-max items-center gap-0.5 px-1.5`}>
      <span className="flex size-7 shrink-0 items-center justify-center">
        <span className="logo size-[18px] bg-primary" role="img" aria-label="Read Aloud" />
      </span>
      {state.download.phase !== "ready" ? <>
        <span role="status" title={state.download.error} className="whitespace-nowrap px-1 text-xs text-foreground/70">
          {state.download.phase === "failed" ? "Voice download failed" : state.download.phase === "checking" ? "Checking voice…" : `Downloading voice… ${state.download.percent}%`}
        </span>
        {state.download.phase === "failed" && <Button variant="ghost" className="h-7 rounded-lg px-2 text-xs" onClick={() => window.readAloud.action("retry")}>Retry</Button>}
        <Button variant="ghost" aria-label="Close" className={icon} onClick={() => window.readAloud.action("hide")}><X aria-hidden="true" /></Button>
      </> : !state.active ? <>
        <span className="whitespace-nowrap px-1 text-xs text-foreground/70">Super+R to read</span>
        <VoiceMenu data={voices} open={menu === "voice"} saving={savingVoice} toggle={() => toggle("voice")} onSelect={selectVoice} />
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
        <VoiceMenu data={voices} open={menu === "voice"} saving={savingVoice} toggle={() => toggle("voice")} onSelect={selectVoice} />
        <SpeedMenu state={state} open={menu === "speed"} toggle={() => toggle("speed")} />
      </>}
    </main>
  )
}

createRoot(document.getElementById("root")!).render(<Player />)
