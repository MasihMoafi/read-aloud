use std::collections::HashMap;
use std::env;
use std::fs;
use std::io::{self, BufRead, BufReader, Read, Write};
use std::os::unix::fs::PermissionsExt;
use std::os::unix::net::{UnixListener, UnixStream};
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::mpsc::{self, Receiver, Sender};
use std::thread;
use std::time::{Duration, Instant};

const SPEEDS: [&str; 7] = ["1.0", "1.25", "1.3", "1.4", "1.5", "1.75", "2.0"];
const MAX_SELECTION: usize = 2 * 1024 * 1024;

extern "C" {
    fn prctl(option: i32, ...) -> i32;
    fn getppid() -> i32;
}

fn child_dies_with_parent(command: &mut Command) {
    unsafe {
        command.pre_exec(|| {
            let parent = getppid();
            if prctl(1, 9, 0, 0, 0) != 0 {
                return Err(io::Error::last_os_error());
            }
            if parent == 1 || getppid() != parent {
                return Err(io::Error::other("Parent process exited"));
            }
            Ok(())
        });
    }
}

fn runtime_dir() -> PathBuf {
    env::var_os("READ_ALOUD_RUNTIME")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from(env::var_os("XDG_RUNTIME_DIR").expect("XDG_RUNTIME_DIR is required"))
                .join("read-aloud")
        })
}

fn config_dir() -> PathBuf {
    env::var_os("XDG_CONFIG_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env::var_os("HOME").unwrap()).join(".config"))
        .join("read-aloud")
}

fn config_file() -> PathBuf {
    config_dir().join("speed")
}

fn preferred_output() -> Option<String> {
    let output = fs::read_to_string(config_dir().join("output")).ok()?;
    let output = output.trim();
    if output.is_empty() {
        return None;
    }
    let ports = Command::new("pw-link").arg("-i").output().ok()?;
    let prefix = format!("{output}:playback_");
    if ports.status.success()
        && String::from_utf8_lossy(&ports.stdout)
            .lines()
            .any(|port| port.starts_with(&prefix))
    {
        Some(output.to_owned())
    } else {
        None
    }
}

fn socket_path() -> PathBuf {
    runtime_dir().join("daemon.sock")
}

/// The words a reader would say: Markdown and HTML markup is dropped so it is never spoken
/// ("**bold**" reads "bold"; "[text](url)" reads "text"; headings, list markers, quotes, code fences,
/// task boxes, table rules and highlight markers disappear). An asterisk between spaces ("2 * 3") stays.
fn speakable(text: &str) -> String {
    let mut lines = Vec::new();
    for raw in text.lines() {
        let mut line = raw.trim();
        if line.starts_with("```") || line.starts_with("~~~") {
            continue;
        }
        // Table separator rows such as |---|:--:|
        if line.contains('-') && line.chars().all(|c| matches!(c, '|' | '-' | ':' | ' ')) {
            continue;
        }
        loop {
            let before = line;
            line = line.trim_start_matches('>').trim_start();
            line = line.trim_start_matches('#').trim_start();
            for marker in ["- ", "* ", "+ "] {
                if let Some(rest) = line.strip_prefix(marker) {
                    line = rest.trim_start();
                }
            }
            for task in ["[ ] ", "[x] ", "[X] "] {
                if let Some(rest) = line.strip_prefix(task) {
                    line = rest;
                }
            }
            if line == before {
                break;
            }
        }
        lines.push(inline_speakable(line));
    }
    lines.join("\n")
}

fn inline_speakable(line: &str) -> String {
    let chars: Vec<char> = line.chars().collect();
    let mut out = String::new();
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        // HTML tags such as <mark style="..."> and </mark>
        if c == '<' {
            if let Some(end) = chars[i..].iter().position(|&x| x == '>') {
                let first = chars.get(i + 1).copied().unwrap_or(' ');
                if first == '/' || first.is_ascii_alphabetic() {
                    i += end + 1;
                    continue;
                }
            }
        }
        // Wiki links [[Note]] or [[Note|shown]] read the shown name
        if c == '[' && chars.get(i + 1) == Some(&'[') {
            if let Some(end) = (i + 2..chars.len().saturating_sub(1))
                .find(|&j| chars[j] == ']' && chars[j + 1] == ']')
            {
                let inner: String = chars[i + 2..end].iter().collect();
                out.push_str(inner.rsplit('|').next().unwrap_or(&inner));
                i = end + 2;
                continue;
            }
        }
        // Links [text](url) and images ![alt](url) read their text
        if c == '[' || (c == '!' && chars.get(i + 1) == Some(&'[')) {
            let open = if c == '!' { i + 1 } else { i };
            if let Some(close) = (open + 1..chars.len()).find(|&j| chars[j] == ']') {
                if chars.get(close + 1) == Some(&'(') {
                    if let Some(end) = (close + 2..chars.len()).find(|&j| chars[j] == ')') {
                        out.extend(&chars[open + 1..close]);
                        i = end + 1;
                        continue;
                    }
                }
            }
        }
        // Emphasis, strike, highlight and code markers; a lone '*' between spaces and snake_case stay
        if matches!(c, '*' | '_' | '~' | '=' | '`') {
            let mut j = i;
            while j < chars.len() && chars[j] == c {
                j += 1;
            }
            let space_before = i == 0 || chars[i - 1].is_whitespace();
            let space_after = j == chars.len() || chars[j].is_whitespace();
            let marker = match c {
                '*' => !(space_before && space_after),
                '_' => space_before != space_after,
                '~' | '=' => j - i >= 2,
                _ => true,
            };
            if marker {
                i = j;
                continue;
            }
        }
        // Rustidian's color markers (==🟢text==) are not words
        if matches!(c, '🟢' | '🔵' | '🟣' | '🟠' | '🟡' | '🔴') {
            i += 1;
            continue;
        }
        out.push(if c == '|' { ' ' } else { c });
        i += 1;
    }
    out.split_whitespace().collect::<Vec<_>>().join(" ")
}

