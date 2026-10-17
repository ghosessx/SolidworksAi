"""
SolidAI — Autonomous Parametric CAD Agent GUI
Features Dual-Mode Operation:
1. Natural Language CAD Agent (Prompt to 3D Model)
2. Blueprint / Technical Drawing Vision Agent (Photo to 3D Model)
Compatible with SOLIDWORKS 2024 / 2025 / 2026.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import sys
import os
import pythoncom
from PIL import Image, ImageTk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import settings
from cad_executor import run_autonomous_cad_agent, run_vision_cad_agent
from vision_analyzer import get_available_vision_models


class SolidAIGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SolidAI — Autonomous Parametric CAD Agent (SOLIDWORKS 2025)")
        self.geometry("780x690")
        self.configure(bg="#1E1E2E")
        self.resizable(False, False)

        self.selected_image_path = None
        self.thumbnail_photo = None

        self._setup_styles()
        self._setup_ui()

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "TNotebook",
            background="#1E1E2E",
            borderwidth=0
        )
        style.configure(
            "TNotebook.Tab",
            background="#313244",
            foreground="#CDD6F4",
            font=("Segoe UI", 10, "bold"),
            padding=[16, 8]
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#89B4FA")],
            foreground=[("selected", "#11111B")]
        )
        style.configure(
            "Horizontal.TProgressbar",
            troughcolor="#313244",
            background="#89B4FA",
            thickness=8
        )

    def _setup_ui(self):
        # Header
        title_label = tk.Label(
            self, text="SolidAI — Autonomous CAD Agent", font=("Segoe UI", 20, "bold"),
            fg="#89B4FA", bg="#1E1E2E"
        )
        title_label.pack(pady=(12, 2))

        subtitle = tk.Label(
            self, text="Autonomous 3D SOLIDWORKS Models from Natural Language Prompts and 2D Blueprints",
            font=("Segoe UI", 10), fg="#A6ADC8", bg="#1E1E2E"
        )
        subtitle.pack(pady=(0, 10))

        # Notebook (Tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=25, pady=(0, 10))

        # Tab 1: Text Prompt
        self.tab_text = tk.Frame(self.notebook, bg="#1E1E2E")
        self.notebook.add(self.tab_text, text="  💬 Natural Language CAD  ")
        self._build_text_tab()

        # Tab 2: Vision Blueprint
        self.tab_vision = tk.Frame(self.notebook, bg="#1E1E2E")
        self.notebook.add(self.tab_vision, text="  📐 Blueprint to 3D CAD  ")
        self._build_vision_tab()

        # Bottom Status Area
        status_frame = tk.Frame(self, bg="#181825", padx=15, pady=8)
        status_frame.pack(fill="x", side="bottom")

        self.lbl_status = tk.Label(
            status_frame, text="🟢 SOLIDWORKS 2025 & AI Engine Ready.",
            font=("Segoe UI", 9, "bold"), fg="#A6E3A1", bg="#181825", anchor="w"
        )
        self.lbl_status.pack(fill="x")

        self.progress = ttk.Progressbar(status_frame, mode="indeterminate", style="Horizontal.TProgressbar")

    def _build_text_tab(self):
        frame = self.tab_text

        # AI Engine & Creativity Options Bar
        opt_bar = tk.Frame(frame, bg="#1E1E2E")
        opt_bar.pack(fill="x", padx=15, pady=(8, 2))

        # Model Engine Selector
        lbl_engine = tk.Label(opt_bar, text="AI Engine:", font=("Segoe UI", 9, "bold"), fg="#89B4FA", bg="#1E1E2E")
        lbl_engine.pack(side="left", padx=(0, 5))

        self.combo_backend = ttk.Combobox(
            opt_bar, state="readonly", width=36,
            values=[
                "🌐 Hybrid (Google Gemini - Deep Reasoning)",
                "💻 Local (Ollama / Qwen2.5-Coder - Offline)"
            ]
        )
        self.combo_backend.current(0)
        self.combo_backend.pack(side="left", padx=(0, 20))

        # Style & Creativity Selector
        lbl_style = tk.Label(opt_bar, text="Design Style:", font=("Segoe UI", 9, "bold"), fg="#A6E3A1", bg="#1E1E2E")
        lbl_style.pack(side="left", padx=(0, 5))

        self.combo_style = ttk.Combobox(
            opt_bar, state="readonly", width=38,
            values=[
                "🏎️ Aerospace & Racing (Lightweight, Pocketed)",
                "🏭 Industrial & Heavy-Duty (Rigid, Robust)",
                "📐 Minimalist & Standard (Direct Geometry)"
            ]
        )
        self.combo_style.current(0)
        self.combo_style.pack(side="left")

        prompt_label = tk.Label(
            frame, text="Enter Mechanical Engineering Requirements:", font=("Segoe UI", 11, "bold"),
            fg="#CDD6F4", bg="#1E1E2E"
        )
        prompt_label.pack(anchor="w", padx=15, pady=(10, 4))

        self.txt_prompt = tk.Text(
            frame, height=4, font=("Segoe UI", 10),
            bg="#313244", fg="#FFFFFF", insertbackground="#FFFFFF",
            relief="flat", padx=10, pady=8
        )
        self.txt_prompt.pack(fill="x", padx=15)
        self.txt_prompt.insert("1.0", "Design an aerodynamic robotic joint link with weight-reduction pockets, mounting holes, and chamfered edges.")

        # Examples
        ex_frame = tk.Frame(frame, bg="#1E1E2E")
        ex_frame.pack(fill="both", expand=True, padx=15, pady=(8, 10))

        ex_title = tk.Label(
            ex_frame, text="💡 Quick Engineering Templates (Click to load):",
            font=("Segoe UI", 8, "bold"), fg="#89B4FA", bg="#1E1E2E"
        )
        ex_title.pack(anchor="w", pady=(0, 4))

        examples = [
            ("Lightweight Robotic Arm Link (Aerospace)", "Design a high-strength, lightweight robotic articulation link with lightening pockets, 4x M5 mounting holes, and chamfered edges."),
            ("Quadcopter 240 mm X-Frame Chassis Plate", "240 mm x 16 mm diagonal arms, 4 motor mounts, 8 mm shaft holes, 4 screw holes around motors, 16 mm center lightening cutout, FC mounting holes, battery slots"),
            ("6-Hole Standard Pipe Flange (Parametric)", "Draw a standard 6-hole pipe flange with 150 mm OD, 80 mm ID, 18 mm thickness, and 6 evenly spaced 12 mm bolt holes."),
            ("Shift Fork & Clevis Linkage (Drawing 36)", "On Top Plane, extrude a 120 mm long cylinder sleeve with OD 40 mm and ID 30 mm. At 101 mm height, create an 80 mm offset fork body 15 mm thick with R40/R25 crescent fork. On Front Plane, extrude a 40 mm wide clevis body at -45 mm offset and 105 mm height, drill a 12 mm pin hole, and cut a 20 mm slot."),
            ("Pillow Block Bearing Bracket", "Design a pillow block bearing bracket with a 140 mm base containing a 38.10 mm bottom center slot, 19 mm trapezoidal back upright, 70 mm bearing cylinder, 38.10 mm bore, 19 mm center reinforcement rib, and mounting holes."),
            ("NEMA 17 Stepper Motor L-Bracket", "Design an L-shaped mounting bracket for a NEMA 17 stepper motor with standard 31 mm mounting hole pattern, 22 mm center bore, and slotted base."),
            ("Stepped Bearing Pillow Block (M10 Threaded)", "On Top Plane, draw a 120x120 mm centered square base and extrude 15 mm. Add a 70 mm diameter 30 mm cylindrical hub on top face. Cut a 40 mm center bore. Add 4x M10 tapped holes at corners with chamfers."),
            ("3-Step Transmission Shaft", "Model a 3-step shaft with diameters 40 mm, 30 mm, 20 mm, lengths 50 mm, 80 mm, 40 mm, and apply 2 mm chamfers on shaft ends."),
            ("5x5 mm Square Prism Test", "Draw a 5x5 mm square on Front Plane and extrude 10 mm")
        ]

        for label, full_prompt in examples:
            btn = tk.Label(
                ex_frame, text=f"• {label}", font=("Segoe UI", 8),
                fg="#CDD6F4", bg="#1E1E2E", cursor="hand2", anchor="w"
            )
            btn.pack(fill="x", pady=1)
            btn.bind("<Button-1>", lambda e, p=full_prompt: self._set_prompt(p))
            btn.bind("<Enter>", lambda e, b=btn: b.config(fg="#89B4FA"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(fg="#CDD6F4"))

        # Action Button
        self.btn_gen_text = tk.Button(
            frame, text="🚀 Generate Parametric CAD in SOLIDWORKS", font=("Segoe UI", 11, "bold"),
            bg="#89B4FA", fg="#11111B", activebackground="#B4BEFE",
            relief="flat", padx=20, pady=8, cursor="hand2",
            command=self._start_text_generation
        )
        self.btn_gen_text.pack(pady=(5, 12))

    def _build_vision_tab(self):
        frame = self.tab_vision

        top_bar = tk.Frame(frame, bg="#1E1E2E")
        top_bar.pack(fill="x", padx=15, pady=(10, 5))

        btn_select_img = tk.Button(
            top_bar, text="📁 Select Blueprint / Drawing (.png, .jpg, .bmp)",
            font=("Segoe UI", 10, "bold"), bg="#CBA6F7", fg="#11111B",
            activebackground="#DDB6F2", relief="flat", padx=12, pady=6,
            cursor="hand2", command=self._select_image
        )
        btn_select_img.pack(side="left")

        self.btn_clear_img = tk.Button(
            top_bar, text="❌ Clear", font=("Segoe UI", 9),
            bg="#F38BA8", fg="#11111B", relief="flat", padx=8, pady=4,
            cursor="hand2", command=self._clear_image, state="disabled"
        )
        self.btn_clear_img.pack(side="left", padx=10)

        # Image Preview Card
        self.preview_card = tk.Frame(frame, bg="#313244", relief="flat", padx=10, pady=10)
        self.preview_card.pack(fill="x", padx=15, pady=5)

        self.lbl_img_preview = tk.Label(
            self.preview_card, text="Please select a 2D technical drawing or blueprint image to analyze.",
            font=("Segoe UI", 9, "italic"), fg="#A6ADC8", bg="#313244"
        )
        self.lbl_img_preview.pack(pady=15)

        self.lbl_img_info = tk.Label(
            self.preview_card, text="", font=("Segoe UI", 8),
            fg="#89B4FA", bg="#313244"
        )
        self.lbl_img_info.pack()

        # Optional user note for vision
        lbl_notes = tk.Label(
            frame, text="Additional Engineering Directives / Notes (Optional):",
            font=("Segoe UI", 9, "bold"), fg="#CDD6F4", bg="#1E1E2E"
        )
        lbl_notes.pack(anchor="w", padx=15, pady=(8, 2))

        self.txt_vision_notes = tk.Text(
            frame, height=2, font=("Segoe UI", 9),
            bg="#313244", fg="#FFFFFF", insertbackground="#FFFFFF",
            relief="flat", padx=8, pady=6
        )
        self.txt_vision_notes.pack(fill="x", padx=15)
        self.txt_vision_notes.insert("1.0", "Reconstruct all features and dimensions strictly adhering to blueprint tolerances and views.")

        # Provider / API Key settings
        prov_frame = tk.Frame(frame, bg="#1E1E2E")
        prov_frame.pack(fill="x", padx=15, pady=8)

        lbl_api = tk.Label(
            prov_frame, text="Google Gemini API Key (High Precision / Multi-View Specialist):",
            font=("Segoe UI", 8), fg="#A6ADC8", bg="#1E1E2E"
        )
        lbl_api.pack(anchor="w")

        self.ent_api_key = tk.Entry(
            prov_frame, font=("Segoe UI", 9), bg="#313244", fg="#FFFFFF",
            insertbackground="#FFFFFF", relief="flat", show="*"
        )
        self.ent_api_key.pack(fill="x", pady=(2, 0))
        saved_key = settings.get_gemini_api_key()
        if saved_key:
            self.ent_api_key.insert(0, saved_key)

        # Vision Action Button
        self.btn_gen_vision = tk.Button(
            frame, text="🚀 Generate 3D CAD from Blueprint", font=("Segoe UI", 11, "bold"),
            bg="#A6E3A1", fg="#11111B", activebackground="#B4BEFE",
            relief="flat", padx=20, pady=8, cursor="hand2",
            command=self._start_vision_generation
        )
        self.btn_gen_vision.pack(pady=(6, 10))

    def _select_image(self):
        file_path = filedialog.askopenfilename(
            title="Select Blueprint / Drawing File",
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg *.bmp *.webp"),
                ("All Files", "*.*")
            ]
        )
        if file_path:
            self.selected_image_path = file_path
            self._display_thumbnail(file_path)
            self.btn_clear_img.config(state="normal")

    def _display_thumbnail(self, path: str):
        try:
            img = Image.open(path)
            orig_w, orig_h = img.size
            size_kb = round(os.path.getsize(path) / 1024, 1)

            img.thumbnail((220, 150), Image.Resampling.LANCZOS)
            self.thumbnail_photo = ImageTk.PhotoImage(img)

            self.lbl_img_preview.config(image=self.thumbnail_photo, text="")
            self.lbl_img_info.config(
                text=f"📄 {os.path.basename(path)} | {orig_w}x{orig_h} px | {size_kb} KB"
            )
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Image Load Error", f"Unable to open image: {e}"))

    def _clear_image(self):
        self.selected_image_path = None
        self.thumbnail_photo = None
        self.lbl_img_preview.config(
            image="", text="Please select a 2D technical drawing or blueprint image to analyze."
        )
        self.lbl_img_info.config(text="")
        self.btn_clear_img.config(state="disabled")

    def _set_prompt(self, text: str):
        self.txt_prompt.delete("1.0", tk.END)
        self.txt_prompt.insert("1.0", text)

    def _set_busy(self, is_busy: bool, status_text: str = ""):
        def update():
            if is_busy:
                self.btn_gen_text.config(state="disabled")
                self.btn_gen_vision.config(state="disabled")
                self.progress.pack(fill="x", pady=(4, 0))
                self.progress.start(10)
                self.lbl_status.config(text=status_text, fg="#F9E2AF")
            else:
                self.progress.stop()
                self.progress.pack_forget()
                self.btn_gen_text.config(state="normal")
                self.btn_gen_vision.config(state="normal")
        self.after(0, update)

    def _update_status(self, text: str, color: str = "#89DCEB"):
        self.after(0, lambda: self.lbl_status.config(text=text, fg=color))

    def _start_text_generation(self):
        prompt = self.txt_prompt.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showwarning("Warning", "Please enter engineering requirements.")
            return

        backend_text = self.combo_backend.get()
        if "Ollama" in backend_text or "Local" in backend_text or "Yerel" in backend_text:
            backend_choice = "ollama"
        else:
            backend_choice = "gemini"

        style_text = self.combo_style.get()
        if "Aerospace" in style_text or "Racing" in style_text or "Havacılık" in style_text:
            style_choice = "aerospace"
        elif "Industrial" in style_text or "Heavy" in style_text or "Endüstriyel" in style_text:
            style_choice = "industrial"
        else:
            style_choice = "minimal"

        self._set_busy(True, "🤖 AI Agent synthesizing parametric engineering plan...")
        threading.Thread(
            target=self._process_text,
            args=(prompt, backend_choice, style_choice),
            daemon=True
        ).start()

    def _process_text(self, prompt: str, backend_choice: str = "gemini", style_choice: str = "aerospace"):
        pythoncom.CoInitialize()
        try:
            result = run_autonomous_cad_agent(
                user_prompt=prompt,
                max_retries=3,
                progress_callback=lambda msg: self._update_status(msg, "#89DCEB"),
                llm_backend=backend_choice,
                creativity_style=style_choice
            )

            if result.get("success"):
                parca = result.get("part_name") or result.get("parca_adi", "Model")
                self._update_status(f"✅ Success! '{parca}' ready in SOLIDWORKS.", "#A6E3A1")
                self.after(0, lambda: messagebox.showinfo("Completed", f"'{parca}' model successfully generated in SOLIDWORKS!"))
            else:
                err = result.get("error", "Unknown error")
                self._update_status(f"❌ {err}", "#F38BA8")
                self.after(0, lambda: messagebox.showerror("Error", err))
        except Exception as e:
            self._update_status(f"❌ Error: {str(e)}", "#F38BA8")
            self.after(0, lambda: messagebox.showerror("Execution Error", str(e)))
        finally:
            pythoncom.CoUninitialize()
            self._set_busy(False)

    def _start_vision_generation(self):
        if not self.selected_image_path or not os.path.exists(self.selected_image_path):
            messagebox.showwarning("Warning", "Please select a technical drawing file first.")
            return

        user_notes = self.txt_vision_notes.get("1.0", tk.END).strip()
        api_key = self.ent_api_key.get().strip()

        if api_key != settings.get_gemini_api_key():
            settings.save_gemini_api_key(api_key)

        self._set_busy(True, "📷 Blueprint is being analyzed by vision AI specialist...")
        threading.Thread(
            target=self._process_vision,
            args=(self.selected_image_path, user_notes, api_key),
            daemon=True
        ).start()

    def _process_vision(self, img_path: str, user_notes: str, api_key: str):
        pythoncom.CoInitialize()
        try:
            result = run_vision_cad_agent(
                image_path=img_path,
                user_notes=user_notes,
                api_key=api_key,
                progress_callback=lambda msg: self._update_status(msg, "#89DCEB")
            )

            if result.get("success"):
                parca = result.get("part_name") or result.get("parca_adi", "Blueprint Model")
                self._update_status(f"✅ Success! '{parca}' modeled in SOLIDWORKS.", "#A6E3A1")
                self.after(0, lambda: messagebox.showinfo("Blueprint Reconstructed", f"'{parca}' blueprint successfully reconstructed in SOLIDWORKS!"))
            else:
                err = result.get("error", "Unknown error")
                self._update_status(f"❌ {err}", "#F38BA8")
                self.after(0, lambda: messagebox.showerror("Error", err))
        except Exception as e:
            self._update_status(f"❌ Vision Processing Error: {str(e)}", "#F38BA8")
            self.after(0, lambda: messagebox.showerror("Execution Error", str(e)))
        finally:
            pythoncom.CoUninitialize()
            self._set_busy(False)


if __name__ == "__main__":
    app = SolidAIGUI()
    app.mainloop()
