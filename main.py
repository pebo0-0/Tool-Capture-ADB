import customtkinter as ctk
import threading
import os
import time
import cv2
import tkinter as tk
from PIL import Image, ImageTk

# Import class ADBHelper từ file adb_manager.py
from adb_manager import ADBHelper 

# Cấu hình giao diện
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ==========================================
# CLASS CỬA SỔ CẮT ẢNH & LẤY TỌA ĐỘ (CÓ ZOOM)
# ==========================================
class RegionSelectionDialog(ctk.CTkToplevel):
    def __init__(self, parent, cv2_image, device_id, adb_helper):
        super().__init__(parent)
        self.title(f"Công Cụ Ảnh - {device_id}")
        
        self.device_id = device_id
        self.adb_helper = adb_helper 
        
        # Dữ liệu ảnh gốc
        self.cv2_image = cv2_image
        rgb_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
        self.pil_image_original = Image.fromarray(rgb_image) # Giữ ảnh gốc để resize
        
        self.tk_image = None
        self.is_picking_mode = False 
        
        # --- BIẾN ZOOM ---
        self.scale = 1.0
        
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

        self.btn_recapture = ctk.CTkButton(self.toolbar, text="🔄 Chụp Lại", width=80, 
                                           fg_color="#F39C12", hover_color="#D35400",
                                           command=self.refresh_screenshot)
        self.btn_recapture.pack(side="left", padx=5)

        self.btn_save_full = ctk.CTkButton(self.toolbar, text="💾 Lưu Full", width=80,
                                           fg_color="#2ECC71", hover_color="#27AE60",
                                           command=self.save_full_screen)
        self.btn_save_full.pack(side="left", padx=5)

        self.btn_pick_coord = ctk.CTkButton(self.toolbar, text="📍 Lấy Tọa Độ", width=100,
                                            fg_color="#3498DB", hover_color="#2980B9",
                                            command=self.toggle_pick_mode)
        self.btn_pick_coord.pack(side="left", padx=5)

        # Nút Zoom thủ công (cho ai không thích lăn chuột)
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
        
        # Bind Lăn chuột để Zoom (Windows)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        # Linux dùng Button-4 và Button-5 (nếu cần)
        self.canvas.bind("<Button-4>", lambda e: self.zoom_in())
        self.canvas.bind("<Button-5>", lambda e: self.zoom_out())

        # Variables vẽ
        self.rect_id = None
        self.start_x = 0
        self.start_y = 0
        self.marker_id = None 

        # Hiển thị ảnh lần đầu
        self.update_image_display()

    # --- CÁC HÀM ZOOM ---
    def zoom_in(self):
        self.scale *= 1.1 # Tăng 10%
        self.update_image_display()

    def zoom_out(self):
        self.scale /= 1.1 # Giảm 10%
        self.update_image_display()
        
    def on_mouse_wheel(self, event):
        # Windows: event.delta dương là lăn lên, âm là lăn xuống
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def update_image_display(self):
        """Vẽ lại ảnh dựa trên tỉ lệ scale hiện tại"""
        if self.pil_image_original is None: return

        # Tính kích thước mới
        new_w = int(self.pil_image_original.width * self.scale)
        new_h = int(self.pil_image_original.height * self.scale)
        
        # Resize ảnh (Dùng NEAREST để giữ pixel sắc nét khi zoom to)
        resized_pil = self.pil_image_original.resize((new_w, new_h), Image.NEAREST)
        self.tk_image = ImageTk.PhotoImage(resized_pil)

        # Xóa canvas và vẽ lại
        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, new_w, new_h))
        self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")
        
        # Cập nhật Label Zoom
        self.lbl_zoom.configure(text=f"{int(self.scale * 100)}%")
        
        # Reset các hình vẽ cũ vì tọa độ đã lệch
        self.rect_id = None
        self.marker_id = None

    # --- CÁC LOGIC CŨ (ĐÃ ĐƯỢC CHỈNH SỬA TỌA ĐỘ) ---
    def toggle_pick_mode(self):
        self.is_picking_mode = not self.is_picking_mode
        if self.is_picking_mode:
            self.btn_pick_coord.configure(text="✂️ Quay lại Cắt", fg_color="#E74C3C", hover_color="#C0392B")
            self.canvas.configure(cursor="tcross")
            if self.rect_id: self.canvas.delete(self.rect_id)
        else:
            self.btn_pick_coord.configure(text="📍 Lấy Tọa Độ", fg_color="#3498DB", hover_color="#2980B9")
            self.canvas.configure(cursor="cross")
            if self.marker_id: self.canvas.delete(self.marker_id)

    def refresh_screenshot(self):
        self.lbl_status.configure(text="Đang chụp...", text_color="yellow")
        self.btn_recapture.configure(state="disabled")
        def task():
            new_img = self.adb_helper.capture_screen()
            if new_img is not None:
                self.cv2_image = new_img
                rgb_image = cv2.cvtColor(new_img, cv2.COLOR_BGR2RGB)
                self.pil_image_original = Image.fromarray(rgb_image) # Cập nhật ảnh gốc
                self.after(0, lambda: self.update_image_display()) # Vẽ lại
                self.after(0, lambda: self.lbl_status.configure(text="Đã cập nhật!", text_color="green"))
            else:
                self.after(0, lambda: self.lbl_status.configure(text="Lỗi chụp!", text_color="red"))
            self.after(0, lambda: self.btn_recapture.configure(state="normal"))
        threading.Thread(target=task, daemon=True).start()

    def save_full_screen(self):
        if self.cv2_image is None: return
        h, w = self.cv2_image.shape[:2]
        self.ask_save(0, 0, w, h)

    def on_button_press(self, event):
        # Lấy tọa độ trên Canvas (đã bị zoom)
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        # TÍNH TOÁN TỌA ĐỘ THỰC (Chia cho scale)
        real_x = int(canvas_x / self.scale)
        real_y = int(canvas_y / self.scale)

        if self.is_picking_mode:
            if self.marker_id: self.canvas.delete(self.marker_id)
            r = 3 * self.scale # Bán kính điểm đỏ cũng to theo zoom cho dễ nhìn
            self.marker_id = self.canvas.create_oval(canvas_x - r, canvas_y - r, canvas_x + r, canvas_y + r, fill="red", outline="yellow")
            
            coord_text = f"{real_x}, {real_y}"
            self.lbl_status.configure(text=f"Đã copy: {coord_text}", text_color="#F1C40F")
            self.clipboard_clear()
            self.clipboard_append(coord_text)
            self.update() 
            return

        self.start_x = canvas_x
        self.start_y = canvas_y
        if self.rect_id: self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="#00FF00", width=2)

    def on_move_press(self, event):
        if self.is_picking_mode: return
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        if self.is_picking_mode: return
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        
        # Tọa độ trên Canvas
        c_x1, c_x2 = sorted([self.start_x, end_x])
        c_y1, c_y2 = sorted([self.start_y, end_y])
        
        # Chuyển đổi về tọa độ thực tế của ảnh (Chia cho Scale)
        real_x1 = int(c_x1 / self.scale)
        real_x2 = int(c_x2 / self.scale)
        real_y1 = int(c_y1 / self.scale)
        real_y2 = int(c_y2 / self.scale)

        # Kiểm tra kích thước (tính theo ảnh thực)
        if (real_x2 - real_x1) < 2 or (real_y2 - real_y1) < 2: return 
        
        self.ask_save(real_x1, real_y1, real_x2, real_y2)

    def ask_save(self, x1, y1, x2, y2):
        dialog = ctk.CTkInputDialog(text="Đặt tên cho ảnh mẫu:", title="Lưu Ảnh")
        filename = dialog.get_input()
        if filename:
            self.save_image(x1, y1, x2, y2, filename)
        else:
            if self.rect_id: self.canvas.delete(self.rect_id)

    def save_image(self, x1, y1, x2, y2, filename):
        h, w = self.cv2_image.shape[:2]
        # Giới hạn trong ảnh gốc
        x1 = max(0, x1); y1 = max(0, y1)
        x2 = min(w, x2); y2 = min(h, y2)
        
        # Cắt ảnh từ ảnh GỐC (self.cv2_image) chứ không phải ảnh đã zoom
        cropped_img = self.cv2_image[y1:y2, x1:x2]
        
        save_dir = "img_data"
        if not os.path.exists(save_dir): os.makedirs(save_dir)
        if not filename.endswith(".png"): filename += ".png"
        full_path = os.path.join(save_dir, filename)
        
        cv2.imwrite(full_path, cropped_img)
        print(f"✅ Đã lưu: {full_path}")
        self.lbl_status.configure(text=f"Đã lưu: {filename}", text_color="#2ECC71")
        if self.rect_id: self.canvas.delete(self.rect_id)