#[cfg(test)]
mod speakable_tests {
    use super::speakable;

    #[test]
    fn markup_is_not_spoken() {
        assert_eq!(
            speakable("This is **really** important."),
            "This is really important."
        );
        assert_eq!(
            speakable("## Heading\n- [ ] a *task* with `code`"),
            "Heading\na task with code"
        );
        assert_eq!(
            speakable("See [the docs](https://x.y) and ![logo](a.png)."),
            "See the docs and logo."
        );
        assert_eq!(
            speakable("> quoted ~~old~~ ==marked== [[Note|shown]]"),
            "quoted old marked shown"
        );
        assert_eq!(speakable("| a | b |\n|---|---|\n| 1 | 2 |"), "a b\n1 2");
        assert_eq!(speakable("```rust\nlet x = 1;\n```"), "let x = 1;");
        assert_eq!(
            speakable("- ==🟢Ship it== <mark style=\"background: #ec4899;\">today</mark>"),
            "Ship it today"
        );
    }

    #[test]
    fn ordinary_text_is_kept() {
        assert_eq!(
            speakable("Two * three is six; my_var stays; 1. First point."),
            "Two * three is six; my_var stays; 1. First point."
        );
    }
}

fn split_sentences(text: &str) -> Vec<String> {
    let mut result = Vec::new();
    let mut sentence = String::new();
    for word in text.split_whitespace() {
        if !sentence.is_empty() && sentence.len() + word.len() + 1 > 220 {
            result.push(std::mem::take(&mut sentence));
        }
        if !sentence.is_empty() {
            sentence.push(' ');
        }
        sentence.push_str(word);
        let word_lower = word
            .trim_matches(|c: char| c == '"' || c == '\'' || c == ')' || c == ']')
            .to_ascii_lowercase();
        let abbreviation = [
            "mr.", "mrs.", "ms.", "dr.", "prof.", "st.", "vs.", "etc.", "e.g.", "i.e.",
        ]
        .contains(&word_lower.as_str());
        if !abbreviation && word_lower.ends_with(['.', '!', '?']) {
            result.push(std::mem::take(&mut sentence));
        }
    }
    if !sentence.is_empty() {
        result.push(sentence);
    }
    result
}

