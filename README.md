# PS4-LLM · BlackServ Coder

This repository is the **BlackServ Coder** project: a local PS4 coding AI based
on the open-source [Garlic LLM](https://github.com/leonardo-alegria/garlic-llm)
engine, with a Qwopus3.5-9B-Coder-Flash fine-tune and a restricted tool agent.
The coding model's full PS4 deployment remains under test; completed unit tests
must not be mistaken for a successful live model release.

**Project files:** [agent and tools](BLACKSERV_CODER.md) · [execution plan](PLAN.md) ·
[local model conversion](LOCAL_CONVERSION_FEASIBILITY.md) ·
[PS4 deployment and rollback](PS4_DEPLOY.md).

The original Garlic LLM documentation follows below. The upstream GPL-3.0
license, copyright and attribution are preserved.

---

<p align="center"><img src="docs/logo.svg" width="112" alt="Garlic LLM logo: a garlic bulb on a blue square"></p>

# Garlic LLM

**A 9-billion-parameter language model running on a PS4. Offline.**

Garlic LLM is a homebrew app for the PlayStation 4. It runs [Qwen3.5-9B](https://huggingface.co/Qwen) on the console's own GPU, with no PC and no internet while it runs. It also listens, talks, and runs the Python it writes.

[Website](https://garlicllm.dev) · [Download](#install) · [Demo video](https://garlicllm.dev/#demo) · [Support the project](#support)

> **Test version 1.21.** The interface in 11 languages, spoken replies in Arabic and Japanese, dictation in six more languages, the PS4 Pro's native mode, other Qwen3.5-9B models, and tools in the API. It has not been tested on a console yet: [download it](https://garlicllm.dev/download/#h-exp) and tell us how it went in an [issue](https://github.com/leonardo-alegria/garlic-llm/issues). The release is still 1.19. This page describes 1.21, and what is new in 1.21 says so.

![Garlic LLM answering a question on a PS4](docs/chat.png)

## What it does

| Feature | Details |
|---|---|
| **Text chat** | Qwen3.5-9B at 31–39 tokens/s, and up to 43 tokens/s on code. 16K-token context. |
| **Voice conversation** | Speak and it answers aloud (Chatterbox) in English, Spanish, Portuguese, Russian, Italian, French and German. Version 1.21 adds Arabic and Japanese; it does not speak Chinese or Korean yet. |
| **Dictation** | Hold a button and talk instead of typing. It understands 25 European languages (Parakeet TDT 0.6B v3). Version 1.21 adds Arabic, Japanese, Korean, Chinese, Turkish and Vietnamese (Nemotron 3.5 ASR), when the console is set to one of them; with the console in Traditional Chinese, it writes simplified characters. |
| **Interface** | It follows the console's language: English, Spanish, Portuguese or Russian. Version 1.21 adds French, German, Arabic, Japanese, Simplified Chinese, Traditional Chinese and Korean. |
| **Python mode** | Ask for a program. It writes MicroPython and the console runs it. |
| **Think mode** | The model reasons before it answers. Off by default; a thought takes about half a minute. |

Everything runs on the console. Nothing is sent anywhere.

Speeds were measured on a base/Slim PS4. On a PS4 Pro, chat runs at up to 45 tokens/s. Version 1.21 runs in the Pro's native mode, which uses its full GPU, and reaches up to 60 tokens/s. In voice mode the chat model runs at about 22 tokens/s, because the voice model takes the memory that speculative decoding uses.

## Requirements

- A PS4, PS4 Slim or PS4 Pro running [GoldHEN](https://github.com/GoldHEN/GoldHEN). It works on firmware 9.00, 9.04, 11.00, 11.52, 12.02, 12.50, 13.50, 13.52 and 14.00.
- About 6 GB of free space, or 12 GB if you copy the package to the console's own disk before installing it. Version 1.21 needs about 6.5 GB, or 13 GB.
- To use your voice: any ordinary microphone the console recognises.
- To type on a real keyboard: any USB keyboard. Press OPTIONS in the chat to open the console's keyboard.

Other firmware versions are not tested yet. If you try one, please [open an issue](https://github.com/leonardo-alegria/garlic-llm/issues) with the result.

## Install

1. Download the all-in-one package, with the models inside: version 1.19 (about 5.7 GB) from [garlicllm.dev](https://garlicllm.dev/download/) or [Hugging Face](https://huggingface.co/garlic-llm/garlic-llm-ps4), or the test version 1.21 (about 6.0 GB) from [garlicllm.dev](https://garlicllm.dev/download/#h-exp).
2. Copy the PKG to the console and install it like any other homebrew package (*Settings → Debug Settings → Game → Package Installer*).
3. Open **Garlic LLM** from the home screen. The first screen loads the model; after that it needs no PC and no connection.

**Updating.** Download the new package and install it over the old one. The models are inside, so there is nothing else to copy. To go back from 1.21 to 1.19, install 1.19 again.

## Controls

**Chat**

| Button | Action |
|---|---|
| ✕ | Type a message |
| OPTIONS | Type with the console's keyboard, which also takes a USB keyboard |
| □ (hold) | Dictate a message; release to finish |
| ○ | Stop the answer |
| △ | New chat |
| ↑ ↓ or left stick | Scroll |
| L1 | Voice mode |
| R1 | Run the Python program in the last answer |
| R3 or touchpad | Think mode on / off |
| L3 | [API](#api) on / off |
| L2 / R2 | Temperature down / up |

After dictating, choose what to do with the text: ✕ send, △ edit, □ record again, ○ discard.

**Keyboard**

| Button | Action |
|---|---|
| ✕ | Type the selected key |
| □ | Delete (hold to repeat) |
| △ | Space |
| L1 | Shift |
| R1 | Emoji |
| L2 (hold) | Dictate and add the text |
| R2 | Send |
| ○ | Close |
| OPTIONS | The console's own keyboard (a USB keyboard; in 1.21 also Chinese, Japanese and Korean input); its text is added |

**Voice mode:** hold □ to talk (this also interrupts the answer), △ starts a new chat, ○ leaves voice mode.

The interface follows the console's language. In 1.21, Arabic and Persian text reads right to left, and the on-screen keyboard has a layout for each interface language except Chinese; for Chinese, press OPTIONS on the keyboard to use the console's own keyboard.

## How it works

A PS4 gives homebrew no compute API and no machine-learning library, so Garlic LLM talks to the GPU directly.

- **Compute kernels.** The model's operations (matrix products over 4-bit weights, attention, normalisation) are OpenCL C kernels compiled by LLVM for the console's GCN architecture. They are in [`shaders/`](shaders/).
- **Hand-written command buffers.** The app dispatches those kernels by writing PM4 packets itself, the low-level commands a graphics driver would normally generate.
- **Speculative decoding.** Qwen3.5's own MTP head drafts up to two tokens ahead, and the full model verifies them in one pass.
- **Custom Q4 and Q3 weights.** The 9B is stored in two formats made for these kernels. Q4 holds 4-bit weights and is used for most matrices and the output head. Q3 holds 3-bit weights (about 3.5 bits each with their scales) and is used for the two largest matrices of each layer, the MLP's gate and up projections. Storing everything in Q4 would take about 384 MiB more, which the console does not have free.
- **4-bit attention cache.** The attention cache is quantized to 4 bits too, which is how a 16K context fits.
- **GPU-visible memory.** The weights live in "Garlic" memory, the PS4's name for the memory the GPU reads directly. That is where the project's name comes from.
- **The rest is plain C.** The tokenizer, the user interface, the text renderer and the audio path run on the CPU. Python programs run on an embedded [MicroPython](https://micropython.org).

The app is built with the open-source [OpenOrbis](https://github.com/OpenOrbis/OpenOrbis-PS4-Toolchain) toolchain. The techniques, the measurements and the dead ends are written up in a 147-page guide, [*Nine Billion Parameters on a PS4*](https://ko-fi.com/s/5d8050b149).

## API

Garlic LLM can serve an OpenAI-compatible API on your network, so that your own programs and apps use the model on the console. It is off until you turn it on.

> The API came with the test version 1.20. This section describes 1.21, which adds tools, reasoning, `context_length`, the usage in streams, `/health`'s busy state and requests of up to 1 MiB.

**Turn it on.** On the chat screen, press **L3** (click the left stick). The top of the screen then shows where the API listens, for example `API · 192.168.1.5:8080`. L3 again turns it off, and the app remembers the choice for the next time.

**Use it.** Point any OpenAI client at that address, with `http://192.168.1.5:8080/v1` as its base URL:

```bash
curl http://192.168.1.5:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello"}],"max_tokens":128}'
```

- `GET /v1/models`, `POST /v1/chat/completions` (`stream: true` for server-sent events), `GET /health`.
- The context window is 16384 tokens. `GET /v1/models` reports it as `context_length`, so clients can size what they send. The messages, the tools' definitions and the reply share it, and `usage.prompt_tokens` counts the tools too. Without `max_tokens` the reply may use the rest of the window, so a long answer or a long tool call is not cut short. A request that does not fit gets `400` with the code `context_length_exceeded` and the numbers.
- `GET /health` also says whether a request sent now would wait, for clients that can send it elsewhere: `{"status":"ok","busy":false,"waiting":0}`. `busy` is `true` while a request is being answered or the console itself uses the model (a chat reply, the keyboard, voice mode, dictation, a Python program); `waiting` counts the requests in line. It needs no API key.
- The OpenAPI 3.1 description is at `GET /openapi.json` (also in [`chat/assets/openapi.json`](chat/assets/openapi.json)). It needs no API key.
- Replies are generated the way the chat generates its own, speculative decoding included.
- One request runs at a time, and the chat screen is busy while it does: it says that a request is being answered, and ○ stops the reply (the client gets what was written so far, with `finish_reason: "length"`). Requests wait while the keyboard, voice mode or a Python program is open. Chat requests sent meanwhile wait their turn, up to 8 in all (more get `503` with the code `busy`); `/v1/models` and `/health` answer at once.
- A client may stop a reply at any time, for example with a stop button or by closing the connection: the console ends that reply and keeps running.
- A request is a conversation of its own, so the one on the console's screen is cleared.
- A conversation is read once. Clients send the whole conversation with every message; the console keeps what it already read of the last one, so a new message only reads what is new. Using the chat, dictation, voice mode or a Python program on the console in between makes the next request read it all again.
- Reasoning follows the console's think mode (R3 or the touch pad). A request can choose for itself: end the last message with `/think` or `/no_think`, or send `"chat_template_kwargs": {"enable_thinking": true}` (or `false`). The reasoning comes back apart from the answer, as `reasoning_content`, so chat apps that show reasoning put it in their thinking box. It takes up to 1024 tokens, the same as on the console, and `max_tokens` counts the answer only.
- Tools (function calling) work as with OpenAI: send `tools`, and the model answers with `tool_calls` and `finish_reason: "tool_calls"`; send the results back as `role: "tool"` messages. `tool_choice` takes `auto`, `none`, `required` or one of the functions in `tools`, and `parallel_tool_calls: false` keeps one call per reply. A streamed reply sends its text as usual and each call whole at the end.
- Agent apps work as they do with other servers: the whole conversation with every request, many tools with their JSON schemas, `developer` messages (read as `system`), assistant turns of calls without content. A request may be up to 1 MiB, with up to 65536 JSON values.
- With `"stream_options": {"include_usage": true}` a stream ends with one more chunk before `data: [DONE]`: no choices, the usage of the whole reply.
- A request the console cannot take says why: the body is not valid JSON, has no body, is not an object or has too many values (`400`, code `invalid_body`); it does not fit the context window (`400`, code `context_length_exceeded`); it is over 1 MiB (`413`). The console's log has each refusal too.
- Web pages can call the API from a browser: every answer allows any origin (CORS).
- Only `n = 1` is supported; `logprobs`, `logit_bias` and similar parameters are ignored.
- For an API key, put it in `/data/garlic_api_key.txt` on the console. Requests then need `Authorization: Bearer <key>`. Without that file, anyone on your network can use the API while it is on, and clients that insist on a key accept any text.
- If the screen shows `API · :8080`, the app could not read the console's address: it is in *Settings → Network → View Connection Status*.
- To try a client without a console, [`tests/api_host/`](tests/api_host/) builds a server for Windows with this same API and a stand-in model that greets, calls tools and reads their results back. The first lines of its `server.c` say how to build and run it.

## Use another model

> New in version 1.21.

Garlic LLM can start another model instead of the built-in Qwen3.5-9B: a fine-tune of Qwen3.5-9B that keeps its shapes and tokenizer, such as a coding model or an abliterated one. Other architectures and bigger models do not run.

**Convert it.** On a PC with this repository, for a model on Hugging Face (`<model>` is the part of its name after the slash):

```bash
python pc/checkpoint.py <owner>/<model>
python -m modal run pc/modal_qwen35_9b.py::convert --src <owner>/<model>
modal volume get garlic-hf-cache out/<model>-mix.bin models/
modal volume get garlic-hf-cache out/<model>-mix.json models/
python pc/convert_9b_q4s.py --mix=models/<model>-mix.bin --out=models/<model>
```

- The first command checks the model against Qwen3.5-9B: its configuration and the name and shape of every tensor. A model that does not match stops there, with a list of what differs.
- The second runs on Modal, like the first conversion of the built-in model (see [Build from source](#build-from-source)).
- The last writes `models/<model>/`, the folder for the console.

**Copy it to the console.** Start GoldHEN's FTP server, set `PS4_IP` to the console's address and run:

```bash
python pc/upload_model.py --model models/<model>
```

It checks the folder and copies it to `/data/garlic/models/<model>/`. A folder copied by hand works the same. It holds `qwen3.5-9b-q4s.bin`, and can also hold `model.idx`, `qwen3.5-9b-mtp.bin` and `mtp.idx`. Its name has at most 32 bytes. Each model takes 4.32 GiB on the console, or 4.52 GiB with its own MTP head.

**Choose it.** When the models folder holds a model, the app shows a list before it loads: the built-in model first, then the folders. ↑ ↓ choose and ✕ starts. The app remembers the choice and opens the list on it the next time. With no model in the folder, the app starts as before.

- It works with the all-in-one package and with a plain build.
- The header and the API show the folder's name as the model's name.
- A folder without its own `qwen3.5-9b-mtp.bin` uses the built-in MTP head. That head was trained on Qwen3.5-9B's own weights: the further a model's weights are from them, the fewer drafted tokens it accepts and the slower chat runs. `convert_9b_q4s.py` converts the model's own MTP head when its checkpoint has one.
- Before it loads a folder, the app checks its files against the built-in model. If they do not match (another conversion, or a file copied halfway), it names the file and starts the built-in model.

## Build from source

You only need this to change the app. The build scripts are written for Windows.

**Tools**

- Python 3 with `numpy` and `Pillow`.
- The [OpenOrbis PS4 Toolchain](https://github.com/OpenOrbis/OpenOrbis-PS4-Toolchain) in `toolchain/OpenOrbis/PS4Toolchain/`.
- [Zig](https://ziglang.org) in `toolchain/zig/`. Its bundled clang compiles both the C code and the GCN kernels.
- The .NET runtime in `toolchain/dotnet/`, for OpenOrbis' package tool.

To keep the tools somewhere else, set the `GARLIC_TOOLCHAIN` environment variable to that folder.

**Build the app**

```bash
python build_chat.py
```

This writes the PKG to `build/chat/`. Add `--upload` to also copy the package to the console over FTP. For `--upload`, set the `PS4_IP` environment variable to your console's address and start GoldHEN's FTP server.

The app's data files (fonts, tokenizer tables, compiled kernels) are already in `chat/assets*`, so a build does not need the scripts in `pc/`.

**Model files**

A plain build keeps the weights outside the package. The app looks for each of these files first inside its package (`/app0/models`) and then in `/data` on the console:

| File | Size | Contents |
|---|---|---|
| `qwen3.5-9b-q4s.bin` | 4.32 GiB | Qwen3.5-9B |
| `qwen3.5-9b-mtp.bin` | 0.20 GiB | The MTP head for speculative decoding |
| `parakeet-v3-q4i.bin` | 0.33 GiB | Speech to text in the European languages |
| `nemotron-3.5-asr-q4i.bin` | 0.33 GiB | Speech to text in Arabic, Japanese, Korean, Chinese, Turkish and Vietnamese |
| `chatterbox-t3.bin` | 0.29 GiB | Text to speech, first stage |
| `chatterbox-s3gen-mf.bin` | 0.09 GiB | Text to speech, second stage |

The code can also build a smaller app with Qwen3.5-4B (`--4b`, weights in `qwen3.5-4b-q4i.bin`). It has no speculative decoding and is not released as a package.

Download them from [Hugging Face](https://huggingface.co/garlic-llm/garlic-llm-ps4). `python pc/upload_model.py <file>` copies a file to `/data` on the console. To build the all-in-one package instead, put the files in `models/` and add `--full` to the build command.

The scripts that made them from the original checkpoints are in `pc/`, and each one's header describes its inputs and the file format it writes. The first conversion of the Qwen models (`pc/modal_qwen35*.py`) runs on [Modal](https://modal.com), on machines with 32 to 64 GB of memory.

**Repository layout**

| Path | Contents |
|---|---|
| `chat/` | The app: engine, user interface, tokenizer, voice, Python runner |
| `chat/py/` | MicroPython and its port to the console |
| `shaders/` | The GPU kernels |
| `pc/` | Converters for the models, reference implementations in NumPy, and the scripts that build the app's data files |
| `build_chat.py` | Builds the PKG |

## Troubleshooting

- **"Couldn't start".** A model file is missing or incomplete. Install the package again. With a build from source, check the files in `/data` against the table above.
- **"This model can't be used"** (1.21). The chosen folder in `/data/garlic/models` does not match the built-in model, and the app started the built-in one. Convert the model again and copy it with `python pc/upload_model.py --model`, which checks the folder first.
- **Dictation hears nothing.** Check that the console sees your microphone, and keep □ held while you speak.
- **Dictation writes the wrong language.** It follows the console's language. To dictate in Arabic, Japanese, Korean, Chinese, Turkish or Vietnamese, set the console to that language (*Settings → Language*) and open the app again.
- **Anything else.** The app writes a log to `/data/ps4ai_log.txt`. Attach it when you [open an issue](https://github.com/leonardo-alegria/garlic-llm/issues).

## Questions

**Does it need internet?** No. The model, the voices and the speech recognition run on the console.

**Does it run on a PS4 Pro?** Yes. Version 1.19 runs at up to 45 tokens/s, as if the Pro were a base PS4. Version 1.21 runs in the Pro's native mode, which uses its full GPU, and reaches up to 60 tokens/s.

**And on a PS5?** No. Garlic LLM is written for the PS4's GPU and system software.

**Can it harm my console?** It is an ordinary homebrew app and contains no exploit. It needs GoldHEN, which you install at your own risk.

**Is this the first AI on a PS4's GPU?** As far as I know, yes. I found no earlier public project that runs a language model on the PS4's GPU. If you know of one, please [open an issue](https://github.com/leonardo-alegria/garlic-llm/issues).

## Support

Garlic LLM is free and open source. If you want to see more of it (more consoles tested, faster kernels), you can help fund the work:

- [PayPal](https://www.paypal.com/donate/?business=leonardoalegria2002%40gmail.com&currency_code=USD)
- [Ko-fi](https://ko-fi.com/leonardoalegria)
- Buy the guide, [*Nine Billion Parameters on a PS4*](https://ko-fi.com/s/5d8050b149) (PDF, pay what you want from 19 USD)

Bug reports and test results from other consoles help just as much.

## Licence and credits

The app's code is licensed under the [GNU General Public License v3.0](LICENSE). The models and third-party components keep their own licences:

| Component | Author | Licence |
|---|---|---|
| Qwen3.5-9B and Qwen3.5-4B | Alibaba Qwen | Apache-2.0 |
| Chatterbox (text to speech) | Resemble AI | MIT |
| Voices for Russian, Arabic and Japanese | Mozilla Common Voice contributors | CC0-1.0 |
| Japanese kanji readings (pykakasi's dictionary, from KAKASI and UniDic) | Hiroshi Miura and contributors, the KAKASI authors | GPL-3.0-or-later |
| Parakeet TDT 0.6B v3 (speech to text) | NVIDIA | CC-BY-4.0 |
| Nemotron 3.5 ASR (speech to text) | NVIDIA | OpenMDW-1.1 |
| MicroPython | The MicroPython project | MIT |
| Twemoji | Twitter, Inc. and other contributors | CC-BY-4.0 |
| Fonts: Selawik, Noto (including Noto Sans Arabic, SC, TC, JP and KR), Arimo, Inconsolata, Cascadia Mono | Their authors | SIL OFL 1.1 |
| DejaVu Sans | Its authors | Bitstream Vera licence and public domain |

The complete notices are in [`CREDITS.md`](CREDITS.md) and ship inside the app.

Garlic LLM is built with the [OpenOrbis PS4 Toolchain](https://github.com/OpenOrbis/OpenOrbis-PS4-Toolchain) and runs on consoles with [GoldHEN](https://github.com/GoldHEN/GoldHEN). Both are third-party projects by their own authors, and Garlic LLM would not exist without them.

## Contact

Garlic LLM is built by [Leonardo Alegría](https://www.linkedin.com/in/leonardoalegria/). Questions, collaborations and press: [leo@garlicllm.dev](mailto:leo@garlicllm.dev). Bugs and test results go to [GitHub issues](https://github.com/leonardo-alegria/garlic-llm/issues).

---

Not affiliated with or endorsed by Sony Interactive Entertainment. PlayStation and PS4 are trademarks of their owners.
