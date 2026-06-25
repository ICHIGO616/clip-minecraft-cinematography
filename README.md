# CLIP-Guided Autonomous Cinematography of Minecraft Settlements

This repository contains the source code, prompts, and raw experimental results for the paper:

> **CLIP-Guided Autonomous Cinematography of Minecraft Settlements via Tri-Region Prompt Evaluation**  
> Masayoshi Ichigo, Koki Oishi, Ibrahim Khan, Ruck Thawonmas  
> IEEE Global Conference on Consumer Electronics (GCCE) 2026

---

## Overview

This system autonomously navigates and films AI-generated Minecraft settlements using CLIP (Contrastive Language-Image Pre-training). The agent splits the game view into three regions (left, center, right), evaluates each region against positive and negative text prompts, and steers toward the highest-scoring direction — requiring no object detection, depth maps, or training data.

![System Overview](fig1_split.png)

---

## Repository Structure

```
clip-minecraft-cinematography/
├── Evaluate_collision.py          # Autonomous cinematography agent with negative scene rate measurement
├── negative_scene_results.csv     # Raw experimental results
├── GDMC 2025 submission map.zip   # Minecraft world used in experiments
└── README.md
```

---

## Files

### `Evaluate_collision.py`
The autonomous cinematography agent used in all experiments. This script navigates the Minecraft settlement and simultaneously measures the **negative scene rate** as defined in Section IV-B of the paper.

**Behavior:**
- Captures the current Minecraft game screen at each time step
- Splits the screen into 3 horizontal regions (left / center / right) + full screen
- Computes CLIP cosine similarity between each region and a positive/negative prompt pair
- Scores each region as: `S = pos - neg × w` (w = 0.4)
- Moves toward the highest-scoring direction
- Triggers avoidance behavior when scores fall below thresholds
- Measures the **negative scene rate**: the proportion of frames in which the full-frame negative-prompt similarity score exceeds a predefined threshold θ
- Automatically terminates after 60 seconds per trial
- Appends results to `negative_scene_results.csv`

**Switching between proposed method and baseline:**
```python
USE_NEGATIVE = True   # Neg-on: proposed method (negative prompts active)
USE_NEGATIVE = False  # Neg-off: baseline (negative prompts disabled)
```

**Threshold θ per scenario:**

| Scenario | θ (NEGATIVE_SCENE_THRESHOLD) |
|---|---|
| Aerial | 0.26 |
| Ground | 0.23 |

**Prompts used in experiments (Table I):**

| Scenario | Type | Prompt |
|---|---|---|
| Aerial | Positive | "A cinematic drone shot of a majestic red Minecraft pagoda and temple" |
| Aerial | Negative | "A close up of a wall, view with no buildings, only sky, water, or terrain" |
| Ground | Positive | "A Minecraft village with houses and temples" |
| Ground | Negative | "A close up of a gray stone wall, blocked view, obstacle, blue ocean, green forest, black space" |

---

### `negative_scene_results.csv`
Raw experimental results from 25 trials per condition (neg-on / neg-off) × scenario (aerial / ground), as reported in Table II of the paper.

**Columns:**

| Column | Description |
|---|---|
| `timestamp` | Date and time of the trial |
| `condition` | `neg_on` (proposed method) or `neg_off` (baseline) |
| `scenario` | `aerial` or `ground` |
| `trial` | Trial number |
| `total_frames` | Total number of frames captured during the 60-second trial |
| `negative_scene_frames` | Number of frames where the negative-prompt similarity exceeded threshold θ |
| `negative_scene_rate(%)` | `negative_scene_frames / total_frames × 100` |
| `neg_mean` | Mean negative-prompt similarity score across all frames |
| `neg_max` | Maximum negative-prompt similarity score across all frames |

**Summary of results (Table II):**

| Scenario | Neg-on (proposed) | Neg-off (baseline) |
|---|---|---|
| Aerial | 24.38 ± 9.79 % | 52.79 ± 6.92 % |
| Ground | 11.17 ± 4.83 % | 31.15 ± 24.03 % |

A two-sample t-test confirmed statistically significant differences in both scenarios (aerial: p < 0.001; ground: p < 0.001).

---

### `GDMC 2025 submission map.zip`
The Minecraft world (runner-up settlement from GDMC 2025) used in all experiments.

#### GDMC Initial Setup

To run the system, the following environment is required.

**Step 1: Install Minecraft (Java Edition)**

Purchase and install Minecraft Java Edition from the [official website](https://www.minecraft.net/).  
After purchase, download and launch **Minecraft Launcher**, then sign in with your Microsoft account.

**Step 2: Set up Minecraft Forge and GDMC HTTP Interface Mod**

The following versions are required:
- Minecraft: `1.21.4`
- Minecraft Forge: `1.21.4-forge-54.1.0`
- GDMC-HTTP-Interface Mod: `1.6.0`

1. Download Minecraft Forge from [https://files.minecraftforge.net/](https://files.minecraftforge.net/), select version `1.21.4`, and run the installer.
2. In Minecraft Launcher, go to **Launch Configurations** → **New**, set the version to `release 1.21.4-forge-54.1.0`, and save.
3. Download the GDMC-HTTP-Interface Mod from [https://github.com/Niels-NTG/gdmc_http_interface](https://github.com/Niels-NTG/gdmc_http_interface) and place the `.jar` file into the `mods` folder of your game directory.
4. Launch Minecraft with the Forge configuration. If `[GDMC-HTTP] Server started at http://localhost:9000/` appears on screen, the setup is complete.

**Step 3: Install GDPC (Python development tool)**

```bash
pip install gdpc
```

Documentation: [https://github.com/avdstaaij/gdpc](https://github.com/avdstaaij/gdpc)

#### Loading the World

Extract `GDMC 2025 submission map.zip` and place the extracted folder into:
```
C:\Users\<username>\AppData\Roaming\.minecraft\saves\
```
Then launch Minecraft and open the world from the single-player menu.

#### World Settings

Before running the scripts, apply the following commands in-game to ensure reproducibility:

```
# Always daytime
/gamerule doDaylightCycle false
/time set 6000

# Enable noclip (walk through walls)
/gamemode spectator

# Teleport to aerial (drone-view) start position
/tp @s -35 110 -30 180 0

# Teleport to ground-level start position
/tp @s -120 65 -70 145 0
```

---

## Requirements

```
Python 3.13.3
torch
clip  # OpenAI CLIP
opencv-python
mss
pydirectinput
keyboard
pywin32
Pillow
```

Install CLIP:
```bash
pip install git+https://github.com/openai/CLIP.git
```

---

## Usage

```bash
python Evaluate_collision.py
# Enter scenario: aerial / ground
# Enter trial number
```

---

## Citation

```bibtex
@inproceedings{ichigo2026clip,
  title     = {CLIP-Guided Autonomous Cinematography of Minecraft Settlements via Tri-Region Prompt Evaluation},
  author    = {Ichigo, Masatomo and Oishi, Kouki and Khan, Ibrahim and Thawonmas, Ruck},
  booktitle = {Proceedings of the IEEE Global Conference on Consumer Electronics (GCCE)},
  year      = {2026}
}
```