enum Event {
    Read(String),
    Pause,
    Stop,
    Speed(i32),
    SetSpeed(usize),
    Subscribe(UnixStream),
    WorkerReady,
    Rendered(u64, usize, u64),
    RenderError(u64, usize, String),
    WorkerExited,
    Shutdown,
}

fn listen(listener: UnixListener, tx: Sender<Event>) {
    thread::spawn(move || {
        for stream in listener.incoming().flatten() {
            let tx = tx.clone();
            thread::spawn(move || {
                if let Err(error) = handle_client(stream, tx) {
                    eprintln!("client: {error}");
                }
            });
        }
    });
}

fn handle_client(mut stream: UnixStream, tx: Sender<Event>) -> io::Result<()> {
    stream.set_read_timeout(Some(Duration::from_secs(5)))?;
    let mut reader = BufReader::new(stream.try_clone()?);
    let mut line = String::new();
    reader.read_line(&mut line)?;
    let command = line.trim_end();
    if command == "SUBSCRIBE" {
        stream.set_read_timeout(None)?;
        stream.set_write_timeout(Some(Duration::from_millis(200)))?;
        tx.send(Event::Subscribe(stream))
            .map_err(io::Error::other)?;
        return Ok(());
    }
    let event = match command {
        "READ" => {
            let mut text = String::new();
            reader
                .take((MAX_SELECTION + 1) as u64)
                .read_to_string(&mut text)?;
            if text.len() > MAX_SELECTION {
                stream.write_all(b"ERROR Selection is too large\n")?;
                return Ok(());
            }
            Event::Read(text)
        }
        "PAUSE" => Event::Pause,
        "STOP" => Event::Stop,
        "FASTER" => Event::Speed(1),
        "SLOWER" => Event::Speed(-1),
        "SHUTDOWN" => Event::Shutdown,
        _ if command.starts_with("SPEED ") => match command[6..].parse::<usize>() {
            Ok(index) if index < SPEEDS.len() => Event::SetSpeed(index),
            _ => {
                stream.write_all(b"ERROR Invalid speed\n")?;
                return Ok(());
            }
        },
        _ => {
            stream.write_all(b"ERROR Unknown command\n")?;
            return Ok(());
        }
    };
    tx.send(event).map_err(io::Error::other)?;
    stream.write_all(b"OK\n")
}

struct Job {
    generation: u64,
    index: usize,
    file: PathBuf,
}

struct Engine {
    worker: Child,
    input: ChildStdin,
    ready: bool,
    generation: u64,
    sentences: Vec<String>,
    current: usize,
    speed: usize,
    paused: bool,
    active: bool,
    inflight: Option<Job>,
    rendered: HashMap<usize, PathBuf>,
    audio: Option<Child>,
    subscribers: Vec<UnixStream>,
    error: String,
    requested: Option<Instant>,
}

impl Engine {
    fn state(&self) -> String {
        format!(
            "STATE\t{}\t{}\t{}\t{}\t{}\t{}\n",
            u8::from(self.active),
            u8::from(self.paused),
            self.speed,
            u8::from(self.ready),
            self.error.replace(['\n', '\t'], " "),
            SPEEDS[self.speed]
        )
    }

    fn broadcast(&mut self) {
        let state = self.state();
        self.subscribers
            .retain_mut(|client| client.write_all(state.as_bytes()).is_ok());
    }

    fn stop_audio(&mut self) {
        if let Some(mut audio) = self.audio.take() {
            let _ = audio.kill();
            let _ = audio.wait();
        }
    }

    fn clear_rendered(&mut self) {
        for (_, file) in self.rendered.drain() {
            let _ = fs::remove_file(file);
        }
    }

    fn invalidate(&mut self) {
        self.generation = self.generation.wrapping_add(1);
        self.stop_audio();
        self.clear_rendered();
    }

    fn fail(&mut self, error: String) {
        eprintln!("read-aloud: {error}");
        self.invalidate();
        self.active = false;
        self.paused = false;
        self.error = error;
        self.broadcast();
    }

