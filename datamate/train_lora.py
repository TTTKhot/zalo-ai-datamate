"""QLoRA finetuning of the intent model on answer-verified data (sft_data.py), Kaggle T4 friendly.

  * base model loaded by llm.load_qwen in 4-bit NF4 (same module tree as inference);
  * LoRA on the language-model linear layers only (vision tower untouched);
  * loss on the assistant JSON only; fp16 autocast + GradScaler (T4 has no bf16);
  * gradient checkpointing, batch 1 + gradient accumulation, length-bucketed order;
  * validation: loss + greedy exact-match of the canonical intent on val shops.

python -m datamate.train_lora --model /kaggle/input/qwen3.5-4b --train sft/train.jsonl \
       --val sft/val.jsonl --out adapters/intent_lora [--epochs 2] [--r 16] [--max-len 3072]
Writes the adapter (+ datamate_loader.json, train_log.json) to --out.

Resume: every --save-every optimizer steps (and on the time budget) the full training state goes to
<out>/checkpoint/ (LoRA weights, optimizer, scheduler, GradScaler, position, RNG) atomically; running the
same command again continues mid-epoch exactly where it stopped. The checkpoint carries a signature
(sha of train/val data + hyper-parameters + base model); a mismatch starts from scratch instead of mixing.
train_log.json has complete=false when training stopped early.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import shutil
import time
from pathlib import Path

from .intent import canonical_intent, parse_intent
from .llm import chat_ids, load_qwen, tokenizer_of
from .runstate import atomic_write_text, fingerprint

SKIP_MODULES = re.compile(r'visual|vision|image|patch_embed|merger|mm_projector|lm_head|embed_tokens')


def lora_targets(model):
    """Leaf names of linear layers in the language model (works for full and linear-attention blocks)."""
    import torch.nn as nn
    leaves = set()
    for name, mod in model.named_modules():
        cls = type(mod).__name__
        if (isinstance(mod, nn.Linear) or cls in ('Linear4bit', 'Linear8bitLt')) and not SKIP_MODULES.search(name):
            leaves.add(name.rsplit('.', 1)[-1])
    return sorted(leaves)


def encode(processor, example, max_len):
    msgs = example['messages']
    prompt = chat_ids(processor, msgs[:-1], add_generation_prompt=True)
    tok = tokenizer_of(processor)
    target = tok(msgs[-1]['content'], add_special_tokens=False)['input_ids']
    eos = tok.convert_tokens_to_ids('<|im_end|>')
    if eos is None or eos == tok.unk_token_id:
        eos = tok.eos_token_id
    target = target + [eos]
    if len(prompt) + len(target) > max_len:            # keep the end of the prompt (question + names)
        prompt = prompt[-(max_len - len(target)):]
    ids = prompt + target
    labels = [-100] * len(prompt) + target
    return ids, labels


def load_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding='utf-8').splitlines() if l.strip()] if path else []


def evaluate(model, processor, data, max_eval, torch, max_new_tokens=256):
    """Validation loss and exact match of canonical intents (greedy)."""
    model.eval()
    losses, hits, n = [], 0, 0
    for ex in data[:max_eval]:
        ids, labels = ex['_enc']
        with torch.no_grad(), torch.autocast('cuda', dtype=torch.float16, enabled=torch.cuda.is_available()):
            x = torch.tensor([ids], device=model.device)
            y = torch.tensor([labels], device=model.device)
            losses.append(float(model(input_ids=x, labels=y).loss))
            prompt = ids[:labels.index(next(t for t in labels if t != -100))]
            p = torch.tensor([prompt], device=model.device)
            out = model.generate(input_ids=p, attention_mask=torch.ones_like(p), max_new_tokens=max_new_tokens,
                                 do_sample=False)
        text = tokenizer_of(processor).decode(out[0][len(prompt):], skip_special_tokens=True)
        pred = parse_intent(text)
        gold = json.loads(ex['messages'][-1]['content'])
        hits += pred is not None and canonical_intent(pred) == canonical_intent(gold)
        n += 1
    model.train()
    return {'val_loss': round(sum(losses) / max(len(losses), 1), 4), 'exact_match': round(hits / max(n, 1), 4), 'n': n}


def train_signature(args) -> dict:
    keep = ('epochs', 'lr', 'r', 'alpha', 'dropout', 'grad_accum', 'max_len', 'no_4bit', 'seed', 'limit')
    return {'train': fingerprint(args.train), 'val': fingerprint(args.val), 'base': Path(str(args.model)).name,
            **{k: getattr(args, k) for k in keep}}


def save_checkpoint(out: Path, model, opt, sched, scaler, pos: dict, log: dict, sig: dict, torch):
    """<out>/checkpoint.tmp -> <out>/checkpoint (old one kept as checkpoint.old until the swap is done)."""
    from peft import get_peft_model_state_dict
    tmp, cur, old = out / 'checkpoint.tmp', out / 'checkpoint', out / 'checkpoint.old'
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    torch.save({'lora': get_peft_model_state_dict(model), 'opt': opt.state_dict(), 'sched': sched.state_dict(),
                'scaler': scaler.state_dict(), 'pos': pos, 'log': log, 'signature': sig,
                'rng': {'py': random.getstate(), 'torch': torch.get_rng_state(),
                        'cuda': torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None}},
               tmp / 'state.pt')
    (tmp / 'signature.json').write_text(json.dumps(sig, indent=1))
    shutil.rmtree(old, ignore_errors=True)
    if cur.exists():
        cur.rename(old)
    tmp.rename(cur)
    shutil.rmtree(old, ignore_errors=True)


def load_checkpoint(out: Path, sig: dict, torch):
    for d in (out / 'checkpoint', out / 'checkpoint.old'):      # .old survives a crash during the swap
        f = d / 'state.pt'
        if not f.exists():
            continue
        ck = torch.load(f, map_location='cpu', weights_only=False)
        if ck.get('signature') != sig:
            diff = sorted(k for k in set(sig) | set(ck.get('signature', {})) if sig.get(k) != ck['signature'].get(k))
            print(f'checkpoint signature differs {diff} -> training from scratch', flush=True)
            return None
        return ck
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--train', required=True)
    ap.add_argument('--val', default='')
    ap.add_argument('--out', required=True)
    ap.add_argument('--epochs', type=float, default=2.0)
    ap.add_argument('--lr', type=float, default=2e-4)
    ap.add_argument('--r', type=int, default=16)
    ap.add_argument('--alpha', type=int, default=32)
    ap.add_argument('--dropout', type=float, default=0.05)
    ap.add_argument('--grad-accum', type=int, default=8)
    ap.add_argument('--max-len', type=int, default=3072)
    ap.add_argument('--max-eval', type=int, default=120)
    ap.add_argument('--noise-val', default='', help='val_noise.jsonl from sft_data --augment: exact match per family')
    ap.add_argument('--eval-every', type=int, default=0, help='optimizer steps; 0 = end of each epoch')
    ap.add_argument('--no-4bit', action='store_true')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--limit', type=int, default=0, help='random subset of train examples (quick runs)')
    ap.add_argument('--max-hours', type=float, default=8.0, help='stop and save before Kaggle timeout (per session)')
    ap.add_argument('--save-every', type=int, default=50, help='optimizer steps between resumable checkpoints; 0 = off')
    ap.add_argument('--no-resume', action='store_true', help='ignore an existing checkpoint')
    args = ap.parse_args(argv)

    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    started = time.time()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    device_map = {'': 0} if torch.cuda.is_available() else None
    model, processor, loader = load_qwen(args.model, quantize_4bit=not args.no_4bit, device_map=device_map)
    (out / 'datamate_loader.json').write_text(json.dumps({'loader': loader, 'base': str(args.model)}))
    model.config.use_cache = False
    if not args.no_4bit and torch.cuda.is_available():
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
                                                gradient_checkpointing_kwargs={'use_reentrant': False})
    else:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
        model.enable_input_require_grads()
    targets = lora_targets(model)
    print('LoRA targets:', targets, flush=True)
    cfg = LoraConfig(r=args.r, lora_alpha=args.alpha, lora_dropout=args.dropout, bias='none', task_type='CAUSAL_LM',
                     target_modules=[t for t in targets if t not in ('lm_head',)],
                     exclude_modules=r'.*(visual|vision).*')
    model = get_peft_model(model, cfg)
    model.print_trainable_parameters()

    train = load_jsonl(args.train)
    val = load_jsonl(args.val)
    if args.limit and len(train) > args.limit:
        train = random.sample(train, args.limit)
    for ex in train + val:
        ex['_enc'] = encode(processor, ex, args.max_len)
    print(f'train {len(train)} val {len(val)} max tokens {max(len(e["_enc"][0]) for e in train)}', flush=True)

    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.0)
    total_steps = math.ceil(len(train) * args.epochs / args.grad_accum)
    warm = max(1, int(0.05 * total_steps))
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / warm) * max(0.0, 0.5 * (1 + math.cos(math.pi * min(s, total_steps) / total_steps))))
    use_amp = torch.cuda.is_available()
    scaler = torch.amp.GradScaler('cuda', enabled=use_amp)
    log = {'args': vars(args), 'targets': targets, 'loader': loader, 'evals': [], 'loss': [], 'sessions': 0}
    step, micro, running, start_i = 0, 0, 0.0, 0
    sig = train_signature(args)
    ck = None if args.no_resume else load_checkpoint(out, sig, torch)
    if ck is not None:
        from peft import set_peft_model_state_dict
        set_peft_model_state_dict(model, ck['lora'])
        opt.load_state_dict(ck['opt'])
        sched.load_state_dict(ck['sched'])
        scaler.load_state_dict(ck['scaler'])
        step, micro, running, start_i = ck['pos']['step'], ck['pos']['micro'], ck['pos']['running'], ck['pos']['next_i']
        log = ck['log']
        print(f'resumed from checkpoint: step {step}/{total_steps}, example {start_i}', flush=True)
    log['sessions'] = log.get('sessions', 0) + 1
    minutes_before = log.get('minutes', 0.0)
    model.train()
    n_micro = int(len(train) * args.epochs)
    order = []
    while len(order) < n_micro:                    # shuffled buckets of similar length -> fewer pad tokens
        idx = list(range(len(train)))
        random.shuffle(idx)
        chunks = [sorted(idx[i:i + 64], key=lambda j: len(train[j]['_enc'][0])) for i in range(0, len(idx), 64)]
        random.shuffle(chunks)
        order += [j for c in chunks for j in c]
    order = order[:n_micro]
    if ck is not None:                             # order above is rebuilt from the seed; RNG continues as saved
        random.setstate(ck['rng']['py'])
        torch.set_rng_state(ck['rng']['torch'])
        if ck['rng']['cuda'] is not None and torch.cuda.is_available():
            torch.cuda.set_rng_state_all(ck['rng']['cuda'])
        del ck

    def checkpoint(next_i):
        if args.save_every:
            log['minutes'] = round(minutes_before + (time.time() - started) / 60, 1)
            save_checkpoint(out, model, opt, sched, scaler, {'step': step, 'micro': micro, 'running': 0.0,
                                                             'next_i': next_i}, log, sig, torch)

    stop = False
    for i, j in enumerate(order):
        if i < start_i:
            continue
        ids, labels = train[j]['_enc']
        x = torch.tensor([ids], device=model.device)
        y = torch.tensor([labels], device=model.device)
        with torch.autocast('cuda', dtype=torch.float16, enabled=use_amp):
            loss = model(input_ids=x, labels=y).loss / args.grad_accum
        scaler.scale(loss).backward()
        running += loss.item()
        micro += 1
        if micro % args.grad_accum == 0 or i == len(order) - 1:
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            scaler.step(opt)
            scaler.update()
            opt.zero_grad(set_to_none=True)
            sched.step()
            step += 1
            log['loss'].append(round(running, 4))
            if step % 10 == 0:
                print(f'step {step}/{total_steps} loss {running:.4f} lr {sched.get_last_lr()[0]:.2e} '
                      f'{(time.time() - started) / 60:.1f} min', flush=True)
            running = 0.0
            epoch_end = (micro % len(train)) < args.grad_accum
            if val and ((args.eval_every and step % args.eval_every == 0) or (not args.eval_every and epoch_end)):
                ev = evaluate(model, processor, val, args.max_eval, torch)
                ev['step'] = step
                log['evals'].append(ev)
                print('eval', ev, flush=True)
            if (time.time() - started) / 3600 > args.max_hours:
                print('time budget reached, saving', flush=True)
                stop = True
            if stop or (args.save_every and step % args.save_every == 0):
                checkpoint(i + 1)
        if stop:
            break
    if val and (not log['evals'] or log['evals'][-1]['step'] != step):
        ev = evaluate(model, processor, val, args.max_eval, torch)
        ev['step'] = step
        log['evals'].append(ev)
        print('eval', ev, flush=True)
    if args.noise_val and not stop and Path(args.noise_val).exists():
        # exact match per noise family on held-out shops; typo/reorder were never in the train set
        noisy = load_jsonl(args.noise_val)
        fams = sorted({ex.get('family', '?') for ex in noisy})
        log['noise_eval'] = {}
        for fam in fams:
            part = [ex for ex in noisy if ex.get('family') == fam][:args.max_eval]
            for ex in part:
                ex['_enc'] = encode(processor, ex, args.max_len)
            log['noise_eval'][fam] = evaluate(model, processor, part, args.max_eval, torch)
            print('noise eval', fam, log['noise_eval'][fam], flush=True)
    model.save_pretrained(out)
    log['minutes'] = round(minutes_before + (time.time() - started) / 60, 1)
    log['complete'] = not stop
    log['step'], log['total_steps'] = step, total_steps
    atomic_write_text(out / 'train_log.json', json.dumps(log, ensure_ascii=False, indent=1))
    if not stop:                                   # finished: the resume state is no longer needed
        shutil.rmtree(out / 'checkpoint', ignore_errors=True)
    print('saved', out, flush=True)


if __name__ == '__main__':
    main()
