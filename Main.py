# -------------------------------------------------------
# © 2025 Shiwa Mardokh Rouhani. All rights reserved.
# This project (including code, assets, and animations)
# is original work and protected by UK copyright law.
# Unauthorized use, copying, or redistribution is prohibited.
# -------------------------------------------------------

import os
import random
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageOps, ImageDraw
import customtkinter as ctk
import time
import threading

# -------------------------------------------------------------- GPT4All import
os.environ["GPT4ALL_CPU_ONLY"] = "1"  # force CPU
try:
    from gpt4all import GPT4All
except Exception as e:
    GPT4All = None
    _GPT_IMPORT_ERROR = str(e)
else:
    _GPT_IMPORT_ERROR = None

# --------------------------------------------------------------------------------------------------------------------------------- Config
ASSETS_DIR = r"[Put your address here]\Desktop Cat\Assets"
MODEL_PATH = r"[Put your address here]\Desktop Cat\Models\llama-3.2-1b-instruct-q4_k_m.gguf"

GPT_MAX_TOKENS = 150
GPT_TEMP = 0.8
GIF_SCALE = 0.12
DEFAULT_DELAY = 120
CHAT_LIMIT = 10

GIF_FILES = {
    "idle": ("idle.gif", 13),
    "idle_to_sleep": ("idle to sleep.gif", 12),
    "sleep": ("sleeping.gif", 22),
    "sleep_to_idle": ("sleep to idle.gif", 22),
    "pizza": ("eating pizza.gif", 24),
    "pizza_to_idle": ("pizza to idle.gif", 16),
    "walk_left": ("walk left.gif", 18),
    "walk_right": ("walk right.gif", 14),
    "idle_to_typing": ("idle_to_typing.gif", 23),
    "typing": ("typing.gif", 9),
}
PROFILE_FILENAME = "profile.png"


# ------------------------------------------------------------------------------------------------------
def resource_path(*parts):
    return os.path.join(ASSETS_DIR, *parts)


def load_gif_frames(filename, n_frames, scale=1.0):
    frames = []
    fp = resource_path(filename)
    try:
        gif = Image.open(fp)
    except Exception as e:
        raise RuntimeError(f"Failed to open GIF {fp}: {e}")
    for i in range(n_frames):
        try:
            gif.seek(i)
        except EOFError:
            break
        frame = gif.convert("RGBA")
        w, h = frame.size
        frame = frame.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        frames.append(ImageTk.PhotoImage(frame))
    if not frames:
        raise RuntimeError(f"No frames loaded from {fp}")
    return frames


def make_circular_ctkimage(pil_path, size):
    pil = Image.open(pil_path).convert("RGBA")
    pil = ImageOps.fit(pil, (size, size))
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    pil.putalpha(mask)
    return ctk.CTkImage(pil, size=(size, size))


# ------------------------------------------------------------------------------------- GPT
class LocalGPT:
    def __init__(self, model_path, device="cpu"):
        self.ready = False
        self._client = None
        if GPT4All is None:
            self.err = f"gpt4all not installed: {_GPT_IMPORT_ERROR}"
            return
        if not os.path.exists(model_path):
            self.err = f"Model not found: {model_path}"
            return
        try:
            self._client = GPT4All(model_path, device=device)
            self.ready = True
        except Exception as e:
            self.err = f"Failed to load GPT4All model: {e}"

    def generate(self, prompt, max_tokens=GPT_MAX_TOKENS, temp=GPT_TEMP):
        if not self.ready:
            return "(model not ready)"
        try:
            out = self._client.generate(prompt, max_tokens=max_tokens, temp=temp)
            if isinstance(out, str):
                return out.strip()
            return str(out).strip()
        except Exception as e:
            return f"(model error) {e}"