    fn set_speed(&mut self, speed: usize) {
        if !self.active || speed == self.speed {
            return;
        }
        self.speed = speed;
        if let Some(parent) = config_file().parent() {
            if let Err(error) =
                fs::create_dir_all(parent).and_then(|_| fs::write(config_file(), SPEEDS[speed]))
            {
                eprintln!("Could not save speed: {error}");
            }
        }
        self.invalidate();
        self.requested = Some(Instant::now());
        self.broadcast();
    }

    fn on_event(&mut self, event: Event) -> bool {
        match event {
            Event::Read(text) => {
                let sentences = split_sentences(&speakable(&text));
                if sentences.is_empty() {
                    return true;
                }
                self.invalidate();
                self.sentences = sentences;
                self.current = 0;
                self.active = true;
                self.paused = false;
                self.error.clear();
                self.requested = Some(Instant::now());
                self.broadcast();
            }
            Event::Pause if self.active => {
                self.paused = !self.paused;
                if let Some(audio) = &self.audio {
                    let signal = if self.paused { "-STOP" } else { "-CONT" };
                    if let Err(error) = Command::new("kill")
                        .args([signal, &audio.id().to_string()])
                        .status()
                    {
                        self.fail(format!("Could not change playback: {error}"));
                        return true;
                    }
                }
                self.broadcast();
            }
            Event::Pause => {}
            Event::Stop => {
                self.invalidate();
                self.active = false;
                self.paused = false;
                self.error.clear();
                self.broadcast();
            }
            Event::Speed(step) => self
                .set_speed((self.speed as i32 + step).clamp(0, SPEEDS.len() as i32 - 1) as usize),
            Event::SetSpeed(speed) => self.set_speed(speed),
            Event::Subscribe(mut client) => {
                if client.write_all(self.state().as_bytes()).is_ok() {
                    self.subscribers.push(client);
                }
            }
            Event::WorkerReady => {
                self.ready = true;
                eprintln!("Kokoro voice ready");
                self.broadcast();
            }
            Event::Rendered(generation, index, elapsed) => {
                if let Some(job) = self.inflight.take() {
                    if job.generation == generation && job.index == index {
                        if self.active && generation == self.generation {
                            eprintln!("Rendered sentence in {elapsed} ms");
                            self.rendered.insert(index, job.file);
                        } else {
                            let _ = fs::remove_file(job.file);
                        }
                    }
                }
            }
            Event::RenderError(generation, index, error) => {
                if let Some(job) = self.inflight.take() {
                    let _ = fs::remove_file(job.file);
                }
                if generation == self.generation && index >= self.current {
                    self.fail(error);
                }
            }
            Event::WorkerExited => {
                self.ready = false;
                self.fail("The speech worker stopped".into());
                return false;
            }
            Event::Shutdown => return false,
        }
        true
    }

    fn advance(&mut self) {
        if let Some(audio) = &mut self.audio {
            match audio.try_wait() {
                Ok(Some(status)) => {
                    self.audio = None;
                    if !status.success() {
                        self.fail("Audio playback failed".into());
                        return;
                    }
                    if let Some(file) = self.rendered.remove(&self.current) {
                        let _ = fs::remove_file(file);
                    }
                    self.current += 1;
                    if self.current >= self.sentences.len() {
                        self.active = false;
                        self.paused = false;
                        self.broadcast();
                    }
                }
                Ok(None) => {}
                Err(error) => {
                    self.fail(format!("Audio playback failed: {error}"));
                    return;
                }
            }
        }
        if !self.active || !self.ready {
            return;
        }
        if self.audio.is_none() && !self.paused {
            if let Some(file) = self.rendered.get(&self.current) {
                let mut command = Command::new("pw-play");
                if let Some(output) = preferred_output() {
                    command.args(["--target", &output]);
                }
                command.arg(file).stdout(Stdio::null());
                child_dies_with_parent(&mut command);
                match command.spawn() {
                    Ok(audio) => {
                        if let Some(started) = self.requested.take() {
                            eprintln!(
                                "Playback started after {} ms",
                                started.elapsed().as_millis()
                            );
                        }
                        self.audio = Some(audio);
                    }
                    Err(error) => {
                        self.fail(format!("Could not start audio: {error}"));
                        return;
                    }
                }
            }
        }
        if self.inflight.is_none() {
            let target = if !self.rendered.contains_key(&self.current) {
                Some(self.current)
            } else if self.audio.is_some()
                && self.current + 1 < self.sentences.len()
                && !self.rendered.contains_key(&(self.current + 1))
            {
                Some(self.current + 1)
            } else {
                None
            };
            if let Some(index) = target {
                let file = runtime_dir().join(format!("audio-{}-{index}.wav", self.generation));
                let line = format!(
                    "{}\t{}\t{}\t{}\t{}\n",
                    self.generation,
                    index,
                    SPEEDS[self.speed],
                    file.display(),
                    self.sentences[index]
                );
                if let Err(error) = self
                    .input
                    .write_all(line.as_bytes())
                    .and_then(|_| self.input.flush())
                {
                    self.fail(format!("Speech worker unavailable: {error}"));
                    return;
                }
                self.inflight = Some(Job {
                    generation: self.generation,
                    index,
                    file,
                });
            }
        }
    }
}

