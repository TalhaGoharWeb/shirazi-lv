# "Hey Shirazi" — training your own wake-word voice model

Shirazi listens for **"Hey Shirazi"**. Out of the box it uses an interim
pre-trained acoustic model, so the feature works immediately. For the real
experience — where it wakes on *your* voice saying *"hey shirazi"* — train a
small custom model once. It stays on your PC; your voice never leaves it.

## What you need

- Your PC's microphone (any working mic).
- ~1 minute of your time.
- Python with `openwakeword` installed (Shirazi installs it for you from
  ⚙ → WAKE WORD, or run `pip install openwakeword`).

## Step 1 — record yourself (2 minutes)

1. Open any voice recorder (Windows Voice Recorder is fine).
2. Record **30–50 short clips** of yourself saying **"hey shirazi"**:
   - One clip per utterance, ~1 second each, with a little silence around it.
   - Vary it naturally: normal voice, slightly louder, slightly faster/slower,
     from a bit further from the mic for a few.
   - Quiet room is best, but 5–10 clips with light background noise (fan, TV
     low) actually help.
3. Save them as `.wav` files (16 kHz mono is ideal; the recorder default is fine).

## Step 2 — train the model

openwakeword provides the training pipeline (runs on CPU; takes a while —
start it and let it run):

1. Follow the official custom-model guide:  
   https://github.com/dscripka/openWakeWord#training-new-models
   (the Colab notebook walks through it: upload your clips as positive
   samples, pick a model name `hey_shirazi`, train, download the `.onnx`).
2. You will get a file named something like `hey_shirazi.onnx`.

No Colab / no GPU? The notebook is the supported path; CPU training locally is
possible but slow. Ask in Shirazi's chat and we'll walk through alternatives.

## Step 3 — install the model into Shirazi

Copy your trained file here (create the folder if needed):

```
C:\Users\<you>\.shirazi\wake_models\hey_shirazi.onnx
```

Restart Shirazi (or toggle wake word off/on in ⚙ → WAKE WORD). The log will say:

```
Wake word: listening for 'Hey Shirazi' (custom 'Hey Shirazi' voice model).
```

That's it — from now on it wakes on *your* "hey shirazi".

## Notes

- The custom model is **yours**: it never uploads anywhere and works fully offline.
- If detection feels too eager or too shy, adjust the threshold in ⚙ → WAKE WORD.
- To go back to the interim model, just remove the `.onnx` file and restart.
- Retraining later with more clips (different rooms, moods) keeps improving it.
