import cv2
import numpy as np
import mss
import torch
import clip
from PIL import Image
import pydirectinput
import time
import keyboard
import random
import win32gui
import win32con
import ctypes
import csv
import os
from datetime import datetime

# --- 設定 ---
#TARGET_TEXT = "A cinematic drone shot of a majestic red Minecraft pagoda and temple"
TARGET_TEXT = "A Minecraft village with houses and temples"

#NEGATIVE_TEXT = "A close up of a wall, view with no buildings, only sky, water, or terrain" #集落上空用
NEGATIVE_TEXT = "A close up of a gray stone wall, blocked view, obstacle, blue ocean, green forest, black space" #集落内（地上視点）用

WINDOW_NAME = "Minecraft* Forge 1.21.4 - シングルプレイ"

CENTER_BIAS = 0.01
BAD_SCORE_THRESHOLD = 0.19
NEGATIVE_WEIGHT = 0.4

# ===== 実験条件の切り替え =====
# True  → ネガティブプロンプトあり（提案手法）
# False → ネガティブプロンプトなし（比較手法）
USE_NEGATIVE = True

# 1試行の走行時間（秒）
RUN_DURATION = 60

# 結果保存先
RESULT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "negative_scene_results.csv")

# --- 高DPI設定 ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

# --- CLIP準備 ---
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Loading CLIP model on {device}...")
model, preprocess = clip.load("ViT-B/32", device=device)

text_inputs = clip.tokenize([TARGET_TEXT, NEGATIVE_TEXT]).to(device)
print("Model loaded.")

def get_minecraft_window_rect():
    hwnd = win32gui.FindWindow(None, WINDOW_NAME)
    if not hwnd:
        print(f"Error: Window '{WINDOW_NAME}' not found!")
        return None
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception as e:
        pass
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    client_point = win32gui.ClientToScreen(hwnd, (0, 0))
    return {'top': client_point[1], 'left': client_point[0],
            'width': right - left, 'height': bottom - top}

def get_screen(monitor):
    with mss.mss() as sct:
        img = np.array(sct.grab(monitor))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

def get_3split_scores(image):
    h, w, _ = image.shape
    w_3 = w // 3

    img_left   = cv2.resize(image[:, :w_3],      (224, 224))
    img_center = cv2.resize(image[:, w_3:2*w_3], (224, 224))
    img_right  = cv2.resize(image[:, 2*w_3:],    (224, 224))
    img_full   = cv2.resize(image,               (224, 224))

    images = [img_full, img_left, img_center, img_right]
    image_tensors = [
        preprocess(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
        for img in images
    ]
    image_input_batch = torch.stack(image_tensors).to(device)

    with torch.no_grad():
        image_features = model.encode_image(image_input_batch)
        text_features  = model.encode_text(text_inputs)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        text_features  /= text_features.norm(dim=-1, keepdim=True)
        sim_matrix = (image_features @ text_features.T).cpu().numpy()

    final_scores = []
    neg_scores   = []
    for i in range(4):
        pos_score = sim_matrix[i][0]
        neg_score = sim_matrix[i][1]
        neg_scores.append(neg_score)

        if USE_NEGATIVE:
            adjusted_score = pos_score - (neg_score * NEGATIVE_WEIGHT)
        else:
            adjusted_score = pos_score

        final_scores.append(adjusted_score)

    full_neg = neg_scores[0]
    return final_scores[0], final_scores[1], final_scores[2], final_scores[3], full_neg

# --- 結果をCSVに追記 ---
def save_result(condition, scenario, trial,
                total_frames, negative_scene_frames, negative_scene_rate,
                neg_mean, neg_max):
    file_exists = os.path.exists(RESULT_CSV)
    with open(RESULT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "timestamp", "condition", "scenario", "trial",
                "total_frames", "negative_scene_frames", "negative_scene_rate(%)",
                "neg_mean", "neg_max"
            ])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            condition, scenario, trial,
            total_frames, negative_scene_frames,
            f"{negative_scene_rate*100:.2f}",
            f"{neg_mean:.4f}",
            f"{neg_max:.4f}"
        ])
    print(f"\n結果を {RESULT_CSV} に保存しました。")