# -------------------------------------------------------------------- Desktop Cat actions and control
class DesktopCatApp:
    def __init__(self, root):
        self.root = root
        self.root.overrideredirect(True)
        self.root.config(bg="black")
        self.root.wm_attributes("-transparentcolor", "black")
        self.root.wm_attributes("-topmost", True)

        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        # Load frames
        self.frames = {}
        for k, (fn, n) in GIF_FILES.items():
            self.frames[k] = load_gif_frames(fn, n, scale=GIF_SCALE)
        self.gif_width = self.frames['idle'][0].width()
        self.gif_height = self.frames['idle'][0].height()
        self.x = self.screen_width - self.gif_width - 100
        self.y = self.screen_height - self.gif_height - 40

        self.label = tk.Label(self.root, bd=0, bg="black")
        self.label.pack()
        for k in self.frames:
            setattr(self.root, f"_{k}", self.frames[k])

        # Action control
        self.actions_paused = False
        self.action_bag = [1, 2, 3, 4, 5]
        self.typing_animation_running = False
        self.typing_loop_id = None

        # Chat state
        self.chat_count = 0
        self.chat_history = []
        self.chat_window_open = False
        self.current_chat_window = None

        # Profile image
        self.profile_ctk = None
        profile_full = resource_path(PROFILE_FILENAME)
        if os.path.exists(profile_full):
            self.profile_ctk = make_circular_ctkimage(profile_full, 80)

        # GPT
        self.gpt = LocalGPT(MODEL_PATH, device="cpu")

        self.root.geometry(f"+{self.x}+{self.y}")
        self.play(self.frames['idle'], delay=180)
        self.root.after(random.randint(2000, 5000), self.next_action)
        self.label.bind("<Double-Button-1>", lambda e: self.open_chat_window())

    # --------------------------------------------------------------------------------- Animation
    def play(self, frames, delay=100, move_x=0):
        for f in frames:
            self.label.config(image=f)
            if move_x > 0 and self.x + self.gif_width + 5 >= self.screen_width:
                break
            if move_x < 0 and self.x <= 0:
                break
            self.x = max(0, min(self.screen_width - self.gif_width, self.x + move_x))
            self.root.geometry(f"+{self.x}+{self.y}")
            self.root.update()
            time.sleep(delay / 1000)

    def _do_idle_n(self, n=10):
        for _ in range(n):
            if self.actions_paused: break
            self.play(self.frames['idle'], delay=180)

    def action_walk_left(self):
        steps = random.randint(3, 6)
        for _ in range(steps):
            if self.actions_paused: return
            self.play(self.frames['walk_left'], delay=100, move_x=-3)
        self._do_idle_n()

    def action_walk_right(self):
        steps = random.randint(3, 6)
        for _ in range(steps):
            if self.actions_paused: return
            self.play(self.frames['walk_right'], delay=100, move_x=3)
        self._do_idle_n()

    def action_eat(self):
        if self.actions_paused: return
        self.play(self.frames['pizza'], delay=150)
        self.play(self.frames['pizza_to_idle'], delay=150)
        self._do_idle_n()

    def action_sleep(self):
        if self.actions_paused: return
        self.play(self.frames['idle_to_sleep'], delay=150)
        self.play(self.frames['sleep'], delay=500)
        self.play(self.frames['sleep_to_idle'], delay=150)
        self._do_idle_n()

    def action_idle_only(self):
        if self.actions_paused: return
        self._do_idle_n()

    def next_action(self):
        if self.actions_paused:
            self.root.after(1000, self.next_action)
            return
        if not self.action_bag:
            self.action_bag = [1, 2, 3, 4, 5]
        choice = random.choice(self.action_bag)
        self.action_bag.remove(choice)
        if choice == 1:
            self.action_walk_left()
        elif choice == 2:
            self.action_eat()
        elif choice == 3:
            self.action_walk_right()
        elif choice == 4:
            self.action_sleep()
        else:
            self.action_idle_only()
        self.root.after(random.randint(2000, 5000), self.next_action)

    # ------------------------------------------------------------------------- Typing animation
    def start_typing_animation(self):
        self.actions_paused = True
        self.typing_animation_running = True
        # Skip transition, go straight to typing loop
        self._start_typing_loop(0)

    def _start_typing_loop(self, idx):
        if not self.typing_animation_running:
            return
        frames = self.frames['typing']
        self.label.config(image=frames[idx % len(frames)])
        idx = (idx + 1) % len(frames)
        self.typing_loop_id = self.root.after(120, lambda: self._start_typing_loop(idx))

    def stop_typing_animation(self):
        self.typing_animation_running = False

        # Cancel animation loop
        if self.typing_loop_id:
            try:
                self.root.after_cancel(self.typing_loop_id)
            except:
                pass
            self.typing_loop_id = None

        # Resume normal actions
        self.actions_paused = False

        # Return to idle animation
        try:
            self.play(self.frames['idle'], delay=180)
        except:
            pass

    # ------------------------------------------------------------------------------------------------- Chat window
    def open_chat_window(self):
        # ----------------------- Close existing window if open
        if self.current_chat_window is not None:
            try:
                self.current_chat_window.destroy()
            except:
                pass

        chat_win = ctk.CTkToplevel(self.root)
        chat_win.geometry("350x550")
        chat_win.title("Cat Language Translator!")

        self.current_chat_window = chat_win
        self.chat_window_open = True
        self.start_typing_animation()

        # ---------------------------------------------------------------------------------------------- Header
        header_frame = ctk.CTkFrame(chat_win, fg_color="#F2A96B", corner_radius=20)
        header_frame.pack(fill="x", padx=10, pady=10)

        if self.profile_ctk:
            profile_label = ctk.CTkLabel(header_frame, image=self.profile_ctk, text="")
            profile_label.image_ref = self.profile_ctk
        else:
            profile_label = ctk.CTkLabel(header_frame, text="[no profile image]", text_color="white")
        profile_label.pack(pady=5)

        tagline = ctk.CTkLabel(header_frame, text="I'm silly but I leave paw prints on your heart 🐾🧡",
                               font=("Segoe UI", 12), text_color="white")
        tagline.pack(pady=(0, 10))

        # --------------------------------------------------------------- Chat container with scrollable frame
        chat_container = ctk.CTkScrollableFrame(chat_win, fg_color="#F5F5F5", corner_radius=0)
        chat_container.pack(fill="both", expand=True, padx=0, pady=0)

        # -------------------------------------------------------------------------------- Input frame
        input_frame = ctk.CTkFrame(chat_win, fg_color="transparent")
        input_frame.pack(fill="x", padx=15, pady=15)

        entry = ctk.CTkEntry(input_frame, placeholder_text="Message", height=40,
                             corner_radius=25, font=("Segoe UI", 14),
                             border_width=2, border_color="#E0E0E0",
                             fg_color="white")
        entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        send_button = ctk.CTkButton(input_frame, width=70, height=40, corner_radius=25,
                                    fg_color="#F2A96B", hover_color="#e48f52", text="Send",
                                    font=("Segoe UI", 13, "bold"))
        send_button.pack()

        # ---------------------------------------------------------------------------------Send logic
        def send_message(event=None):
            # Check if window is still valid
            try:
                if not chat_win.winfo_exists():
                    return
            except:
                return

            user_msg = entry.get().strip()
            if not user_msg:
                return
            entry.delete(0, tk.END)

            # ----------------------------- Create user bubble (right-aligned, orange)
            user_frame = ctk.CTkFrame(chat_container, fg_color="transparent")
            user_frame.pack(fill="x", padx=15, pady=5)

            user_bubble = ctk.CTkFrame(user_frame, fg_color="#d46f28", corner_radius=20)
            user_bubble.pack(anchor="e", padx=(50, 0))

            user_label = ctk.CTkLabel(user_bubble, text=user_msg,
                                      font=("Segoe UI", 13), text_color="white",
                                      justify="left", wraplength=200)
            user_label.pack(padx=15, pady=10)

            chat_container._parent_canvas.yview_moveto(1.0)

            def generate_response():
                self.chat_count += 1
                prompt = (
                    "You are Miki, a cute mew-human hybrid cat. "
                    "RULES: "
                    "1. ONLY respond to the user's message. "
                    "2. NEVER create new messages for the user. "
                    "3. NEVER write 'You:' or pretend to be the user. "
                    "4. NEVER continue the conversation script. "
                    "5. ONLY write ONE reply as Miki.\n"
                    f"User message: {user_msg}\n"
                    "Miki:"
                )
                if "food" in user_msg.lower():
                    prompt += " Your favorite food is Pizza."

                if not hasattr(self.gpt, 'ready') or not self.gpt.ready:
                    response = f"Mew~ I'm sleeeeepy! {user_msg[:10]}"
                else:
                    response = self.gpt.generate(prompt)

                self.chat_history.append(f"You: {user_msg}")
                self.chat_history.append(f"Miki: {response}")

                # Check if window still exists before updating
                try:
                    if not chat_win.winfo_exists():
                        return
                except:
                    return

                # ----------------------------------------------------- Create Miki bubble (left)
                miki_frame = ctk.CTkFrame(chat_container, fg_color="transparent")
                miki_frame.pack(fill="x", padx=15, pady=5)

                miki_bubble = ctk.CTkFrame(miki_frame, fg_color="#FFFFFF", corner_radius=20,
                                           border_width=2, border_color="#D2691E")
                miki_bubble.pack(anchor="w", padx=(0, 50))

                miki_label = ctk.CTkLabel(miki_bubble, text=response,
                                          font=("Segoe UI", 13), text_color="#8B4513",
                                          justify="left", wraplength=200)
                miki_label.pack(padx=15, pady=10)

                chat_container._parent_canvas.yview_moveto(1.0)

            # donno why threading
            threading.Thread(target=generate_response, daemon=True).start()

        entry.bind("<Return>", send_message)
        send_button.configure(command=send_message)

        def on_close():
            self.chat_window_open = False
            self.current_chat_window = None

            # --- Stop typing and resume actions
            self.stop_typing_animation()

            # --- Destroy the window immediately
            chat_win.quit()
            chat_win.destroy()

        chat_win.protocol("WM_DELETE_WINDOW", on_close)


# -------------------------------------------------------------------------------------------------- Run
if __name__ == "__main__":
    root = tk.Tk()
    try:
        app = DesktopCatApp(root)
        root.mainloop()
    except Exception as e:
        try:
            messagebox.showerror("Desktop Cat - Error", f"An error occurred:\n{e}")
        except:
            print("Error:", e)
        raise