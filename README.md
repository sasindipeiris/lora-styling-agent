# 👗 Personal Styling Assistant

This project implements a minimal LLM agent that picks outfits from a madeup wardrobe by calling external tools. The experiment tests how LoRA finetuning helps a base model learn how to use tools by comparing against its zero shot performance.

### Methodology

1. **Mock Database:** To ensure the model actually learns to use tools rather than answering from its pretrained memory we built a mock database consisting of 14 venues, 7 event types, a weekly weather table for 5 cities and a 61 item wardrobe. All of the data is made up so the model has to call the tools instead of answering from memory.

2. **Data.** Requests come from templates. User prompts are generated dynamically by plugging variables from the mock database into a variety of text templates. We test three types:
   - `no_tool`: general fashion questions or small talk
   - `single_tool`: one lookup
   - `full_outfit`: a chain of 5 to 8 calls (venue → weather → wardrobe searches → color check → answer)

   The final dataset is split into **1,200 training**, **100 validation**, and **100 test** examples. The splits maintain a balanced mix of tasks. For example, the 100 request test set contains 30 `no_tool` requests, 30 `single_tool` requests, and 40 `full_outfit` requests.

   Train and test use different phrasings and test outfit requests use venue/event/day/time combinations never seen in training.

3. **Agent loop.** The loop repeats generate → parse `<tool_call>` → run tool → add the result as a `tool` message. It stops at a plain text answer, an unparseable call or after 10 steps. Tool errors are sent back to the model so it can correct itself.

4. **Finetuning.** LoRA finetuning is applied only to the assistant's turns. We evaluate on a test set with combinations never seen in training.

### Implementation Details

**Tools** (`src/tools.py`):

| Tool                                                                                     | Returns                                                                 |
| ---------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `get_venue_info(venue, event_type)`                                                      | City, setting (indoor/covered/outdoor), formality range and dress rules |
| `get_weather(city, day, time_of_day)`                                                    | Temperature (°C) and chance of rain (%)                                 |
| `search_wardrobe(category, min_formality, max_formality, rules, waterproof, min_warmth)` | Up to 5 matching items                                                  |
| `check_color_harmony(item_ids)`                                                          | Clashing color pairs and whether there are more than 2 accent colors    |

**Settings** (`config.yaml`):

| Setting  | Value                                                                                               |
| -------- | --------------------------------------------------------------------------------------------------- |
| Model    | Qwen2.5-0.5B-Instruct, fp16, greedy decoding, up to 256 new tokens per step, at most 10 agent steps |
| Data     | 1200 train / 100 validation / 100 test                                                              |
| LoRA     | Rank 16 or 4, alpha = 2 × rank, dropout 0.05, applied to all attention and MLP projections          |
| Training | Learning rate 2e-4, cosine schedule, 2 epochs, effective batch size 8, maximum length 3072 tokens   |

### Results

All results are on the 100 request test set (30 `no_tool`, 30 `single_tool`, 40 `full_outfit`).

| Run       | Call validity | Call accuracy | Abstention | Task success | no_tool | single_tool | full_outfit |
| --------- | ------------- | ------------- | ---------- | ------------ | ------- | ----------- | ----------- |
| Zero-shot | 100.0         | 15.7          | 10.0       | 12.0         | 10.0    | 30.0        | 0.0         |
| LoRA r=16 | 98.6          | **47.1**      | **80.0**   | **71.0**     | 80.0    | **66.7**    | **67.5**    |
| LoRA r=4  | 98.6          | 35.7          | 80.0       | 65.0         | 80.0    | 50.0        | 65.0        |

Compared with zero-shot, LoRA r=16 fixes 59 requests and breaks none. LoRA r=4 fixes 57 and breaks 4, all of them by picking the wrong tool.

**How each metric is scored:**

- **call validity**: the output parses as a tool call in the expected format
- **call accuracy**: right tool and right arguments
- **abstention**: correctly answering without a tool when none is needed
- **task success**: the agent’s final answer is correct (end to end)

- **Task success:**
  - `no_tool`: answered without calling a tool.
  - `single_tool`: the answer contains the required key facts and none of the rejected phrases.
  - `full_outfit`: the chosen item IDs pass every check in `check_outfit` (slots, formality, rules, cold, rain, heat, colors).

### Reproduce

**Option A: Colab notebook.** Open [styling_agent.ipynb](styling_agent.ipynb) in Google Colab, choose a T4 GPU (Runtime → Change runtime type), and select Run all. The notebook:

- Clones this repo and installs the requirements
- Saves all outputs to Google Drive (`MyDrive/styling-agent/outputs`)
- Runs data generation, the baseline evaluation, LoRA r=16 training and evaluation followed by the comparison and failure analysis.

This takes about 40 minutes of GPU time. Rank 4 is optional: set `RUN_RANK_4 = True` in section 8. If the session disconnects, run all cells again. Finished steps are skipped and training resumes from its last checkpoint.

**Option B: command line.**

```bash
pip install -r requirements.txt
python -m src.dataset.build_db            # data/mock_db.json
python -m src.dataset.split               # data/{train,val,test}.jsonl
python -m src.evaluate --tag zeroshot     # baseline
python -m src.train --rank 16             # outputs/lora_r16/adapter
python -m src.train --rank 4              # outputs/lora_r4/adapter
python -m src.evaluate --tag lora_r16
python -m src.evaluate --tag lora_r4
python -m src.evaluate --compare          # outputs/comparison.md
python -m src.chat --tag lora_r16         # interactive demo (/reset, /quit)
```

Use `--limit N` with `evaluate` for a quick run. On a 16 GB T4, set `batch_size: 1` and `grad_accum: 8`. Training saves a checkpoint every 50 steps and resumes from the latest one automatically.

### Discussion & Conclusion

The baseline model already writes tool calls in a format that parses but it uses tools badly:

- Calls tools for small talk
- Passes wrong arguments, such as an event type the tool does not accept or a test only phrase like "night" that is not one of the allowed times of day
- Never finishes the outfit chain

This is despite a system prompt that spells out the outfit procedure step by step. LoRA fine tuning on about 1.2k traces lifts task success from 12% to 71% and abstention from 10% to 80%.

The remaining errors come mostly from test wording never seen in training:

- **"night":** the fine tuned models fail on many requests that use it. LoRA r=16 succeeds on only 8 of the 20 tool requests that say "night", against 39 of 50 for the rest.
- **"Any dress rules…":** this question is often answered with a wardrobe search instead of a venue lookup.
- **Retrying instead of reading the error:** after a tool error, the models often retry blindly until they run out of steps, instead of using the valid options listed in the error message.

Rank 16 beats rank 4 mainly on single tool requests. On outfits the two are close.

### Further Development

- Add more variety in phrasing to the training data such as synonyms for the time of day and for the event so the model generalizes better.
- Add training traces that recover from a wrong argument error by using the options listed in the error message.
- Send unparseable calls back to the model as an error instead of stopping the loop.
- Use a larger test set, since 30 single tool requests make the gap between rank 4 and rank 16 a noisy measurement.

### References

- Qwen Team. _Qwen2.5 Technical Report_, 2024. [https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct)
- Hu et al. _LoRA: Low-Rank Adaptation of Large Language Models_, ICLR 2022. [https://arxiv.org/abs/2106.09685](https://arxiv.org/abs/2106.09685)