# --- メイン ---
def main():
    monitor = get_minecraft_window_rect()
    if monitor is None:
        return

    print("\n===== 実験情報を入力してください =====")
    scenario = input("シナリオ (aerial / ground): ").strip()

    # シナリオに応じてネガティブシーン判定閾値を設定
    if scenario == "aerial":
        NEGATIVE_SCENE_THRESHOLD = 0.26
    elif scenario == "ground":
        NEGATIVE_SCENE_THRESHOLD = 0.23
    else:
        NEGATIVE_SCENE_THRESHOLD = 0.25

    trial    = input("試行番号 (1 / 2 / 3 / 4 / 5): ").strip()
    condition = "neg_on" if USE_NEGATIVE else "neg_off"
    print(f"条件: {condition} | シナリオ: {scenario} | 試行: {trial}")
    print(f"NEGATIVE_SCENE_THRESHOLD: {NEGATIVE_SCENE_THRESHOLD}")
    print(f"\n{RUN_DURATION}秒後に自動終了します。'q'で途中終了。")
    print("3秒後にスタートします...")

    cv2.namedWindow("Collision Evaluator", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Collision Evaluator", cv2.WND_PROP_TOPMOST, 1)
    cv2.moveWindow("Collision Evaluator", 1200, 0)

    total_frames          = 0
    negative_scene_frames = 0
    neg_score_log         = []

    time.sleep(3)

    first_frame = get_screen(monitor)
    s_full, s_left, s_center, s_right, _ = get_3split_scores(first_frame)
    avg_full, avg_left, avg_center, avg_right = s_full, s_left, s_center, s_right

    start_time = time.time()

    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed >= RUN_DURATION:
                print("\n時間終了！")
                break
            if keyboard.is_pressed('q'):
                print("\n手動終了。")
                break

            curr_frame = get_screen(monitor)
            s_full, s_left, s_center, s_right, full_neg = get_3split_scores(curr_frame)

            avg_full   = avg_full   * 0.7 + s_full   * 0.3
            avg_left   = avg_left   * 0.7 + s_left   * 0.3
            avg_center = avg_center * 0.7 + s_center * 0.3
            avg_right  = avg_right  * 0.7 + s_right  * 0.3

            # ===== ネガティブシーンカウント =====
            total_frames += 1
            neg_score_log.append(full_neg)
            is_negative_scene = full_neg > NEGATIVE_SCENE_THRESHOLD
            if is_negative_scene:
                negative_scene_frames += 1

            # 行動決定
            action    = 'wait'
            state_msg = ""

            if avg_full < 0.15:
                state_msg = "Blocked! U-Turn"
                action = 'u_turn'
            else:
                scores = {
                    'left':     avg_left,
                    'straight': avg_center + CENTER_BIAS,
                    'right':    avg_right
                }
                best_direction = max(scores, key=scores.get)

                if best_direction == 'straight' and scores['straight'] < 0.18:
                    state_msg = "Avoid Wall"
                    action = 'right' if avg_right > avg_left else 'left'
                else:
                    action = best_direction
                    state_msg = f"{action.upper()} ({scores[action]:.3f})"

            negative_scene_rate = negative_scene_frames / total_frames if total_frames > 0 else 0
            remaining = RUN_DURATION - elapsed

            print(f"[{elapsed:5.1f}s] neg:{full_neg:.3f} {'⚠NEG_SCENE' if is_negative_scene else '          '} "
                  f"| rate:{negative_scene_rate*100:.1f}% | {state_msg} | 残り{remaining:.0f}s")

            # 移動
            if action == 'straight':
                pydirectinput.keyDown('w'); time.sleep(0.1); pydirectinput.keyUp('w')
            elif action == 'left':
                pydirectinput.moveRel(-150, 0)
                pydirectinput.keyDown('w'); time.sleep(0.1); pydirectinput.keyUp('w')
            elif action == 'right':
                pydirectinput.moveRel(150, 0)
                pydirectinput.keyDown('w'); time.sleep(0.1); pydirectinput.keyUp('w')
            elif action == 'u_turn':
                direction = 400 if random.random() < 0.5 else -400
                pydirectinput.moveRel(direction, 0)
                pydirectinput.keyDown('w'); time.sleep(0.2); pydirectinput.keyUp('w')

            # デバッグ表示
            debug_img = curr_frame.copy()
            h, w, _ = debug_img.shape
            w_3 = w // 3
            cv2.line(debug_img, (w_3, 0), (w_3, h), (0, 255, 255), 2)
            cv2.line(debug_img, (2*w_3, 0), (2*w_3, h), (0, 255, 255), 2)
            if is_negative_scene:
                cv2.rectangle(debug_img, (0, 0), (w-1, h-1), (0, 0, 255), 6)
            cv2.putText(debug_img, f"neg:{full_neg:.3f}  rate:{negative_scene_rate*100:.1f}%",
                        (10, 40), 0, 1.0, (0, 0, 255) if is_negative_scene else (0, 255, 0), 2)
            cv2.putText(debug_img, f"USE_NEGATIVE={USE_NEGATIVE}  {condition}",
                        (10, 80), 0, 0.8, (255, 255, 0), 2)
            cv2.putText(debug_img, f"{avg_left:.2f}", (10, h-50), 0, 0.7, (0, 255, 0), 2)
            cv2.putText(debug_img, f"{avg_center:.2f}", (w_3+10, h-50), 0, 0.7, (0, 255, 0), 2)
            cv2.putText(debug_img, f"{avg_right:.2f}", (2*w_3+10, h-50), 0, 0.7, (0, 255, 0), 2)
            cv2.putText(debug_img, state_msg, (10, 120), 0, 1.0, (0, 0, 255), 2)
            cv2.imshow("Collision Evaluator", debug_img)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except Exception as e:
        print(f"エラー: {e}")

    finally:
        cv2.destroyAllWindows()

        if total_frames > 0:
            negative_scene_rate = negative_scene_frames / total_frames
            neg_mean = np.mean(neg_score_log)
            neg_max  = np.max(neg_score_log)

            print("\n========== 結果 ==========")
            print(f"条件                     : {condition}")
            print(f"シナリオ                 : {scenario}")
            print(f"試行                     : {trial}")
            print(f"総フレーム数             : {total_frames}")
            print(f"ネガティブシーンフレーム : {negative_scene_frames}")
            print(f"ネガティブシーン率       : {negative_scene_rate*100:.2f}%")
            print(f"neg平均                  : {neg_mean:.4f}")
            print(f"neg最大                  : {neg_max:.4f}")
            print("===========================\n")

            save_result(condition, scenario, trial,
                        total_frames, negative_scene_frames, negative_scene_rate,
                        neg_mean, neg_max)

if __name__ == "__main__":
    main()