impl Drop for Engine {
    fn drop(&mut self) {
        self.stop_audio();
        self.clear_rendered();
        let _ = self.worker.kill();
        let _ = self.worker.wait();
        if let Some(job) = self.inflight.take() {
            let _ = fs::remove_file(job.file);
        }
        let _ = fs::remove_file(socket_path());
    }
}

fn worker(tx: Sender<Event>, root: &Path) -> io::Result<(Child, ChildStdin)> {
    let python = env::var_os("READ_ALOUD_PYTHON")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            let bundled = root.join("runtime/bin/python");
            let local = PathBuf::from(env::var_os("HOME").unwrap_or_default())
                .join(".local/share/rustidian/kokoro-venv/bin/python");
            if bundled.is_file() {
                bundled
            } else if local.is_file() {
                local
            } else {
                PathBuf::from("python3")
            }
        });
    let mut command = Command::new(python);
    command
        .arg("-u")
        .arg(root.join("worker/kokoro.py"))
        .env("ONNX_PROVIDER", "CPUExecutionProvider")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped());
    child_dies_with_parent(&mut command);
    let mut child = command.spawn()?;
    let input = child.stdin.take().unwrap();
    let output = child.stdout.take().unwrap();
    thread::spawn(move || {
        for line in BufReader::new(output).lines().map_while(Result::ok) {
            let parts: Vec<&str> = line.splitn(4, '\t').collect();
            let event = match parts.as_slice() {
                ["READY", "CPUExecutionProvider"] => Some(Event::WorkerReady),
                ["DONE", generation, index, elapsed] => generation
                    .parse()
                    .ok()
                    .zip(index.parse().ok())
                    .zip(elapsed.parse().ok())
                    .map(|((g, i), e)| Event::Rendered(g, i, e)),
                ["ERROR", generation, index, error] => generation
                    .parse()
                    .ok()
                    .zip(index.parse().ok())
                    .map(|(g, i)| Event::RenderError(g, i, (*error).into())),
                _ => None,
            };
            if let Some(event) = event {
                if tx.send(event).is_err() {
                    return;
                }
            }
        }
        let _ = tx.send(Event::WorkerExited);
    });
    Ok((child, input))
}

