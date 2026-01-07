import customtkinter as ctk
import threading
import subprocess
import os
import time
import cv2
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk

# Cấu hình giao diện
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ==========================================
# PHẦN 1: ADB HELPER
# ==========================================
class ADBHelper:
    def __init__(self, device_id):
        self.device_id = device_id
        self.adb_path = "adb" 

    def capture_screen(self):
        """Chụp màn hình -> OpenCV Image"""
        try:
            pipe = subprocess.Popen(
                f'{self.adb_path} -s {self.device_id} shell screencap -p',
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                shell=True
            )
            image_bytes = pipe.stdout.read().replace(b'\r\n', b'\n')
            if not image_bytes: return None
            
            return cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        except Exception as e:
            print(f"Error capture: {e}")
            return None

    @staticmethod
    def get_connected_devices():
        try:
            process = subprocess.Popen("adb devices", shell=True, stdout=subprocess.PIPE)
            output = process.stdout.read().decode('utf-8')
            devices = []
            for line in output.split('\n')[1:]:
                if '\tdevice' in line:
                    devices.append(line.split('\t')[0])
            return devices
        except: return []

# ==========================================
# PHẦN 2: CỬA SỔ CẮT ẢNH (NÂNG CẤP)
# ==========================================
class RegionSelectionDialog(ctk.CTkToplevel):
    def __init__(self, parent, cv2_image, device_id, adb_helper):
        super().__init__(parent)
        self.title(f"Cắt Ảnh Mẫu - {device_id}")
        self.geometry("1100x800")
        self.attributes("-topmost", True)
        self.focus_force()

        self.device_id = device_id
        self.adb_helper = adb_helper # Lưu object adb để gọi chụp lại
        self.cv2_image = None
        self.tk_image = None
        self.pil_image = None

        # --- TOOLBAR (Thanh công cụ bên trên) ---
        self.toolbar = ctk.CTkFrame(self, height=50)
        self.toolbar.pack(side="top", fill="x", padx=5, pady=5)

        # Nút Chụp Lại
        self.btn_recapture = ctk.CTkButton(self.toolbar, text="🔄 Chụp Lại (Reset)", width=150, 
                                           fg_color="#F39C12", hover_color="#D35400",
                                           command=self.refresh_screenshot)
        self.btn_recapture.pack(side="left", padx=10, pady=5)

        # Nút Lưu Toàn Màn Hình
        self.btn_save_full = ctk.CTkButton(self.toolbar, text="💾 Lưu Full Màn Hình", width=150,
                                           fg_color="#2ECC71", hover_color="#27AE60",
                                           command=self.save_full_screen)
        self.btn_save_full.pack(side="left", padx=10, pady=5)

        self.lbl_status = ctk.CTkLabel(self.toolbar, text="Kéo chuột để cắt...", text_color="gray")
        self.lbl_status.pack(side="right", padx=20)

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

        # Variables vẽ
        self.rect_id = None
        self.start_x = 0
        self.start_y = 0

        # Bind chuột
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        # Load ảnh lần đầu
        self.update_image_display(cv2_image)

    def update_image_display(self, cv2_img):
        """Hàm cập nhật ảnh lên Canvas"""
        if cv2_img is None: return
        self.cv2_image = cv2_img
        
        rgb_image = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
        self.pil_image = Image.fromarray(rgb_image)
        self.tk_image = ImageTk.PhotoImage(self.pil_image)

        # Reset Canvas
        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, self.pil_image.width, self.pil_image.height))
        self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")
        
        self.lbl_status.configure(text=f"Kích thước: {self.pil_image.width}x{self.pil_image.height}")

    def refresh_screenshot(self):
        """Chụp lại màn hình mới từ ADB"""
        self.lbl_status.configure(text="Đang chụp lại...", text_color="yellow")
        self.btn_recapture.configure(state="disabled")
        
        def task():
            new_img = self.adb_helper.capture_screen()
            if new_img is not None:
                self.after(0, lambda: self.update_image_display(new_img))
                self.after(0, lambda: self.lbl_status.configure(text="Đã cập nhật ảnh mới!", text_color="green"))
            else:
                self.after(0, lambda: self.lbl_status.configure(text="Lỗi chụp ảnh!", text_color="red"))
            self.after(0, lambda: self.btn_recapture.configure(state="normal"))

        threading.Thread(target=task, daemon=True).start()

    def save_full_screen(self):
        """Lưu toàn bộ ảnh mà không cần cắt"""
        if self.cv2_image is None: return
        
        h, w = self.cv2_image.shape[:2]
        self.ask_save(0, 0, w, h)

    def on_button_press(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if self.rect_id: self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="#00FF00", width=2)

    def on_move_press(self, event):
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        x1, x2 = sorted([int(self.start_x), int(end_x)])
        y1, y2 = sorted([int(self.start_y), int(end_y)])

        if (x2 - x1) < 5 or (y2 - y1) < 5: return 
        self.ask_save(x1, y1, x2, y2)

    def ask_save(self, x1, y1, x2, y2):
        """Hiện hộp thoại lưu ảnh"""
        dialog = ctk.CTkInputDialog(text="Đặt tên cho ảnh mẫu:", title="Lưu Ảnh")
        filename = dialog.get_input()
        
        if filename:
            self.save_image(x1, y1, x2, y2, filename)
        else:
            if self.rect_id: self.canvas.delete(self.rect_id) # Hủy chọn nếu cancel

    def save_image(self, x1, y1, x2, y2, filename):
        h, w = self.cv2_image.shape[:2]
        x1 = max(0, x1); y1 = max(0, y1)
        x2 = min(w, x2); y2 = min(h, y2)

        cropped_img = self.cv2_image[y1:y2, x1:x2]
        
        save_dir = "img_data"
        if not os.path.exists(save_dir): os.makedirs(save_dir)
        
        if not filename.endswith(".png"): filename += ".png"
        full_path = os.path.join(save_dir, filename)
        
        cv2.imwrite(full_path, cropped_img)
        print(f"✅ Đã lưu: {full_path}")
        self.lbl_status.configure(text=f"Đã lưu: {filename}", text_color="#2ECC71")
        
        if self.rect_id: self.canvas.delete(self.rect_id) # Xóa khung vẽ để cắt tiếp

# ==========================================
# PHẦN 3: APP CHÍNH
# ==========================================
class CaptureToolApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Công Cụ Lấy Mẫu ADB Pro")
        self.geometry("600x500")
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
                # Truyền cả object adb vào window để nó dùng lại
                self.after(0, lambda: RegionSelectionDialog(self, screen_img, device_id, adb))
                self.after(0, lambda: self.lbl_status.configure(text="Đã mở cửa sổ cắt."))
            else:
                self.after(0, lambda: self.lbl_status.configure(text=f"Lỗi chụp {device_id}"))

if __name__ == "__main__":
    app = CaptureToolApp()
    app.mainloop()