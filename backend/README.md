`uv run python app.py`

Or with the Flask CLI:

`uv run flask --app app run --debug`
# Backend

ROS-like node architecture using [Zenoh](https://zenoh.io/) for pub/sub messaging. Each node runs in its own thread and communicates via topics.

## Nodes

| Node | File | Subscribes | Publishes |
|------|------|------------|-----------|
| **SerialNode** | `nodes/serial_node.py` | `serial/audio_out` | `serial/audio_in`, `serial/button` |
| **StateMachineNode** | `nodes/state_machine_node.py` | `serial/button`, `stt/transcription` | `state/changed`, `state/listening`, `state/transcription_text` |
| **STTNode** | `nodes/stt_node.py` | `serial/audio_in`, `state/listening` | `stt/transcription` |

## State machine

```
IDLE --[button]--> LISTENING --[button]--> PROCESSING --[speech_done]--> IDLE
```

## Setup

```bash
uv sync
```

### Firmware (embedded)

The `embedded/` directory has a `Justfile` for building and uploading Arduino firmware:

```bash
cd ../embedded
just install        # install arduino-cli + SAMD core
just compile        # compile only
just upload         # compile + upload to /dev/ttyACM0
just monitor        # open serial monitor (115200 baud)
```

## Run

```bash
uv run python main.py
```

Requires a serial device at `/dev/ttyACM0`. Pass a different port via `SerialNode(bus, port="/dev/ttyUSB0")` in `main.py`.

## Test without hardware

```bash
uv run python test_state_machine.py
```

Interactive REPL that mocks serial events by publishing directly to the Zenoh bus. Flags:

| Flag | Description |
|------|-------------|
| `--serial` | Connect to real serial device |
| `--stt` | Load STT node with whisper model |
| `--tts` | Load TTS node with piper model |

Commands:

| Command | Description |
|---------|-------------|
| `b` / `base` | Send base button press |
| `o` / `open_lid` | Send open_lid button press |
| `a` / `audio [n]` | Send `n` audio chunks (default 10) |
| `t` / `transcribe TEXT` | Inject a transcription result |
| `d` / `done` | Send SPEECH_DONE event |
| `s` / `state` | Print current state |
| `q` / `quit` | Exit |