fn run_daemon(root: &Path) -> io::Result<()> {
    let parent = unsafe { getppid() };
    if unsafe { prctl(1, 15, 0, 0, 0) } != 0 {
        return Err(io::Error::last_os_error());
    }
    if parent == 1 || unsafe { getppid() } != parent {
        return Err(io::Error::other("Parent process exited"));
    }
    let dir = runtime_dir();
    fs::create_dir_all(&dir)?;
    fs::set_permissions(&dir, fs::Permissions::from_mode(0o700))?;
    let socket = socket_path();
    if socket.exists() {
        if UnixStream::connect(&socket).is_ok() {
            return Err(io::Error::new(
                io::ErrorKind::AddrInUse,
                "daemon is already running",
            ));
        }
        fs::remove_file(&socket)?;
    }
    for entry in fs::read_dir(&dir)?.flatten() {
        let name = entry.file_name();
        let name = name.to_string_lossy();
        if name.starts_with("audio-") && name.ends_with(".wav") && entry.file_type()?.is_file() {
            fs::remove_file(entry.path())?;
        }
    }
    let listener = UnixListener::bind(&socket)?;
    fs::set_permissions(&socket, fs::Permissions::from_mode(0o600))?;
    let (tx, rx): (Sender<Event>, Receiver<Event>) = mpsc::channel();
    let (worker, input) = match worker(tx.clone(), root) {
        Ok(value) => value,
        Err(error) => {
            let _ = fs::remove_file(socket);
            return Err(error);
        }
    };
    listen(listener, tx);
    let saved = fs::read_to_string(config_file()).unwrap_or_default();
    let speed = SPEEDS.iter().position(|s| *s == saved.trim()).unwrap_or(0);
    let mut engine = Engine {
        worker,
        input,
        ready: false,
        generation: 0,
        sentences: vec![],
        current: 0,
        speed,
        paused: false,
        active: false,
        inflight: None,
        rendered: HashMap::new(),
        audio: None,
        subscribers: vec![],
        error: String::new(),
        requested: None,
    };
    loop {
        match rx.recv_timeout(Duration::from_millis(20)) {
            Ok(event) => {
                let worker_exited = matches!(&event, Event::WorkerExited);
                if !engine.on_event(event) {
                    if worker_exited {
                        return Err(io::Error::other("The speech worker stopped"));
                    }
                    break;
                }
            }
            Err(mpsc::RecvTimeoutError::Timeout) => {}
            Err(mpsc::RecvTimeoutError::Disconnected) => break,
        }
        engine.advance();
    }
    Ok(())
}

fn send(command: &str, data: Option<&str>, wait_for_start: bool, root: &Path) -> io::Result<()> {
    let mut stream = match UnixStream::connect(socket_path()) {
        Ok(stream) => stream,
        Err(error) if wait_for_start => {
            Command::new(
                env::var_os("READ_ALOUD_START")
                    .map(PathBuf::from)
                    .unwrap_or_else(|| root.join("scripts/start.sh")),
            )
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()?;
            let start = Instant::now();
            loop {
                if let Ok(stream) = UnixStream::connect(socket_path()) {
                    break stream;
                }
                if start.elapsed() > Duration::from_secs(600) {
                    return Err(error);
                }
                thread::sleep(Duration::from_millis(100));
            }
        }
        Err(error) => return Err(error),
    };
    stream.write_all(command.as_bytes())?;
    stream.write_all(b"\n")?;
    if let Some(data) = data {
        stream.write_all(data.as_bytes())?;
    }
    stream.shutdown(std::net::Shutdown::Write)?;
    let mut response = String::new();
    stream.read_to_string(&mut response)?;
    if response.starts_with("OK") {
        Ok(())
    } else {
        Err(io::Error::other(response))
    }
}

fn main() -> io::Result<()> {
    let root = PathBuf::from(
        env::var_os("READ_ALOUD_ROOT")
            .unwrap_or_else(|| env::current_dir().unwrap().into_os_string()),
    );
    let command = env::args().nth(1).unwrap_or_default();
    match command.as_str() {
        "daemon" => run_daemon(&root),
        "read" => {
            let output = Command::new("xclip")
                .args(["-o", "-selection", "primary"])
                .output()?;
            if !output.status.success() {
                return Err(io::Error::other("Could not read the selected text"));
            }
            if output.stdout.len() > MAX_SELECTION {
                return Err(io::Error::other("Selection is too large"));
            }
            let text = String::from_utf8_lossy(&output.stdout);
            if text.trim().is_empty() {
                return Ok(());
            }
            send("READ", Some(&text), true, &root)
        }
        "faster" => send("FASTER", None, false, &root),
        "slower" => send("SLOWER", None, false, &root),
        "stop" => send("STOP", None, false, &root),
        "shutdown" => send("SHUTDOWN", None, false, &root),
        _ => Err(io::Error::other(
            "Use daemon, read, faster, slower, stop, or shutdown",
        )),
    }
}
