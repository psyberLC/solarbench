# Running a model

A language model drives a robot through one adapter, [`solarbench/agents/endpoint.py`](../solarbench/agents/endpoint.py). It speaks the chat-completions protocol that local model servers and hosted services share, so where the model runs is a URL.

**What the code does today:** the adapter speaks profile R2, which one registered task offers: `SolarBench-T3-ClampTighten-UR16e-R2-v0`. The evaluator hands it the work order and the channels it selected. Runs so far are exploratory and lockstep: the simulation waits for the model (board: `eval-latency`).

## Settings
Each setting is given with the policy name, or else read from the environment variable `SOLARBENCH_ENDPOINT_<NAME>` (for example `SOLARBENCH_ENDPOINT_URL`).

| Setting | Default | What |
|---|---|---|
| `endpoint:<model>` | | The model name as the server knows it |
| `url=` | | The server's base address, ending in `/v1`. Never written to a result or a log |
| `wrench=on` | `off` | Select the wrist force-torque channel |
| `reasoning=off` | `on` | Ask the server's chat template to let the model think first, or not (`chat_template_kwargs.enable_thinking`) |
| `temperature=` `max_tokens=` `seed=` | `0`, `4096`, `0` | Sampling settings |
| `rounds=` | `40` | Most calls per episode; after that the robot holds until the episode ends |
| `log=` | none | A JSON-lines file that gets one line per call |
| `SOLARBENCH_ENDPOINT_KEY` | | Sent as a bearer token if set. Never written to a result, a log or the policy's settings |

```bash
export SOLARBENCH_ENDPOINT_URL=http://127.0.0.1:8080/v1
.venv/bin/python scripts/evaluate.py --task SolarBench-T3-ClampTighten-UR16e-R2-v0 \
    --policy endpoint:<model>,wrench=on,log=calls.jsonl --split dev --episodes 16 --num_envs 4 --viz none
```

## What the model is sent
1. A system message: the description of its body ([`solarbench/agents/prompts`](../solarbench/agents/prompts), in the variant with or without force sensing), then how to reply.
2. The work order of the episode.
3. One message per round: the tick, how its last command ended, and each field of each selected channel as text with four decimals. Its own earlier replies stay in the conversation.

The first two never change within an episode, and each request extends the one before, so a server's prompt cache keeps the prefix. The text is the same for every model.

## What the model sends back
Reasoning if it wishes, then a JSON object: a tool pose in the base frame, or `{"done": true}`. The object may span lines or sit in a code fence. It becomes one `TOOL_POSE` or `DONE` record of the [interface](interface.md), and a quaternion is normalised. A reply that does not end with a whole command is asked for once more. If the second reply cannot be read either, nothing is sent and the robot holds. The call is counted as unreadable, and the model is told so in the next round.

## What is kept
- Per call, on the policy and in the `log=` file: wall time, tokens read, cached and written as the server reports them, whether the reply could be read, and whether it was the second ask. The log also keeps the reply, the reasoning text and the command. Writing these into the episode records is `contract-result-fields`.
- Per run: the model name, the sampling settings, reasoning on or off, the encoding, and whether the endpoint was on this machine or elsewhere. Not the address.

Requests for all environments whose queue is empty go out at the same time. The adapter waits a minute for a server it cannot reach. An error the server answers with stops the run: that is not scored as a failure of the model.
