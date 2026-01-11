import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk
import cv2
import threading
import os
import json

class RegionSelectionDialog(ctk.CTkToplevel):
    def __init__(self, parent, cv2_image, device_id, adb_helper):
        super().__init__(parent)
        self.title(f"Công Cụ Ảnh - {device_id}")
        
        self.device_id = device_id
        self.adb_helper = adb_helper 
        
        # Dữ liệu ảnh gốc
        self.cv2_image = cv2_image
        rgb_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
        self.pil_image_original = Image.fromarray(rgb_image) 
        
        self.tk_image = None
        self.scale = 1.0

        # --- CÁC BIẾN TRẠNG THÁI ---
        # "CROP": Cắt ảnh mẫu (Xanh lá)
        # "PICK_COORD": Lấy tọa độ điểm (Đỏ)
        # "SELECT_ROI": Chọn vùng tìm kiếm (Xanh dương)
        self.mode = "CROP" 
        
        # --- TÍNH TOÁN KÍCH THƯỚC CỬA SỔ ---
        img_h, img_w = cv2_image.shape[:2]
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        
        final_w = min(img_w + 50, screen_w - 50)
        final_h = min(img_h + 150, screen_h - 100)
        pos_x = (screen_w - final_w) // 2
        pos_y = (screen_h - final_h) // 2
        
        self.geometry(f"{final_w}x{final_h}+{pos_x}+{pos_y}")
        self.attributes("-topmost", True)
        self.focus_force()

        # --- TOOLBAR ---
        self.toolbar = ctk.CTkFrame(self, height=50)
        self.toolbar.pack(side="top", fill="x", padx=5, pady=5)

        # 1. Nút Chụp Lại
        self.btn_recapture = ctk.CTkButton(self.toolbar, text="🔄 Chụp Lại", width=80, 
                                           fg_color="#F39C12", hover_color="#D35400",
                                           command=self.refresh_screenshot)
        self.btn_recapture.pack(side="left", padx=5)

        # 2. Nút Lưu Full
        self.btn_save_full = ctk.CTkButton(self.toolbar, text="💾 Lưu Full", width=80,
                                           fg_color="#2ECC71", hover_color="#27AE60",
                                           command=self.save_full_screen)
        self.btn_save_full.pack(side="left", padx=5)

        # 3. Nút Lấy Tọa Độ
        self.btn_pick_coord = ctk.CTkButton(self.toolbar, text="📍 Lấy Tọa Độ", width=100,
                                            fg_color="#3498DB", hover_color="#2980B9",
                                            command=self.toggle_pick_mode)
        self.btn_pick_coord.pack(side="left", padx=5)

        # 4. Nút Chọn Vùng ROI (TÍNH NĂNG MỚI)
        self.btn_select_roi = ctk.CTkButton(self.toolbar, text="🟦 Chọn Khu Vực", width=100,
                                            fg_color="#9B59B6", hover_color="#8E44AD",
                                            command=self.toggle_roi_mode)
        self.btn_select_roi.pack(side="left", padx=5)

        # Các nút Zoom
        ctk.CTkLabel(self.toolbar, text="|").pack(side="left", padx=5)
        self.btn_zoom_out = ctk.CTkButton(self.toolbar, text="-", width=30, command=self.zoom_out)
        self.btn_zoom_out.pack(side="left", padx=2)
        self.lbl_zoom = ctk.CTkLabel(self.toolbar, text="100%", width=40)
        self.lbl_zoom.pack(side="left", padx=2)
        self.btn_zoom_in = ctk.CTkButton(self.toolbar, text="+", width=30, command=self.zoom_in)
        self.btn_zoom_in.pack(side="left", padx=2)

        self.lbl_status = ctk.CTkLabel(self.toolbar, text=f"{img_w}x{img_h}", text_color="gray")
        self.lbl_status.pack(side="right", padx=10)

        # --- KHUNG ẢNH CHÍNH ---
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True)

        self.v_scroll = ctk.CTkScrollbar(self.main_frame, orientation="vertical")
        self.h_scroll = ctk.CTkScrollbar(self.main_frame, orientation="horizontal")
        self.v_scroll.pack(side="right", fill="y")
        self.h_scroll.pack(side="bottom", fill="x")

        self.canvas = tk.Canvas(self.main_frame, bg="#2b2b2b", highlightthickness=0,
                                cursor="cross",
                                yscrollcommand=self.v_scroll.set,
                                xscrollcommand=self.h_scroll.set)
        self.canvas.pack(side="left", expand=True, fill="both")

        self.v_scroll.configure(command=self.canvas.yview)
        self.h_scroll.configure(command=self.canvas.xview)

        # Bind chuột
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.zoom_in())
        self.canvas.bind("<Button-5>", lambda e: self.zoom_out())

        self.rect_id = None
        self.start_x = 0
        self.start_y = 0
        self.marker_id = None 

        self.update_image_display()

    # --- CÁC HÀM ZOOM ---
    def zoom_in(self):
        self.scale *= 1.1
        self.update_image_display()
    def zoom_out(self):
        self.scale /= 1.1
        self.update_image_display()
    def on_mouse_wheel(self, event):
        if event.delta > 0: self.zoom_in()
        else: self.zoom_out()
    def update_image_display(self):
        if self.pil_image_original is None: return
        new_w = int(self.pil_image_original.width * self.scale)
        new_h = int(self.pil_image_original.height * self.scale)
        resized_pil = self.pil_image_original.resize((new_w, new_h), Image.NEAREST)
        self.tk_image = ImageTk.PhotoImage(resized_pil)
        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, new_w, new_h))
        self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")
        self.lbl_zoom.configure(text=f"{int(self.scale * 100)}%")
        self.rect_id = None
        self.marker_id = None

    # --- QUẢN LÝ CHẾ ĐỘ ---
    def reset_buttons(self):
        """Đặt lại màu các nút về mặc định"""
        self.btn_pick_coord.configure(text="📍 Lấy Tọa Độ", fg_color="#3498DB")
        self.btn_select_roi.configure(text="🟦 Chọn Khu Vực", fg_color="#9B59B6")
        self.canvas.configure(cursor="cross")

    def toggle_pick_mode(self):
        if self.mode == "PICK_COORD":
            self.mode = "CROP"
            self.reset_buttons()
            self.lbl_status.configure(text="[MODE: CẮT ẢNH] Kéo chuột để cắt", text_color="white")
        else:
            self.mode = "PICK_COORD"
            self.reset_buttons()
            self.btn_pick_coord.configure(text="❌ Hủy Lấy TĐ", fg_color="#E74C3C")
            self.canvas.configure(cursor="tcross")
            self.lbl_status.configure(text="[MODE: LẤY TỌA ĐỘ] Click để lấy điểm", text_color="#3498DB")
            if self.rect_id: self.canvas.delete(self.rect_id)

    def toggle_roi_mode(self):
        if self.mode == "SELECT_ROI":
            self.mode = "CROP"
            self.reset_buttons()
            self.lbl_status.configure(text="[MODE: CẮT ẢNH] Kéo chuột để cắt", text_color="white")
        else:
            self.mode = "SELECT_ROI"
            self.reset_buttons()
            self.btn_select_roi.configure(text="❌ Hủy Chọn Vùng", fg_color="#E74C3C")
            self.canvas.configure(cursor="cross")
            self.lbl_status.configure(text="[MODE: CHỌN VÙNG] Kéo chuột chọn vùng tìm kiếm", text_color="#9B59B6")
            if self.rect_id: self.canvas.delete(self.rect_id)

    # --- SỰ KIỆN CHUỘT ---
    def on_button_press(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        real_x = int(canvas_x / self.scale)
        real_y = int(canvas_y / self.scale)

        # MODE 1: LẤY TỌA ĐỘ
        if self.mode == "PICK_COORD":
            if self.marker_id: self.canvas.delete(self.marker_id)
            r = 3 * self.scale
            self.marker_id = self.canvas.create_oval(canvas_x - r, canvas_y - r, canvas_x + r, canvas_y + r, fill="red", outline="yellow")
            coord_text = f"{real_x}, {real_y}"
            self.lbl_status.configure(text=f"Đã copy: {coord_text}", text_color="#F1C40F")
            self.clipboard_clear()
            self.clipboard_append(coord_text)
            self.update() 
            return

        # MODE CROP hoặc SELECT_ROI: Vẽ hình chữ nhật
        self.start_x = canvas_x
        self.start_y = canvas_y
        if self.rect_id: self.canvas.delete(self.rect_id)
        
        # Màu sắc khác nhau cho từng chế độ
        # Xanh lá (CROP) vs Xanh dương (ROI)
        color = "#00FF00" if self.mode == "CROP" else "#00FFFF" 
        self.rect_id = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline=color, width=2)

    def on_move_press(self, event):
        if self.mode == "PICK_COORD": return
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        if self.mode == "PICK_COORD": return
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        
        c_x1, c_x2 = sorted([self.start_x, end_x])
        c_y1, c_y2 = sorted([self.start_y, end_y])
        
        real_x1 = int(c_x1 / self.scale)
        real_x2 = int(c_x2 / self.scale)
        real_y1 = int(c_y1 / self.scale)
        real_y2 = int(c_y2 / self.scale)

        if (real_x2 - real_x1) < 2 or (real_y2 - real_y1) < 2: return 
        
        # XỬ LÝ THEO CHẾ ĐỘ
        if self.mode == "SELECT_ROI":
             self.ask_save_roi(real_x1, real_y1, real_x2, real_y2)
        else: # Default CROP
             self.ask_save_image(real_x1, real_y1, real_x2, real_y2)

    # --- HÀM LƯU DỮ LIỆU ---
    def ask_save_roi(self, x1, y1, x2, y2):
        dialog = ctk.CTkInputDialog(text="Đặt tên cho KHU VỰC này (VD: vung_menu):", title="Lưu Khu Vực (ROI)")
        name = dialog.get_input()
        if name:
            # Lưu tọa độ với đánh dấu là ROI
            self.save_to_json(name, x1, y1, x2, y2, is_roi=True)
        else:
            if self.rect_id: self.canvas.delete(self.rect_id)

    def ask_save_image(self, x1, y1, x2, y2):
        dialog = ctk.CTkInputDialog(text="Đặt tên cho ẢNH MẪU (VD: nut_start):", title="Lưu Ảnh Mẫu")
        name = dialog.get_input()
        if name:
            # Lưu file ảnh
            self.save_image_file(name, x1, y1, x2, y2)
            # Lưu tọa độ với đánh dấu là TEMPLATE
            self.save_to_json(name, x1, y1, x2, y2, is_roi=False)
        else:
            if self.rect_id: self.canvas.delete(self.rect_id)

    def save_image_file(self, filename, x1, y1, x2, y2):
        h, w = self.cv2_image.shape[:2]
        x1 = max(0, x1); y1 = max(0, y1)
        x2 = min(w, x2); y2 = min(h, y2)
        
        save_dir = "img_data"
        if not os.path.exists(save_dir): os.makedirs(save_dir)
        
        clean_name = filename.strip()
        if not clean_name.lower().endswith(".png"): clean_name += ".png"
        full_path = os.path.join(save_dir, clean_name)
        
        cropped_img = self.cv2_image[y1:y2, x1:x2]
        cv2.imwrite(full_path, cropped_img)
        print(f"✅ Đã lưu ảnh: {full_path}")

    def save_to_json(self, name, x1, y1, x2, y2, is_roi=False):
        save_dir = "img_data"
        if not os.path.exists(save_dir): os.makedirs(save_dir)
        json_path = os.path.join(save_dir, "coordinates.json")

        clean_name = name.strip()
        if clean_name.lower().endswith(".png"): clean_name = clean_name[:-4]

        # Tạo data
        new_data = {
            "x1": int(x1), "y1": int(y1),
            "x2": int(x2), "y2": int(y2),
            "type": "REGION" if is_roi else "TEMPLATE"
        }

        # Đọc file cũ
        current_db = {}
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    current_db = json.load(f)
            except: current_db = {}

        current_db[clean_name] = new_data
        
        # Ghi file
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(current_db, f, indent=4, ensure_ascii=False)

        msg = f"Đã lưu VÙNG: {clean_name}" if is_roi else f"Đã lưu ẢNH: {clean_name}"
        color = "#9B59B6" if is_roi else "#2ECC71"
        
        print(f"📝 JSON Update: {clean_name} | {new_data}")
        self.lbl_status.configure(text=msg, text_color=color)
        if self.rect_id: self.canvas.delete(self.rect_id)

    def refresh_screenshot(self):
        self.lbl_status.configure(text="Đang chụp...", text_color="yellow")
        self.btn_recapture.configure(state="disabled")
        def task():
            new_img = self.adb_helper.capture_screen()
            if new_img is not None:
                self.cv2_image = new_img
                rgb_image = cv2.cvtColor(new_img, cv2.COLOR_BGR2RGB)
                self.pil_image_original = Image.fromarray(rgb_image)
                self.after(0, lambda: self.update_image_display())
                self.after(0, lambda: self.lbl_status.configure(text="Đã cập nhật!", text_color="green"))
            else:
                self.after(0, lambda: self.lbl_status.configure(text="Lỗi chụp!", text_color="red"))
            self.after(0, lambda: self.btn_recapture.configure(state="normal"))
        threading.Thread(target=task, daemon=True).start()

    def save_full_screen(self):
        if self.cv2_image is None: return
        h, w = self.cv2_image.shape[:2]
        self.ask_save_image(0, 0, w, h)