# ==========================================
# CLASS APP CHÍNH
# ==========================================
class CaptureToolApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Công Cụ Lấy Mẫu ADB Pro (Zoom)")

        # Căn giữa màn hình
        w, h = 600, 500
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        self.device_helpers = {} 
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.btn_scan = ctk.CTkButton(self.header_frame, text="🔄 Quét Thiết Bị", command=self.scan_devices)
        self.btn_scan.pack(side="left", padx=10, pady=10)
        self.lbl_status = ctk.CTkLabel(self.header_frame, text="Sẵn sàng")
        self.lbl_status.pack(side="left", padx=10)

        # List
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Danh sách LDPlayer")
        self.scroll_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        # Footer
        self.footer_frame = ctk.CTkFrame(self)
        self.footer_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        self.btn_open_folder = ctk.CTkButton(self.footer_frame, text="📂 Mở Thư Mục Ảnh", fg_color="gray", 
                                             command=lambda: os.startfile("img_data") if os.path.exists("img_data") else None)
        self.btn_open_folder.pack(side="right", padx=10, pady=5)

        self.after(500, self.scan_devices)

    def scan_devices(self):
        self.lbl_status.configure(text="Đang quét ADB...")
        for widget in self.scroll_frame.winfo_children(): widget.destroy()
        self.device_helpers.clear()

        devices = ADBHelper.get_connected_devices()
        if not devices:
            self.lbl_status.configure(text="Không tìm thấy thiết bị!")
            return

        for dev_id in devices:
            self.device_helpers[dev_id] = ADBHelper(dev_id)
            self.add_device_row(dev_id)
        self.lbl_status.configure(text=f"Đã kết nối: {len(devices)} thiết bị.")

    def add_device_row(self, device_id):
        row = ctk.CTkFrame(self.scroll_frame)
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text=f"📱 {device_id}", width=200, anchor="w", font=("Arial", 14, "bold")).pack(side="left", padx=15, pady=10)
        ctk.CTkButton(row, text="📸 Mở Công Cụ Cắt", width=150, fg_color="#E67E22", hover_color="#D35400",
                      command=lambda d=device_id: self.start_capture_process(d)).pack(side="right", padx=15, pady=10)

    def start_capture_process(self, device_id):
        self.lbl_status.configure(text=f"Đang lấy hình ảnh từ {device_id}...")
        threading.Thread(target=self._capture_thread, args=(device_id,), daemon=True).start()

    def _capture_thread(self, device_id):
        adb = self.device_helpers.get(device_id)
        if adb:
            screen_img = adb.capture_screen()
            if screen_img is not None:
                self.after(0, lambda: RegionSelectionDialog(self, screen_img, device_id, adb))
                self.after(0, lambda: self.lbl_status.configure(text="Đã mở cửa sổ cắt."))
            else:
                self.after(0, lambda: self.lbl_status.configure(text=f"Lỗi chụp {device_id}"))

if __name__ == "__main__":
    app = CaptureToolApp()
    app.mainloop()